# FMA dataset inspection results

**Measured locally:** 2026-10-11  
**Reproduction command:** `python scripts/inspect_dataset.py --output docs/dataset_inspection.json`  
**Machine-readable output:** `docs/dataset_inspection.json` (includes every original header and per-column low-level feature statistics). The script reads CSV rows incrementally; it does not load audio or the low-level feature matrix into memory.

The canonical loader caches parsed records in-process using source-file size and modification-time fingerprints, and returns copies to callers so changing returned objects does not mutate cached records.

## Files and schema

The supplied `data/fma_metadata/` directory currently contains `tracks.csv` (261,249,887 bytes), `genres.csv` (4,086 bytes), `features.csv` (951,223,763 bytes), and `echonest.csv` (44,013,580 bytes). The extracted `checksums` and `README.txt` are also present. These current file sizes differ slightly from the original Phase 1 inspection; the machine-readable report was regenerated from the current local files. The archive ZIP itself was not supplied; extracted files were accessible.

| File | Actual structure | Key columns / data |
|---|---|---|
| `tracks.csv` | 3 header/index rows; 53 columns | Index `track_id`; multi-level columns `album.*`, `artist.*`, `set.*`, `track.*`. Display fields: `track.title`, `artist.id`, `artist.name`; genres: `track.genre_top`, `track.genres`, `track.genres_all`; `track.interest` is source-defined interest; `track.license` contains per-track license text. |
| `genres.csv` | 1 header row; 5 columns | `genre_id`, `#tracks`, `parent`, `title`, `top_level`. `genre_id` joins to IDs embedded in track genre lists. |
| `features.csv` | 3 column-header levels plus index-name row; 519 columns incl. ID | Index `track_id`; 518 scalar low-level summaries across `chroma_cens`, `chroma_cqt`, `chroma_stft`, `mfcc`, `rmse`, `spectral_bandwidth`, `spectral_centroid`, `spectral_contrast`, `spectral_rolloff`, `tonnetz`, and `zcr`. Header fields encode statistic and component (for example `mfcc.mean.01`). |
| `echonest.csv` | 3 column-header levels plus index-name row; 250 columns | Index `track_id`; groups `audio_features`, `metadata`, `ranks`, `social_features`, `temporal_features`. Audio features include acousticness, danceability, energy, instrumentalness, liveness, speechiness, tempo, valence. |

CSV parsing reads raw values as strings; numeric columns are parsed and validated by the loader. IDs remain strings to preserve source identifiers. Exact expanded 53/5/519/250 column names are recorded in the JSON report. The loader joins genre ID `track.genres` to `genres.csv.genre_id` and high-level features to tracks with exact `track_id`; no title/artist fuzzy matching is used.

## Measured catalogue quality

| Measure | Locally measured result |
|---|---:|
| Source track rows | 106,574 |
| Distinct / missing track IDs | 106,574 / 0 |
| Distinct artist IDs | 16,341 |
| Genre table rows | 163 |
| Distinct track genre IDs | 161 |
| Track genre IDs not in lookup | 0 |
| Exact duplicate track rows (extra copies) | 0 |
| Duplicate track IDs (extra rows) | 0 |
| Tracks with usable non-empty ID, title, and artist | 106,573 |
| Rows after deterministic cleaning | 106,573 |

Missingness in important track fields:

| Field | Missing | Percent |
|---|---:|---:|
| `track.title` | 1 | 0.0009% |
| `artist.id` | 0 | 0% |
| `artist.name` | 0 | 0% |
| `track.genre_top` | 56,976 | 53.4614% |
| `track.genres` empty list (`[]`) or blank | 2,231 | 2.094% |

Deduplication is first source row per non-empty `track_id`; omit missing ID, title, or artist. It is deterministic and has no effect on duplicate records here. Genre IDs in the observed track list all resolve, including IDs not necessarily present in the top-level `track.genre_top` field.

## Audio feature measurements

