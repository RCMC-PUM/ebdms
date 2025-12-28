import os
import time
import re
import requests

from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand, CommandError

from ontologies.models import ICDDiagnosis


TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
API_BASE = "https://id.who.int"


@dataclass
class RateLimiter:
    rps: float
    _min_interval: float = 0.0
    _last_ts: float = 0.0

    def __post_init__(self):
        if self.rps <= 0:
            raise ValueError("rps must be > 0")
        self._min_interval = 1.0 / float(self.rps)

    def wait(self):
        now = time.time()
        elapsed = now - self._last_ts
        sleep_for = self._min_interval - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)
        self._last_ts = time.time()


class WhoIcdClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        language: str = "en",
        api_version: str = "v2",
        rps: float = 5.0,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.language = language
        self.api_version = api_version

        self._access_token: Optional[str] = None
        self._token_expiry_ts: float = 0.0

        self._rl = RateLimiter(rps=rps)
        self._session = requests.Session()

    def _get_token(self) -> str:
        # reuse token until almost expired
        if self._access_token and time.time() < (self._token_expiry_ts - 30):
            return self._access_token

        self._rl.wait()
        resp = self._session.post(
            TOKEN_URL,
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials", "scope": "icdapi_access"},
            timeout=30,
        )
        if resp.status_code >= 400:
            raise CommandError(f"WHO token request failed ({resp.status_code}): {resp.text[:300]}")

        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            raise CommandError("WHO token response missing access_token")

        expires_in = int(payload.get("expires_in", 3600))
        self._access_token = token
        self._token_expiry_ts = time.time() + expires_in
        return token

    def get_json(self, url: str, *, max_retries: int = 6) -> Dict[str, Any]:
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Accept-Language": self.language,
            "API-Version": self.api_version,
        }

        attempt = 0
        backoff = 0.5
        while True:
            attempt += 1
            self._rl.wait()
            resp = self._session.get(url, headers=headers, timeout=60)

            if 200 <= resp.status_code < 300:
                return resp.json()

            # Retry on rate limit / transient errors
            if resp.status_code in (429, 500, 502, 503, 504) and attempt <= max_retries:
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_s = float(retry_after)
                    except ValueError:
                        wait_s = backoff
                else:
                    wait_s = backoff

                time.sleep(wait_s)
                backoff = min(backoff * 2.0, 10.0)
                continue

            raise CommandError(f"WHO GET failed ({resp.status_code}) url={url} body={resp.text[:300]}")


