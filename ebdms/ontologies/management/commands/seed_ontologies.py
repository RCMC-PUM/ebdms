from django.core.management.base import BaseCommand
from django.db import transaction

from ontologies.models import (
    CommunicationLanguage,
    MaritalStatus,
    RelationType,
    SampleType,
    Unit,
)


class Command(BaseCommand):
    help = "Seed reference terminology tables (languages, sample types, units, marital statuses, relation types)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.seed_languages()
        self.seed_units()
        self.seed_sample_types()
        self.seed_marital_statuses()
        self.seed_relation_types()
        self.stdout.write(self.style.SUCCESS("Seed completed."))

    def upsert(
        self,
        model,
        *,
        system: str,
        code: str,
        name: str,
        description: str = "",
    ) -> bool:
        """
        Assumes your terminology models have fields:
          - system (str)
          - code (str)
          - name (str)   <-- human readable label
          - description (text, optional)

        (No 'display' field.)
        """
        _, created = model.objects.update_or_create(
            system=system,
            code=code,
            defaults={
                "name": name,
                "description": description,
            },
        )
        return created

    def seed_languages(self):
        system = "urn:ietf:bcp:47"  # common language tag system
        rows = [
            ("pl", "Polish (PL)", "Language: Polish (Poland)"),
            ("en", "English (EN)", "Language: English"),
        ]
        created = 0
        for code, name, desc in rows:
            created += int(
                self.upsert(
                    CommunicationLanguage,
                    system=system,
                    code=code,
                    name=name,
                    description=desc,
                )
            )
        self.stdout.write(f"CommunicationLanguage: +{created}")

    def seed_units(self):
        # Prefer UCUM codes for units where possible.
        system = "http://unitsofmeasure.org"  # UCUM
        rows = [
            ("L", "liter", ""),
            ("mL", "milliliter", ""),
            ("uL", "microliter", "Often written as uL in UCUM."),
            ("dL", "deciliter", ""),

            ("g", "gram", ""),
            ("mg", "milligram", ""),
            ("ug", "microgram", "Often written as ug in UCUM."),
            ("kg", "kilogram", ""),

            ("ng", "nanogram", ""),
            ("pg", "picogram", ""),

            ("mmol/L", "millimole per liter", ""),
            ("umol/L", "micromole per liter", "Often written as umol/L in UCUM."),

            ("%", "percent", ""),
        ]
        created = 0
        for code, name, desc in rows:
            created += int(
                self.upsert(
                    Unit,
                    system=system,
                    code=code,
                    name=name,
                    description=desc,
                )
            )
        self.stdout.write(f"Unit: +{created}")

    def seed_sample_types(self):
        # Minimal “standard” starter pack
        system = "urn:local:sample-type"
        rows = [
            ("whole_blood", "Whole blood", "Venous or capillary whole blood."),
            ("plasma", "Plasma", ""),
            ("serum", "Serum", ""),
            ("buffy_coat", "Buffy coat", ""),

            ("saliva", "Saliva", ""),
            ("urine", "Urine", ""),
            ("stool", "Stool", ""),

            ("csf", "Cerebrospinal fluid", ""),
            ("swab_buccal", "Buccal swab", ""),
            ("swab_nasal", "Nasal swab", ""),

            ("tissue_ffpe", "Tissue (FFPE)", "Formalin-fixed paraffin-embedded tissue."),
            ("tissue_frozen", "Tissue (frozen)", ""),
        ]
        created = 0
        for code, name, desc in rows:
            created += int(
                self.upsert(
                    SampleType,
                    system=system,
                    code=code,
                    name=name,
                    description=desc,
                )
            )
        self.stdout.write(f"SampleType: +{created}")

    def seed_marital_statuses(self):
        # HL7 v3 MaritalStatus code system (FHIR uses it)
        system = "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus"
        rows = [
            ("A", "Annulled", "Marriage contract declared null."),
            ("D", "Divorced", "Marriage contract dissolved."),
            ("I", "Interlocutory", "Subject to an interlocutory decree."),
            ("L", "Legally separated", ""),
            ("M", "Married", "Active marriage contract."),

            ("C", "Common law", "Common law marriage (where recognized)."),
            ("P", "Polygamous", "More than one current spouse."),
            ("T", "Domestic partner", "Domestic partner relationship exists."),

            ("U", "Unmarried", "Currently not in a marriage contract."),
            ("S", "Never married", "No marriage contract ever entered."),
            ("W", "Widowed", "Spouse has died."),
        ]
        created = 0
        for code, name, desc in rows:
            created += int(
                self.upsert(
                    MaritalStatus,
                    system=system,
                    code=code,
                    name=name,
                    description=desc,
                )
            )
        self.stdout.write(f"MaritalStatus: +{created}")

    def seed_relation_types(self):
        system = "urn:local:relation-type"
        rows = [
            # --- Direct biological lineage
            ("biological_parent", "Biological parent"),
            ("biological_child", "Biological child"),
            ("mother", "Mother"),
            ("father", "Father"),
            ("son", "Son"),
            ("daughter", "Daughter"),

            # --- Siblings
            ("full_sibling", "Full sibling (same parents)"),
            ("half_sibling", "Half sibling (one parent)"),
            ("twin_monozygotic", "Identical twin (monozygotic)"),
            ("twin_dizygotic", "Fraternal twin (dizygotic)"),

            # --- Extended biological family
            ("grandparent", "Grandparent"),
            ("grandchild", "Grandchild"),
            ("aunt", "Aunt"),
            ("uncle", "Uncle"),
            ("niece", "Niece"),
            ("nephew", "Nephew"),
            ("cousin_first", "First cousin"),
            ("cousin_second", "Second cousin"),

            # --- Other
            ("other", "Other"),
            ("unknown", "Unknown"),
        ]

        created = 0
        for code, name in rows:
            created += int(
                self.upsert(
                    RelationType,
                    system=system,
                    code=code,
                    name=name,
                )
            )
        self.stdout.write(f"RelationType: +{created}")
