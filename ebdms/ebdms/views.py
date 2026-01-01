# core/admin_dashboard.py
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union

from django.apps import apps
from django.db.models import Model


ValueProvider = Union[Any, Callable[[Any], Any]]


@dataclass(frozen=True)
class DashboardCard:
    title: str
    value: ValueProvider
    subtitle: Optional[str] = None
    icon: str = "insights"
    tone: str = "neutral"

    # indicator config
    max_value: Optional[int] = None
    segments: int = 10


def model_count(app_label: str, model_name: str) -> Callable[[Any], int]:
    def _provider(request) -> int:
        ModelCls: Model = apps.get_model(app_label, model_name)
        return ModelCls._default_manager.count()

    return _provider


# Predefined cards

cards: List[DashboardCard] = [
    DashboardCard(
        title="Projects",
        value=model_count("projects", "Project"),
        subtitle="Total projects",
        icon="work",
        tone="info",
        max_value=100,
        segments=10,
    ),
    DashboardCard(
        title="Donors",
        value=model_count("biobank", "Donor"),
        subtitle="Total donors",
        icon="person",
        tone="success",
        max_value=10000,
        segments=10,
    ),
    DashboardCard(
        title="Users",
        value=model_count("auth", "User"),
        subtitle="Total users",
        icon="group",
        tone="neutral",
        max_value=25,
        segments=5,
    ),
    DashboardCard(
        title="Stock items",
        value=model_count("lims", "StockItem"),
        subtitle="Total stock items",
        icon="box",
        tone="neutral",
        max_value=1000,
        segments=10,
    ),
]


def dashboard_callback(request, context: Dict[str, Any]) -> Dict[str, Any]:
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
                "tone": c.tone,
                "segments": c.segments,
                "filled": filled,  # <- NUMBER OF ACTIVE SEGMENTS
            }
        )

    context["dashboard_cards"] = rendered_cards
    return context
