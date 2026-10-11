# MoodShift X implementation plan

## Project state (updated 2026-10-11)

Phases 0 through 4 are implemented for the local prototype. Phase 4's audit, fixes, expanded tests, real-catalogue measurements, and operating guidance are recorded in `phase4_audit.md`, `phase4_test_report.md`, and `evaluation.md`. The local data directory is excluded from Git. No cloud deployment has been performed.

## Intended architecture

- `src/moodshiftx/`: reusable catalogue loading/validation and deterministic recommendation logic, independent of Streamlit.
- `app.py`: Streamlit inputs, recommendations, explanations, and session feedback.
- `data/`: locally acquired catalogue, excluded from version control unless its terms permit redistribution.
- `tests/`: unit and integration tests for data handling, ranking, explanations, and feedback.
- `docs/`: dataset provenance, implementation decisions, and operating instructions.

The recommendation core is callable without Streamlit and currently uses the Python standard library. Catalogue schema mappings and unavailable metadata are explicit; missing measurements stay missing. Pandas/NumPy can be introduced where useful in later application work, rather than as an unnecessary Phase 2 requirement.

## Phases

0. Inspect workspace and record state (complete).
1. Discover and document a dataset; inspect its actual schema and quality; implement reusable validation and reproduce catalogue statistics (complete for local FMA files; high-level mood features cover 13,129 joined IDs, 13,128 of which have usable display metadata).
2. Implement and test the deterministic recommendation engine independently (complete; mood-target scoring limited to the verified feature-bearing subset).
3. Build the Streamlit interface and present structured engine explanations (complete; verified with Streamlit 1.65.0).
4. Connect existing pure-Python feedback state to Streamlit session state (complete; verified using Streamlit AppTest).
5. Run UI-level functional tests, fix defects, benchmark actual catalogue behavior, and document installation, architecture, limitations, and deployment readiness (complete for the local prototype; public deployment remains blocked on data provisioning and license review).

## Dependencies and assumptions

The product stack is Python 3.10+ and Streamlit 1.65.0, pinned in `requirements.txt`; `requirements-dev.txt` adds pytest 9.1.1. The catalogue loader and recommendation engine use the Python standard library. The local dataset is acquired separately and is not committed. The evaluation script uses `psutil` only when it is available to report process RSS; it is not an application dependency.

FMA is selected. The local metadata has artist/genre information and the Echo Nest table supplies all six desired high-level features for 13,129 tracks joined by track ID; one lacks a display title, leaving 13,128 scoreable recommendations. The feature terms should be reviewed before redistribution/public deployment. The full 106,573-row cleaned display catalogue does not have mood features, so it cannot receive full-catalogue audio-goal scores.

## Current blockers

The archive ZIP is not present, but extracted local CSVs are available. A clean checkout has no `data/fma_metadata/`, so a hosted app needs an authorized runtime data provisioning method before recommendations can work. Echo Nest/Spotify terms have not been independently confirmed for redistribution; review them before publishing or serving derived feature data. Full-catalogue audio-goal scoring remains unsupported by this dataset.

## Milestone acceptance criteria

- Phase 0: workspace inventory and architecture are recorded without overwriting existing work. **Met.**
- Phase 1: source, creator, terms, and exact acquisition steps are documented; actual schema is mapped; canonical fields and quality checks are implemented; statistics are reproducible; unavailable data remains explicitly pending. **Met for the supplied extracted files.** Measured results are in `dataset_inspection.md` and `dataset_inspection.json`; feature-based scoring coverage is 13,128 clean recommendations.
- Phase 2: target, preference, discovery, and diversity scoring use verified inputs; feedback is bounded and idempotent; unsupported components remain explicit; explanations carry calculation evidence; ties are deterministic; automated tests and real-catalogue integration are recorded. **Met:** see `phase4_test_report.md` and `evaluation.md` for current results.
- Phase 3: **complete for the local prototype.** Streamlit 1.65.0 is pinned in `requirements.txt`; startup and health endpoint are checked in the Phase 4 test report. Streamlit AppTest exercises catalogue-backed submission, results and evidence, like/skip/more-like feedback, more-variety reranking, reset, safe metadata rendering, and a missing catalogue. See `README.md` for local setup and limitations.
- Phase 4: **complete for local QA and readiness documentation.** The app caches catalogue option/candidate subsets, escapes source metadata, handles missing data without exposing absolute paths, and validates links. Engine ranking avoids generating full explanation payloads for discarded candidates; diversity similarity uses precomputed signatures. Full regression results, reproducible local benchmark, and outstanding deployment blockers are reported in `phase4_test_report.md`, `evaluation.md`, and `phase4_audit.md`.
- Phase 2 onward: each subsystem is implemented and verified before being connected to the next layer; no fabricated catalogue records, feature values, listening links, or artwork are introduced.
