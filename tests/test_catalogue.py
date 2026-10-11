import csv
import tempfile
import unittest
from pathlib import Path

from src.moodshiftx.catalogue import CatalogueError, inspect_catalogue, load_catalogue


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerows(rows)


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_csv(self.root / "genres.csv", [
            ["genre_id", "#tracks", "parent", "title", "top_level"],
            ["1", "2", "0", "Rock", "1"],
        ])
        self.track_header = [
            ["", "artist", "artist", "track", "track", "track", "track"],
            ["", "id", "name", "genre_top", "genres", "interest", "title"],
            ["track_id", "", "", "", "", "", ""],
        ]
        write_csv(self.root / "tracks.csv", self.track_header + [
            ["10", "7", "Artist", "Rock", "[1]", "22", "Song"],
            ["10", "7", "Artist", "Rock", "[1]", "22", "Song duplicate"],
            ["11", "8", "Other", "Rock", "[1]", "", "No feature"],
            ["12", "9", "", "Rock", "[1]", "", "No artist"],
        ])
        self.echo_header = [
            ["", "echonest", "echonest", "echonest", "echonest", "echonest", "echonest", "echonest"],
            ["", "audio_features", "audio_features", "audio_features", "audio_features", "audio_features", "audio_features", "audio_features"],
            ["", "acousticness", "danceability", "energy", "instrumentalness", "tempo", "valence", "extra"],
            ["track_id", "", "", "", "", "", "", ""],
        ]
        write_csv(self.root / "echonest.csv", self.echo_header + [
            ["10", ".5", ".6", ".7", ".8", "120", ".9", ""],
            ["11", "bad", ".6", "1.4", ".8", "0", ".9", ""],
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_multilevel_headers_genre_features_and_duplicates(self):
        catalogue = load_catalogue(self.root)
        self.assertEqual([x["track_id"] for x in catalogue], ["10", "11"])
        self.assertTrue({"track_id", "track_name", "artist_id", "artist_name", "genre", "energy",
                         "valence", "danceability", "acousticness", "tempo", "instrumentalness",
                         "track_url", "image_url", "popularity"}.issubset(catalogue[0]))
        self.assertEqual(catalogue[0]["genre"], "Rock")
        self.assertEqual(catalogue[0]["energy"], .7)
        self.assertEqual(catalogue[1]["energy"], None)
        self.assertEqual(catalogue[1]["acousticness"], None)
        self.assertIsNone(catalogue[0]["track_url"])

    def test_inspection_is_reproducible_and_counts_duplicates(self):
        one = inspect_catalogue(self.root)
        two = inspect_catalogue(self.root)
        self.assertEqual(one, two)
        self.assertEqual(one["track_rows"], 4)
        self.assertEqual(one["duplicate_track_id_extra_rows"], 1)
        self.assertEqual(one["clean_records"], 2)
        self.assertEqual(one["feature_stats"]["energy"]["invalid"], 1)

    def test_missing_optional_echonest_is_supported(self):
        (self.root / "echonest.csv").unlink()
        catalogue = load_catalogue(self.root)
        self.assertIsNone(catalogue[0]["energy"])

    def test_missing_required_file_has_clear_error(self):
        (self.root / "tracks.csv").unlink()
        with self.assertRaisesRegex(CatalogueError, "tracks.csv"):
            load_catalogue(self.root)

    def test_empty_catalogue_is_rejected(self):
        write_csv(self.root / "tracks.csv", self.track_header)
        with self.assertRaisesRegex(CatalogueError, "No usable tracks"):
            load_catalogue(self.root)

    def test_invalid_required_schema_is_rejected(self):
        write_csv(self.root / "tracks.csv", [["", "wrong"], ["", "column"], ["track_id", ""], ["10", "Song"]])
        with self.assertRaisesRegex(CatalogueError, "Invalid tracks.csv schema"):
            load_catalogue(self.root)


if __name__ == "__main__":
    unittest.main()
