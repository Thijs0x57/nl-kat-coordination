from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from logging import getLogger
from operator import attrgetter
from typing import Any, Literal, cast
from uuid import uuid4

from account.mixins import OrganizationView
from django.contrib import messages
from django.forms import Form
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from katalogus.client import KATalogusError, Plugin, get_katalogus
from pydantic import RootModel, TypeAdapter
from tools.ooi_helpers import create_ooi
from tools.view_helpers import BreadcrumbsMixin

from octopoes.models import OOI, Reference
from octopoes.models.ooi.reports import Report as ReportOOI
from reports.forms import OOITypeMultiCheckboxForReportForm
from reports.report_types.concatenated_report.report import ConcatenatedReport
from reports.report_types.definitions import AggregateReport, BaseReportType, MultiReport, Report, ReportType
from reports.report_types.helpers import get_plugins_for_report_ids, get_report_by_id
from rocky.views.mixins import OOIList
from rocky.views.ooi_view import OOIFilterView

REPORTS_PRE_SELECTION = {
    "clearance_level": ["2", "3", "4"],
    "clearance_type": "declared",
}


def get_selection(request: HttpRequest, pre_selection: dict[str, str | Sequence[str]] | None = None) -> str:
    if pre_selection is not None:
        return "?" + urlencode(pre_selection, True)
    return "?" + urlencode(request.GET, True)


logger = getLogger(__name__)


class ReportBreadcrumbs(OrganizationView, BreadcrumbsMixin):
    breadcrumbs_step: int = 1

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.breadcrumbs = self.build_breadcrumbs()

    def get_kwargs(self):
        return {"organization_code": self.organization.code}

    def is_valid_breadcrumbs(self):
        return self.breadcrumbs_step < len(self.breadcrumbs)

    def build_breadcrumbs(self):
        kwargs = self.get_kwargs()
        selection = get_selection(self.request)

        breadcrumbs = [
            {
                "url": reverse("reports", kwargs=kwargs) + selection,
                "text": _("Reports"),
            },
        ]

        return breadcrumbs

    def get_breadcrumbs(self):
        if self.is_valid_breadcrumbs():
            return self.breadcrumbs[: self.breadcrumbs_step]
        return self.breadcrumbs

    def get_current(self):
        return self.breadcrumbs[self.breadcrumbs_step - 1]["url"]

    def get_previous(self):
        if self.is_valid_breadcrumbs() and self.breadcrumbs_step >= 2:
            return self.breadcrumbs[self.breadcrumbs_step - 2]["url"]
        return self.get_current()

    def get_next(self):
        if self.is_valid_breadcrumbs():
            return self.breadcrumbs[self.breadcrumbs_step]["url"]
        return self.get_current()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = self.get_breadcrumbs()
        context["next"] = self.get_next()
        context["previous"] = self.get_previous()
        return context