Source scale descriptions: Echo Nest high-level features are conventionally bounded 0–1 except tempo in BPM; the supplied measurements were checked directly. Values below are local observed min–max, not theoretical boundaries. All six have 13,129 non-missing, valid values and 13,129 tracks joined by ID, equivalent to 12.32% of source tracks. There are zero missing/invalid values among the 13,129 Echo Nest rows for these six fields. One joined track has no title and is removed by the display-quality policy, so each single-feature strategy and the complete six-feature strategy can score 13,128 recommendation records. A metadata genre-preference baseline has 104,342 tracks with usable IDs, titles, artists, and at least one mapped genre.

| Feature | Exact column | Observed range / unit | Invalid | Strategy suitability |
|---|---|---:|---:|---|
| Energy | `echonest.audio_features.energy` | 0.0000201659–0.9999637108, 0–1 | 0 | 13,128 clean tracks; mood-goal feature |
| Valence | `echonest.audio_features.valence` | 0.000010–0.999990, 0–1 | 0 | 13,128 clean tracks; musical positivity proxy, not user mood |
| Danceability | `echonest.audio_features.danceability` | 0.051307487–0.9686446617, 0–1 | 0 | 13,128 clean tracks; mood-goal feature |
| Acousticness | `echonest.audio_features.acousticness` | 0.0000009035–0.9957964501, 0–1 | 0 | 13,128 clean tracks; mood-goal feature |
| Tempo | `echonest.audio_features.tempo` | 12.753–251.072 BPM | 0 | 13,128 clean tracks; use after choosing normalization/target range |
| Instrumentalness | `echonest.audio_features.instrumentalness` | 0–0.9980162209, 0–1 | 0 | 13,128 clean tracks; mood-goal feature |

`features.csv` has 518 numeric columns, 106,574 values per column, no missing or non-numeric entries. Across each aggregate feature group, observed minima/maxima are:

| Low-level group | Aggregate minimum | Aggregate maximum |
|---|---:|---:|
| chroma_cens | -26.4571 | 8,843.3672 |
| chroma_cqt | -146.4497 | 22,525.9023 |
| chroma_stft | -55.2244 | 5,790.3164 |
| mfcc | -1,131.3708 | 2,829.8850 |
| rmse | -23.2565 | 8,358.9219 |
| spectral_bandwidth | -22.5458 | 5,495.5845 |
| spectral_centroid | -13.8576 | 10,895.6416 |
| spectral_contrast | -15.2686 | 388.3651 |
| spectral_rolloff | -48.1130 | 12,581.2305 |
| tonnetz | -14.8874 | 284.2456 |
| zcr | -15.7280 | 8,438.0146 |

These low-level statistics span heterogeneous features/components and are not normalized mood measures. No canonical mood feature is derived from them. Exact per-column ranges are in `dataset_inspection.json`.

## Interpretation and decision

FMA metadata supports genre/artist discovery over 106,573 displayable tracks, or genre-filtered ranking across 104,342 records with a valid mapped genre. Verified high-level audio features support goal-target matching over 13,129 source IDs and 13,128 clean recommendation records. The full catalogue must not be described as supporting audio-mood matching. A genre/metadata baseline is feasible, but it cannot claim energy/valence movement. No compatible alternative dataset was established, so none is merged.

FMA authors state metadata is CC BY 4.0 and audio is licensed individually by its artists. The local archive README confirms per-artist audio licensing. The Echo Nest feature provenance is documented in the FMA project, but its independent current redistribution grant was not confirmed; review before public/commercial deployment or redistribution. Retain attribution. `track.license` values can inform later track-level policy, but do not grant rights to the underlying audio automatically.

**Phase 2 readiness:** ready for a scoped prototype using only the 13,128 clean recommendation records with verified feature values, assuming Phase 2's algorithm requires the verified feature set. Full-catalogue goal scoring and public feature-data redistribution remain out of scope pending broader feature data and terms review.
