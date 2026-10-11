# Dataset discovery and selection

**Inspection date:** 2026-10-11  
**Selected source:** Free Music Archive (FMA) metadata archive, supplied locally at `data/fma_metadata/`.

## Source and terms

- **Dataset:** FMA: A Dataset for Music Analysis; authors Michaël Defferrard, Kirell Benzi, Pierre Vandergheynst, and Xavier Bresson.
- **Primary source:** [FMA project repository](https://github.com/mdeff/fma); archive URL documented by the authors: `https://os.unil.cloud.switch.ch/fma/fma_metadata.zip`.
- **Archive provenance:** local `README.txt` identifies the FMA project and says each MP3 is licensed by its artist. The authors' project page says metadata is released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) and characterizes the dataset as intended for research. Keep attribution and license notices. The catalogue uses metadata only and does not package audio.
- **Feature provenance:** `echonest.csv` contains the Echo Nest audio features in the FMA archive (including energy, valence, danceability, acousticness, tempo, and instrumentalness). The project authors' metadata license statement is recorded, but a separate current redistribution/commercial-use grant from Echo Nest/Spotify was not independently verified. Treat this feature subset as suitable for local research/prototyping; review its upstream terms before public/commercial distribution.
- **Acquisition/verification:** obtain `fma_metadata.zip` from the source; the project documents SHA-1 `f0df49ffe5f2a6008d7dc83c6915b31835dfe733`. The supplied extracted files were accessible and inspected. The archive itself was not present, so its ZIP checksum was not re-run. The extracted folder includes a `checksums` file for files in the archive.
- **Attribution:** Defferrard, Michaël, Kirell Benzi, Pierre Vandergheynst, and Xavier Bresson. “FMA: A Dataset for Music Analysis.” ISMIR, 2017. See the project repository and cite the paper when using the data.

## Local inspection result

All four expected CSVs exist: `tracks.csv`, `genres.csv`, `features.csv`, and `echonest.csv`. The exact columns, source counts, missingness, and measured feature ranges are in the generated [inspection JSON](/D:/MAJOR%20PROJECTS/MoodShiftX/docs/dataset_inspection.json) and readable summary in `dataset_inspection.md`. Reproduce both with:

```powershell
python scripts/inspect_dataset.py --output docs/dataset_inspection.json
```

The CSV parser keeps values as strings until conversion; `track_id`, `artist.id`, and `genre_id` are numeric-looking source identifiers and are preserved as strings in the canonical catalogue. Track columns use three header/index rows; `features.csv` and `echonest.csv` use three column-header levels plus an index-name row. `genres.csv` has a single header row.

Canonical mapping:

| Canonical field | Source field / handling |
|---|---|
| `track_id` | `tracks.csv` index; `echonest.csv` index for feature join |
| `track_name` | `track.title` |
| `artist_id`, `artist_name` | `artist.id`, `artist.name` |
| `genre` | First ID in `track.genres`, looked up by `genre_id` in `genres.csv`; no unmatched IDs in inspected data |
| `energy`, `valence`, `danceability`, `acousticness`, `tempo`, `instrumentalness` | `echonest.audio_features.*`; validated, with unknown values left missing |
| `popularity` | `track.interest`, source-defined count-like value; not used until a normalization policy is selected |
| `track_url`, `image_url` | Unavailable; remain missing |

`features.csv` has 518 low-level librosa-derived columns (519 including track index), grouped under chroma CENS/CQT/STFT, MFCC, RMSE, spectral bandwidth/centroid/contrast/rolloff, tonnetz, and zero-crossing rate. These are not equivalent to the named high-level mood inputs and are not substituted for them.

## Feature decision

`echonest.csv` has 13,129 rows with IDs, and every one joins to the 106,574-track catalogue using exact `track_id`. Each of the six requested high-level features is non-missing and range-valid for all 13,129 joined tracks. The other tracks remain unscored for goal-based audio matching. Feature ranges and units measured locally:

| Feature | Source column | Local range | Scored records | Suitability |
|---|---|---:|---:|---|
| Energy | `echonest.audio_features.energy` | 0.000020–0.999964 (0–1 scale) | 13,128 | Directly suitable on the feature subset |
| Valence | `echonest.audio_features.valence` | 0.000010–0.999990 (0–1 scale) | 13,128 | Directly suitable on the feature subset; proxy for musical positivity, not user mood |
| Danceability | `echonest.audio_features.danceability` | 0.051307–0.968645 (0–1 scale) | 13,128 | Directly suitable on the feature subset |
| Acousticness | `echonest.audio_features.acousticness` | 0.0000009–0.995796 (0–1 scale) | 13,128 | Directly suitable on the feature subset |
| Tempo | `echonest.audio_features.tempo` | 12.753–251.072 BPM | 13,128 | Directly suitable after BPM scaling/target bounds are decided |
| Instrumentalness | `echonest.audio_features.instrumentalness` | 0–0.998016 (0–1 scale) | 13,128 | Directly suitable on the feature subset |

No invalid values were found under the documented rules: bounded values in [0,1] and tempo strictly greater than zero. The 13,129 fully featured Echo Nest IDs all join to source track IDs, but one joined track has no display title, leaving 13,128 clean recommendations scoreable on all six features. This supports option A for a feature-based prototype restricted to that subset. Option B can cover the larger catalogue only as a genre/metadata discovery baseline and must not claim target audio matching. No separate dataset is merged: the FMA Echo Nest table has reliable direct track-ID joins, while no third-party alternative has a verified grant and compatibility advantage.

## Cleaning policy and limitations

- Keep the first source row for each non-empty `track_id` in source order; omit a row with empty ID, title, or artist name. In the supplied data there are no duplicate rows or IDs, and one source track has no title, leaving 106,573 rows with required display fields.
- Parse genre IDs as lists and join them to `genres.csv` with integer IDs. Unknown genre IDs are an error in the report; none were found.
- Reject non-finite/non-numeric feature values and out-of-range values as missing. Do not replace missing features with zero.
- FMA's `track.genre_top` is missing for 56,976 tracks (53.4614%); `track.genres` is blank or `[]` for 2,231 tracks (2.094%).
- No listening or image URL is confirmed in these schemas; never manufacture one.
- Genre entries count 163; track genre IDs cover 161 distinct values, with no unmapped IDs.
- Recommendation targets should not be interpreted as measuring a user's actual emotional state. Valence is a property estimated for the music, not a psychological assessment.

## Recommendation

The catalogue is ready for Phase 2 only if the goal-matching engine explicitly operates on the 13,128 clean, verified feature-bearing tracks. A full-catalogue genre baseline may be added as a separately labeled strategy. Do not advertise mood-target audio scoring over all 106,574 records. Resolve Echo Nest/Spotify redistribution terms before deploying or republishing derived feature data.
