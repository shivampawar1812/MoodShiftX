"""Streamlit integration checks; skipped when the UI dependency is not installed."""
from __future__ import annotations

import unittest
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

try:
    import streamlit  # noqa: F401
    from streamlit.testing.v1 import AppTest
    import app as moodshift_app
except ImportError:
    AppTest = None
    moodshift_app = None


@unittest.skipIf(AppTest is None, "Install requirements.txt to run Streamlit UI tests")
class StreamlitAppTests(unittest.TestCase):
    def test_profile_validation_and_supported_targets(self):
        profile = moodshift_app.build_profile({
            "goal": "calm", "target_features": ["energy", "tempo"],
            "target_overrides": {"energy": .4}, "weights": {"target": .6, "preference": .25, "discovery": .15},
        }, {"energy"})
        self.assertEqual(dict(profile.target_features), {"energy": .4})
        unsupported = moodshift_app.build_profile({"goal": "calm", "target_features": ["unknown"]}, {"energy"})
        self.assertEqual(dict(unsupported.target_features), {})

    def test_app_submission_feedback_and_reset_with_real_catalogue(self):
        path = Path(__file__).resolve().parents[1] / "app.py"
        app_test = AppTest.from_file(str(path), default_timeout=180).run()
        self.assertFalse(app_test.exception)
        self.assertTrue(any("MoodShift X" in title.value for title in app_test.title))

        submit = next(button for button in app_test.button if button.label == "Find my tracks")
        submit.click().run(timeout=180)
        self.assertFalse(app_test.exception)
        self.assertTrue(any("Your recommendations" in item.value for item in app_test.markdown))
        results = app_test.session_state["results"]
        self.assertTrue(results)
        self.assertTrue(all(row["target_score"] is not None for row in results))
        self.assertTrue(all(row["overall_score"] == row["original_ranking_score"] for row in results))
        self.assertTrue(all(row["final_reranking_score"] is not None for row in results))
        self.assertTrue(all(row.get("track_url") is None and row.get("image_url") is None for row in results))
        self.assertTrue(all(row["explanation"]["evidence"] for row in results))

        like_button = next(button for button in app_test.button if button.label == "Like")
        track_id = like_button.key.removeprefix("feedback-like-")
        like_button.click().run(timeout=180)
        self.assertIn(track_id, app_test.session_state["feedback"].liked_track_ids)

        skip_button = next(button for button in app_test.button if button.label == "Skip")
        skipped_id = skip_button.key.removeprefix("feedback-skip-")
        skip_button.click().run(timeout=180)
        self.assertIn(skipped_id, app_test.session_state["feedback"].skipped_track_ids)

        more_button = next(button for button in app_test.button if button.label == "More like this")
        more_id = more_button.key.removeprefix("feedback-more-")
        more_button.click().run(timeout=180)
        self.assertIn(more_id, app_test.session_state["feedback"].more_like_track_ids)

        variety = next(widget for widget in app_test.checkbox if widget.label == "More variety")
        variety.check().run(timeout=180)
        self.assertTrue(app_test.session_state["feedback"].more_variety)

        reset = next(button for button in app_test.button if button.label == "Reset session")
        reset.click().run(timeout=30)
        self.assertEqual(app_test.session_state["feedback"].liked_track_ids, frozenset())
        self.assertIsNone(app_test.session_state["profile"])

    def test_only_valid_external_urls_are_accepted(self):
        self.assertIsNone(moodshift_app._valid_url(None))
        self.assertIsNone(moodshift_app._valid_url("javascript:alert(1)"))
        self.assertIsNone(moodshift_app._valid_url("https://user:password@example.com/track"))
        self.assertIsNone(moodshift_app._valid_url("https://example.com:bad/track"))
        self.assertIsNone(moodshift_app._valid_url("https://example.com/track with spaces"))
        self.assertEqual(moodshift_app._valid_url("https://example.com/track"), "https://example.com/track")

    def test_catalogue_text_is_escaped_before_markdown_rendering(self):
        escaped = moodshift_app._plain_markdown("[track](https://example.invalid) <img>\nname")
        self.assertEqual(escaped, r"\[track\]\(https://example\.invalid\) \<img\> name")

    def test_missing_catalogue_error_is_actionable_without_leaking_path(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        with TemporaryDirectory() as missing_dir, patch.dict(os.environ, {"MOODSHIFTX_DATA_DIR": missing_dir}):
            app_test = AppTest.from_file(str(app_path), default_timeout=30).run()
        self.assertFalse(app_test.exception)
        rendered = [element.value for element in app_test.error]
        rendered += [element.value for element in app_test.markdown]
        rendered += [element.value for element in app_test.caption]
        self.assertTrue(any("could not be loaded" in value for value in rendered), repr(rendered))
        self.assertTrue(any("tracks.csv and genres.csv are required" in value for value in rendered))
        self.assertFalse(any(missing_dir in value for value in rendered))


if __name__ == "__main__":
    unittest.main()
