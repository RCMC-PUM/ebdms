from dataclasses import dataclass
from datetime import timedelta
from django.utils import timezone

from typing import Any, Callable, Dict, List, Optional, Union

from django.apps import apps

ValueProvider = Union[Any, Callable[[Any], Any]]

# 1) App-level default tones (single source of truth)
APP_TONE: Dict[str, str] = {
    "projects": "info",
    "biobank": "success",
    "ehr": "warning",
    "ngs": "primary",
    "lims": "neutral",
    # add more app labels here...
}

DEFAULT_TONE = "neutral"


def tone_for_app(app_label: Optional[str]) -> str:
    if not app_label:
        return DEFAULT_TONE
    return APP_TONE.get(app_label, DEFAULT_TONE)


@dataclass(frozen=True)
class DashboardCard:
    title: str
    value: ValueProvider
    subtitle: Optional[str] = None
    icon: str = "insights"

    # if tone is None -> auto from app_label; if string -> explicit override
    tone: Optional[str] = None
    app_label: Optional[str] = None  # used to infer tone

    # indicator config
    max_value: Optional[int] = None
    segments: int = 10


def model_count(app_label: str, model_name: str) -> Callable[[Any], int]:
    def _provider(request) -> int:
        ModelCls = apps.get_model(app_label, model_name)
        return ModelCls._default_manager.count()

    return _provider


# Predefined cards
cards: List[DashboardCard] = [
    DashboardCard(
        title="Projects",
        value=model_count("projects", "Project"),
        subtitle="Total projects",
        icon="work",
        app_label="projects",
        max_value=100,
        segments=10,
    ),
    DashboardCard(
        title="Participants",
        value=model_count("projects", "Participant"),
        subtitle="Total donors",
        icon="person",
        app_label="projects",
        max_value=10000,
        segments=10,
    ),
    DashboardCard(
        title="Specimen",
        value=model_count("biobank", "Specimen"),
        subtitle="Total specimens",
        icon="bloodtype",
        app_label="biobank",
        max_value=10000,
        segments=10,
    ),
    DashboardCard(
        title="Aliquots",
        value=model_count("biobank", "Aliquot"),
        subtitle="Total aliquots",
        icon="labs",
        app_label="biobank",
        max_value=10000,
        segments=10,
    ),
    DashboardCard(
        title="EHR Forms",
        value=model_count("ehr", "Forms"),
        subtitle="Total forms",
        icon="docs",
        app_label="ehr",
        max_value=100,
        segments=1,
    ),
    DashboardCard(
        title="EHR assignments",
        value=model_count("ehr", "Assignments"),
        subtitle="Total Assignments",
        icon="checklist",
        app_label="ehr",
        max_value=100,
        segments=1,
    ),
    DashboardCard(
        title="NGS results",
        value=model_count("ngs", "OmicsArtifacts"),
        subtitle="Total NGS records",
        icon="genetics",
        app_label="ngs",
        max_value=100,
        segments=1,
    ),
    DashboardCard(
        title="Orders",
        value=model_count("lims", "Order"),
        subtitle="Total orders",
        icon="warehouse",
        app_label="lims",
        max_value=100,
        segments=1,
    ),
    DashboardCard(
        title="Stock items",
        value=model_count("lims", "StockItem"),
        subtitle="Total stock items",
        icon="box",
        app_label="lims",
        max_value=1000,
        segments=10,
    ),

    # Example: explicit override for a single card
    # DashboardCard(..., app_label="lims", tone="danger"),
]


def _week_start(dt):
    # Monday as start of week
    dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt - timedelta(days=dt.weekday())


def weekly_created_series(app_label: str, model_name: str, *, date_field: str = "created_at", weeks: int = 12):
    """
    Returns (labels, values) for last N weeks, counting objects created in each week.
    Requires a datetime/date field (default created_at). Fallback to zeros on errors.
    """
    ModelCls = apps.get_model(app_label, model_name)
    now = timezone.now()
    start = _week_start(now) - timedelta(weeks=weeks - 1)  # inclusive first bucket
    buckets = []

    # Build week boundaries
    week_starts = [start + timedelta(weeks=i) for i in range(weeks)]
    week_ends = [ws + timedelta(weeks=1) for ws in week_starts]

    try:
        # Pull counts in one query using filtering per bucket (simple + reliable)
        # If you want faster later -> annotate + TruncWeek, but this is “keep simple”.
        for ws, we in zip(week_starts, week_ends):
            cnt = ModelCls._default_manager.filter(**{f"{date_field}__gte": ws, f"{date_field}__lt": we}).count()
            label = ws.strftime("%d.%m")  # e.g. 29.12
            buckets.append((label, cnt))
    except Exception:
        buckets = [(ws.strftime("%d.%m"), 0) for ws in week_starts]

    labels = [l for l, _ in buckets]
    values = [v for _, v in buckets]
    return labels, values


def dashboard_callback(request, context: Dict[str, Any]) -> Dict[str, Any]:
    # --- your existing cards rendering stays as-is ---
    rendered_cards: List[Dict[str, Any]] = []

    for c in cards:
        try:
            value = c.value(request) if callable(c.value) else c.value
        except Exception:
            value = 0

        filled = None
        if c.max_value and c.max_value > 0:
            ratio = min(max(value / c.max_value, 0), 1)
            filled = int(round(ratio * c.segments))

        rendered_cards.append(
            {
                "title": c.title,
                "value": value,
                "subtitle": c.subtitle,
                "icon": c.icon,
                "tone": c.tone,  # keep your existing tone resolution if you already have it
                "segments": c.segments,
                "filled": filled,
            }
        )

    context["dashboard_cards"] = rendered_cards

    # --- NEW: history/plots data (separate, doesn't touch DashboardCard) ---
    series_specs = [
        # (key, title, app_label, model_name, date_field, tone)
        ("projects", "Projects / week", "projects", "Project", "created_at", "info"),
        ("participants", "Participants / week", "projects", "Participant", "created_at", "success"),
        ("specimen", "Specimen / week", "biobank", "Specimen", "created_at", "success"),
        ("aliquots", "Aliquots / week", "biobank", "Aliquot", "created_at", "success"),
        ("orders", "Orders / week", "lims", "Order", "created_at", "neutral"),
        # add more if useful
    ]

    dashboard_series = []
    for key, title, app_label, model_name, date_field, tone in series_specs:
        labels, values = weekly_created_series(app_label, model_name, date_field=date_field, weeks=12)
        dashboard_series.append(
            {
                "key": key,
                "title": title,
                "labels": labels,
                "values": values,
                "max": max(values) if values else 0,
                "last": values[-1] if values else 0,
                "sum": sum(values) if values else 0,
                "tone": tone,
            }
        )

    context["dashboard_series"] = dashboard_series
    context["dashboard_series_weeks"] = 12
    context["dashboard_asof"] = timezone.now()

    return context
