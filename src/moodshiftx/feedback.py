"""Session-ready, idempotent feedback state independent of Streamlit."""
from __future__ import annotations

from dataclasses import dataclass


def _track_id(value: str) -> str:
    identifier = str(value).strip()
    if not identifier:
        raise ValueError("Feedback requires a non-empty stable track_id")
    return identifier


@dataclass(frozen=True)
class FeedbackState:
    """One current signal per track; repeated button events cannot accumulate."""

    liked_track_ids: frozenset[str] = frozenset()
    skipped_track_ids: frozenset[str] = frozenset()
    more_like_track_ids: frozenset[str] = frozenset()
    more_variety: bool = False


def like(state: FeedbackState, track_id: str) -> FeedbackState:
    tid = _track_id(track_id)
    return FeedbackState(state.liked_track_ids | {tid}, state.skipped_track_ids - {tid},
                         state.more_like_track_ids, state.more_variety)


def skip(state: FeedbackState, track_id: str) -> FeedbackState:
    tid = _track_id(track_id)
    return FeedbackState(state.liked_track_ids - {tid}, state.skipped_track_ids | {tid},
                         state.more_like_track_ids - {tid}, state.more_variety)


def more_like_this(state: FeedbackState, track_id: str) -> FeedbackState:
    tid = _track_id(track_id)
    return FeedbackState(state.liked_track_ids, state.skipped_track_ids - {tid},
                         state.more_like_track_ids | {tid}, state.more_variety)


def more_variety(state: FeedbackState, enabled: bool = True) -> FeedbackState:
    return FeedbackState(state.liked_track_ids, state.skipped_track_ids,
                         state.more_like_track_ids, bool(enabled))


def reset_feedback() -> FeedbackState:
    return FeedbackState()

