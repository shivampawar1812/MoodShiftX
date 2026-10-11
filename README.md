# MoodShift X

MoodShift X is a local music discovery app. It ranks tracks using explicit listening preferences, FMA genre metadata, verified Echo Nest audio measurements, optional session feedback, and a deterministic diversity reranker.

## Features

- Listening goals, current listening context, activity, catalogue-derived genre options, and strict or soft genre matching.
- Adjustable target, preference, and discovery weights; supported feature targets and per-feature weights; result count and variety.
- Ranked cards with engine scores, evidence-backed explanations, available audio measurements, and session-only Like, Skip, and More like this actions.
- Session-only More variety and reset controls. There is no login, database, remote service, or audio playback backend.

## Install and run

Use Python 3.10 or newer. From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

On macOS or Linux, activate with `source .venv/bin/activate`.

## Dataset setup

The app does not download data. Place extracted FMA metadata under `data/fma_metadata/`; `tracks.csv` and `genres.csv` are required, and `echonest.csv` provides the verified high-level audio measurements. To use another local path, set `MOODSHIFTX_DATA_DIR` to that directory before starting the app.

The repository intentionally excludes the local catalogue. With the inspected data, goal matching covers 13,128 clean records that contain every selected target feature. The remaining 93,445 displayable records lack at least one of the five default calm-goal measurements and are not scored for that goal. Metadata-only ranking remains available when no target features are selected. See [dataset provenance and schema](docs/dataset.md) and the [inspection report](docs/dataset_inspection.md).

## Tests and evaluation

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/evaluate_engine.py
```

The tests cover the engine, real-catalogue integration when local data is available, and Streamlit app interactions. The evaluation script reports repeatability, feature coverage, time, process memory when `psutil` is installed, result diversity, and a descriptive raw-interest comparison. See [evaluation methodology and results](docs/evaluation.md) and the [Phase 4 test report](docs/phase4_test_report.md).

## Recommendation methodology

`PreferenceProfile` validates target and preference inputs. `recommend_tracks` combines target match, genre/feedback preference, catalogue-relative genre discovery, and deterministic diversity reranking. Effective weights are normalized over supported evidence. Cards show algorithmic relevance scores, not probabilities. See [engine architecture](docs/architecture.md).

Goal defaults are configurable product choices, not clinically validated interpretations of emotional states. Current state and activity are explicit profile context; the app does not infer emotion, analyze faces, use deep learning, or call an LLM.

## Deployment readiness

The app has been verified locally, but it is **not ready for a functioning public deployment**. A clean GitHub checkout has no `data/fma_metadata/`, and Echo Nest/Spotify feature redistribution terms have not been independently confirmed. Do not upload or serve the feature-bearing catalogue until an authorized data delivery method and applicable terms are confirmed. Without data provisioning, the app displays its missing-catalogue recovery message and cannot recommend tracks.

After those blockers are resolved, the manual Community Cloud steps are:

1. Confirm authorized terms and implement a runtime-accessible data provisioning method; the app currently supports local paths only and does not provision hosted data.
2. In Streamlit Community Cloud, create an app from `shivampawar1812/MoodShiftX`, branch `main`, entry point `app.py`.
3. In Advanced settings, select a supported Python version (the current default is Python 3.12). No API secrets are required.
4. Deploy, inspect app logs, and verify catalogue loading and a complete recommendation/feedback workflow before sharing the URL.

Streamlit 1.65.0 and pytest 9.1.1 declare Python 3.10+ support; the clean installation was verified here with Python 3.14.5. Run a deployment-version smoke test before launch. A local run used 212.0 MB process RSS after loading and generating recommendations; hosted sizing should allow additional headroom for Python, Streamlit, rendering, and concurrent sessions, and has not been measured. Follow Streamlit's current [deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [dependency guidance](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies), and [app management documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app). No cloud deployment has been performed.

## Supported data and limitations

- Verified high-level fields: energy, valence, danceability, acousticness, tempo, and instrumentalness.
- Genre and artist metadata supports catalogue preference and diversity; it does not establish audio mood.
- Artwork and listening URLs are absent from the supplied canonical data, so cards do not invent them.
- The FMA low-level feature matrix is not treated as mood data.
- Echo Nest/Spotify feature redistribution terms have not been independently confirmed. Retain attribution and respect track-specific licenses.
- This is a metadata discovery prototype; it does not play audio or provide mental-health advice.
