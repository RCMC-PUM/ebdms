from datetime import date, datetime
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import date, datetime
from django.utils.dateparse import parse_date, parse_datetime

from django.views.generic import FormView
from unfold.views import UnfoldModelAdminViewMixin

from .models import Assignment, Response
from .forms_dynamic import build_django_form_class


def pythonize(value):
    if isinstance(value, dict):
        return {k: pythonize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [pythonize(v) for v in value]
    if isinstance(value, str):
        # Try datetime first (ISO-8601)
        dt = parse_datetime(value)
        if dt is not None:
            return dt
        d = parse_date(value)
        if d is not None:
            return d
    return value


def json_safe(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    return value


class AssignmentFillView(UnfoldModelAdminViewMixin, FormView):
    title = _("Electronic Health Record")
    template_name = "ehr/fill.html"
    permission_required = ("ehr.change_assignment",)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assignment"] = self.assignment
        return context

    def dispatch(self, request, *args, **kwargs):
        try:
            self.assignment = (
                Assignment.objects
                .select_related("participant", "form")
                .prefetch_related("form__fields")
                .get(pk=kwargs["pk"])
            )
        except Assignment.DoesNotExist:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        return build_django_form_class(self.assignment.form, assignment=self.assignment)

    def get_initial(self):
        initial = super().get_initial()

        resp, _ = Response.objects.get_or_create(
            participant=self.assignment.participant,
            form=self.assignment.form,
            defaults={"result": {}},
        )
        # Parse JSON to pythonic format
        if resp.result:
            initial.update(pythonize(resp.result))

        return initial

    def get_success_url(self):
        return reverse("admin:ehr_assignment_changelist")

    def form_valid(self, form):
        response, _ = Response.objects.get_or_create(
            participant=self.assignment.participant,
            form=self.assignment.form,
            defaults={"result": {}},
        )

        response.result = json_safe(form.cleaned_data)
        response.save(update_fields=["result", "updated_at"])

        self.assignment.completed_at = timezone.now()
        self.assignment.save(update_fields=["completed_at", "updated_at"])

        messages.success(self.request, f"Saved {self.assignment.form} form for {self.assignment.participant}.")
        return redirect(self.get_success_url())
