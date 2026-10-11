# Phase 4 test and integration report

**Date:** 2026-10-11<br>
**Runtime:** Python 3.14.5; application dependency pinned to Streamlit 1.65.0.

## Clean dependency installation

Created an empty project `.venv` and installed only the declared development requirements:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Result: completed successfully. The environment installed Streamlit 1.65.0 and pytest 9.1.1 from the project requirements, along with their resolved transitive packages.

## Regression suite

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Result: **33 passed in 57.82 seconds** in the clean `.venv`. The requested workspace command `python -m pytest -q` also passed **33 tests in 47.02 seconds**. The pre-change pytest baseline was **30 passed in 85.96 seconds**. During the first final-suite run, the missing-catalogue case exposed that the data path was captured at import time; resolving it at runtime fixed the case. The real-data submission followed by a missing-data directory regression pair passed (**2 passed in 41.26 seconds**), followed by the complete passing suite.

Coverage includes catalogue parsing and real-data integration, recommendation scoring/feedback/diversity, Streamlit submission and session actions, missing-catalogue recovery, path privacy, URL validation, and Markdown escaping.

## Streamlit startup check

Started the app from the clean environment:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.port 8765
```

`http://127.0.0.1:8765/_stcore/health` returned **HTTP 200, `ok`**; the app root returned **HTTP 200**. The local server was stopped after the check. Streamlit AppTest also submitted a real-catalogue profile and exercised recommendation results, feedback, more-variety, reset, and missing-catalogue behavior.

## Real-catalogue evaluation

`python scripts/evaluate_engine.py` completed successfully on the local dataset:

- 106,573 displayable catalogue tracks; 13,128 complete calm-goal candidates.
- Load 13.016 seconds; recommendation generation 4.177 seconds.
- Process RSS after load 199.7 MB; after recommendations 212.2 MB.
- Identical result IDs on repeat; zero duplicates, 10 distinct artists, and 10 genres among 10 results.
- Calm target features were available for 13,128 of 106,573 records (12.3183%); discovery metadata was scoreable for 104,340 (97.9047%). Preference/discovery scoring was deliberately disabled in this target-only profile.
- Raw `track.interest` baseline: 9 artists, 7 genres, mean calm target score 0.434351 versus 0.831132 for the engine results.

These measurements describe one local run and do not establish user relevance or cloud capacity. Detailed methodology is in `evaluation.md`.

## Deployment status

No Streamlit Community Cloud deployment was performed. The repository does not contain the dataset, and a runtime data provisioning method and Echo Nest/Spotify feature terms review remain necessary before a functioning public deployment.
