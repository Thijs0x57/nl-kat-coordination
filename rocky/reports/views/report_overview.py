from datetime import datetime, timezone

from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView

from octopoes.models.ooi.reports import ReportRecipe
from reports.views.base import ReportBreadcrumbs, get_selection
from rocky.paginator import RockyPaginator
from rocky.scheduler import scheduler_client
from rocky.views.mixins import OctopoesView, ReportList


class BreadcrumbsReportOverviewView(ReportBreadcrumbs):
    def build_breadcrumbs(self):
        breadcrumbs = super().build_breadcrumbs()
        kwargs = self.get_kwargs()
        selection = get_selection(self.request)
        breadcrumbs += [
            {
                "url": reverse("report_history", kwargs=kwargs) + selection,
                "text": _("Reports history"),
            },
            {
                "url": reverse("subreports", kwargs=kwargs) + selection,
                "text": _("Subreports"),
            },
        ]
        return breadcrumbs


class ScheduledReportsView(BreadcrumbsReportOverviewView, OctopoesView, ListView):
    """
    Shows all the reports that have ever been generated for the organization.
    """

    paginate_by = 20
    breadcrumbs_step = 2
    context_object_name = "reports"
    paginator = RockyPaginator
    template_name = "report_overview/scheduled_reports.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.client = scheduler_client(self.organization.code)

    def get_queryset(self):
        scheduler_id = f"report-{self.organization.code}"
        scheduled_reports = self.client.get_scheduled_reports(
            scheduler_id=scheduler_id
        )  # All contain a report_recipe_id

        report_recipes = self.octopoes_api_connector.list_objects(
            types={ReportRecipe}, valid_time=datetime.now(timezone.utc)
        ).items

        scheduled_reports_dict = {schedule["data"]["report_recipe_id"]: schedule for schedule in scheduled_reports}

        for report_recipe_id, schedule in scheduled_reports_dict.items():
            if schedule["deadline_at"]:
                schedule["deadline_at"] = datetime.fromisoformat(schedule["deadline_at"])
            for recipe in report_recipes:
                if str(recipe.recipe_id) == report_recipe_id:
                    schedule["report_recipe"] = recipe

        # Rapporten ophalen die al gegenereerd zijn met dit report_recipe_id
        self.scheduled_reports = scheduled_reports_dict
        return scheduled_reports

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["scheduled_reports"] = self.scheduled_reports
        return context


class ReportHistoryView(BreadcrumbsReportOverviewView, OctopoesView, ListView):
    """
    Shows all the reports that have ever been generated for the organization.
    """

    paginate_by = 30
    breadcrumbs_step = 2
    context_object_name = "reports"
    paginator = RockyPaginator
    template_name = "report_overview/report_history.html"

    def get_queryset(self) -> ReportList:
        return ReportList(
            self.octopoes_api_connector,
            valid_time=self.observed_at,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_oois"] = len(self.object_list)
        return context


class SubreportView(BreadcrumbsReportOverviewView, OctopoesView, ListView):
    """
    Shows all the subreports that belong to the selected parent report.
    """

    paginate_by = 150
    breadcrumbs_step = 3
    context_object_name = "subreports"
    paginator = RockyPaginator
    template_name = "report_overview/subreports.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.report_id = self.request.GET.get("report_id")

    def get_queryset(self) -> ReportList:
        return ReportList(
            self.octopoes_api_connector,
            valid_time=self.observed_at,
            parent_report_id=self.report_id,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_oois"] = len(self.object_list)
        context["parent_report_id"] = self.report_id
        return context
