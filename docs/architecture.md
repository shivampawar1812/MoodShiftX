# Recommendation engine architecture

## Scope

The Phase 2 engine is a deterministic Python library. It has no Streamlit dependency. It consumes canonical track dictionaries from `catalogue.load_catalogue`, a validated `PreferenceProfile`, and optional immutable `FeedbackState`; it returns scored records with component scores, contribution weights, explanations, and diversity reranking details.

The inspected FMA source provides six usable Echo Nest audio features for 13,128 displayable tracks: energy, valence, danceability, acousticness, tempo, and instrumentalness. The engine uses only those verified fields. Tracks without a requested valid value have an unsupported target component (`None`); missing data is never converted to zero. Genre matching and catalogue-relative genre rarity are the available metadata components. Listening URLs and artwork are unavailable and remain absent.

## Phase 3 Streamlit data flow

`app.py` resolves the project root from its own file and loads `data/fma_metadata/` through `catalogue.load_catalogue`. Streamlit's resource cache holds the parsed catalogue as an immutable tuple of read-only mapping records for the process. Each browser session stores its own validated `PreferenceProfile`, immutable `FeedbackState`, and result records in `st.session_state`.

Submitting the form builds the profile through `PreferenceProfile` validation and calls `recommend_tracks`; the UI does not calculate scores. If targets are selected, candidates are scoped to records with every requested measurement, making target scoring coverage explicit and comparable. With no targets, the app uses the metadata catalogue and makes no audio-goal claim. Each result card renders only `component_weights` present in the engine output, preserves `overall_score` / `original_ranking_score`, and separately shows `final_reranking_score`. Explanations come directly from the engine's structured evidence and limitations.

Card actions update session-local feedback through the pure transitions in `feedback.py`, then rerun the same recommendation function. The global variety toggle uses `more_variety`; reset clears feedback, preferences, and results without touching the cached catalogue. External links and artwork render only if valid URLs exist in actual records. No remote persistence or network media fetch is added.

## Modules

- `preferences.py`: profile validation, supported feature bounds, configurable goal-to-target defaults, and normalized target/preference/discovery weights.
- `catalogue.py`: local CSV loading, stable-ID joins, first-row duplicate policy, missing-value preservation, and source fingerprint caching.
- `feedback.py`: pure state transitions for like, skip, more-like-this, more-variety, and reset. Each track has at most one like/skip state; repeated events are idempotent.
- `ranking.py`: feature target match, genre preference, bounded feedback similarity, genre-frequency discovery, component-aware weight renormalization, stable sorting, and `recommend_tracks` orchestration.
- `diversity.py`: deterministic greedy reranking using feature, genre, and artist evidence, with optional artist cap and an explicit repeat penalty.
- `explanations.py`: structured evidence derived from ranking calculations and actual track metadata.

## Target match

For each candidate, use only the intersection of target features and valid candidate measurements. Bounded [0,1] features retain their scale. Tempo targets are in BPM and are divided by 250 for distance calculations; candidates over 250 BPM remain valid and may produce a normalized value slightly above 1. Target feature weights default equally and are renormalized across dimensions actually present for the track:

`D = sqrt(sum(a_j * (x_j - u_j)^2) / sum(a_j))`

`S_target = exp(-3 * D)`

The decay `k=3` maps zero distance to 1 and steadily reduces the score as normalized RMS distance grows. It is a transparent product choice, not a calibrated perceptual or psychological model. Unsupported target components are excluded from the combination and named in `unsupported_components`.

The configurable goal defaults (`calm`, `uplifting`, `focused`, `energized`, `reflective`) are hand-set starting points for music attributes. Current listening state and activity are captured in the profile for later product context; this engine does not infer or assess emotions from them.

## Preference, discovery, and total score

Genre preference is 1 for a selected genre, 0.25 for a nonmatching genre under soft filtering, and omitted when the user selected no genres. Strict mode removes nonmatching tracks before ranking. When explicit feedback exists, similarity is calculated from shared valid audio features (`exp(-3d)`); when no feature dimensions overlap but both genre labels are known, same genre is a 0.6 fallback and different genres score 0. If there is no comparable feature or genre metadata, feedback is unsupported for that candidate. The feedback score is `clip(0.5 + 0.25 * (mean positive similarity - mean skipped similarity), 0, 1)`. Feedback IDs are unique sets, so repeating one event does not increase its effect. When both genre and feedback evidence exist, preference score is 65% genre and 35% feedback.

Discovery is inverse log frequency of a known genre in the input catalogue. It means less frequent in this catalogue; it is not a quality score or an assertion that the track is new to a user. If genre evidence is unavailable or there is only one genre, discovery is unsupported.

Default component weights are target 0.60, preference 0.25, and discovery 0.15. They are normalized on profile creation. For each track, weights are renormalized across meaningful supported components only. All-zero configured weights safely fall back to equal weights across supported components. If supported components have zero requested weight because the positively weighted component is unsupported for that track, the score is zero and `zero_weight_supported_components` makes that condition explicit; no supported components also yields a finite zero score. “More variety” raises discovery weight by 0.15 before renormalization and uses at least 0.8 variety in the diversity step.

## Diversity and output

Greedy reranking combines preserved `overall_score` relevance and novelty using `variety` in [0,1], subtracts a configurable soft artist-repeat penalty, and optionally avoids exceeding an artist cap while alternatives remain. Pairwise similarity uses valid shared audio features normalized as above, plus known same/different genre and artist metadata. Unknown data is neutral rather than evidence of novelty. Output keeps `overall_score` and `original_ranking_score`; `final_reranking_score` and its components are separate.

Sorting uses score descending and string `track_id` ascending for ties. Duplicate IDs are collapsed by first occurrence. Result counts gracefully shrink for small catalogues. No network APIs, random values, or generated track metadata are used.

## Explanation contract

Each result's `explanation` has a summary, structured evidence, and limitations. Target evidence records actual and target values and normalized differences. Genre evidence names the selected genre. Feedback evidence references the stable ID and measured similarity. Discovery evidence records the source genre frequency. Unsupported target matches produce an explicit limitation and no target-based claim.
