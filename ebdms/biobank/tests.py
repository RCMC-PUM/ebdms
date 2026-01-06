from datetime import date

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from ontologies.models import SampleType

from projects.models import (
    Project,
    Participant,
    Institution,
    PrincipalInvestigator,
)

from biobank.models import (
    Storage,
    Box,
    ProcessingProtocol,
    Specimen,
    Aliquot,
)


class BiobankModelsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # --- REQUIRED FK CHAIN ---
        cls.institution = Institution.objects.create(
            name="Test Institution",
            code="INST01",
        )

        cls.pi = PrincipalInvestigator.objects.create(
            name="Alice",
            surname="Nowak",
            email="alice@example.com",
            institution=cls.institution,
        )

        cls.project = Project.objects.create(
            name="Test Project",
            code="PRJ01",
            principal_investigator=cls.pi,
            start_date=date(2024, 1, 1),
        )

        cls.participant = Participant.objects.create(
            project=cls.project,
            institution=cls.institution,
            name="Jan",
            surname="Kowalski",
            gender=Participant.Gender.MALE,
        )

        cls.sample_type = SampleType.objects.create(name="Blood")

        # --- BIOBANK OBJECTS ---
        cls.storage = Storage.objects.create(name="Freezer A")
        cls.box = Box.objects.create(storage=cls.storage, name="Box 01", rows=5, cols=5)
        cls.protocol = ProcessingProtocol.objects.create(
            name="DNA extraction",
            description="",
        )

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    def test_storage_str(self):
        self.assertEqual(str(self.storage), "Freezer A")

    def test_storage_name_unique(self):
        with self.assertRaises(IntegrityError):
            Storage.objects.create(name="Freezer A")

    # ------------------------------------------------------------------
    # Box
    # ------------------------------------------------------------------
    def test_box_capacity(self):
        self.assertEqual(self.box.n_total_samples, 25)
        self.assertEqual(self.box.n_samples, 0)
        self.assertEqual(self.box.occupation_percent, 0.0)

    def test_box_unique_per_storage(self):
        with self.assertRaises(IntegrityError):
            Box.objects.create(storage=self.storage, name="Box 01", rows=3, cols=3)
            Box.objects.create(storage=self.storage, name="Box 01", rows=3, cols=3)

    # ------------------------------------------------------------------
    # Specimen
    # ------------------------------------------------------------------
    def test_specimen_identifier_generated(self):
        s = Specimen.objects.create(
            project=self.project,
            participant=self.participant,
            sample_type=self.sample_type,
        )
        s.refresh_from_db()
        self.assertEqual(s.identifier, f"{self.project.code}_{s.pk}")

    def test_specimen_participant_must_match_project(self):
        other_project = Project.objects.create(
            name="Other Project",
            code="PRJ02",
            principal_investigator=self.pi,
            start_date=date(2024, 2, 1),
        )

        bad_participant = Participant.objects.create(
            project=other_project,
            institution=self.institution,
            name="Bad",
            surname="Guy",
            gender=Participant.Gender.MALE,
        )

        s = Specimen(
            project=self.project,
            participant=bad_participant,
            sample_type=self.sample_type,
        )

        with self.assertRaises(ValidationError):
            s.full_clean()

    # ------------------------------------------------------------------
    # Aliquot
    # ------------------------------------------------------------------
    def test_aliquot_defaults_sample_type(self):
        s = Specimen.objects.create(
            project=self.project,
            participant=self.participant,
            sample_type=self.sample_type,
        )
        a = Aliquot.objects.create(specimen=s)
        self.assertEqual(a.sample_type, self.sample_type)

    # def test_aliquot_identifier_generated(self):
    #     s = Specimen.objects.create(
    #         project=self.project,
    #         participant=self.participant,
    #         sample_type=self.sample_type,
    #     )
    #     a = Aliquot.objects.create(specimen=s)
    #     a.refresh_from_db() # TODO check this unit
    #     self.assertEqual(a.identifier, f"{self.project.code}_{s.pk}_{a.pk}")

    def test_aliquot_box_requires_row_and_col(self):
        s = Specimen.objects.create(
            project=self.project,
            participant=self.participant,
            sample_type=self.sample_type,
        )
        a = Aliquot(specimen=s, box=self.box)
        with self.assertRaises(ValidationError):
            a.full_clean()

    def test_aliquot_row_out_of_range(self):
        s = Specimen.objects.create(
            project=self.project,
            participant=self.participant,
            sample_type=self.sample_type,
        )
        a = Aliquot(specimen=s, box=self.box, row=999, col=1)
        with self.assertRaises(ValidationError):
            a.full_clean()

    def test_aliquot_check_constraint(self):
        s = Specimen.objects.create(
            project=self.project,
            participant=self.participant,
            sample_type=self.sample_type,
        )
        with self.assertRaises(ValidationError):
            Aliquot.objects.create(specimen=s, box=self.box, row=1, col=1)
            Aliquot.objects.create(specimen=s, box=self.box, row=1, col=1)
