# Evaluation and verification

## Reproduce the checks

Install application and test dependencies, then run:

```powershell
python -m pytest -q
python scripts/evaluate_engine.py
```

`evaluate_engine.py` loads the local FMA catalogue and reports load and recommendation time, process RSS when `psutil` is installed, selected-feature coverage, distinct artists and genres, feature spread, deterministic repeatability, and a raw-interest baseline. It compares the engine's calm-target results against the same eligible tracks ranked by the source `track.interest` field. Raw interest is count-like metadata and is not calibrated as relevance or quality.

## Local FMA run (2026-10-11)

Environment: Python 3.14.5, Streamlit 1.65.0, local extracted FMA metadata. Results from `python scripts/evaluate_engine.py`:

- Catalogue load: 106,573 displayable tracks; all five default calm target measurements were present on 13,128 tracks (12.3183% of the catalogue). The other 93,445 displayable tracks lacked at least one selected target measurement and were excluded from this comparison.
- Goal matching ranked the 13,128 eligible rows in 4.177 seconds, before UI rendering. Catalogue loading took 13.016 seconds. Process RSS was 199.7 MB after loading and 212.2 MB after recommendation generation. These are local measurements, not cloud capacity guarantees.
- The 10 returned IDs matched on a second run, with no duplicate IDs. The results contained 10 distinct artists and 10 distinct genres. Mean target score was 0.831132.
- In this controlled target-only profile, target scoring was enabled and supported for all 13,128 candidates. Preference scoring was disabled because no genre or feedback was selected. Discovery evidence was available for 104,340 catalogue records (97.9047%) but discovery scoring was also disabled in this profile.
- The top 10 raw-interest baseline contained 9 distinct artists and 7 distinct genres, with mean calm-target score 0.434351. The baseline is descriptive and uses a different ordering objective; this is not evidence of user preference or recommendation quality.
- The engine's per-feature population standard deviations were: energy 0.051763, valence 0.074345, danceability 0.046018, acousticness 0.064970, tempo 7.739387 BPM. Feature spread alone does not establish useful diversity.

The benchmark prints the exact target values, selected track IDs, and full machine-readable metrics. Results can shift if local data or the implementation changes. The ranking outputs are deterministic for a fixed catalogue, profile, and code version.

## Automated test coverage

The test suite covers profile validation, target formula and feature weights, score contribution arithmetic, supported/missing values, genre filtering, feedback transitions, stable ordering, evidence generation, diversity, catalogue parsing and errors, real-catalogue integration, Streamlit submission and session interactions, missing-data UI, URL validation, and safe rendering of catalogue text. See `docs/phase4_test_report.md` for the exact run commands and outcomes.

## Limits

There are no listener judgments, target-transition labels, or held-out relevance data. These tests and the local benchmark establish implementation behavior, not emotional effect, listener preference, or recommendation quality. Goal targets are configurable product defaults, not a psychological model. Genre rarity is relative to this catalogue. The popularity comparison uses raw `track.interest`, not a normalized or calibrated popularity score.

The repository excludes the local dataset. Echo Nest/Spotify feature redistribution terms have not been independently verified; resolve that question before exposing the feature-bearing catalogue through a public service. The app has not been deployed to Streamlit Community Cloud.
