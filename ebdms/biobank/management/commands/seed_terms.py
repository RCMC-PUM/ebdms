from django.core.management.base import BaseCommand
from biobank.models import Term


class Command(BaseCommand):
    help = "Populate Term table with basic controlled vocabulary"

    DEFAULT_TERMS = {
        "sex": [
            ("Male", "Biological male"),
            ("Female", "Biological female"),
            ("Other", "Other / non-binary / prefer not to say"),
        ],
        "diagnosis": [
            ("Healthy", "No known diagnosis"),
            ("Cancer", "Any type of cancer diagnosis"),
            ("Diabetes", "Diabetes mellitus"),
        ],
        "consent_status": [
            ("Consented", "Patient gave consent"),
            ("Withdrawn", "Patient withdrew consent"),
            ("Pending", "Consent not yet received"),
        ],
        "sample_type": [
            ("Blood", "Whole blood sample"),
            ("Plasma", "Plasma derived from blood"),
            ("Serum", "Serum separated from blood"),
            ("Tissue", "Biopsy or tissue sample"),
            ("Urine", "Urine sample"),
        ],
        "collection_method": [
            ("Venipuncture", "Blood collection via vein"),
            ("Biopsy", "Tissue biopsy"),
            ("Urine Cup", "Urine collected in cup"),
        ],
        "storage_condition": [
            ("Frozen", "-20°C or -80°C storage"),
            ("Refrigerated", "Stored at 2-8°C"),
            ("Room Temperature", "Stored at ambient temperature"),
        ],
        "preparation_method": [
            ("Centrifugation", "Spun to separate plasma/serum"),
            ("Aliquoting", "Sample divided into aliquots"),
        ],
        "storage_type": [
            ("Freezer", "Mechanical freezer"),
            ("Liquid Nitrogen", "Stored in LN2 tank"),
            ("Refrigerator", "Standard fridge"),
        ],
    }

    def handle(self, *args, **kwargs):
        created_count = 0
        for category, terms in self.DEFAULT_TERMS.items():
            for name, desc in terms:
                obj, created = Term.objects.get_or_create(
                    category=category, name=name,
                    defaults={"description": desc}
                )
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Added {category} - {name}"))
                else:
                    self.stdout.write(self.style.WARNING(f"Skipped {category} - {name} (already exists)"))

        self.stdout.write(self.style.SUCCESS(f"\nDone! Created {created_count} new terms."))
