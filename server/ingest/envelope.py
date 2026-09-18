"""The telemetry envelope (§7.1) as a Pydantic model — the validation
boundary between whatever a client sends and what ever reaches Postgres.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Surface = Literal["home", "category", "search", "detail", "compare", "cart"]
Mode = Literal["discovery", "directed_search", "broad_search", "comparison", "refind"]

# detail_view_start/detail_view_end are diagnostic only -- stored and
# shown in the admin event-log viewer, never read by replay.py, live.py,
# or anything in features/. The detail page's real view_start/view_end
# (surface: detail, same tracked-card mechanism every other surface uses)
# is what actually feeds the pipeline. See web/src/lib/eventSchema.ts,
# the single source of truth this set should stay a superset of.
EVENT_TYPES = {
    "page_view", "item_impression", "view_start", "view_end", "detail_view_start", "detail_view_end",
    "pointer_batch", "scroll_batch", "hover_start", "hover_end", "click", "zoom", "gallery_advance",
    "panel_open", "search", "autocomplete_select", "filter", "sort", "cart_add", "cart_remove",
    "wishlist", "checkout_start", "rec_impression", "visibility_change", "session_end",
}

COMMITMENT_TYPES = {"cart_add", "wishlist", "checkout_start"}


class Envelope(BaseModel):
    event_id: UUID
    session_id: UUID
    seq: int
    ts_mono: float
    ts_wall: float  # epoch ms; converted to a Postgres timestamptz at insert
    demo: bool
    surface: Surface
    mode: Mode | None = None
    type: str
    payload: dict = Field(default_factory=dict)

    def is_commitment(self) -> bool:
        return self.type in COMMITMENT_TYPES
