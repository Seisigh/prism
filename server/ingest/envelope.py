"""The telemetry envelope (§7.1) as a Pydantic model — the validation
boundary between whatever a client sends and what ever reaches Postgres.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Surface = Literal["home", "category", "search", "detail", "compare", "cart"]
Mode = Literal["discovery", "directed_search", "broad_search", "comparison", "refind"]

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
