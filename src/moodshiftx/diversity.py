"""Deterministic greedy diversity reranking that preserves relevance scores."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .preferences import FEATURE_RANGES, SUPPORTED_FEATURES

TEMPO_SCALE = 250.0


def _normalized(track: Mapping[str, Any], feature: str) -> float | None:
    value = track.get(feature)
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    lo, hi = FEATURE_RANGES[feature]
    valid = value > 0 if feature == "tempo" else lo <= value <= hi
    if not math.isfinite(value) or not valid:
        return None
    return value / TEMPO_SCALE if feature == "tempo" else value


def feature_similarity(left: Mapping[str, Any], right: Mapping[str, Any]) -> float | None:
    """Return exp(-3d) on valid shared dimensions; None when none are shared."""
    deltas = []
    for name in sorted(SUPPORTED_FEATURES):
        a, b = _normalized(left, name), _normalized(right, name)
        if a is not None and b is not None:
            deltas.append((a - b) ** 2)
    return math.exp(-3.0 * math.sqrt(sum(deltas) / len(deltas))) if deltas else None


def _pair_similarity(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    feature = feature_similarity(left, right)
    signals: list[float] = []
    if feature is not None:
        signals.append(feature)
    left_genre, right_genre = left.get("genre"), right.get("genre")
    if left_genre and right_genre:
        signals.append(1.0 if str(left_genre).casefold() == str(right_genre).casefold() else 0.0)
    left_artist = left.get("artist_id") or left.get("artist_name")
    right_artist = right.get("artist_id") or right.get("artist_name")
    if left_artist and right_artist:
        signals.append(1.0 if str(left_artist).casefold() == str(right_artist).casefold() else 0.0)
    # Unknown metadata is neutral. It is not evidence that two tracks are
    # maximally different or novel.
    return sum(signals) / len(signals) if signals else 0.5


def rerank_for_diversity(
    recommendations: Sequence[Mapping[str, Any]],
    *,
    variety: float = 0.35,
    max_tracks_per_artist: int | None = None,
    artist_repeat_penalty: float = 0.08,
    count: int | None = None,
) -> list[dict[str, Any]]:
    """Greedily trade some relevance for novelty; never overwrite relevance.

    Pairwise feature distance uses shared normalized features and exp(-3d).
    Tempo is normalized by 250 BPM; [0,1] features are unchanged. If no shared
    feature exists, known genre identity supplies the metadata fallback.
    """
    variety = float(variety)
    artist_repeat_penalty = float(artist_repeat_penalty)
    if not math.isfinite(variety) or not 0 <= variety <= 1:
        raise ValueError("variety must be in [0, 1]")
    if not math.isfinite(artist_repeat_penalty) or not 0 <= artist_repeat_penalty <= 1:
        raise ValueError("artist_repeat_penalty must be in [0, 1]")
    if max_tracks_per_artist is not None and max_tracks_per_artist < 1:
        raise ValueError("max_tracks_per_artist must be positive")
    requested = len(recommendations) if count is None else max(0, int(count))
    unique: dict[str, dict[str, Any]] = {}
    for item in recommendations:
        tid = str(item.get("track_id", "")).strip()
        if not tid or tid in unique:
            continue
        row = dict(item)
        relevance = row.get("overall_score", row.get("ranking_score", row.get("original_ranking_score")))
        try:
            relevance = float(relevance)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Recommendation {tid} has no finite original score") from exc
        if not math.isfinite(relevance):
            raise ValueError(f"Recommendation {tid} has no finite original score")
        relevance = min(1.0, max(0.0, relevance))
        row["original_ranking_score"] = relevance
        unique[tid] = row
    remaining = list(unique.values())
    selected: list[dict[str, Any]] = []
    artist_counts: dict[str, int] = {}
    while remaining and len(selected) < requested:
        candidates = remaining
        if max_tracks_per_artist is not None:
            under_cap = [row for row in remaining
                         if artist_counts.get(str(row.get("artist_id") or row.get("artist_name") or ""), 0) < max_tracks_per_artist]
            if under_cap:
                candidates = under_cap
        evaluated = []
        for row in candidates:
            if selected:
                novelty = 1.0 - max(_pair_similarity(row, chosen) for chosen in selected)
            else:
                novelty = 1.0
            artist = str(row.get("artist_id") or row.get("artist_name") or "")
            repeats = artist_counts.get(artist, 0) if artist else 0
            repeat_penalty = artist_repeat_penalty if repeats else 0.0
            final = (1.0 - variety) * row["original_ranking_score"] + variety * novelty - repeat_penalty
            evaluated.append((final, row["original_ranking_score"], str(row["track_id"]), row, novelty, repeat_penalty))
        # Highest rerank score, then original relevance, then stable track ID.
        final, relevance, _, best, novelty, repeat_penalty = min(
            evaluated, key=lambda value: (-value[0], -value[1], value[2]))
        best = dict(best)
        best["final_reranking_score"] = min(1.0, max(0.0, final))
        best["rerank_components"] = {"original_ranking_score": relevance,
                                     "novelty_score": novelty,
                                     "artist_repeat_penalty": repeat_penalty}
        selected.append(best)
        artist = str(best.get("artist_id") or best.get("artist_name") or "")
        if artist:
            artist_counts[artist] = artist_counts.get(artist, 0) + 1
        remaining = [row for row in remaining if row["track_id"] != best["track_id"]]
    return selected

