"""Deterministic feature-aware ranking with explicit unsupported components."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .diversity import feature_similarity
from .explanations import explain_recommendation
from .feedback import FeedbackState
from .preferences import FEATURE_RANGES, PreferenceProfile, SUPPORTED_FEATURES

TARGET_DECAY_K = 3.0
TEMPO_NORMALIZATION_BPM = 250.0
FEEDBACK_STRENGTH = 0.25
SOFT_GENRE_MISS_SCORE = 0.25


def _feature_value(track: Mapping[str, Any], name: str) -> float | None:
    raw = track.get(name)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    lo, hi = FEATURE_RANGES[name]
    if name == "tempo":
        return value if value > 0 else None
    return value if lo <= value <= hi else None


def _normalized_value(name: str, value: float) -> float:
    return value / TEMPO_NORMALIZATION_BPM if name == "tempo" else value


def target_match(track: Mapping[str, Any], profile: PreferenceProfile) -> tuple[float | None, dict[str, Any]]:
    """Calculate S=exp(-3D) with weighted RMS distance over available dimensions."""
    targets = profile.target_features or {}
    if not targets:
        return None, {"reason": "no_targets_configured", "feature_comparisons": []}
    dimensions = []
    configured = profile.target_feature_weights
    for name, target in targets.items():
        actual = _feature_value(track, name)
        weight = float(configured.get(name, 1.0))
        if actual is None or weight <= 0:
            continue
        difference = _normalized_value(name, actual) - _normalized_value(name, float(target))
        dimensions.append((name, actual, float(target), weight, difference))
    if not dimensions:
        return None, {"reason": "no_valid_target_features_on_track", "feature_comparisons": []}
    weight_scale = max(part[3] for part in dimensions)
    scaled_weights = [part[3] / weight_scale for part in dimensions]
    total_weight = sum(scaled_weights)
    delta_scale = max(abs(part[4]) for part in dimensions)
    if delta_scale == 0:
        distance = 0.0
    else:
        unit_mean_square = sum(weight * (part[4] / delta_scale) ** 2
                               for weight, part in zip(scaled_weights, dimensions)) / total_weight
        distance = delta_scale * math.sqrt(unit_mean_square)
    score = math.exp(-TARGET_DECAY_K * distance)
    comparisons = [{
        "field": name, "actual_value": actual, "target_value": target,
        "normalized_difference": abs(difference), "feature_weight": weight,
        "weighted_squared_difference": weight * difference ** 2,
    } for (name, actual, target, _, difference), weight in zip(dimensions, scaled_weights)]
    return score, {"distance": distance, "feature_comparisons": comparisons}


def _genre_match(track: Mapping[str, Any], genres: Sequence[str]) -> bool:
    value = track.get("genre")
    return isinstance(value, str) and value.strip().casefold() in {g.casefold() for g in genres}


def _build_feedback_lookup(
    tracks: Sequence[Mapping[str, Any]], feedback: FeedbackState
) -> dict[str, Mapping[str, Any]]:
    return {str(track.get("track_id")): track for track in tracks if track.get("track_id") is not None}


def _feedback_score(
    track: Mapping[str, Any], feedback: FeedbackState, lookup: Mapping[str, Mapping[str, Any]]
) -> tuple[float | None, list[dict[str, Any]]]:
    positive_ids = feedback.liked_track_ids | feedback.more_like_track_ids
    negative_ids = feedback.skipped_track_ids
    positive, negative, evidence = [], [], []
    for kind, ids, output in (("like", positive_ids, positive), ("skip", negative_ids, negative)):
        if kind == "like":
            more_like = feedback.more_like_track_ids
        for tid in sorted(ids):
            reference = lookup.get(tid)
            if reference is None:
                continue
            if str(track.get("track_id")) == tid:
                similarity = 1.0
            else:
                similarity = feature_similarity(track, reference)
                if similarity is None:
                    left_genre, right_genre = track.get("genre"), reference.get("genre")
                    if not (left_genre and right_genre):
                        continue
                    similarity = 0.6 if str(left_genre).casefold() == str(right_genre).casefold() else 0.0
            output.append(similarity)
            evidence.append({"kind": "more_like_this" if kind == "like" and tid in more_like else kind,
                             "track_id": tid, "similarity": similarity})
    if not positive and not negative:
        return None, []
    positive_mean = sum(positive) / len(positive) if positive else 0.0
    negative_mean = sum(negative) / len(negative) if negative else 0.0
    score = min(1.0, max(0.0, 0.5 + FEEDBACK_STRENGTH * (positive_mean - negative_mean)))
    return score, evidence


def _genre_rarity(track: Mapping[str, Any], counts: Mapping[str, int], max_count: int) -> dict[str, Any] | None:
    genre = track.get("genre")
    if not isinstance(genre, str) or not genre.strip() or max_count <= 1:
        return None
    count = counts.get(genre.casefold())
    if not count:
        return None
    denominator = math.log1p(max_count - 1)
    score = 1.0 - math.log1p(count - 1) / denominator if denominator else 0.0
    return {"score": min(1.0, max(0.0, score)), "genre_count": count}


def _effective_weights(
    requested: Mapping[str, float], active: Sequence[str], extra_discovery: float = 0.0,
    fallback_equal: bool = False,
) -> dict[str, float]:
    values = {name: float(requested.get(name, 0.0)) for name in active}
    if "discovery" in values:
        values["discovery"] += extra_discovery
    total = sum(values.values())
    if total > 0:
        return {name: value / total for name, value in values.items()}
    if fallback_equal and active:
        return {name: 1.0 / len(active) for name in active}
    return {}


def rank_tracks(
    catalogue: Sequence[Mapping[str, Any]],
    profile: PreferenceProfile,
    feedback: FeedbackState | None = None,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Score, explain, and stably order catalogue tracks; no UI dependencies."""
    feedback = feedback or FeedbackState()
    tracks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in catalogue:
        tid = str(raw.get("track_id", "")).strip()
        if not tid or tid in seen:
            continue
        seen.add(tid)
        track = dict(raw)
        if profile.genre_filter == "strict" and profile.preferred_genres and not _genre_match(track, profile.preferred_genres):
            continue
        tracks.append(track)
    if not tracks:
        return []
    lookup = _build_feedback_lookup(catalogue, feedback)
    genre_counts: dict[str, int] = {}
    for track in catalogue:
        genre = track.get("genre")
        if isinstance(genre, str) and genre.strip():
            key = genre.casefold()
            genre_counts[key] = genre_counts.get(key, 0) + 1
    max_genre_count = max(genre_counts.values(), default=0)
    results: list[dict[str, Any]] = []
    for track in tracks:
        target_score, target_detail = target_match(track, profile)
        feedback_score, feedback_evidence = _feedback_score(track, feedback, lookup)
        genre_match = _genre_match(track, profile.preferred_genres) if profile.preferred_genres else False
        preference_score: float | None = None
        if profile.preferred_genres or feedback_score is not None:
            genre_score = (1.0 if genre_match else SOFT_GENRE_MISS_SCORE) if profile.preferred_genres else None
            if genre_score is not None and feedback_score is not None:
                preference_score = 0.65 * genre_score + 0.35 * feedback_score
            else:
                preference_score = genre_score if genre_score is not None else feedback_score
        rarity = _genre_rarity(track, genre_counts, max_genre_count)
        discovery_score = rarity["score"] if rarity is not None else None
        components = {"target": target_score, "preference": preference_score, "discovery": discovery_score}
        active = [name for name, value in components.items() if value is not None]
        weights = _effective_weights(profile.weights, active,
                                     extra_discovery=0.15 if feedback.more_variety else 0.0,
                                     fallback_equal=not any(profile.weights.values()))
        total = sum(weights[name] * float(components[name]) for name in weights)
        total = min(1.0, max(0.0, total))
        detail = {
            "target_features": target_detail["feature_comparisons"],
            "genre_match": genre_match,
            "preferred_genres": list(profile.preferred_genres),
            "feedback_similarities": feedback_evidence,
            "genre_rarity": rarity,
            "unsupported_components": [name for name in components if components[name] is None],
            "zero_weight_supported_components": [name for name in active if name not in weights],
        }
        explanation = explain_recommendation(track, components, weights, detail)
        contributions = {name: weights[name] * float(components[name]) for name in weights}
        results.append({
            **track,
            "target_score": target_score,
            "preference_score": preference_score,
            "discovery_score": discovery_score,
            "overall_score": total,
            "ranking_score": total,
            "component_weights": weights,
            "component_contributions": contributions,
            "contributing_components": list(weights),
            "unsupported_components": detail["unsupported_components"],
            "zero_weight_supported_components": detail["zero_weight_supported_components"],
            "target_distance": target_detail.get("distance"),
            "explanation": explanation,
        })
    results.sort(key=lambda row: (-row["overall_score"], str(row["track_id"])))
    return results[:(profile.recommendation_count if limit is None else max(0, limit))]


def recommend_tracks(
    catalogue: Sequence[Mapping[str, Any]],
    profile: PreferenceProfile,
    feedback: FeedbackState | None = None,
    *,
    max_tracks_per_artist: int | None = None,
) -> list[dict[str, Any]]:
    """Run full-candidate scoring followed by deterministic diversity reranking."""
    from .diversity import rerank_for_diversity

    feedback = feedback or FeedbackState()
    ranked = rank_tracks(catalogue, profile, feedback, limit=len(catalogue))
    variety = max(profile.variety, 0.8) if feedback.more_variety else profile.variety
    return rerank_for_diversity(
        ranked, variety=variety, max_tracks_per_artist=max_tracks_per_artist,
        count=profile.recommendation_count,
    )

