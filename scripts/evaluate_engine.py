"""Measure deterministic recommendation behavior on the local FMA catalogue."""
from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys
import time

try:
    import psutil
except ImportError:  # optional local diagnostic, not an application dependency
    psutil = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.moodshiftx.catalogue import load_catalogue
from src.moodshiftx.preferences import PreferenceProfile
from src.moodshiftx.ranking import recommend_tracks, target_match


def _result_metrics(rows: list[dict], features: tuple[str, ...]) -> dict:
    artists = [str(row.get("artist_id") or row.get("artist_name") or "") for row in rows]
    genres = [str(row.get("genre") or "") for row in rows]
    per_feature = {}
    for feature in features:
        values = [float(row[feature]) for row in rows if row.get(feature) is not None]
        per_feature[feature] = round(statistics.pstdev(values), 6) if len(values) > 1 else None
    return {
        "result_count": len(rows),
        "unique_track_ids": len({row["track_id"] for row in rows}),
        "duplicate_recommendation_rate": round(
            (len(rows) - len({row["track_id"] for row in rows})) / len(rows), 6) if rows else None,
        "distinct_artists": len(set(artists) - {""}),
        "distinct_genres": len(set(genres) - {""}),
        "mean_target_score": round(statistics.mean(row["target_score"] for row in rows), 6) if rows else None,
        "feature_population_stddev": per_feature,
    }


def main() -> int:
    started = time.perf_counter()
    catalogue = load_catalogue(ROOT / "data" / "fma_metadata")
    load_seconds = time.perf_counter() - started
    process = psutil.Process() if psutil is not None else None
    rss_after_load_mb = process.memory_info().rss / (1024 * 1024) if process else None
    profile = PreferenceProfile(
        desired_experience="calm", weights={"target": 1, "preference": 0, "discovery": 0},
        recommendation_count=10, variety=0.35,
    )
    features = tuple(profile.target_features or {})
    supported = [row for row in catalogue if all(row.get(name) is not None for name in features)]
    genre_counts: dict[str, int] = {}
    for row in catalogue:
        genre = row.get("genre")
        if isinstance(genre, str) and genre.strip():
            key = genre.casefold()
            genre_counts[key] = genre_counts.get(key, 0) + 1
    profile_component_coverage = {
        "target": sum(all(row.get(name) is not None for name in features) for row in catalogue),
        "preference": 0,  # This controlled profile selects no genre and has no feedback.
        "discovery": sum(isinstance(row.get("genre"), str) and bool(row["genre"].strip())
                         and genre_counts.get(row["genre"].casefold(), 0) > 1 for row in catalogue),
    }
    started = time.perf_counter()
    first = recommend_tracks(supported, profile)
    recommendation_seconds = time.perf_counter() - started
    rss_after_recommendations_mb = process.memory_info().rss / (1024 * 1024) if process else None
    second = recommend_tracks(supported, profile)
    repeat_ids_match = [r["track_id"] for r in first] == [r["track_id"] for r in second]

    # A transparent descriptive baseline: rank the same eligible subset by
    # the source's raw track.interest value, with stable IDs breaking ties.
    popularity = [row for row in supported if row.get("popularity") is not None]
    popularity.sort(key=lambda row: (-float(row["popularity"]), str(row["track_id"])))
    baseline = popularity[:profile.recommendation_count]
    baseline_scored = []
    for row in baseline:
        score, _ = target_match(row, profile)
        baseline_scored.append({**row, "target_score": score})

    report = {
        "method": "Local FMA descriptive benchmark; no listener relevance labels",
        "catalogue_load_seconds": round(load_seconds, 3),
        "recommendation_generation_seconds": round(recommendation_seconds, 3),
        "process_rss_mb_after_load": round(rss_after_load_mb, 1) if rss_after_load_mb is not None else None,
        "process_rss_mb_after_recommendations": round(rss_after_recommendations_mb, 1) if rss_after_recommendations_mb is not None else None,
        "candidate_count": len(supported),
        "catalogue_displayable_tracks": len(catalogue),
        "tracks_without_all_selected_goal_features": len(catalogue) - len(supported),
        "goal": profile.desired_experience,
        "target_feature_values": dict(profile.target_features or {}),
        "feature_coverage": {
            feature: sum(row.get(feature) is not None for row in catalogue)
            for feature in features
        },
        "profile_component_coverage": {
            name: {"supported_tracks": count, "catalogue_fraction": round(count / len(catalogue), 6),
                   "enabled_in_controlled_profile": name == "target"}
            for name, count in profile_component_coverage.items()
        },
        "results_repeat_identically": repeat_ids_match,
        "engine": _result_metrics(first, features),
        "raw_popularity_baseline": _result_metrics(baseline_scored, features),
        "baseline_definition": "Top eligible rows by source track.interest descending; track_id ascending breaks ties. Raw interest is not calibrated quality or relevance.",
        "top_results": [{"track_id": row["track_id"], "track_name": row["track_name"],
                         "artist_name": row["artist_name"], "target_score": round(row["target_score"], 6),
                         "final_reranking_score": round(row["final_reranking_score"], 6)} for row in first],
        "interpretation": "Descriptive behavior and runtime only. This comparison does not establish listener preference, emotional effect, or recommendation quality.",
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if repeat_ids_match and first else 1


if __name__ == "__main__":
    raise SystemExit(main())
