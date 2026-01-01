import math
from typing import Any
from datetime import date, datetime

from decimal import Decimal
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.views.generic import FormView
from django.utils.translation import gettext_lazy as _
from django.utils.dateparse import parse_date, parse_datetime

from unfold.views import UnfoldModelAdminViewMixin

from .models import Assignment, Response
from .forms_dynamic import build_django_form_class


# Helpers for safe to json and from json types conversion
def json_safe(value: Any):
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, list):
        return [json_safe(v) for v in value]

    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}

    return value


def pythonize(value):
    if isinstance(value, str):
        # Try datetime first (ISO-8601)
        dt = parse_datetime(value)
        if dt is not None:
            return dt

        # Try date (ISO-8601)
        d = parse_date(value)
        if d is not None:
            return d

    if isinstance(value, dict):
        return {k: pythonize(v) for k, v in value.items()}

    if isinstance(value, list):
        return [pythonize(v) for v in value]

    return value


class AssignmentFillView(UnfoldModelAdminViewMixin, FormView):
    title = _("Electronic Health Record")
    template_name = "ehr/fill.html"
    permission_required = ("ehr.change_assignment",)

    PAGE_SIZE = 5  # fields per page

    def dispatch(self, request, *args, **kwargs):
        try:
            self.assignment = (
                Assignment.objects.select_related("participant", "form")
                .prefetch_related("form__fields")
                .get(pk=kwargs["pk"])
            )
        except Assignment.DoesNotExist:
            raise Http404

        self.page = int(request.GET.get("page", 1))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        total_fields = self.assignment.form.fields.count()
        total_pages = max(1, math.ceil(total_fields / self.PAGE_SIZE))

        ctx.update(
            {
                "assignment": self.assignment,
                "page": self.page,
                "total_pages": total_pages,
                "is_first_page": self.page <= 1,
                "is_last_page": self.page >= total_pages,
                "back_url": reverse("admin:ehr_assignment_changelist"),
            }
        )
        return ctx

    def get_form_class(self):
        return build_django_form_class(
            self.assignment.form,
            assignment=self.assignment,
            page=self.page,
            page_size=self.PAGE_SIZE,
        )

    def get_initial(self):
        initial = super().get_initial()

        resp, _ = Response.objects.get_or_create(
            participant=self.assignment.participant,
            form=self.assignment.form,
            defaults={"result": {}},
        )

        if resp.result:
            initial.update(
                pythonize(resp.result)
            )  # make sure date / datetime fields format is proper if form filled

        return initial

    def get_success_url(self):
        return reverse("admin:ehr_assignment_changelist")

    def form_valid(self, form):
        response, _ = Response.objects.get_or_create(
            participant=self.assignment.participant,
            form=self.assignment.form,
            defaults={"result": {}},
        )

        # MERGE partial page data (due to pagination)
        data = response.result or {}
        data.update(json_safe(form.cleaned_data))

        response.result = data
        response.save(update_fields=["result", "updated_at"])

        total_fields = self.assignment.form.fields.count()
        total_pages = max(1, math.ceil(total_fields / self.PAGE_SIZE))

        # NEXT PAGE
        if self.page < total_pages:
            return redirect(f"{self.request.path}?page={self.page + 1}")

        # LAST PAGE → COMPLETE
        self.assignment.completed_at = timezone.now()
        self.assignment.save(update_fields=["completed_at", "updated_at"])

        messages.success(
            self.request,
            f"Saved {self.assignment.form} form for {self.assignment.participant}.",
        )
        return redirect(self.get_success_url())
