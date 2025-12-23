from django.urls import path
from django.contrib import admin

from django.urls import reverse
from django.utils.html import format_html

from unfold.admin import StackedInline

from accounts.admin import UnfoldReversionAdmin
from .views import AssignmentFillView
from .models import Assignment, Form, FormField, Response


# -----------------------------
# Inlines
# -----------------------------
class FormFieldInline(StackedInline):
    model = FormField
    extra = 0
    tab = True
    ordering = ("order", "id")
    fields = (
        "order",
        "key",
        "label",
        "field_type",
        "required",
        "help_text",
        "choices",
    )


# -----------------------------
# Form admin
# -----------------------------
@admin.register(Form)
class FormAdmin(UnfoldReversionAdmin):
    # keep it compatible with your current Form model (no slug)
    list_display = ("name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = [FormFieldInline]


# -----------------------------
# Response admin
# -----------------------------
@admin.register(Response)
class ResponseAdmin(UnfoldReversionAdmin):
    list_display = ("id", "form", "participant", "created_at")
    list_filter = ("form",)
    search_fields = ("form__name", "participant__id")
    readonly_fields = ("created_at", "updated_at")


# -----------------------------
# Assignment admin
# -----------------------------
@admin.register(Assignment)
class AssignmentAdmin(UnfoldReversionAdmin):
    list_display = ("participant", "form", "completed_at", "is_active", "fill_link")
    readonly_fields = ("fill_link",)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/fill/",
                self.admin_site.admin_view(
                    AssignmentFillView.as_view(model_admin=self)
                ),
                name="ehr_assignment_fill",
            ),
        ]
        return custom + urls

    @admin.display(description="Fill")
    def fill_link(self, obj: Assignment):
        if not obj.pk or not obj.form.is_active:
            return "—"
        url = reverse("admin:ehr_assignment_fill", args=[obj.pk])
        return format_html(
            '<a href="{}" >Fill ➡️</a>',
            url,
        )
