"""Validated user preference profiles and configurable product defaults.

Goal mappings are configurable UI/product defaults, not clinically validated
models of emotion or claims about a user's psychological state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Mapping

SUPPORTED_FEATURES = frozenset({
    "energy", "valence", "danceability", "acousticness", "tempo", "instrumentalness",
})
FEATURE_RANGES = {
    "energy": (0.0, 1.0), "valence": (0.0, 1.0), "danceability": (0.0, 1.0),
    "acousticness": (0.0, 1.0), "instrumentalness": (0.0, 1.0), "tempo": (0.0, 250.0),
}
DEFAULT_GOAL_TARGETS: dict[str, dict[str, float]] = {
    "calm": {"energy": 0.30, "valence": 0.48, "danceability": 0.35, "acousticness": 0.70, "tempo": 90.0},
    "uplifting": {"energy": 0.65, "valence": 0.78, "danceability": 0.62},
    "focused": {"energy": 0.42, "instrumentalness": 0.70, "danceability": 0.35},
    "energized": {"energy": 0.82, "valence": 0.70, "danceability": 0.78, "tempo": 125.0},
    "reflective": {"energy": 0.35, "valence": 0.42, "acousticness": 0.55, "tempo": 85.0},
}
DEFAULT_WEIGHTS = {"target": 0.60, "preference": 0.25, "discovery": 0.15}


def _validate_target(name: str, value: float) -> float:
    if name not in SUPPORTED_FEATURES:
        raise ValueError(f"Unsupported target feature: {name}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Target for {name} must be numeric") from exc
    lo, hi = FEATURE_RANGES[name]
    if not math.isfinite(number) or not lo <= number <= hi or (name == "tempo" and number == 0):
        raise ValueError(f"Target for {name} must be in {lo}..{hi} (tempo must be positive)")
    return number


def targets_for_goal(goal: str | None, mapping: Mapping[str, Mapping[str, float]] | None = None) -> dict[str, float]:
    """Return copied product-default targets for a goal, or an empty mapping."""
    source = DEFAULT_GOAL_TARGETS if mapping is None else mapping
    target_map = {key.strip().casefold(): values for key, values in source.items()}
    if goal is None:
        return {}
    raw = target_map.get(goal.strip().casefold(), {})
    return {name: _validate_target(name, value) for name, value in raw.items()}


def normalize_weights(weights: Mapping[str, float]) -> dict[str, float]:
    """Normalize nonnegative weights; preserve all-zero input for safe fallback."""
    keys = ("target", "preference", "discovery")
    if set(weights) - set(keys):
        raise ValueError(f"Weights may only contain {', '.join(keys)}")
    values = {key: float(weights.get(key, 0.0)) for key in keys}
    if any(not math.isfinite(value) or value < 0 for value in values.values()):
        raise ValueError("Weights must be finite and non-negative")
    scale = max(values.values(), default=0.0)
    if not scale:
        return values
    scaled = {key: value / scale for key, value in values.items()}
    total = sum(scaled.values())
    return {key: value / total for key, value in scaled.items()}


@dataclass(frozen=True)
class PreferenceProfile:
    """Explicit listening preferences consumed by the local recommendation core."""

    current_state: str = ""
    desired_experience: str = ""
    activity: str = ""
    preferred_genres: tuple[str, ...] = ()
    genre_filter: str = "soft"  # soft or strict
    target_features: Mapping[str, float] | None = None
    goal_target_mapping: Mapping[str, Mapping[str, float]] | None = None
    target_feature_weights: Mapping[str, float] = field(default_factory=dict)
    weights: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    variety: float = 0.35
    recommendation_count: int = 10

    def __post_init__(self) -> None:
        if self.genre_filter not in {"soft", "strict"}:
            raise ValueError("genre_filter must be 'soft' or 'strict'")
        if isinstance(self.preferred_genres, str):
            raise ValueError("preferred_genres must be a sequence of genre labels, not a string")
        genres = tuple(dict.fromkeys(g.strip() for g in self.preferred_genres if isinstance(g, str) and g.strip()))
        object.__setattr__(self, "preferred_genres", genres)
        mapping = self.goal_target_mapping
        if mapping is not None:
            mapping = MappingProxyType({str(goal).strip().casefold(): MappingProxyType(
                {name: _validate_target(name, value) for name, value in values.items()})
                for goal, values in mapping.items()})
            object.__setattr__(self, "goal_target_mapping", mapping)
        targets = (targets_for_goal(self.desired_experience, mapping) if self.target_features is None
                   else {name: _validate_target(name, value) for name, value in self.target_features.items()})
        object.__setattr__(self, "target_features", MappingProxyType(dict(targets)))
        feature_weights: dict[str, float] = {}
        for name, raw in self.target_feature_weights.items():
            if name not in SUPPORTED_FEATURES:
                raise ValueError(f"Unsupported target feature weight: {name}")
            value = float(raw)
            if not math.isfinite(value) or value < 0:
                raise ValueError("Target feature weights must be finite and non-negative")
            feature_weights[name] = value
        object.__setattr__(self, "target_feature_weights", MappingProxyType(feature_weights))
        object.__setattr__(self, "weights", MappingProxyType(normalize_weights(self.weights)))
        variety = float(self.variety)
        if not math.isfinite(variety) or not 0 <= variety <= 1:
            raise ValueError("variety must be between 0 and 1")
        object.__setattr__(self, "variety", variety)
        if isinstance(self.recommendation_count, bool):
            raise ValueError("recommendation_count must be between 1 and 100")
        try:
            count = int(self.recommendation_count)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("recommendation_count must be an integer from 1 to 100") from exc
        if isinstance(self.recommendation_count, float) and self.recommendation_count != count:
            raise ValueError("recommendation_count must be an integer from 1 to 100")
        if not 1 <= count <= 100:
            raise ValueError("recommendation_count must be between 1 and 100")
        object.__setattr__(self, "recommendation_count", count)

