import datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from projects.models import (
    Institution,
    PrincipalInvestigator,
    Project,
    Participant,
    ParticipantRelation,
)

from ontologies.models import RelationType, ICDDiagnosis


# ----------------------------
# Helper
# ----------------------------
def ensure_relation_type(code: str, **kwargs) -> RelationType:
    obj, _ = RelationType.objects.get_or_create(
        code=code, defaults={"code": code, **kwargs}
    )
    return obj


#####################################
# mk_* -> instance makers
#####################################
class BaseModelTestCase(TestCase):
    def mk_institution(self, **kwargs) -> Institution:
        data = {
            "name": "Uni Hospital",
            "department": "Genomics",
            "address": "Somewhere 1, 00-001",
            "code": "INST001",
        }
        data.update(kwargs)
        return Institution.objects.create(**data)

    def mk_pi(self, institution: Institution, **kwargs) -> PrincipalInvestigator:
        data = {
            "name": "Alice",
            "surname": "Smith",
            "email": "alice.smith@example.com",
            "phone": "+48123123123",
            "institution": institution,
        }
        data.update(kwargs)
        return PrincipalInvestigator.objects.create(**data)

    def mk_project(self, pi: PrincipalInvestigator, **kwargs) -> Project:
        data = {
            "name": "Project A",
            "code": "PRJ0001",
            "description": "Test",
            "principal_investigator": pi,
            "status": True,
            "start_date": timezone.localdate() - datetime.timedelta(days=10),
            "end_date": None,
        }

        data.update(kwargs)

        p = Project(**data)
        p.full_clean()
        p.save()

        return p

    def mk_participant(
        self, project: Project, institution: Institution, **kwargs
    ) -> Participant:
        data = {
            "project": project,
            "institution": institution,
            "active": True,
            "name": "Jan",
            "surname": "Kowalski",
            "gender": Participant.Gender.MALE,
            "birth_date": timezone.localdate() - datetime.timedelta(days=365 * 30),
            "email": None,
            "phone_number_prefix": None,
            "phone_number": None,
        }
        data.update(kwargs)
        p = Participant(**data)
        p.save()  # save() calls full_clean() internally

        return p


