import math
import unittest
from pathlib import Path

from src.moodshiftx.diversity import feature_similarity, rerank_for_diversity
from src.moodshiftx.explanations import explain_recommendation
from src.moodshiftx.feedback import FeedbackState, like, more_like_this, more_variety, reset_feedback, skip
from src.moodshiftx.preferences import PreferenceProfile, normalize_weights, targets_for_goal
from src.moodshiftx.ranking import rank_tracks, recommend_tracks, target_match
from src.moodshiftx.catalogue import load_catalogue


FIXTURE = [
    {"track_id": "a", "track_name": "Soft", "artist_id": "artist-a", "artist_name": "Artist A",
     "genre": "Ambient", "energy": 0.2, "valence": 0.4, "danceability": 0.2,
     "acousticness": 0.8, "tempo": 80.0, "instrumentalness": 0.8},
    {"track_id": "b", "track_name": "Bright", "artist_id": "artist-a", "artist_name": "Artist A",
     "genre": "Rock", "energy": 0.8, "valence": 0.8, "danceability": 0.8,
     "acousticness": 0.2, "tempo": 140.0, "instrumentalness": 0.1},
    {"track_id": "c", "track_name": "Bright 2", "artist_id": "artist-c", "artist_name": "Artist C",
     "genre": "Rock", "energy": 0.7, "valence": 0.75, "danceability": 0.7,
     "acousticness": 0.3, "tempo": 130.0, "instrumentalness": 0.2},
    {"track_id": "d", "track_name": "No audio", "artist_id": "artist-d", "artist_name": "Artist D",
     "genre": "Ambient", "energy": None, "valence": None, "danceability": None,
     "acousticness": None, "tempo": None, "instrumentalness": None},
]


class PreferenceTests(unittest.TestCase):
    def test_goal_targets_are_configurable_defaults(self):
        self.assertEqual(targets_for_goal("custom", {"custom": {"energy": .5}}), {"energy": .5})
        self.assertIn("energy", targets_for_goal("calm"))
        profile = PreferenceProfile(desired_experience="Custom",
                                   goal_target_mapping={"custom": {"energy": .25}})
        self.assertEqual(profile.target_features, {"energy": .25})

    def test_targets_and_profile_validation(self):
        with self.assertRaises(ValueError):
            PreferenceProfile(target_features={"fake_feature": .2})
        with self.assertRaises(ValueError):
            PreferenceProfile(target_features={"energy": float("nan")})
        with self.assertRaises(ValueError):
            PreferenceProfile(genre_filter="maybe")

    def test_weight_normalization_and_all_zero(self):
        self.assertEqual(normalize_weights({"target": 2, "preference": 1, "discovery": 1}),
                         {"target": .5, "preference": .25, "discovery": .25})
        self.assertEqual(normalize_weights({"target": 0, "preference": 0, "discovery": 0}),
                         {"target": 0, "preference": 0, "discovery": 0})


