"""Streaming FMA metadata inspection and canonical catalogue loading."""
from __future__ import annotations

import ast
import csv
import copy
import json
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any


class CatalogueError(ValueError):
    """Raised when source data is missing or structurally unusable."""


CANONICAL_FIELDS = (
    "track_id", "track_name", "artist_id", "artist_name", "genre",
    "energy", "valence", "danceability", "acousticness", "tempo",
    "instrumentalness", "track_url", "image_url", "popularity",
)
MOOD_FEATURES = ("energy", "valence", "danceability", "acousticness", "tempo", "instrumentalness")
RANGES = {"energy": (0.0, 1.0), "valence": (0.0, 1.0), "danceability": (0.0, 1.0),
          "acousticness": (0.0, 1.0), "instrumentalness": (0.0, 1.0), "tempo": (0.0, math.inf)}


def _columns(path: Path, header_rows: int) -> list[str]:
    if not path.is_file():
        raise CatalogueError(f"Required dataset file not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        headers = [next(reader, None) for _ in range(header_rows)]
    if any(row is None for row in headers):
        raise CatalogueError(f"{path} is missing its {header_rows}-row header")
    # FMA's exported multi-index CSVs contain a final `track_id` index-name
    # line after the three levels of column labels. It is not a data record.
    index_marker = header_rows >= 3 and headers[-1][0].strip() == "track_id"
    if index_marker:
        headers = headers[:-1]
    if header_rows == 1:
        cols = headers[0]
    else:
        cols = []
        for i, leaf in enumerate(headers[-1]):
            if i == 0 and index_marker:
                cols.append("track_id")
                continue
            prefix = [row[i].strip() for row in headers[:-1] if row[i].strip()]
            name = leaf.strip() or (prefix[-1] if prefix else f"column_{i}")
            cols.append(".".join(prefix + ([] if name in prefix else [name])))
    counts = Counter(cols)
    if any(n > 1 for n in counts.values()):
        used = Counter()
        cols = [f"{col}#{used.update([col]) or used[col]}" if counts[col] > 1 else col for col in cols]
    return cols


def _records(path: Path, header_rows: int):
    if not path.is_file():
        raise CatalogueError(f"Required dataset file not found: {path}")
    columns = _columns(path, header_rows)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        for _ in range(header_rows):
            next(reader)
        for line_number, row in enumerate(reader, header_rows + 1):
            if not row or (len(row) == 1 and not row[0]):
                continue
            if len(row) != len(columns):
                raise CatalogueError(f"{path}:{line_number} has {len(row)} cells; expected {len(columns)}")
            yield dict(zip(columns, row))


def _number(raw: Any) -> float | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        number = float(raw)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def _valid(feature: str, value: float) -> bool:
    low, high = RANGES[feature]
    return low <= value <= high and (feature != "tempo" or value > 0)


def _id_list(raw: str) -> list[int]:
    try:
        values = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return []
    if isinstance(values, (tuple, list)):
        return [int(v) for v in values if str(v).lstrip("-").isdigit()]
    return []


def inspect_catalogue(data_dir: str | Path) -> dict[str, Any]:
    """Return streaming, reproducible quality statistics for FMA CSVs."""
    root = Path(data_dir)
    tracks, genres = root / "tracks.csv", root / "genres.csv"
    echo, low = root / "echonest.csv", root / "features.csv"
    if not tracks.is_file() or not genres.is_file():
        raise CatalogueError(f"Expected tracks.csv and genres.csv under {root}")
    track_columns = _columns(tracks, 3)
    genre_columns = _columns(genres, 1)
    required_track = {"track_id", "artist.id", "artist.name", "track.title"}
    required_genre = {"genre_id", "title"}
    if not required_track.issubset(track_columns):
        raise CatalogueError(f"Invalid tracks.csv schema; missing {sorted(required_track - set(track_columns))}")
    if not required_genre.issubset(genre_columns):
        raise CatalogueError(f"Invalid genres.csv schema; missing {sorted(required_genre - set(genre_columns))}")
    genre_rows = list(_records(genres, 1))
    genre_map = {int(r["genre_id"]): r["title"] for r in genre_rows}
    track_count = 0
    ids, displayable_ids, artists, track_genres = set(), set(), set(), set()
    exact_rows, id_counts = Counter(), Counter()
    missing = Counter({field: 0 for field in ("track.title", "artist.id", "artist.name", "track.genre_top", "track.genres")})
    usable, usable_with_genre = 0, 0
    for row in _records(tracks, 3):
        track_count += 1
        tid = row.get("track_id", "").strip()
        artist_id = row.get("artist.id", "").strip()
        title = row.get("track.title", "").strip()
        artist = row.get("artist.name", "").strip()
        if tid:
            ids.add(tid)
            id_counts[tid] += 1
        if artist_id:
            artists.add(artist_id)
        exact_rows[tuple(row.values())] += 1
        for col in ("track.title", "artist.id", "artist.name", "track.genre_top", "track.genres"):
            if not row.get(col, "").strip() or (col == "track.genres" and not _id_list(row.get(col, ""))):
                missing[col] += 1
        genre_ids = _id_list(row.get("track.genres", ""))
        track_genres.update(genre_ids)
        usable += bool(tid and title and artist)
        if tid and title and artist:
            displayable_ids.add(tid)
        usable_with_genre += bool(tid and title and artist and any(gid in genre_map for gid in genre_ids))

    stats = {f: {"non_missing": 0, "missing": 0, "invalid": 0, "min": None, "max": None}
             for f in MOOD_FEATURES}
    feature_ids = {f: set() for f in MOOD_FEATURES}
    echo_rows, common_six, echo_ids, all_feature_ids = 0, 0, set(), set()
    echo_columns = _columns(echo, 4) if echo.is_file() else []
    source_cols = {f: f"echonest.audio_features.{f}" for f in MOOD_FEATURES}
    for feature, col in source_cols.items():
        if col not in echo_columns:
            stats[feature]["missing_column"] = True
    selected = [source_cols[f] for f in MOOD_FEATURES]
    for row in _records(echo, 4) if echo.is_file() else ():
        echo_id = row.get("track_id", "").strip()
        if echo_id:
            echo_rows += 1
            echo_ids.add(echo_id)
        complete = True
        for feature, col in source_cols.items():
            if col not in row:
                complete = False
                continue
            raw = row[col]
            value = _number(raw)
            item = stats[feature]
            if value is None:
                item["missing"] += 1
                item["invalid"] += bool(str(raw).strip())
                complete = False
                continue
            item["non_missing"] += 1
            low_bound, high_bound = RANGES[feature]
            if not _valid(feature, value):
                item["invalid"] += 1
                complete = False
            item["min"] = value if item["min"] is None else min(item["min"], value)
            item["max"] = value if item["max"] is None else max(item["max"], value)
            if _valid(feature, value) and echo_id:
                feature_ids[feature].add(echo_id)
        common_six += complete
        if complete and echo_id:
            all_feature_ids.add(echo_id)
    duplicates = sum(n - 1 for n in exact_rows.values() if n > 1)
    duplicate_ids = sum(n - 1 for key, n in id_counts.items() if key and n > 1)
    scoreable = {f: len(displayable_ids & feature_ids[f]) for f in MOOD_FEATURES}
    scoreable["all_six_features"] = len(displayable_ids & all_feature_ids)
    scoreable["metadata_genre_baseline"] = usable_with_genre
    missing_percent = {field: round(100 * count / track_count, 4) if track_count else 0
                       for field, count in missing.items()}
    for feature in MOOD_FEATURES:
        stats[feature]["catalogue_coverage_percent"] = round(100 * scoreable[feature] / track_count, 4) if track_count else 0
    low_level_stats = {}
    if low.is_file():
        low_columns = _columns(low, 4)
        low_level_stats = {name: {"non_missing": 0, "missing": 0, "invalid": 0, "min": None, "max": None}
                           for name in low_columns[1:]}
        for row in _records(low, 4):
            for name, item in low_level_stats.items():
                value = _number(row.get(name))
                if value is None:
                    item["missing"] += 1
                    item["invalid"] += bool(str(row.get(name, "")).strip())
                else:
                    item["non_missing"] += 1
                    item["min"] = value if item["min"] is None else min(item["min"], value)
                    item["max"] = value if item["max"] is None else max(item["max"], value)
    return {
        "data_dir": str(root), "track_header_columns": track_columns,
        "genre_header_columns": genre_columns, "echonest_header_columns": echo_columns,
        "features_header_columns": _columns(low, 4) if low.is_file() else [],
        "track_rows": track_count, "distinct_track_ids": len(ids), "distinct_artist_ids": len(artists),
        "genre_records": len(genre_rows), "distinct_track_genre_ids": len(track_genres),
        "unmapped_track_genre_ids": sorted(track_genres - genre_map.keys()),
        "missing_counts": dict(missing), "exact_duplicate_rows_extra": duplicates,
        "missing_percent": missing_percent,
        "duplicate_track_id_extra_rows": duplicate_ids,
        "deduplication_policy": "Keep first source row per non-empty track_id; omit missing ID, title, or artist.",
        "clean_records": max(0, usable - duplicate_ids), "echonest_rows_with_id": echo_rows,
        "echonest_tracks_joined_to_catalogue": len(ids & echo_ids),
        "echonest_tracks_joined_to_clean_catalogue": len(displayable_ids & echo_ids),
        "feature_stats": stats, "scoreable_records": scoreable,
        "low_level_feature_stats": low_level_stats,
        "source_files_bytes": {p.name: p.stat().st_size for p in (tracks, genres, low, echo) if p.is_file()},
    }


def load_catalogue(data_dir: str | Path) -> list[dict[str, Any]]:
    """Load a catalogue, reusing parsed data until any source file changes."""
    root = Path(data_dir).resolve()
    files = [root / name for name in ("tracks.csv", "genres.csv", "echonest.csv")]
    fingerprint = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) if path.exists()
                        else (str(path), -1, -1) for path in files)
    return copy.deepcopy(list(_load_catalogue_cached(str(root), fingerprint)))


