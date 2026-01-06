from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.apps import apps
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

# Projects
from projects.models import Institution, PrincipalInvestigator, Project, Participant

# Biobank
from biobank.models import Storage, Box, ProcessingProtocol, Specimen, Aliquot

# Ontologies
from ontologies.models import (
    SampleType,
    MaritalStatus,
    CommunicationLanguage,
    RelationType,
    ICDDiagnosis,
)

# NGS
from ngs.models import Device, Target, Chemistry, OmicsArtifact

# EHR
from ehr.models import Form, FormField, Assignment, Response


# =============================================================================
# Helpers
# =============================================================================

@dataclass
class Slot:
    box: Box
    row: int
    col: int


class BoxAllocator:
    """
    Very small allocator:
    - ensures boxes exist
    - assigns next free (row,col) sequentially
    - creates a new box when current is full
    """

    def __init__(self, storage: Storage, *, rows: int = 9, cols: int = 9):
        self.storage = storage
        self.rows = rows
        self.cols = cols

        self._box_index = 0
        self._current_box: Optional[Box] = None
        self._next_row = 1
        self._next_col = 1

        # start from existing boxes (if any)
        existing = list(
            Box.objects.filter(storage=storage).order_by("id").values_list("id", flat=True)
        )

        self._box_index = len(existing)

        if existing:
            # continue filling last box (simple approach: start new box anyway to avoid searching occupancy)
            self._current_box = None

    def _create_box(self) -> Box:
        self._box_index += 1
        idx = self._box_index

        # rack positions: deterministic and unique within storage
        rack_level = (idx - 1) // 100 + 1
        rack_row = ((idx - 1) // 10) % 10 + 1
        rack_col = (idx - 1) % 10 + 1

        box = Box.objects.create(
            storage=self.storage,
            name=f"BOX-{idx:04d}",
            rack_level=rack_level,
            rack_row=rack_row,
            rack_col=rack_col,
            rows=self.rows,
            cols=self.cols,
        )

        self._current_box = box
        self._next_row = 1
        self._next_col = 1

        return box

    def next_slot(self) -> Slot:
        if self._current_box is None:
            self._create_box()

        # if full -> new box
        if self._next_row > self.rows:
            self._create_box()

        slot = Slot(box=self._current_box, row=self._next_row, col=self._next_col)

        # advance
        self._next_col += 1
        if self._next_col > self.cols:
            self._next_col = 1
            self._next_row += 1

        return slot


def get_model_or_none(app_label: str, model_name: str):
    try:
        return apps.get_model(app_label, model_name)

    except Exception: # noqa
        return None


def _seed_ontologies_if_needed() -> None:
    # SampleType
    if not SampleType.objects.exists():
        for code, name in [
            ("WB", "Whole blood"),
            ("PL", "Plasma"),
            ("SR", "Serum"),
            ("SAL", "Saliva"),
            ("STL", "Stool"),
        ]:
            SampleType.objects.create(
                system="local:sample-type",
                code=code,
                name=name,
                description="Seeded demo term.",
            )

    if not MaritalStatus.objects.exists():
        for code, name in [("S", "Single"), ("M", "Married"), ("D", "Divorced"), ("W", "Widowed")]:
            MaritalStatus.objects.create(
                system="http://terminology.hl7.org/CodeSystem/v3-MaritalStatus",
                code=code,
                name=name,
                description="Seeded demo term.",
            )

    if not CommunicationLanguage.objects.exists():
        for code, name in [("pl", "Polish"), ("en", "English"), ("de", "German")]:
            CommunicationLanguage.objects.create(
                system="urn:ietf:bcp:47",
                code=code,
                name=name,
                description="Seeded demo term.",
            )

    # ensure twin_monozygotic exists (your Participant.clean expects it)
    RelationType.objects.get_or_create(
        system="local:relation-type",
        code="twin_monozygotic",
        defaults={"name": "Monozygotic twin", "description": "Required by model logic."},
    )
    if RelationType.objects.count() < 3:
        for code, name in [("parent", "Parent"), ("child", "Child"), ("sibling", "Sibling"),
                           ("partner", "Partner")]:
            RelationType.objects.get_or_create(
                system="local:relation-type",
                code=code,
                defaults={"name": name, "description": "Seeded demo term."},
            )

    if not ICDDiagnosis.objects.exists():
        for code, name in [
            ("1A00", "Cholera"),
            ("BA00", "Type 2 diabetes mellitus"),
            ("CA40", "Essential hypertension"),
        ]:
            ICDDiagnosis.objects.create(
                version=ICDDiagnosis.ICDVersion.ICD11,
                system="https://icd.who.int/icd11",
                code=code,
                name=name,
                description="Seeded demo ICD-11 term.",
            )


def _create_demo_forms() -> list[Form]:
    f1, _ = Form.objects.get_or_create(
        name="Demo Form Intake",
        defaults={"description": "Baseline intake questionnaire", "is_active": True},
    )
    f2, _ = Form.objects.get_or_create(
        name="Demo Form Lifestyle",
        defaults={"description": "Lifestyle survey", "is_active": True},
    )
    f3, _ = Form.objects.get_or_create(
        name="Demo Form Follow-up",
        defaults={"description": "Follow-up survey", "is_active": True},
    )
    forms = [f1, f2, f3]

    # minimal fields (idempotent-ish via unique constraint on label per form)
    def add_field(form: Form, order: int, label: str, field_type: str, required: bool = False,
                  choices: str | None = None):
        FormField.objects.get_or_create(
            form=form,
            label=label,
            defaults={
                "order": order,
                "field_type": field_type,
                "required": required,
                "choices": choices,
                "help_text": "",
            },
        )

    add_field(f1, 1, "Height_cm", FormField.FieldType.INTEGER, required=False)
    add_field(f1, 2, "Weight_kg", FormField.FieldType.DECIMAL, required=False)
    add_field(f1, 3, "Smoker", FormField.FieldType.BOOLEAN, required=False)

    add_field(f2, 1, "Alcohol_frequency", FormField.FieldType.CHOICE, required=False,
              choices="never,monthly,weekly,daily")
    add_field(f2, 2, "Exercise_days_per_week", FormField.FieldType.INTEGER, required=False)

    add_field(f3, 1, "Any_new_diagnosis", FormField.FieldType.BOOLEAN, required=False)
    add_field(f3, 2, "Visit_date", FormField.FieldType.DATE, required=False)

    return forms


def _create_random_relations(rng, ParticipantRelation, participants) -> None:
    """
    Creates a small number of within-project relations.
    We don't assume your exact schema beyond typical:
    - participant (or participant_a)
    - related_participant (or participant_b)
    - relation_type (RelationType FK)
    """
    rel_types = list(RelationType.objects.all())
    if not rel_types:
        return

    # Try to detect likely field names (keep it robust)
    fields = {f.name for f in ParticipantRelation._meta.fields}

    # Common patterns
    a_field = "participant" if "participant" in fields else ("participant_a" if "participant_a" in fields else None)
    b_field = "related_participant" if "related_participant" in fields else (
        "participant_b" if "participant_b" in fields else None)
    rt_field = "relation_type" if "relation_type" in fields else None

    if not (a_field and b_field and rt_field):
        # If your model is different, skip silently
        return

    # Create ~5% relations
    n = max(5, int(len(participants) * 0.05))
    for _ in range(n):
        a, b = rng.sample(participants, 2)
        rt = rng.choice(rel_types)
        kwargs = {a_field: a, b_field: b, rt_field: rt}

        # avoid duplicates if you have unique constraints
        try:
            ParticipantRelation.objects.get_or_create(**kwargs)
        except Exception:
            continue


def _create_dummy_omics_artifact(rng, project, specimen, target, device, chemistry) -> None:
    """
    Creates a fake .parquet + qc_metrics .json artifact.
    """
    # small, deterministic bytes
    payload = f"DEMO:{project.code}:{specimen.identifier}:{rng.randint(1, 10 ** 9)}\n".encode("utf-8")

    parquet_name = f"{specimen.identifier}.parquet"
    qc_name = f"{specimen.identifier}.qc.json"

    qc_json = (
        f'{{"specimen":"{specimen.identifier}","assay":"WGS","chemistry":"WGS PCR-free","status":"OK"}}\n'
    ).encode("utf-8")

    oa = OmicsArtifact(
        project=project,
        specimen=specimen,
        target=target,
        device=device,
        chemistry=chemistry,
    )

    oa.file.save(parquet_name, ContentFile(payload), save=False)
    oa.qc_metrics.save(qc_name, ContentFile(qc_json), save=False)

    # save() will upload and compute md5 into metadata
    oa.save()


# =============================================================================
# Command
# =============================================================================

class Command(BaseCommand):
    help = "Seed demo data."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing DEMO projects + generated demo objects.")
        parser.add_argument("--seed", type=int, default=12345, help="Deterministic random seed.")
        parser.add_argument("--ngs-rate", type=float, default=0.25, help="Fraction of specimens that get an OmicsArtifact (0..1).")

    # Helpers

    @transaction.atomic
    def handle(self, *args, **opts):
        rng = random.Random(int(opts["seed"]))
        reset = bool(opts["reset"])
        ngs_rate = float(opts["ngs_rate"])

        demo_codes = [f"DEMO{i:02d}" for i in range(1, 25)]

        if reset:
            # Projects will protect some relations; easiest: delete in a safe order.
            # forms/assignments: only delete demo forms we create
            Form.objects.filter(name__startswith="Demo Form ").delete()

            # We only delete demo projects + objects referencing them.
            OmicsArtifact.objects.filter(project__code__in=demo_codes).delete()
            Specimen.objects.filter(project__code__in=demo_codes).delete()
            Participant.objects.filter(project__code__in=demo_codes).delete()
            Project.objects.filter(code__in=demo_codes).delete()

            # Keep storage/boxes (or you can wipe demo storage too)
            Box.objects.filter(storage__name__in=["Demo Freezer A1", "Demo Freezer B1"]).delete()
            Storage.objects.filter(name__in=["Demo Freezer A1", "Demo Freezer B1"]).delete()

            self.stdout.write(self.style.WARNING("Reset done (demo projects + related artifacts removed)."))
            return

        # Abort if already exists (unless reset was used and succeeded)
        if Project.objects.filter(code__in=demo_codes).exists():
            self.stdout.write(self.style.ERROR("Demo projects already exist. Use --reset."))
            return

        _seed_ontologies_if_needed()

        sample_types = list(SampleType.objects.all())
        marital_statuses = list(MaritalStatus.objects.all())
        languages = list(CommunicationLanguage.objects.all())
        icd_terms = list(ICDDiagnosis.objects.all())

        # storage setup (2 freezers)
        storage_a = Storage.objects.create(
            name="Demo Freezer A1",
            conditions="-80C",
            location="Building A / Floor -1 / Room 01",
        )
        storage_b = Storage.objects.create(
            name="Demo Freezer B1",
            conditions="-80C",
            location="Building B / Floor -1 / Room 02",
        )

        allocator_a = BoxAllocator(storage_a, rows=9, cols=9)
        allocator_b = BoxAllocator(storage_b, rows=9, cols=9)

        # institution + PI
        inst, _ = Institution.objects.get_or_create(
            code="DEMO",
            defaults={
                "name": "Demo Institute of Biomedical Data",
                "department": "Biobank & Omics Unit",
                "address": "Demo Street 1, 00-000 Warsaw, Poland",
            },
        )
        pi, _ = PrincipalInvestigator.objects.get_or_create(
            name="Jan",
            surname="Kowalski",
            defaults={"email": "pi.demo@example.org", "institution": inst, "phone": "+48 000 000 000"},
        )

        protocol, _ = ProcessingProtocol.objects.get_or_create(
            name="Demo Protocol",
            defaults={"description": "Simulated processing protocol for development/demo."},
        )

        # NGS dictionary tables
        target, _ = Target.objects.get_or_create(name="WGS", defaults={"description": "Whole genome sequencing"})
        device, _ = Device.objects.get_or_create(
            name="NovaSeq X", defaults={"vendor": "Illumina", "description": "Simulated device"}
        )
        chemistry, _ = Chemistry.objects.get_or_create(
            name="WGS PCR-free", defaults={"description": "PCR-free whole genome library prep"}
        )

        # EHR: 3 forms + some fields
        forms = _create_demo_forms()

        # ParticipantRelation model (optional)
        ParticipantRelation = get_model_or_none("projects", "ParticipantRelation")

        # deterministic participant counts (50..500) per project
        # "precise": this is fixed for a given seed
        project_participant_counts = {
            code: rng.randint(50, 500) for code in demo_codes
        }

        # names
        first_names_m = ["Adam", "Piotr", "Krzysztof", "Marek", "Tomasz", "Paweł", "Jan"]
        first_names_f = ["Anna", "Maria", "Katarzyna", "Agnieszka", "Magdalena", "Ewa", "Zofia"]
        last_names = ["Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kaczmarek", "Mazur", "Krawczyk"]

        today = timezone.localdate()

        # Create projects + data
        for idx, code in enumerate(demo_codes, start=1):
            n_participants = project_participant_counts[code]

            project = Project.objects.create(
                name=f"Demo Project {idx:02d}",
                code=code,
                description=f"Seeded demo dataset ({n_participants} participants).",
                principal_investigator=pi,
                status=True,
                start_date=today - timedelta(days=120),
            )
            self.stdout.write(self.style.SUCCESS(f"Creating {project.code} with {n_participants} participants"))

            participants: list[Participant] = []

            # create participants, specimens, aliquots, artifacts, assignments
            for i in range(1, n_participants + 1):
                gender = "male" if rng.random() < 0.5 else "female"
                name = rng.choice(first_names_m if gender == "male" else first_names_f)
                surname = rng.choice(last_names)

                age_years = rng.randint(18, 80)
                birth_date = today - timedelta(days=age_years * 365 + rng.randint(0, 364))

                p = Participant.objects.create(
                    project=project,
                    institution=inst,
                    name=name,
                    surname=surname,
                    gender=gender,
                    birth_date=birth_date,
                    country="Poland",
                    marital_status=rng.choice(marital_statuses) if marital_statuses else None,
                    communication=rng.choice(languages) if languages else None,
                    deceased=False,
                )
                participants.append(p)

                # add ICD for ~15%
                if icd_terms and rng.random() < 0.15:
                    k = 1 if rng.random() < 0.8 else 2
                    p.icd.add(*rng.sample(icd_terms, k=k))

                # EHR assignments: assign all 3 demo forms
                for f in forms:
                    Assignment.objects.get_or_create(participant=p, form=f)

                # 1-3 specimens
                n_specimens = rng.randint(1, 3)
                for _ in range(n_specimens):
                    st = rng.choice(sample_types)
                    specimen = Specimen.objects.create(
                        project=project,
                        participant=p,
                        sample_type=st,
                        note=None,
                    )

                    # 1-5 aliquots; each must have location
                    n_aliquots = rng.randint(1, 5)
                    for _a in range(n_aliquots):
                        # spread across storages for realism
                        allocator = allocator_a if rng.random() < 0.6 else allocator_b
                        slot = allocator.next_slot()

                        a = Aliquot.objects.create(
                            specimen=specimen,
                            sample_type=None,  # defaults from specimen in clean()
                            box=slot.box,
                            row=slot.row,
                            col=slot.col,
                        )

                        # Your Aliquot.save() builds identifier too early; fix after pk exists
                        correct = f"{specimen.project.code}_{specimen.pk}_{a.pk}"
                        Aliquot.objects.filter(pk=a.pk).update(identifier=correct)
                        a.identifier = correct

                    # NGS artifacts for subset of specimens
                    if rng.random() < ngs_rate:
                        _create_dummy_omics_artifact(
                            rng=rng,
                            project=project,
                            specimen=specimen,
                            target=target,
                            device=device,
                            chemistry=chemistry,
                        )

            # Participant relations within project (optional)
            if ParticipantRelation and len(participants) >= 3:
                _create_random_relations(rng, ParticipantRelation, participants)

        self.stdout.write(self.style.SUCCESS("All demo data created."))