class RankingTests(unittest.TestCase):
    def test_target_match_formula_and_partial_feature_renormalization(self):
        profile = PreferenceProfile(target_features={"energy": .5}, weights={"target": 1})
        score, detail = target_match({"energy": .5}, profile)
        self.assertEqual(score, 1.0)
        self.assertEqual(detail["distance"], 0)
        off, _ = target_match({"energy": 0}, profile)
        self.assertAlmostEqual(off, math.exp(-1.5))
        unsupported, detail = target_match({"energy": None}, profile)
        self.assertIsNone(unsupported)
        self.assertEqual(detail["reason"], "no_valid_target_features_on_track")

    def test_tempo_normalization_is_bpm_aware(self):
        profile = PreferenceProfile(target_features={"tempo": 125}, weights={"target": 1})
        score, detail = target_match({"tempo": 250}, profile)
        self.assertAlmostEqual(detail["distance"], .5)
        self.assertAlmostEqual(score, math.exp(-1.5))

    def test_stable_ranking_and_strict_genre_filter(self):
        profile = PreferenceProfile(target_features={"energy": .7}, preferred_genres=("rock",),
                                    genre_filter="strict", weights={"target": .7, "preference": .3, "discovery": 0})
        first = rank_tracks(FIXTURE, profile)
        second = rank_tracks(FIXTURE, profile)
        self.assertEqual([x["track_id"] for x in first], [x["track_id"] for x in second])
        self.assertEqual({x["genre"] for x in first}, {"Rock"})
        self.assertTrue(all(math.isfinite(x["overall_score"]) for x in first))
        self.assertTrue(all(0 <= x["overall_score"] <= 1 for x in first))

    def test_missing_target_component_is_not_fabricated(self):
        profile = PreferenceProfile(target_features={"energy": .5}, weights={"target": 1})
        rows = rank_tracks([FIXTURE[-1]], profile)
        self.assertIsNone(rows[0]["target_score"])
        self.assertIn("target", rows[0]["unsupported_components"])
        self.assertNotIn("target", rows[0]["component_weights"])

    def test_all_zero_weights_falls_back_over_supported_components(self):
        profile = PreferenceProfile(target_features={"energy": .2}, preferred_genres=("Ambient",),
                                    weights={"target": 0, "preference": 0, "discovery": 0})
        rows = rank_tracks(FIXTURE, profile)
        self.assertTrue(all(abs(sum(row["component_weights"].values()) - 1) < 1e-12 for row in rows))

    def test_disabled_discovery_does_not_replace_missing_target_weight(self):
        profile = PreferenceProfile(target_features={"energy": .5},
                                    weights={"target": 1, "discovery": 0, "preference": 0})
        row = next(r for r in rank_tracks(FIXTURE, profile) if r["track_id"] == "d")
        self.assertEqual(row["overall_score"], 0)
        self.assertEqual(row["component_weights"], {})
        self.assertIn("discovery", row["zero_weight_supported_components"])

    def test_genre_filter_soft_vs_strict(self):
        soft = PreferenceProfile(target_features={}, preferred_genres=("Ambient",), genre_filter="soft")
        strict = PreferenceProfile(target_features={}, preferred_genres=("Ambient",), genre_filter="strict")
        self.assertEqual(len(rank_tracks(FIXTURE, soft)), 4)
        self.assertTrue(all(row["genre"] == "Ambient" for row in rank_tracks(FIXTURE, strict)))

    def test_genre_discovery_uses_catalogue_frequency(self):
        profile = PreferenceProfile(target_features={}, weights={"discovery": 1})
        catalogue = FIXTURE + [dict(FIXTURE[0], track_id="rare", genre="Jazz", artist_id="rare")]
        rows = {row["track_id"]: row for row in rank_tracks(catalogue, profile)}
        self.assertGreater(rows["rare"]["discovery_score"], rows["b"]["discovery_score"])
        self.assertIsNone(rows["a"]["preference_score"])

    def test_feedback_responsiveness_is_bounded_and_explainable(self):
        profile = PreferenceProfile(target_features={}, weights={"preference": 1})
        liked = {row["track_id"]: row for row in rank_tracks(FIXTURE, profile, like(FeedbackState(), "a"))}
        skipped = {row["track_id"]: row for row in rank_tracks(FIXTURE, profile, skip(FeedbackState(), "b"))}
        self.assertGreater(liked["c"]["preference_score"], skipped["c"]["preference_score"])
        self.assertLessEqual(abs(liked["c"]["preference_score"] - skipped["c"]["preference_score"]), .5)
        self.assertTrue(any(e["category"] == "feedback_similarity" for e in liked["c"]["explanation"]["evidence"]))
        anchor = {row["track_id"]: row for row in rank_tracks(FIXTURE, profile, more_like_this(FeedbackState(), "a"))}
        self.assertGreater(anchor["c"]["preference_score"], skipped["c"]["preference_score"])

    def test_feedback_without_comparable_metadata_is_unsupported(self):
        tracks = [{"track_id": "x"}, {"track_id": "y"}]
        profile = PreferenceProfile(target_features={}, weights={"preference": 1})
        row = next(r for r in rank_tracks(tracks, profile, like(FeedbackState(), "y")) if r["track_id"] == "x")
        self.assertIsNone(row["preference_score"])
        self.assertIn("preference", row["unsupported_components"])

    def test_more_variety_adjusts_component_weight_and_runs_diversity(self):
        profile = PreferenceProfile(target_features={}, preferred_genres=("Rock",),
                                    weights={"preference": .5, "discovery": .5}, variety=.2)
        normal = rank_tracks(FIXTURE, profile, limit=4)
        varied = rank_tracks(FIXTURE, profile, more_variety(FeedbackState()), limit=4)
        self.assertGreater(varied[0]["component_weights"].get("discovery", 0),
                           normal[0]["component_weights"].get("discovery", 0))
        self.assertTrue(all("final_reranking_score" in row for row in
                            recommend_tracks(FIXTURE, profile, more_variety(FeedbackState()))))
        variety_catalogue = [
            {"track_id": "a", "artist_name": "Artist A", "genre": "Rock", "energy": .8},
            {"track_id": "b", "artist_name": "Artist A", "genre": "Rock", "energy": .78},
            {"track_id": "j", "artist_name": "Artist J", "genre": "Jazz", "energy": .4},
            {"track_id": "m", "artist_name": "Artist M", "genre": "Ambient", "energy": .2},
        ]
        profile = PreferenceProfile(target_features={"energy": .8},
                                    weights={"target": .8, "discovery": .2},
                                    variety=0, recommendation_count=3)
        normal_order = [row["track_id"] for row in recommend_tracks(variety_catalogue, profile)]
        varied_order = [row["track_id"] for row in
                        recommend_tracks(variety_catalogue, profile, more_variety(FeedbackState()))]
        self.assertNotEqual(normal_order, varied_order)

    def test_duplicate_track_ids_and_deterministic_tie_break(self):
        tied = [{"track_id": "z", "energy": .5}, {"track_id": "a", "energy": .5},
                {"track_id": "a", "energy": 1.0}]
        profile = PreferenceProfile(target_features={"energy": .5}, weights={"target": 1})
        self.assertEqual([r["track_id"] for r in rank_tracks(tied, profile)], ["a", "z"])

    def test_explanation_values_are_actual_metadata(self):
        profile = PreferenceProfile(target_features={"energy": .8}, preferred_genres=("Rock",))
        result = next(row for row in rank_tracks(FIXTURE, profile) if row["track_id"] == "b")
        explanation = result["explanation"]
        evidence = explanation["evidence"]
        self.assertEqual(next(e["actual_value"] for e in evidence if e["field"] == "energy"), .8)
        self.assertTrue(any("Rock" in e["text"] for e in evidence))
        self.assertTrue(all(e["source_component"] in {"target", "preference", "discovery"} for e in evidence))