# ----------------------------
# Institution tests
# ----------------------------
class InstitutionModelTests(BaseModelTestCase):
    def test_str_with_department(self):
        inst = self.mk_institution(
            name="X", department="Dept", code="INST002", address="Addr2"
        )
        self.assertEqual(str(inst), "Dept (X)")

    def test_str_without_department(self):
        inst = self.mk_institution(
            name="X2", department=None, code="INST003", address="Addr3"
        )
        self.assertEqual(str(inst), "X2")

    def test_unique_name_department_constraint(self):
        self.mk_institution(
            name="Same", department="Dept1", code="INST004", address="Addr4"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.mk_institution(
                    name="Same", department="Dept1", code="INST005", address="Addr5"
                )


# ----------------------------
# Project tests
# ----------------------------
class ProjectModelTests(BaseModelTestCase):
    def test_clean_requires_end_date_when_inactive(self):
        inst = self.mk_institution(code="INST010", address="Addr10")
        pi = self.mk_pi(inst, email="pi10@example.com", surname="S10")

        p = Project(
            name="Inactive project",
            code="PRJ0010",
            principal_investigator=pi,
            status=False,
            start_date=timezone.localdate() - datetime.timedelta(days=10),
            end_date=None,
            description="",
        )

        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()

        self.assertIn("status", ctx.exception.message_dict)

    def test_is_active_false_when_status_false(self):
        inst = self.mk_institution(code="INST011", address="Addr11")
        pi = self.mk_pi(inst, email="pi11@example.com", surname="S11")

        p = self.mk_project(
            pi,
            name="P11",
            code="PRJ0011",
            status=False,
            end_date=timezone.localdate(),
        )
        self.assertFalse(p.is_active)

    def test_is_active_true_when_active_and_no_end_date(self):
        inst = self.mk_institution(code="INST012", address="Addr12")
        pi = self.mk_pi(inst, email="pi12@example.com", surname="S12")

        p = self.mk_project(pi, name="P12", code="PRJ0012", status=True, end_date=None)
        self.assertTrue(p.is_active)


# ----------------------------
# Participant tests
# ----------------------------
class ParticipantModelTests(BaseModelTestCase):
    def test_identifier_generated_once_on_first_save(self):
        inst = self.mk_institution(code="INST100", address="Addr100")
        pi = self.mk_pi(inst, email="pi100@example.com", surname="S100")
        project = self.mk_project(pi, name="P100", code="PRJ0100")

        part = self.mk_participant(project, inst, name="A", surname="B")

        self.assertEqual(part.identifier, f"{inst.code}-{project.code}-{part.pk}")

        old_identifier = part.identifier
        part.name = "A2"
        part.save()
        part.refresh_from_db()

        self.assertEqual(part.identifier, old_identifier)

    def test_save_requires_project_and_institution_if_identifier_missing(self):
        inst = self.mk_institution(code="INST101", address="Addr101")
        pi = self.mk_pi(inst, email="pi101@example.com", surname="S101")
        project = self.mk_project(pi, name="P101", code="PRJ0101")

        p1 = Participant(
            project=project,
            institution=None,  # missing
            name="X",
            surname="Y",
            gender=Participant.Gender.MALE,
        )
        # Pass if VE
        with self.assertRaises(ValidationError):
            p1.save()

        p2 = Participant(
            project=None,  # missing
            institution=inst,
            name="X",
            surname="Y",
            gender=Participant.Gender.MALE,
        )
        # Pass if VE
        with self.assertRaises(ValidationError):
            p2.save()

    def test_clean_deceased_date_requires_deceased_true(self):
        inst = self.mk_institution(code="INST102", address="Addr102")
        pi = self.mk_pi(inst, email="pi102@example.com", surname="S102")
        project = self.mk_project(pi, name="P102", code="PRJ0102")

        p = Participant(
            project=project,
            institution=inst,
            name="X",
            surname="Y",
            gender=Participant.Gender.MALE,
            deceased=False,
            deceased_date_time=timezone.localdate() - datetime.timedelta(days=1),
        )

        # Pass if VE on validation (full_clean()), assigned to 'deceased' field
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()

        self.assertIn("deceased", ctx.exception.message_dict)

    def test_clean_deceased_true_requires_deceased_date(self):
        inst = self.mk_institution(code="INST103", address="Addr103")
        pi = self.mk_pi(inst, email="pi103@example.com", surname="S103")
        project = self.mk_project(pi, name="P103", code="PRJ0103")

        p = Participant(
            project=project,
            institution=inst,
            name="X",
            surname="Y",
            gender=Participant.Gender.MALE,
            deceased=True,
            deceased_date_time=None,
        )

        # Pass if VE on validation (full_clean()), assigned to 'deceased_date_time' field
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()

        self.assertIn("deceased_date_time", ctx.exception.message_dict)

    def test_clean_birth_date_cannot_be_future(self):
        inst = self.mk_institution(code="INST104", address="Addr104")
        pi = self.mk_pi(inst, email="pi104@example.com", surname="S104")
        project = self.mk_project(pi, name="P104", code="PRJ0104")

        p = Participant(
            project=project,
            institution=inst,
            name="X",
            surname="Y",
            gender=Participant.Gender.MALE,
            birth_date=timezone.localdate() + datetime.timedelta(days=1),
        )

        # Pass if VE on validation (full_clean()), assigned to 'birth_date' field
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()

        self.assertIn("birth_date", ctx.exception.message_dict)

    def test_is_healthy_true_when_no_icd(self):
        inst = self.mk_institution(code="INST105", address="Addr105")
        pi = self.mk_pi(inst, email="pi105@example.com", surname="S105")
        project = self.mk_project(pi, name="P105", code="PRJ0105")

        p = self.mk_participant(project, inst)

        # No ICD attached, so is healthy (property validation not model's field!)
        self.assertTrue(p.is_healthy)

    def test_is_healthy_false_when_has_icd(self):
        inst = self.mk_institution(code="INST106", address="Addr106")
        pi = self.mk_pi(inst, email="pi106@example.com", surname="S106")
        project = self.mk_project(pi, name="P106", code="PRJ0106")

        p = self.mk_participant(project, inst)

        icd, _ = ICDDiagnosis.objects.get_or_create(
            code="X00", defaults={"name": "Test ICD"}
        )
        p.icd.add(icd)

        # ICD attached, so is not healthy (property validation not model's field!)
        self.assertFalse(p.is_healthy)

    def test_has_relations_includes_both_directions(self):
        inst = self.mk_institution(code="INST107", address="Addr107")
        pi = self.mk_pi(inst, email="pi107@example.com", surname="S107")
        project = self.mk_project(pi, name="P107", code="PRJ0107")

        a = self.mk_participant(project, inst, name="A", surname="A")
        b = self.mk_participant(project, inst, name="B", surname="B")

        rt = ensure_relation_type("parent")
        ParticipantRelation.objects.create(
            from_participant=a, to_participant=b, relation_type=rt
        )

        # Test bidirectional 'has_relations' model's property
        self.assertEqual(a.has_relations.count(), 1)
        self.assertEqual(b.has_relations.count(), 1)


# ----------------------------
# ParticipantRelation tests
# ----------------------------
class ParticipantRelationModelTests(BaseModelTestCase):
    def test_db_constraint_no_self_relation(self):
        inst = self.mk_institution(code="INST200", address="Addr200")
        pi = self.mk_pi(inst, email="pi200@example.com", surname="S200")
        project = self.mk_project(pi, name="P200", code="PRJ0200")
        p = self.mk_participant(project, inst)

        rt = ensure_relation_type("sibling")

        # Pass if IE, self-to-self relation permitted
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ParticipantRelation.objects.create(
                    from_participant=p,
                    to_participant=p,  # violates CheckConstraint
                    relation_type=rt,
                )

    def test_clean_monozygotic_twins_birth_date_must_match(self):
        # Your ParticipantRelation.clean checks code="monozygotic_twin"
        mono = ensure_relation_type("twin_monozygotic")

        inst = self.mk_institution(code="INST201", address="Addr201")
        pi = self.mk_pi(inst, email="pi201@example.com", surname="S201")
        project = self.mk_project(pi, name="P201", code="PRJ0201")

        a = self.mk_participant(
            project,
            inst,
            birth_date=datetime.date(2000, 1, 1),
            gender=Participant.Gender.MALE,
        )
        b = self.mk_participant(
            project,
            inst,
            birth_date=datetime.date(2001, 1, 1),
            gender=Participant.Gender.MALE,
        )

        rel = ParticipantRelation(
            from_participant=a, to_participant=b, relation_type=mono
        )

        # Validation error has to be raised here on full_clean()
        # Monozygotic twins have to have the same 'birth_date'
        with self.assertRaises(ValidationError) as ctx:
            rel.full_clean()

        # Error assigned to 'relation_type' field
        self.assertIn("relation_type", ctx.exception.message_dict)

    def test_clean_monozygotic_twins_gender_must_match(self):
        mono = ensure_relation_type("twin_monozygotic")

        inst = self.mk_institution(code="INST202", address="Addr202")
        pi = self.mk_pi(inst, email="pi202@example.com", surname="S202")
        project = self.mk_project(pi, name="P202", code="PRJ0202")

        a = self.mk_participant(
            project,
            inst,
            birth_date=datetime.date(2000, 1, 1),
            gender=Participant.Gender.MALE,
        )
        b = self.mk_participant(
            project,
            inst,
            birth_date=datetime.date(2000, 1, 1),
            gender=Participant.Gender.FEMALE,
        )

        rel = ParticipantRelation(
            from_participant=a, to_participant=b, relation_type=mono
        )

        # Validation error has to be raised here on full_clean()
        # Monozygotic twins have to have the same 'gender'
        with self.assertRaises(ValidationError) as ctx:
            rel.full_clean()

        # Error assigned to 'gender' field
        self.assertIn("gender", ctx.exception.message_dict)