@lru_cache(maxsize=2)
def _load_catalogue_cached(data_dir: str, fingerprint: tuple[tuple[str, int, int], ...]) -> tuple[dict[str, Any], ...]:
    """Load canonical track metadata and validated Echonest measurements."""
    root = Path(data_dir)
    track_columns = _columns(root / "tracks.csv", 3)
    genre_columns = _columns(root / "genres.csv", 1)
    required_track = {"track_id", "artist.id", "artist.name", "track.title"}
    if not required_track.issubset(track_columns):
        raise CatalogueError(f"Invalid tracks.csv schema; missing {sorted(required_track - set(track_columns))}")
    if not {"genre_id", "title"}.issubset(genre_columns):
        raise CatalogueError("Invalid genres.csv schema; expected genre_id and title columns")
    genre_map = {int(r["genre_id"]): r["title"] for r in _records(root / "genres.csv", 1)}
    feature_by_id = {}
    echo = root / "echonest.csv"
    if echo.exists():
        for row in _records(echo, 4):
            tid = row.get("track_id", "").strip()
            if not tid or tid in feature_by_id:
                continue
            values = {}
            for feature in MOOD_FEATURES:
                value = _number(row.get(f"echonest.audio_features.{feature}"))
                lo, hi = RANGES[feature]
                values[feature] = value if value is not None and _valid(feature, value) else None
            feature_by_id[tid] = values
    output, seen = [], set()
    for row in _records(root / "tracks.csv", 3):
        tid = row.get("track_id", "").strip()
        title, artist = row.get("track.title", "").strip(), row.get("artist.name", "").strip()
        if not tid or tid in seen or not title or not artist:
            continue
        seen.add(tid)
        ids = _id_list(row.get("track.genres", ""))
        genre = genre_map.get(ids[0]) if ids else row.get("track.genre_top", "").strip() or None
        item = {key: None for key in (
            "track_id", "track_name", "artist_id", "artist_name", "genre", *MOOD_FEATURES,
            "track_url", "image_url", "popularity", "license", "duration_seconds",
            "source_genre_ids", "source_track_tags")}
        item.update(track_id=tid, track_name=title, artist_id=row.get("artist.id", "").strip() or None,
                    artist_name=artist, genre=genre, popularity=_number(row.get("track.interest")),
                    license=row.get("track.license", "").strip() or None,
                    duration_seconds=_number(row.get("track.duration")), source_genre_ids=ids,
                    source_track_tags=row.get("track.tags", "").strip() or None)
        item.update(feature_by_id.get(tid, {}))
        output.append(item)
    if not output:
        raise CatalogueError(f"No usable tracks found in {root / 'tracks.csv'}")
    return tuple(output)


def write_report(data_dir: str | Path, output_path: str | Path) -> dict[str, Any]:
    report = inspect_catalogue(data_dir)
    Path(output_path).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
