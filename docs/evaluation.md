# Phase 2 evaluation and verification

## Commands

Run the full unit and local-data integration suite:

```powershell
python -m unittest discover -s tests -v
```

Run a real-catalogue descriptive ranking check:

```powershell
python scripts/evaluate_engine.py
```

The second command loads the local catalogue, limits candidates to tracks with all features required by the chosen `calm` product-default target, ranks twice, and checks stable IDs. It prints the selected target values and top five actual track records. It does not claim recommendation quality.

## Test results

Verified locally with Python 3.14.5:

- `python -m unittest discover -s tests -v`: **27 tests passed**. The suite covers profile validation; goal defaults; target formula and tempo normalization; partial/missing feature behavior; all-zero and normalized weights; strict/soft genre filtering; feedback responsiveness, idempotency, and reset; catalogue genre discovery; stable ties and duplicate IDs; explanation evidence; diversity behavior, artist caps, small catalogues, and score preservation; plus a real FMA subset integration check.
- The local FMA integration test measured **106,573** clean catalogue records and **13,128** records with all six high-level features. On this verified subset, target-only ranking returned three finite results with target score equal to overall score.
- Phase 1 inspection measured 106,574 source tracks, 16,341 artist IDs, 163 genre records, no duplicate track IDs, 518 clean low-level feature columns, and 13,128 clean recommendations supported by all six audio features. These counts are detailed in `dataset_inspection.md` and `dataset_inspection.json`.

The descriptive run `python scripts/evaluate_engine.py` ranked 13,128 real records against the configurable `calm` defaults (energy 0.30, valence 0.48, danceability 0.35, acousticness 0.70, tempo 90 BPM), with target-only weight and diversity variety 0. It returned identical track IDs on both runs. Its first results were:

| Track ID | Track | Artist | Target score |
|---:|---|---|---:|
| 31886 | Slits live @ Primavera Sound 2010 (full set) | The Slits | 0.868730 |
| 45462 | In the Casbah | Silver Abuse | 0.866822 |
| 38538 | Come on in My Kitchen | Nobody's Bizness | 0.852899 |
| 34085 | Burn the World | Grand Mal | 0.850889 |
| 32482 | Respect | CM aka Creative | 0.844002 |

These are the deterministic top rows for that explicit target configuration, not user-tested recommendations or evidence of emotional effect.

## Limits of this evaluation

No listener judgments, target-transition labels, or held-out relevance data are available. The tests establish formula correctness, deterministic behavior, bounded outputs, honest unsupported handling, and evidence fidelity. They do not establish that a target profile changes a listener's emotion or that recommendations are preferred by listeners. Genre rarity is catalogue-relative. Current state and activity are collected but are not treated as measured emotional information.

Only the Phase 2 unit/integration test suite and the scripted local-catalogue check are reported as tests. A public license review for Echo Nest feature redistribution remains necessary before publishing derived feature data.
