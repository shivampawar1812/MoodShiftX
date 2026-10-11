# Phase 4 audit and release readiness

**Audit date:** 2026-10-11<br>
**Starting commit:** `aa5d491` (`Initial commit: MoodShiftX music recommendation system`)<br>
**Scope:** local integration tests, defect fixes, real-catalogue evaluation, operating and deployment documentation. This phase does not deploy or publish the app.

## Inspection findings

The repository contains the Streamlit entry point, reusable package under `src/moodshiftx/`, tests, inspection/evaluation scripts, documentation, dependency files, and `.streamlit/config.toml`. Local FMA data exists under the ignored `data/fma_metadata/` directory and is not tracked by Git. The Streamlit configuration contains only theme settings; no app secrets are required. The public repository contains no raw catalogue CSVs. The ignore rules cover local datasets, virtual environments, test caches, and common build artifacts.

Before changes, the unittest suite passed 30 tests in 85.411 seconds. Pytest was not installed initially; pytest 9.1.1 was subsequently added as local tooling. A pre-fix pytest run also passed all 30 existing tests. The baseline did not cover safe handling of catalogue text, missing-data messaging, feature-weight sensitivity, or weighted-contribution arithmetic.

## Defects fixed

1. **Local path disclosure:** missing/invalid catalogue screens no longer print exception details or absolute paths. The recovery message names the configured relative data location; details remain in local logs.
2. **Untrusted metadata in Markdown:** titles, artists, genres, IDs, and explanation text are escaped before Markdown rendering. URL validation rejects non-HTTP(S), credentials, malformed ports, whitespace, and control characters.
3. **Repeated catalogue scans:** genre and feature options and target-complete candidate subsets use process resource caches. Candidate records remain immutable.
4. **Expensive discarded explanations:** the ranking path used by recommendations avoids building explanations for all candidates and only constructs evidence for selected results. Diversity reranking precomputes normalized feature/genre/artist signatures.
5. **Regression gaps:** tests now cover missing-catalogue recovery without path leaks, Markdown escaping, malformed URLs, target-feature weighting, score contribution arithmetic, and an empty strict-genre result.
6. **Stale/incomplete operating evidence:** pinned application/test dependencies, README setup and deployment readiness, architecture notes, dataset file sizes, evaluation methodology, and a Phase 4 test report are being maintained with current measured results.
7. **Environment-specific inspection path:** the generated public inspection report now stores a project-relative path for in-repository data and a generic label for external locations instead of a machine-specific absolute path.

## Real catalogue measurement

Using `python scripts/evaluate_engine.py` with Python 3.14.5, Streamlit 1.65.0, and local FMA files:

- 106,573 displayable catalogue tracks; 13,128 (12.3183%) had all five default calm-goal features; 93,445 lacked at least one. Genre discovery metadata was available on 104,340 records (97.9047%).
- Catalogue load: 13.016 seconds; recommendation generation across 13,128 candidates: 4.177 seconds.
- Process RSS: 199.7 MB after load; 212.2 MB after recommendation generation.
- The two repeated runs returned identical IDs without duplicates. Top 10 results had 10 distinct artists and genres and mean target score 0.831132. The controlled profile enabled target scoring only; preference and discovery were disabled.
- A raw `track.interest` descending baseline on the same eligible set had 9 distinct artists, 7 genres, and mean target score 0.434351. This is only an implementation comparison; the field is not calibrated, and no user-quality conclusion follows.

These are measurements from one local machine and current local files, not hosted capacity guarantees. The script and `docs/evaluation.md` document the method and limitations.

## Deployment readiness and remaining blockers

- A clean GitHub checkout does not contain the local dataset. Without an authorized runtime data provisioning method, a hosted instance can only show the missing-catalogue recovery state.
- FMA/Echo Nest attribution is documented, but an independent current redistribution grant for Echo Nest/Spotify features has not been confirmed. Review the applicable terms before making the feature-bearing catalogue available through a public service.
- Local `tracks.csv` is 261,249,887 bytes and `features.csv` is 951,223,763 bytes. The app does not read `features.csv`, but it reads large track and Echo Nest files at startup. Local RSS/time measurements must not be treated as cloud sizing guarantees.
- Community Cloud deployment was not performed. The README documents current setup references and the data/license blockers without claiming a live deployment.
- The app supports `MOODSHIFTX_DATA_DIR` for a local directory override, but it does not download or provision hosted data.

## Verification status

Clean dependency installation succeeded in `.venv`; the full suite passed **33 tests in 57.82 seconds**. Streamlit AppTest covers real-catalogue submission and session actions plus missing-catalogue handling. The app started locally, and both its root and health endpoint returned HTTP 200. Exact commands and results are recorded in `phase4_test_report.md`. Deployment blockers above remain explicit.
