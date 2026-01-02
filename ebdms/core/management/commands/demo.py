import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from projects.models import (
    Institution,
    PrincipalInvestigator,
    Project,
    Participant,
)

from biobank.models import (
    ProcessingProtocol,
    Specimen,
    Aliquot,
    Storage,
    Box,
)

from ontologies.models import (
    SampleType,
    MaritalStatus,
    CommunicationLanguage,
    RelationType,
    ICDDiagnosis,
)


class Command(BaseCommand):
    help = "Seed demo data: 3 projects (100/1k/10k participants) + specimens + aliquots."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo projects (DEMO100/DEMO1K/DEMO10K) and related data first.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=12345,
            help="Random seed for reproducible simulated data.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        reset = bool(opts["reset"])
        seed = int(opts["seed"])
        rng = random.Random(seed)

        demo_codes = ["DEMO100", "DEMO1K", "DEMO10K"]

        if reset:
            # Delete projects -> cascades participants/specimens/aliquots (where CASCADE),
            # some are PROTECT, but your related models mostly cascade downstream.
            Project.objects.filter(code__in=demo_codes).delete()
            self.stdout.write(self.style.WARNING("Deleted existing demo projects."))

        # Abort if already present (simple safety)
        if Project.objects.filter(code__in=demo_codes).exists():
            self.stdout.write(
                self.style.ERROR(
                    "Demo projects already exist. Use --reset to recreate."
                )
            )
            return

        self._seed_ontologies_if_needed(rng)
        sample_types = list(SampleType.objects.all())
        marital_statuses = list(MaritalStatus.objects.all())
        languages = list(CommunicationLanguage.objects.all())
        icd_terms = list(ICDDiagnosis.objects.all())

        # Minimal lab/storage objects (optional, but harmless)
        storage, _ = Storage.objects.get_or_create(
            name="Demo Freezer A1",
            defaults={"conditions": "-80C", "location": "Building A / Floor -1"},
        )
        # One box if you ever want to assign positions later (we won't, to keep simple)
        Box.objects.get_or_create(
            storage=storage,
            name="Demo Box 01",
            defaults={"rack_level": 1, "rack_row": 1, "rack_col": 1, "rows": 9, "cols": 9},
        )

        # Institution + PI used by all demo projects
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

        # Project specs: (code, name, n_participants, specimens_per_participant, aliquot_range)
        specs = [
            ("DEMO100", "Demo Project 100", 100, 1, (1, 3)),
            ("DEMO1K", "Demo Project 1K", 1000, 2, (1, 4)),
            ("DEMO10K", "Demo Project 10K", 10000, 3, (1, 5)),
        ]

        for code, name, n_participants, n_specimens, aliquot_range in specs:
            project = Project.objects.create(
                name=name,
                code=code,
                description=f"Seeded demo dataset ({n_participants} participants).",
                principal_investigator=pi,
                status=True,
                start_date=timezone.localdate() - timedelta(days=180),
            )
            self.stdout.write(self.style.SUCCESS(f"Created project {project.code}"))

            self._create_participants_specimens_aliquots(
                rng=rng,
                project=project,
                institution=inst,
                n_participants=n_participants,
                specimens_per_participant=n_specimens,
                aliquot_range=aliquot_range,
                sample_types=sample_types,
                marital_statuses=marital_statuses,
                languages=languages,
                icd_terms=icd_terms,
                protocol=protocol,
            )

        self.stdout.write(self.style.SUCCESS("Done."))

    # ---------------------------------------------------------------------

    def _seed_ontologies_if_needed(self, rng: random.Random) -> None:
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

        # MaritalStatus
        if not MaritalStatus.objects.exists():
            for code, name in [
                ("S", "Single"),
                ("M", "Married"),
                ("D", "Divorced"),
                ("W", "Widowed"),
            ]:
                MaritalStatus.objects.create(
                    system="http://terminology.hl7.org/CodeSystem/v3-MaritalStatus",
                    code=code,
                    name=name,
                    description="Seeded demo term.",
                )

        # CommunicationLanguage
        if not CommunicationLanguage.objects.exists():
            for code, name in [
                ("pl", "Polish"),
                ("en", "English"),
                ("de", "German"),
            ]:
                CommunicationLanguage.objects.create(
                    system="urn:ietf:bcp:47",
                    code=code,
                    name=name,
                    description="Seeded demo term.",
                )

        # RelationType (ensure twin_monozygotic exists because your model expects it)
        if not RelationType.objects.exists():
            RelationType.objects.create(
                system="local:relation-type",
                code="twin_monozygotic",
                name="Monozygotic twin",
                description="Required by model logic.",
            )
            for code, name in [
                ("parent", "Parent"),
                ("child", "Child"),
                ("sibling", "Sibling"),
                ("partner", "Partner"),
            ]:
                RelationType.objects.create(
                    system="local:relation-type",
                    code=code,
                    name=name,
                    description="Seeded demo term.",
                )
        else:
            RelationType.objects.get_or_create(
                system="local:relation-type",
                code="twin_monozygotic",
                defaults={"name": "Monozygotic twin", "description": "Required by model logic."},
            )

        # ICDDiagnosis (minimal)
        if not ICDDiagnosis.objects.exists():
            for code, name in [
                ("1A00", "Cholera"),
                ("2A00", "Malignant neoplasm of lip"),
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

    def _create_participants_specimens_aliquots(
        self,
        *,
        rng: random.Random,
        project: Project,
        institution: Institution,
        n_participants: int,
        specimens_per_participant: int,
        aliquot_range: tuple[int, int],
        sample_types: list[SampleType],
        marital_statuses: list[MaritalStatus],
        languages: list[CommunicationLanguage],
        icd_terms: list[ICDDiagnosis],
        protocol: ProcessingProtocol,
    ) -> None:
        first_names_m = ["Adam", "Piotr", "Krzysztof", "Marek", "Tomasz", "Paweł", "Jan"]
        first_names_f = ["Anna", "Maria", "Katarzyna", "Agnieszka", "Magdalena", "Ewa", "Zofia"]
        last_names = ["Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kaczmarek", "Mazur", "Krawczyk"]

        # batched progress prints (simple)
        step = 500 if n_participants >= 1000 else 50

        for i in range(1, n_participants + 1):
            gender = "male" if rng.random() < 0.5 else "female"
            if gender == "male":
                name = rng.choice(first_names_m)
            else:
                name = rng.choice(first_names_f)
            surname = rng.choice(last_names)

            # Stable-ish but random birth_date (18-80y)
            today = timezone.localdate()
            age_years = rng.randint(18, 80)
            birth_date = today - timedelta(days=age_years * 365 + rng.randint(0, 364))

            p = Participant.objects.create(
                project=project,
                institution=institution,
                name=name,
                surname=surname,
                gender=gender,
                birth_date=birth_date,
                email=None,  # keep simple (optional field)
                phone_number_prefix=None,
                phone_number=None,
                street=None,
                street_number=None,
                apartment=None,
                city=None,
                postal_code=None,
                country="Poland",
                marital_status=rng.choice(marital_statuses) if marital_statuses else None,
                deceased=False,
                deceased_date_time=None,
                communication=rng.choice(languages) if languages else None,
                # consent fields have defaults
            )

            # Optional: attach 0-2 ICD terms randomly (keep most healthy)
            if icd_terms and rng.random() < 0.15:
                k = 1 if rng.random() < 0.8 else 2
                p.icd.add(*rng.sample(icd_terms, k=k))

            # Create specimens
            for _ in range(specimens_per_participant):
                st = rng.choice(sample_types)

                specimen = Specimen.objects.create(
                    project=project,
                    participant=p,
                    sample_type=st,
                    note=None,
                    protocols=protocol,
                )

                # Create aliquots (variable number per specimen)
                n_aliquots = rng.randint(aliquot_range[0], aliquot_range[1])
                for _a in range(n_aliquots):
                    a = Aliquot.objects.create(
                        specimen=specimen,
                        sample_type=None,  # defaults from specimen in clean()
                        box=None,
                        row=None,
                        col=None,
                    )
                    # Fix identifier (your model computes it too early)
                    correct = f"{specimen.project.code}_{specimen.pk}_{a.pk}"
                    Aliquot.objects.filter(pk=a.pk).update(identifier=correct)
                    a.identifier = correct

            if i % step == 0:
                self.stdout.write(f"{project.code}: created {i}/{n_participants} participants...")
