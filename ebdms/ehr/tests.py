# ehr/tests/test_models.py

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from ehr.models import Assignment, Form, FormField, Response
from projects.models import Institution, PrincipalInvestigator, Project, Participant


class EHRModelsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.institution = Institution.objects.create(
            name="PUM",
            department="Genomics",
            address="Szczecin, Poland",
            code="PUM",
        )

        cls.pi = PrincipalInvestigator.objects.create(
            name="Anna",
            surname="Nowak",
            email="anna.nowak@example.com",
            institution=cls.institution,
        )

        cls.project = Project.objects.create(
            name="My Project",
            code="PRJ001",
            description="Test project",
            principal_investigator=cls.pi,
            status=True,
            start_date=timezone.localdate() - timedelta(days=30),
        )

        cls.participant = Participant.objects.create(
            project=cls.project,
            institution=cls.institution,
            active=True,
            name="Jan",
            surname="Kowalski",
            gender=Participant.Gender.MALE,
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
        )

        cls.participant.refresh_from_db()

        cls.form = Form.objects.create(
            name="Intake",
            description="Baseline form",
            is_active=True,
        )

    # -------------------------
    # Form
    # -------------------------

    def test_form_str(self):
        self.assertEqual(str(self.form), "Intake")

    # -------------------------
    # FormField
    # -------------------------

    def test_formfield_ordering_meta(self):
        f1 = FormField.objects.create(form=self.form, label="A", order=2)
        f2 = FormField.objects.create(form=self.form, label="B", order=1)

        qs = list(
            self.form.fields.all()
        )  # related_name="fields", Meta.ordering=("order",)
        self.assertEqual([x.id for x in qs], [f2.id, f1.id])

    def test_formfield_unique_label_per_form_full_clean(self):
        FormField.objects.create(form=self.form, label="Height", order=1)
        dup = FormField(form=self.form, label="Height", order=2)

        with self.assertRaises(ValidationError) as ctx:
            dup.full_clean()

        # UniqueConstraint zwykle ląduje w "__all__"
        self.assertTrue(
            "__all__" in ctx.exception.message_dict
            or "label" in ctx.exception.message_dict
        )

    def test_formfield_unique_order_per_form_full_clean(self):
        FormField.objects.create(form=self.form, label="Height", order=1)
        dup = FormField(form=self.form, label="Weight", order=1)

        with self.assertRaises(ValidationError) as ctx:
            dup.full_clean()

        self.assertTrue(
            "__all__" in ctx.exception.message_dict
            or "order" in ctx.exception.message_dict
        )

    def test_formfield_unique_constraints_db_level(self):
        FormField.objects.create(form=self.form, label="Height", order=1)

        # duplicate label (same form)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            FormField.objects.create(form=self.form, label="Height", order=2)

        # duplicate order (same form)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            FormField.objects.create(form=self.form, label="Weight", order=1)

    # -------------------------
    # Response
    # -------------------------

    def test_response_str(self):
        r = Response.objects.create(
            participant=self.participant, form=self.form, result={"a": 1}
        )
        self.assertEqual(
            str(r), f"Response(form={self.form.id}, participant={self.participant.id})"
        )

    def test_response_unique_participant_form_full_clean(self):
        Response.objects.create(
            participant=self.participant, form=self.form, result={"x": 1}
        )
        dup = Response(participant=self.participant, form=self.form, result={"x": 2})

        with self.assertRaises(ValidationError) as ctx:
            dup.full_clean()

        self.assertTrue("__all__" in ctx.exception.message_dict)

    def test_response_unique_participant_form_db_level(self):
        Response.objects.create(
            participant=self.participant, form=self.form, result={"x": 1}
        )

        with transaction.atomic(), self.assertRaises(IntegrityError):
            Response.objects.create(
                participant=self.participant, form=self.form, result={"x": 2}
            )

    def test_response_ordering_by_created_at_desc(self):
        f2 = Form.objects.create(name="Follow-up", description="", is_active=True)

        r1 = Response.objects.create(
            participant=self.participant, form=self.form, result={"n": 1}
        )
        r2 = Response.objects.create(
            participant=self.participant, form=f2, result={"n": 2}
        )

        older = timezone.now() - timedelta(days=2)
        newer = timezone.now() - timedelta(days=1)

        Response.objects.filter(pk=r1.pk).update(created_at=older)
        Response.objects.filter(pk=r2.pk).update(created_at=newer)

        ordered = list(Response.objects.all())
        self.assertEqual([x.pk for x in ordered], [r2.pk, r1.pk])

    # -------------------------
    # Assignment
    # -------------------------

    def test_assignment_str(self):
        a = Assignment.objects.create(
            participant=self.participant, form=self.form, is_active=True
        )
        s = str(a)
        self.assertIn(self.form.name, s)
        self.assertIn(str(self.participant), s)

    def test_assignment_unique_participant_form_full_clean(self):
        Assignment.objects.create(participant=self.participant, form=self.form)
        dup = Assignment(participant=self.participant, form=self.form)

        with self.assertRaises(ValidationError) as ctx:
            dup.full_clean()

        self.assertTrue("__all__" in ctx.exception.message_dict)

    def test_assignment_unique_participant_form_db_level(self):
        Assignment.objects.create(participant=self.participant, form=self.form)

        with transaction.atomic(), self.assertRaises(IntegrityError):
            Assignment.objects.create(participant=self.participant, form=self.form)

    def test_assignment_mark_completed_sets_completed_at(self):
        a = Assignment.objects.create(
            participant=self.participant, form=self.form, completed_at=None
        )
        self.assertIsNone(a.completed_at)

        before = timezone.now()
        a.mark_completed()
        after = timezone.now()

        a.refresh_from_db()
        self.assertIsNotNone(a.completed_at)
        self.assertTrue(before <= a.completed_at <= after)

    def test_assignment_ordering_by_created_at_desc(self):
        a1 = Assignment.objects.create(participant=self.participant, form=self.form)
        a2 = Assignment.objects.create(
            participant=self.participant,
            form=Form.objects.create(name="Another", description="", is_active=True),
        )

        older = timezone.now() - timedelta(days=5)
        newer = timezone.now() - timedelta(days=3)

        Assignment.objects.filter(pk=a1.pk).update(created_at=older)
        Assignment.objects.filter(pk=a2.pk).update(created_at=newer)

        ordered = list(Assignment.objects.all())
        self.assertEqual([x.pk for x in ordered], [a2.pk, a1.pk])
