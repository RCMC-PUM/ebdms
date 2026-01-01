import os
import time
from collections import deque

import requests
from django.core.management.base import BaseCommand, CommandError

from ontologies.models import ICDDiagnosis

TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
API_BASE = "https://id.who.int"


class WHO:
    def __init__(
        self, client_id: str, client_secret: str, lang: str = "en", rps: float = 5.0
    ):
        self.cid = client_id
        self.csec = client_secret
        self.lang = lang
        self.min_dt = 1.0 / max(rps, 0.1)
        self.last = 0.0
        self.s = requests.Session()
        self.token = None
        self.exp = 0.0

    def _sleep(self):
        dt = time.time() - self.last
        if dt < self.min_dt:
            time.sleep(self.min_dt - dt)
        self.last = time.time()

    def _token(self) -> str:
        if self.token and time.time() < (self.exp - 30):
            return self.token
        self._sleep()
        r = self.s.post(
            TOKEN_URL,
            auth=(self.cid, self.csec),
            data={"grant_type": "client_credentials", "scope": "icdapi_access"},
            timeout=30,
        )
        if r.status_code >= 400:
            raise CommandError(f"WHO token failed ({r.status_code}): {r.text[:200]}")
        j = r.json()
        self.token = j["access_token"]
        self.exp = time.time() + int(j.get("expires_in", 3600))
        return self.token

    def get(self, url: str) -> dict:
        self._sleep()
        r = self.s.get(
            url,
            headers={
                "Authorization": f"Bearer {self._token()}",
                "Accept": "application/json",
                "Accept-Language": self.lang,
                "API-Version": "v2",
            },
            timeout=60,
        )
        if r.status_code >= 400:
            raise CommandError(
                f"WHO GET failed ({r.status_code}) {url} --> {r.text[:200]}"
            )
        return r.json()


def _children(node: dict) -> list[str]:
    out = []

    def add(x):
        if isinstance(x, str) and x.startswith("http"):
            out.append(x.replace("http://", "https://"))
        elif isinstance(x, dict):
            u = x.get("@id") or x.get("id")
            if isinstance(u, str) and u.startswith("http"):
                out.append(u.replace("http://", "https://"))

    for k in ("child", "foundationChildElsewhere", "relatedEntitiesInLinearization"):
        v = node.get(k)
        if isinstance(v, list):
            for it in v:
                add(it)
        elif v:
            add(v)

    # de-dup
    return list(dict.fromkeys(out))


def _text(v) -> str:
    # WHO returns either string or {"@value": "..."}
    if isinstance(v, dict):
        v = v.get("@value") or v.get("value") or ""
    if not isinstance(v, str):
        return ""
    v = v.strip()
    if v.lower().startswith("!markdown"):
        v = v[len("!markdown") :].strip()
    return " ".join(v.split())


def _title(node: dict) -> str:
    for k in ("title", "label", "fullySpecifiedName", "display"):
        t = _text(node.get(k))
        if t:
            return t
    return _text(node.get("@id")) or "—"


def _definition(node: dict) -> str:
    return _text(node.get("definition"))


def _code(node: dict) -> str | None:
    c = node.get("code")
    return c.strip() if isinstance(c, str) and c.strip() else None


def _is_category(node: dict) -> bool:
    ck = node.get("classKind")
    if isinstance(ck, dict):
        ck = ck.get("@value") or ck.get("value") or ck.get("@id") or ""
        if isinstance(ck, str) and "/" in ck:
            ck = ck.rsplit("/", 1)[-1]
    return isinstance(ck, str) and ck.strip().lower() == "category"


class Command(BaseCommand):
    """
    ICD11 importer:
      - ICD-11 MMS only
      - leaf categories only (most precise)
    """

    help = "Import ICD-11 leaf categories (chapters 01-18) from WHO into ICDDiagnosis."

    def add_arguments(self, parser):
        parser.add_argument("--release", default="2025-01")
        parser.add_argument("--rps", type=float, default=0.05)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        cid = os.getenv("ICD_CLIENT_ID")
        csec = os.getenv("ICD_CLIENT_SECRET")

        if not cid or not csec:
            raise CommandError("Set env vars: ICD_CLIENT_ID and ICD_CLIENT_SECRET")

        who = WHO(cid, csec, rps=o["rps"])

        root = f"{API_BASE}/icd/release/11/{o['release']}/mms"
        system = f"http://id.who.int/icd/release/11/{o['release']}/mms"

        q = deque([root])
        seen = set()
        saved = 0

        while q:
            url = q.popleft()
            if url in seen:
                continue
            seen.add(url)

            node = who.get(url)
            kids = _children(node)
            if kids:
                q.extend(kids)

            code = _code(node)
            if not code:
                continue
            if not _is_category(node):
                continue
            if kids:  # leaf only
                continue

            name = _title(node)
            desc = _definition(node)

            if not o["dry_run"]:
                ICDDiagnosis.objects.update_or_create(
                    version=ICDDiagnosis.ICDVersion.ICD11,
                    system=system,
                    code=code,
                    defaults={"name": name, "description": desc},
                )

            saved += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. visited={len(seen)} saved={saved} (leaf categories, ch 01-18)"
            )
        )
