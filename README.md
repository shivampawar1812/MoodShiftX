# MoodShift X

MoodShift X is a local music discovery app. It ranks tracks using explicit listening preferences, FMA genre metadata, verified Echo Nest audio measurements, optional session feedback, and the project's deterministic diversity reranker.

## Features

- Listening goals, current listening context, activity, catalogue-derived genre options, and strict or soft genre matching.
- Adjustable target, preference, and discovery weights; supported feature targets and per-feature weights; result count and variety.
- Ranked cards with scores from the recommendation engine, evidence-backed explanations, available audio measurements, and per-session Like, Skip, and More like this actions.
- A session-only More variety control and reset action. No login, database, remote service, or audio playback backend.

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

Place the extracted FMA metadata files in `data/fma_metadata/`. `tracks.csv` and `genres.csv` are required; `echonest.csv` adds the verified high-level audio measurements. The files are not installed or downloaded by the app. See [dataset provenance and schema](docs/dataset.md) and the measured [inspection report](docs/dataset_inspection.md).

Without the Echo Nest feature table, the app can only offer metadata and genre discovery. With the supplied local catalogue, goal matching is limited to 13,128 clean tracks with verified audio features; the app filters to tracks that contain every selected target measurement. Genre choices are drawn from loaded catalogue records.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use the Streamlit testing API for app rendering and interaction when Streamlit is installed. The engine tests remain independent of Streamlit.

## Recommendation methodology

`PreferenceProfile` validates targets, preference inputs, component weights, variety, and result count. `recommend_tracks` runs the shared `rank_tracks` scoring and deterministic diversity reranking. Target match uses the engine's normalized feature-distance formula. Genre preference is explicit; discovery reflects relative genre frequency in the loaded catalogue. Effective weights are normalized over each track's supported components. Cards show only components with nonzero effective contribution, preserve the engine's original relevance score, and display the separate diversity-adjusted score. Scores are algorithmic relevance values, not probabilities.

The goal defaults are configurable product choices, not clinically validated interpretations of emotional states. Current state and activity are retained as explicit profile context; the app does not infer emotion, analyze faces, use deep learning, or call an LLM.

## Supported data and limitations

- Verified high-level fields: energy, valence, danceability, acousticness, tempo, and instrumentalness.
- Genre/artist metadata supports catalogue-level preference and diversity; it does not establish audio mood.
- Artwork and listening URLs are absent from the supplied canonical data, so cards do not invent them.
- The FMA low-level feature matrix is not treated as mood data.
- Echo Nest/Spotify feature redistribution terms have not been independently confirmed. Review the terms before public or commercial redistribution. Retain dataset attribution and respect track-specific licenses.
- This is a metadata discovery prototype; it does not play audio or provide mental-health advice.