class BaseSelectionView(OrganizationView):
    """
    Some views just need to check on user selection and pass selection from view to view.
    The calculations for the selections are done in their own view.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.selected_oois = self.check_oois_selection(sorted(set(request.GET.getlist("ooi", []))))
        self.selected_report_types = request.GET.getlist("report_type", [])

    def check_oois_selection(self, selected_oois: list[str]) -> list[str]:
        """all in selection overrides the rest of the selection."""
        if "all" in selected_oois and len(selected_oois) > 1:
            selected_oois = ["all"]
        return selected_oois

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["selected_oois"] = self.selected_oois
        context["selected_report_types"] = self.selected_report_types
        return context


class ReportOOIView(OOIFilterView, BaseSelectionView):
    """
    This class will show a list of OOIs with filters and handles OOIs selections.
    Needs BaseSelectionView to get selected oois.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.oois = self.get_oois()
        self.oois_pk = self.get_oois_pk()

    def get_oois_pk(self) -> list[str]:
        oois_pk = self.selected_oois
        if "all" in self.selected_oois:
            oois_pk = [ooi.primary_key for ooi in self.oois]
        return oois_pk

    def get_total_objects(self):
        if "all" in self.selected_oois:
            return len(self.oois_pk)
        return len(self.selected_oois)

    def get_oois(self) -> list[OOI]:
        if "all" in self.selected_oois:
            return self.octopoes_api_connector.list_objects(
                self.get_ooi_types(),
                valid_time=self.observed_at,
                limit=OOIList.HARD_LIMIT,
                scan_level=self.get_ooi_scan_levels(),
                scan_profile_type=self.get_ooi_profile_types(),
            ).items

        oois = []
        for ooi_id in self.selected_oois:
            try:
                oois.append(self.get_single_ooi(ooi_id))
            except Exception:
                logger.warning("No data could be found for '%s' ", ooi_id)
        return oois

    def get_ooi_filter_forms(self, ooi_types: Iterable[type[OOI]]) -> dict[str, Form]:
        return {
            "ooi_type_form": OOITypeMultiCheckboxForReportForm(
                sorted([ooi_class.get_ooi_type() for ooi_class in ooi_types]),
                self.request.GET,
            )
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["oois"] = self.oois
        return context


class ReportTypeView(BaseSelectionView):
    """
    This view lists all report types that is being fetched from the OOIs selection.
    Each report type has its own input ooi witch will be matched with the oois selection.
    Needs BaseSelectionView to get and remember report type selection.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.report_types: Sequence[type[Report] | type[MultiReport]] = self.get_report_types_from_choice()
        self.report_ids = [report.id for report in self.report_types]

    def get_report_types_from_choice(self) -> list[type[Report] | type[MultiReport]]:
        report_types = []
        for report_type in self.selected_report_types:
            try:
                report = get_report_by_id(report_type)
                report_types.append(report)
            except ValueError:
                error_message = _("Report type '%s' does not exist.") % report_type
                messages.error(self.request, error_message)
        return report_types

    @staticmethod
    def get_report_types(reports: set[type[BaseReportType]]) -> list[dict[str, str]]:
        return [
            {
                "id": report_type.id,
                "name": report_type.name,
                "description": report_type.description,
                "label_style": report_type.label_style,
            }
            for report_type in reports
        ]


class ReportPluginView(ReportOOIView, ReportTypeView, TemplateView):
    """
    This view shows the required and optional plugins.
    Needs ReportTypeView to know which report type is selected to get their plugins.
    The plugin ids will be collected and fetched form KAT-alogus.
    The user is able to activate plugins they need for the scans.
    The oois selection is also remembered by ReportOOIView.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        try:
            self.plugins, self.all_plugins_enabled = self.get_all_plugins()
        except KATalogusError as error:
            messages.error(self.request, error.message)
            self.plugins = {}
            self.all_plugins_enabled = {}

    def report_has_required_plugins(self) -> bool:
        if self.plugins:
            required_plugins = self.plugins["required"]
            return required_plugins != [] or required_plugins is not None
        return False

    def plugins_enabled(self) -> bool:
        if self.all_plugins_enabled:
            return self.all_plugins_enabled["required"] and self.all_plugins_enabled["optional"]
        return False

    def get_all_plugins(self) -> tuple[dict[str, list[Plugin]], dict[str, bool]]:
        return self.get_required_optional_plugins(get_plugins_for_report_ids(self.report_ids))

    def get_required_optional_plugins(
        self, plugin_ids_dict: dict[str, set[str]]
    ) -> tuple[dict[str, list[Plugin]], dict[str, bool]]:
        required_optional_plugins: dict[str, list[Plugin]] = {}
        plugins_enabled: dict[str, bool] = {}

        for required_optional, plugin_ids in plugin_ids_dict.items():
            plugins: list[Plugin] = (
                get_katalogus(self.organization.code).get_plugins(ids=list(plugin_ids)) if plugin_ids else []
            )

            sorted_plugins = sorted(plugins, key=attrgetter("name"))
            are_plugins_enabled: list[bool] = []
            for plugin in sorted_plugins:
                are_plugins_enabled.append(plugin.enabled)
            required_optional_plugins[required_optional] = plugins
            plugins_enabled[required_optional] = all(are_plugins_enabled)

        return required_optional_plugins, plugins_enabled

    def get_plugin_data(self):
        report_types: dict[str, Any] = {}
        plugin_report_types: dict[str, list] = {}
        total_enabled_plugins = {"required": 0, "optional": 0}
        total_available_plugins = {"required": 0, "optional": 0}

        if self.plugins:
            for report_type in self.report_types:
                for plugin_type in ["required", "optional"]:
                    # Mypy doesn't infer this automatically https://github.com/python/mypy/issues/9168
                    plugin_type = cast(Literal["required", "optional"], plugin_type)
                    number_of_enabled = sum(
                        (1 if plugin.enabled and plugin.id in report_type.plugins[plugin_type] else 0)
                        for plugin in self.plugins[plugin_type]
                    )
                    report_plugins = report_type.plugins[plugin_type]

                    for plugin in report_plugins:
                        if plugin not in plugin_report_types:
                            plugin_report_types[plugin] = [
                                {
                                    "name": report_type.name,
                                    "label_style": report_type.label_style,
                                }
                            ]
                        else:
                            plugin_report_types[plugin].append(
                                {
                                    "name": report_type.name,
                                    "label_style": report_type.label_style,
                                }
                            )

                    total_enabled_plugins[plugin_type] += number_of_enabled
                    total_available_plugins[plugin_type] += len(report_plugins)

                    if report_type.name not in report_types:
                        report_types[report_type.name] = {}

                    report_types[report_type.name][f"number_of_enabled_{plugin_type}"] = number_of_enabled
                    report_types[report_type.name][f"number_of_available_{plugin_type}"] = len(report_plugins)

        plugin_data = {
            "total_enabled_plugins": total_enabled_plugins,
            "total_available_plugins": total_available_plugins,
            "report_types": report_types,
            "plugin_report_types": plugin_report_types,
        }

        return plugin_data

    def save_report(
        self,
        data: dict,
        report_type: ReportType | None,
        input_ooi: Reference | None,
        parent: Reference | None,
        has_parent: bool,
        observed_at: datetime,
    ) -> ReportOOI:
        report_data_raw_id = self.bytes_client.upload_raw(
            raw=ReportDataDict(data).model_dump_json(), manual_mime_types={"openkat/report"}
        )

        report_ooi = ReportOOI(
            name=str(report_type.name) if report_type else None,
            report_type=str(report_type.id) if report_type and report_type is not ConcatenatedReport else None,
            template=report_type.template_path if report_type else None,
            report_id=uuid4(),
            organization_code=self.organization.code,
            organization_name=self.organization.name,
            organization_tags=list(self.organization.tags.all()),
            data_raw_id=report_data_raw_id,
            date_generated=datetime.now(timezone.utc),
            input_ooi=input_ooi,
            observed_at=observed_at,
            parent_report=parent,
            has_parent=has_parent,
        )

        create_ooi(
            api_connector=self.octopoes_api_connector,
            bytes_client=self.bytes_client,
            ooi=report_ooi,
            observed_at=observed_at,
        )

        return report_ooi

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["created_at"] = datetime.now()
        context["selected_oois"] = self.selected_oois
        context["selected_report_types"] = self.selected_report_types
        context["plugins"] = self.plugins
        context["all_plugins_enabled"] = self.all_plugins_enabled
        context["plugin_data"] = self.get_plugin_data()
        context["oois"] = self.get_oois()
        return context


class ReportsLandingView(ReportBreadcrumbs, TemplateView):
    """
    Landing page for Reports.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return redirect(reverse("report_history", kwargs=self.get_kwargs()))


class ReportDataDict(RootModel):
    root: Any

    class Config:
        arbitrary_types_allowed = True


def recursive_dict():
    return defaultdict(recursive_dict)


class ViewReportView(OOIFilterView, TemplateView):
    """
    This will display reports using report id from report history.
    Will fetch Report OOI and recreate report with data saved in bytes.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.report_id = request.GET.get("report_id", "")
        self.report_ooi = self.octopoes_api_connector.get(
            Reference.from_str(f"{self.report_id}"), valid_time=self.observed_at
        )

    def get_template_names(self):
        if self.report_ooi.report_type and issubclass(get_report_by_id(self.report_ooi.report_type), AggregateReport):
            return [
                "aggregate_report.html",
            ]
        else:
            return [
                "generate_report.html",
            ]

    def get_context_data(self, **kwargs):
        # TODO: add config and plugins
        # TODO: add template OOI
        context = super().get_context_data(**kwargs)

        if self.report_ooi.input_ooi:
            input_oois = [
                self.octopoes_api_connector.get(
                    Reference.from_str(self.report_ooi.input_ooi), valid_time=self.observed_at
                )
            ]

        else:
            input_oois = []

        self.bytes_client.login()
        report_data: dict = {}
        if not self.report_ooi.report_type:
            # its multiple single reports
            children = self.octopoes_api_connector.query(
                "Report.<parent_report[is Report]", valid_time=self.observed_at, source=self.report_ooi.reference
            )
            for report in children:
                if report.report_type not in report_data:
                    report_data[report.report_type] = {}

                # Ensure the input_ooi exists within the report_type
                if report.input_ooi not in report_data[report.report_type]:
                    report_data[report.report_type][report.input_ooi] = {}

                # Set the data within the input_ooi
                report_data[report.report_type][report.input_ooi] = {
                    "data": TypeAdapter(Any, config={"arbitrary_types_allowed": True}).validate_json(
                        self.bytes_client.get_raw(raw_id=report.data_raw_id)
                    ),
                    "template": report.template,
                    "report_name": get_report_by_id(report.report_type).name,
                }
            context["report_data"] = report_data
            context["report_types"] = [
                report.class_attributes() for report in {get_report_by_id(report.report_type) for report in children}
            ]
            input_oois = list(
                {self.octopoes_api_connector.get(child.input_ooi, valid_time=self.observed_at) for child in children}
            )

        elif issubclass(get_report_by_id(self.report_ooi.report_type), AggregateReport):
            # its an aggregate report
            context["post_processed_data"] = TypeAdapter(Any, config={"arbitrary_types_allowed": True}).validate_json(
                self.bytes_client.get_raw(raw_id=self.report_ooi.data_raw_id)
            )
            children = self.octopoes_api_connector.query(
                "Report.<parent_report[is Report]", valid_time=self.observed_at, source=self.report_ooi.reference
            )
            context["report_types"] = [
                report.class_attributes() for report in {get_report_by_id(report.report_type) for report in children}
            ]
            input_oois = list(
                {self.octopoes_api_connector.get(child.input_ooi, valid_time=self.observed_at) for child in children}
            )
        else:
            # its a single report
            report_data[self.report_ooi.report_type] = {}
            report_data[self.report_ooi.report_type][self.report_ooi.input_ooi] = {
                "data": TypeAdapter(Any, config={"arbitrary_types_allowed": True}).validate_json(
                    self.bytes_client.get_raw(raw_id=self.report_ooi.data_raw_id)
                ),
                "template": self.report_ooi.template,
                "report_name": get_report_by_id(self.report_ooi.report_type).name,
            }
            context["report_data"] = report_data
            context["report_types"] = [get_report_by_id(self.report_ooi.report_type).class_attributes()]

        context["created_at"] = self.report_ooi.date_generated
        context["selected_oois"] = input_oois
        context["oois"] = input_oois
        context["template"] = self.report_ooi.template
        return context
