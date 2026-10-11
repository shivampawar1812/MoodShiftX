"""Run a reproducible, descriptive check on the local real FMA feature subset."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from moodshiftx.catalogue import load_catalogue
from moodshiftx.preferences import PreferenceProfile
from moodshiftx.ranking import rank_tracks


def main() -> int:
    catalogue = load_catalogue(ROOT / "data" / "fma_metadata")
    profile = PreferenceProfile(
        desired_experience="calm", weights={"target": 1, "preference": 0, "discovery": 0},
        recommendation_count=5, variety=0,
    )
    features = profile.target_features or {}
    supported = [row for row in catalogue if all(row.get(name) is not None for name in features)]
    first = rank_tracks(supported, profile)
    second = rank_tracks(supported, profile)
    report = {
        "catalogue_displayable_tracks": len(catalogue),
        "tracks_with_all_goal_target_features": len(supported),
        "results_repeat_identically": [r["track_id"] for r in first] == [r["track_id"] for r in second],
        "goal": profile.desired_experience,
        "target_feature_values": dict(profile.target_features or {}),
        "top_results": [{"track_id": row["track_id"], "track_name": row["track_name"],
                         "artist_name": row["artist_name"], "target_score": row["target_score"],
                         "target_distance": row["target_distance"]} for row in first],
        "quality_claim": "Descriptive implementation check only; no listener relevance ground truth was available.",
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["results_repeat_identically"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
