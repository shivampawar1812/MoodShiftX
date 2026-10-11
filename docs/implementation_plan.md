# MoodShift X implementation plan

## Existing workspace state (updated 2026-10-11)

The workspace was empty at inspection: no application code, data, documentation, tests, or configuration files were present. There were no `AGENTS.md` instructions. No existing work was replaced.

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
5. Run UI-level functional tests, fix defects, and document installation, architecture, limitations, and deployment (complete for the local prototype).

## Dependencies and assumptions

The product stack remains Python, Streamlit, pandas, NumPy, scikit-learn, pytest, and a local CSV. Phase 1 inspection/loader tooling currently uses only the Python standard library and runs with Python 3.14.5 in this workspace; choose product dependency pins when the application skeleton is implemented. Dataset files are acquired by the developer and are not silently committed.

FMA is selected. The local metadata has artist/genre information and the Echo Nest table supplies all six desired high-level features for 13,129 tracks joined by track ID; one lacks a display title, leaving 13,128 scoreable recommendations. The feature terms should be reviewed before redistribution/public deployment. The full 106,573-row cleaned display catalogue does not have mood features, so it cannot receive full-catalogue audio-goal scores.

## Current blockers

No Phase 1 blocker remains for local catalogue inspection and loader work. The archive ZIP is not present, but the extracted CSVs are. The upstream Echo Nest/Spotify terms have not been independently confirmed for redistribution; review them before publishing derived feature data. Full-catalogue mood scoring remains unsupported by this dataset.

## Milestone acceptance criteria

- Phase 0: workspace inventory and architecture are recorded without overwriting existing work. **Met.**
- Phase 1: source, creator, terms, and exact acquisition steps are documented; actual schema is mapped; canonical fields and quality checks are implemented; statistics are reproducible; unavailable data remains explicitly pending. **Met for the supplied extracted files.** Measured results are in `dataset_inspection.md` and `dataset_inspection.json`; feature-based scoring coverage is 13,128 clean recommendations.
- Phase 2: target, preference, discovery, and diversity scoring use verified inputs; feedback is bounded and idempotent; unsupported components remain explicit; explanations carry calculation evidence; ties are deterministic; the full automated suite passes; real-catalogue integration is recorded. **Met:** 27 tests passed; see `architecture.md` and `evaluation.md`.
- Phase 3: **complete for the local prototype.** Streamlit 1.65.0 was installed from `requirements.txt`; the app launched at `http://localhost:8501` and returned HTTP 200 from Streamlit's health endpoint. Streamlit AppTest exercised a real-catalogue submission, engine results and evidence, like/skip/more-like feedback, more-variety reranking, and reset. Full suite: 30 tests passed. See `README.md` for local setup and known limitations.
- Phase 2 onward: each subsystem is implemented and verified before being connected to the next layer; no fabricated catalogue records, feature values, listening links, or artwork are introduced.