def _as_list(v: Any) -> List[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _extract_uris(node: Dict[str, Any]) -> List[str]:
    uris: List[str] = []

    for key in ("child", "foundationChildElsewhere", "relatedEntitiesInLinearization"):
        for item in _as_list(node.get(key)):
            if isinstance(item, str) and item.startswith("http"):
                uris.append(item.replace("http://", "https://"))
            elif isinstance(item, dict):
                uri = item.get("@id") or item.get("id")
                if isinstance(uri, str) and uri.startswith("http"):
                    uris.append(uri.replace("http://", "https://"))

    # de-dup preserve order
    seen = set()
    out: List[str] = []
    for u in uris:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


_MARKDOWN_PREFIX_RE = re.compile(r"^\s*!markdown\s*", re.IGNORECASE)


def _clean_text(s: str) -> str:
    # remove WHO "!markdown" prefix and normalize whitespace
    s = _MARKDOWN_PREFIX_RE.sub("", s or "")
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _pick_text(node: Dict[str, Any], key: str) -> str:
    v = node.get(key)
    if isinstance(v, dict):
        # WHO often returns {"@value": "...", "@language": "en"}
        vv = v.get("@value") or v.get("value")
        if isinstance(vv, str):
            return _clean_text(vv)
    if isinstance(v, str):
        return _clean_text(v)
    return ""


def _pick_title(node: Dict[str, Any]) -> str:
    for k in ("title", "label", "fullySpecifiedName", "display"):
        t = _pick_text(node, k)
        if t:
            return t
    fallback = (node.get("@id") or "").strip()
    return fallback or "—"


def _pick_definition(node: Dict[str, Any]) -> str:
    return _pick_text(node, "definition")


def _pick_code(node: Dict[str, Any]) -> Optional[str]:
    code = node.get("code")
    if isinstance(code, str):
        code = code.strip()
        return code or None
    return None


def _pick_class_kind(node: Dict[str, Any]) -> Optional[str]:
    """
    ICD-11 linearization entity kind:
      - chapter, block, window, category, ...
    We want ONLY 'category' for codable diagnosis entities.
    """
    ck = node.get("classKind")
    if isinstance(ck, dict):
        v = ck.get("@value") or ck.get("value")
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
        cid = ck.get("@id")
        if isinstance(cid, str) and cid.strip():
            return cid.strip().split("/")[-1].lower()
    if isinstance(ck, str) and ck.strip():
        return ck.strip().lower()
    return None


class Command(BaseCommand):
    help = "Import ICD codes from WHO ICD API into ICDDiagnosis (filtered to categories only)."

    def add_arguments(self, parser):
        parser.add_argument("--icd-version", choices=["icd11"], default="icd11")
        parser.add_argument("--release", default="2025-01", help="e.g. 2025-01 (ICD-11 MMS), 2019 (ICD-10)")
        parser.add_argument("--language", default="en")
        parser.add_argument("--linearization", default="mms", help="ICD-11 linearization name (usually 'mms')")
        parser.add_argument("--max", type=int, default=0, help="Optional cap for saved codes (0 = no cap)")
        parser.add_argument("--rps", type=float, default=5.0, help="Max WHO requests per second (default 5)")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--only-leaf",
            action="store_true",
            help="Save only leaf categories (no children). Useful if you want only final, most specific codes.",
        )

    def handle(self, *args, **opts):
        cid = os.getenv("ICD_CLIENT_ID")
        csec = os.getenv("ICD_CLIENT_SECRET")
        if not cid or not csec:
            raise CommandError("Missing env vars: ICD_CLIENT_ID and ICD_CLIENT_SECRET.")

        icd_version = opts["icd_version"]
        release = opts["release"]
        language = opts["language"]
        linearization = opts["linearization"]
        max_n = int(opts["max"] or 0)
        rps = float(opts["rps"] or 5.0)
        dry = bool(opts["dry_run"])
        only_leaf = bool(opts["only_leaf"])

        client = WhoIcdClient(client_id=cid, client_secret=csec, language=language, rps=rps)

        if icd_version == "icd11":
            root_url = f"{API_BASE}/icd/release/11/{release}/{linearization}"
            system = f"http://id.who.int/icd/release/11/{release}/{linearization}"
            model_version = ICDDiagnosis.ICDVersion.ICD11
        else:
            root_url = f"{API_BASE}/icd/release/10/{release}"
            system = f"http://id.who.int/icd/release/10/{release}"
            # NOTE: make sure your ICDVersion enum includes ICD10
            model_version = ICDDiagnosis.ICDVersion.ICD10  # type: ignore[attr-defined]

        self.stdout.write(
            f"Importing {icd_version.upper()} release={release} lang={language} rps={rps} root={root_url} "
            f"only_leaf={only_leaf} dry_run={dry}"
        )

        visited = set()
        queue = deque([root_url])

        saved = 0
        seen_with_code = 0
        saved_categories = 0

        while queue:
            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            data = client.get_json(url)

            # Always traverse children first/also, so we don't miss real categories
            child_uris = _extract_uris(data)
            if child_uris:
                queue.extend(child_uris)

            code = _pick_code(data)
            if not code:
                continue
            seen_with_code += 1

            class_kind = _pick_class_kind(data)
            # HARD FILTER: only real codable ICD categories
            if class_kind != "category":
                continue

            if only_leaf and child_uris:
                # category but not leaf -> skip
                continue

            title = _pick_title(data)
            definition = _pick_definition(data)

            if not dry:
                ICDDiagnosis.objects.update_or_create(
                    version=model_version,
                    system=system,
                    code=code,
                    defaults={
                        "display": title,
                        "name": "",
                        "description": definition,
                    },
                )

            saved += 1
            saved_categories += 1

            if max_n and saved >= max_n:
                break

            if len(visited) % 250 == 0:
                self.stdout.write(
                    f"Visited={len(visited)} saved={saved} categories_saved={saved_categories} "
                    f"nodes_with_code_seen={seen_with_code} queue={len(queue)}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. visited={len(visited)} saved={saved} categories_saved={saved_categories} "
                f"nodes_with_code_seen={seen_with_code} dry_run={dry}"
            )
        )
