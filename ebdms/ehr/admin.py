from django.contrib import admin
from django.db import models
from django import forms
from reversion.admin import VersionAdmin
from django_jsonform.widgets import JSONFormWidget

from .models import EHRModel, EHRRecord


@admin.register(EHRModel)
class EHRFormAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ("id", "name")


def generate_dynamic_form(ehr_form):
    """Generate a Django Form subclass from EHRModel schema."""
    fields = {}
    for field_schema in ehr_form.schema:
        field_type = field_schema["type"]
        name = field_schema["name"]
        label = field_schema.get("label", name)
        required = field_schema.get("required", False)

        if field_type == "text":
            fields[name] = forms.CharField(label=label, required=required, widget=forms.TextInput)
        elif field_type == "int":
            fields[name] = forms.IntegerField(label=label, required=required)
        elif field_type == "float":
            fields[name] = forms.FloatField(label=label, required=required)
        elif field_type == "bool":
            fields[name] = forms.BooleanField(label=label, required=required)
        elif field_type == "choice":
            fields[name] = forms.ChoiceField(
                label=label,
                required=required,
                choices=[(c, c) for c in field_schema.get("choices", [])],
            )
        elif field_type == "multichoice":
            fields[name] = forms.MultipleChoiceField(
                label=label,
                required=required,
                choices=[(c, c) for c in field_schema.get("choices", [])],
                widget=forms.CheckboxSelectMultiple,
            )
        elif field_type == "date":
            fields[name] = forms.DateField(label=label, required=required, widget=widgets.DateInput(attrs={"type": "date"}))

        elif field_type == "datetime":
            fields[name] = forms.DateTimeField(label=label, required=required, widget=widgets.DateTimeInput(attrs={"type": "datetime-local"}))

        elif field_type == "time":
            fields[name] = forms.TimeField(label=label, required=required, widget=widgets.TimeInput(attrs={"type": "time"}))

        elif field_type == "email":
            fields[name] = forms.EmailField(label=label, required=required)

        elif field_type == "url":
            fields[name] = forms.URLField(label=label, required=required)

        elif field_type == "phone":
            fields[name] = forms.CharField(label=label, required=required, widget=forms.TextInput(attrs={"type": "tel"}))

    return type("DynamicEHRForm", (forms.Form,), fields)


@admin.register(EHRRecord)
class EHRRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "form")

    def get_form(self, request, obj=None, **kwargs):
        if obj:  # editing an existing record
            ehr_form = obj.form
        else:  # creating new one, form must be preselected in add view
            ehr_form_id = request.GET.get("form")
            if ehr_form_id:
                from .models import EHRModel
                ehr_form = EHRModel.objects.get(id=ehr_form_id)
            else:
                ehr_form = None

        if ehr_form:
            DynamicForm = generate_dynamic_form(ehr_form)

            class RecordForm(forms.ModelForm):
                extra = DynamicForm  # injected fields

                class Meta:
                    model = EHRRecord
                    fields = ["form", "data"]

                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    # preload existing data into dynamic fields
                    if self.instance and self.instance.data:
                        for k, v in self.instance.data.items():
                            if k in self.fields:
                                self.fields[k].initial = v

                    # merge dynamic fields
                    for k, f in self.extra.base_fields.items():
                        self.fields[k] = f

                def save(self, commit=True):
                    obj = super().save(commit=False)
                    obj.data = {name: self.cleaned_data[name] for name in self.extra.base_fields}
                    if commit:
                        obj.save()
                    return obj

            kwargs["form"] = RecordForm

        return super().get_form(request, obj, **kwargs)
