from typing import Any, Dict, Tuple

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from octopoes.models import Reference
from reports.report_types.aggregate_organisation_report.report import AggregateOrganisationReport
from reports.report_types.helpers import (
    get_ooi_types_from_aggregate_report,
    get_plugins_for_report_ids,
    get_report_types_from_aggregate_report,
)
from reports.views.base import (
    BaseReportView,
    ReportBreadcrumbs,
)
from rocky.views.ooi_view import BaseOOIListView


class BreadcrumbsAggregateReportView(ReportBreadcrumbs):
    def build_breadcrumbs(self):
        breadcrumbs = super().build_breadcrumbs()
        kwargs = self.get_kwargs()
        selection = self.get_selection()
        breadcrumbs += [
            {
                "url": reverse("aggregate_report_landing", kwargs=kwargs) + selection,
                "text": _("Aggregate report"),
            },
            {
                "url": reverse("aggregate_report_select_oois", kwargs=kwargs) + selection,
                "text": _("Select OOIs"),
            },
            {
                "url": reverse("aggregate_report_select_report_types", kwargs=kwargs) + selection,
                "text": _("Select report types"),
            },
            {
                "url": reverse("aggregate_report_view", kwargs=kwargs) + selection,
                "text": _("View report"),
            },
        ]
        return breadcrumbs


class LandingAggregateReportView(BreadcrumbsAggregateReportView, TemplateView):
    """
    Landing page to start the 'Aggregate Report' flow.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return redirect(reverse("aggregate_report_select_oois", kwargs=self.get_kwargs()))


class OOISelectionAggregateReportView(BreadcrumbsAggregateReportView, BaseOOIListView, BaseReportView):
    """
    Select OOIs for the 'Aggregate Report' flow.
    """

    template_name = "aggregate_report/select_oois.html"
    current_step = 3
    ooi_types = get_ooi_types_from_aggregate_report(AggregateOrganisationReport)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_ooi_filter_forms(self.ooi_types))
        return context


class ReportTypesSelectionAggregateReportView(BreadcrumbsAggregateReportView, BaseReportView, TemplateView):
    """
    Shows all possible report types from a list of OOIs.
    Chooses report types for the 'Aggregate Report' flow.
    """

    template_name = "aggregate_report/select_report_types.html"
    current_step = 4

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.available_report_types = self.get_report_types_for_aggregate_report(
            get_report_types_from_aggregate_report(AggregateOrganisationReport)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["oois"] = self.get_oois()
        context["available_report_types_aggregate"] = self.available_report_types
        context["count_available_report_types_aggregate"] = len(self.available_report_types["required"]) + len(
            self.available_report_types["optional"]
        )
        return context


class SetupScanAggregateReportView(BreadcrumbsAggregateReportView, BaseReportView, TemplateView):
    """
    Show required and optional plugins to start scans to generate OOIs to include in report.
    """

    template_name = "aggregate_report/setup_scan.html"
    current_step = 4

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.plugins = self.get_required_optional_plugins(get_plugins_for_report_ids(self.selected_report_types))

    def get(self, request, *args, **kwargs):
        if not self.selected_report_types:
            messages.error(self.request, _("Select at least one report type to proceed."))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["plugins"] = self.plugins
        return context


class AggregateReportView(BreadcrumbsAggregateReportView, BaseReportView, TemplateView):
    """
    Shows the report generated from OOIS and report types.
    """

    template_name = "aggregate_report.html"
    current_step = 5

    def generate_reports_for_oois(self) -> Tuple[Any, Any, Dict[Any, Dict[Any, Any]]]:
        report_data = {}
        aggregate_report = AggregateOrganisationReport(self.octopoes_api_connector)
        aggregate_template = aggregate_report.template_path
        for ooi in self.selected_oois:
            report_data[ooi] = {}
            for report_type in aggregate_report.reports["required"]:
                if Reference.from_str(ooi).class_type in report_type.input_ooi_types:
                    report = report_type(self.octopoes_api_connector)
                    data = report.generate_data(ooi, valid_time=self.valid_time)
                    template = report.template_path
                    report_data[ooi][report_type.name] = {"data": data, "template": template}
        post_processed_data = aggregate_report.post_process_data(report_data)

        return aggregate_template, post_processed_data, report_data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["report_types"] = self.get_report_types()
        template, post_processed_data, report_data = self.generate_reports_for_oois()
        context["template"] = template
        context["post_processed_data"] = post_processed_data
        context["report_data"] = report_data
        return context