class FeedbackTests(unittest.TestCase):
    def test_like_skip_duplicate_more_like_variety_and_reset(self):
        state = like(FeedbackState(), "a")
        state = like(state, "a")
        self.assertEqual(state.liked_track_ids, {"a"})
        state = skip(state, "a")
        self.assertNotIn("a", state.liked_track_ids)
        self.assertEqual(state.skipped_track_ids, {"a"})
        state = more_like_this(state, "b")
        state = more_variety(state)
        self.assertEqual(state.more_like_track_ids, {"b"})
        self.assertTrue(state.more_variety)
        state = skip(state, "b")
        self.assertNotIn("b", state.more_like_track_ids)
        self.assertIn("b", state.skipped_track_ids)
        self.assertEqual(reset_feedback(), FeedbackState())
        with self.assertRaises(ValueError):
            like(state, " ")


class DiversityTests(unittest.TestCase):
    def test_artist_penalty_and_cap_diversify_without_changing_relevance(self):
        ranked = [dict(FIXTURE[0], overall_score=.95), dict(FIXTURE[1], overall_score=.9),
                  dict(FIXTURE[2], overall_score=.8)]
        rows = rerank_for_diversity(ranked, variety=.9, max_tracks_per_artist=1, count=3)
        self.assertEqual(len({r["track_id"] for r in rows}), 3)
        self.assertEqual(rows[0]["track_id"], "a")
        self.assertEqual(rows[1]["track_id"], "c")
        self.assertEqual(rows[0]["overall_score"], rows[0]["original_ranking_score"])
        self.assertIn("final_reranking_score", rows[0])

    def test_small_catalogue_duplicate_and_feature_similarity(self):
        rows = rerank_for_diversity([dict(FIXTURE[0], overall_score=.5),
                                     dict(FIXTURE[0], overall_score=.4)], count=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["track_id"], "a")
        self.assertAlmostEqual(feature_similarity(FIXTURE[0], FIXTURE[0]), 1.0)
        self.assertIsNone(feature_similarity({"energy": None}, {"energy": .4}))

    def test_ties_are_deterministic_and_output_bounded(self):
        ranked = [{"track_id": tid, "artist_name": tid, "genre": "G", "overall_score": .5}
                  for tid in ("b", "a", "c")]
        one = rerank_for_diversity(ranked, variety=.5)
        two = rerank_for_diversity(ranked, variety=.5)
        self.assertEqual([r["track_id"] for r in one], [r["track_id"] for r in two])
        self.assertTrue(all(0 <= row["final_reranking_score"] <= 1 for row in one))


class RealCatalogueIntegrationTests(unittest.TestCase):
    def test_real_feature_subset_when_local_catalogue_is_available(self):
        data = Path(__file__).resolve().parents[1] / "data" / "fma_metadata"
        if not (data / "tracks.csv").exists():
            self.skipTest("Local FMA catalogue is not available")
        catalogue = load_catalogue(data)
        supported = [row for row in catalogue if row.get("energy") is not None]
        self.assertEqual(len(catalogue), 106573)
        self.assertEqual(len(supported), 13128)
        profile = PreferenceProfile(target_features={"energy": .65}, weights={"target": 1}, recommendation_count=3)
        results = rank_tracks(supported, profile)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(row["target_score"] is not None for row in results))
        self.assertTrue(all(row["overall_score"] == row["target_score"] for row in results))


if __name__ == "__main__":
    unittest.main()

