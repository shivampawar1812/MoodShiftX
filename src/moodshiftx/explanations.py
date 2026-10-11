"""Structured explanations from ranking evidence and source metadata only."""
from __future__ import annotations

from typing import Any, Mapping


def explain_recommendation(
    track: Mapping[str, Any],
    components: Mapping[str, float | None],
    effective_weights: Mapping[str, float],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Build concise reasons whose values come from computed ranking evidence."""
    result: list[dict[str, Any]] = []
    target = components.get("target")
    if target is not None:
        for comparison in evidence.get("target_features", []):
            field = comparison["field"]
            actual, desired = comparison["actual_value"], comparison["target_value"]
            result.append({
                "category": "target_match", "field": field,
                "actual_value": actual, "target_value": desired,
                "difference": comparison["normalized_difference"],
                "score_contribution": effective_weights.get("target", 0.0) * target,
                "source_component": "target",
                "text": f"{field} is {actual:g} against your target of {desired:g}.",
            })
    if evidence.get("genre_match"):
        genre = track.get("genre")
        result.append({
            "category": "genre_preference", "field": "genre", "actual_value": genre,
            "target_value": evidence["preferred_genres"], "difference": None,
            "score_contribution": effective_weights.get("preference", 0.0) * (components.get("preference") or 0.0),
            "source_component": "preference",
            "text": f"{genre} is among your selected genres.",
        })
    for item in evidence.get("feedback_similarities", []):
        kind = item["kind"]
        phrase = "resembles a track you liked" if kind in {"like", "more_like_this"} else "is similar to a track you skipped"
        result.append({
            "category": "feedback_similarity", "field": "track_id",
            "actual_value": track.get("track_id"), "target_value": item["track_id"],
            "difference": None, "similarity": item["similarity"],
            "score_contribution": effective_weights.get("preference", 0.0) * (components.get("preference") or 0.0),
            "source_component": "preference", "text": f"This track {phrase} (feature similarity {item['similarity']:.2f}).",
        })
    if evidence.get("genre_rarity") is not None:
        rarity = evidence["genre_rarity"]
        result.append({
            "category": "catalogue_genre_variety", "field": "genre",
            "actual_value": track.get("genre"), "target_value": None,
            "difference": None, "catalogue_genre_count": rarity["genre_count"],
            "score_contribution": effective_weights.get("discovery", 0.0) * (components.get("discovery") or 0.0),
            "source_component": "discovery",
            "text": f"{track.get('genre')} occurs on {rarity['genre_count']} tracks in this catalogue; this supports genre variety, not a quality claim.",
        })
    categories = {item["category"] for item in result}
    summaries = []
    if "target_match" in categories:
        summaries.append(f"Matches the supported audio targets (score {target:.2f}).")
    if "genre_preference" in categories:
        summaries.append(f"Fits your selected genre ({track.get('genre')}).")
    if "feedback_similarity" in categories:
        summaries.append("Reflects your explicit track feedback.")
    if "catalogue_genre_variety" in categories:
        summaries.append("Adds catalogue genre variety.")
    return {"summary": " ".join(summaries), "evidence": result,
            "limitations": [] if target is not None else ["No supported audio-target match was calculated for this track."]}

