"""MoodShift X local Streamlit application."""
from __future__ import annotations

import logging
import os
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlparse

import streamlit as st

from src.moodshiftx.catalogue import CatalogueError, load_catalogue
from src.moodshiftx.feedback import FeedbackState, like, more_like_this, more_variety, reset_feedback, skip
from src.moodshiftx.preferences import DEFAULT_GOAL_TARGETS, PreferenceProfile
from src.moodshiftx.ranking import recommend_tracks

ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)
MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>])")
FEATURE_LABELS = {
    "energy": "Energy", "valence": "Valence", "danceability": "Danceability",
    "acousticness": "Acousticness", "tempo": "Tempo", "instrumentalness": "Instrumentalness",
}
WEIGHT_HELP = {
    "target": "How closely supported audio features match your selected listening goal.",
    "preference": "How well tracks fit selected genres and your explicit track feedback.",
    "discovery": "Favors less frequent genres in this catalogue; it is not a quality score.",
}


@st.cache_resource(show_spinner="Loading local music catalogue…")
def get_catalogue(data_dir: str | None = None) -> tuple[Mapping, ...]:
    """Share an immutable canonical catalogue across sessions."""
    records = load_catalogue(data_dir or str(_data_dir()))
    return tuple(MappingProxyType({**row, "source_genre_ids": tuple(row.get("source_genre_ids") or ())})
                 for row in records)


@st.cache_resource(show_spinner=False)
def get_catalogue_options(data_dir: str | None = None) -> tuple[tuple[str, ...], frozenset[str]]:
    """Cache immutable genre and supported-feature choices across reruns."""
    catalogue = get_catalogue(data_dir or str(_data_dir()))
    genres = tuple(sorted({str(row["genre"]) for row in catalogue if row.get("genre")}))
    features = frozenset(name for row in catalogue for name in FEATURE_LABELS
                         if row.get(name) is not None)
    return genres, features


@st.cache_resource(show_spinner=False)
def get_goal_candidates(features: tuple[str, ...], data_dir: str | None = None) -> tuple[Mapping, ...]:
    """Reuse feature-complete candidate pools for repeated feedback reranks."""
    catalogue = get_catalogue(data_dir or str(_data_dir()))
    return tuple(row for row in catalogue if all(row.get(name) is not None for name in features))


def _plain_markdown(value: object) -> str:
    """Escape source-derived values before placing them in Streamlit Markdown."""
    text = str(value).replace("\r", " ").replace("\n", " ")
    return MARKDOWN_SPECIAL.sub(r"\\\1", text)


def _data_dir() -> Path:
    return Path(os.environ.get("MOODSHIFTX_DATA_DIR", str(ROOT / "data" / "fma_metadata"))).expanduser().resolve()


def _catalogue_location_label() -> str:
    try:
        return _data_dir().relative_to(ROOT).as_posix()
    except ValueError:
        return "the configured MOODSHIFTX_DATA_DIR location"


def build_profile(values: dict, available_features: set[str] | None = None) -> PreferenceProfile:
    """Validate UI values through the same preference model used by the engine."""
    goal = values["goal"]
    enabled = set(values.get("target_features", DEFAULT_GOAL_TARGETS.get(goal, {})))
    if available_features is not None:
        enabled &= available_features
    targets = {name: value for name, value in DEFAULT_GOAL_TARGETS.get(goal, {}).items() if name in enabled}
    for name, value in values.get("target_overrides", {}).items():
        if name in enabled:
            targets[name] = value
    return PreferenceProfile(
        current_state=values.get("current_state", ""), desired_experience=goal,
        activity=values.get("activity", ""), preferred_genres=tuple(values.get("genres", ())),
        genre_filter=values.get("genre_filter", "soft"), target_features=targets,
        target_feature_weights=values.get("feature_weights", {}),
        weights=values.get("weights", {"target": .60, "preference": .25, "discovery": .15}),
        variety=values.get("variety", .35), recommendation_count=values.get("count", 10),
    )


def _rerun_recommendations() -> None:
    profile = st.session_state.get("profile")
    if profile is None:
        return
    try:
        if profile.target_features:
            # Goal matching is scoped to tracks with every requested measurement.
            candidates = get_goal_candidates(tuple(sorted(profile.target_features)), str(_data_dir()))
        else:
            candidates = get_catalogue(str(_data_dir()))
        results = recommend_tracks(candidates, profile, st.session_state.get("feedback", FeedbackState()))
        no_scoreable = bool(results) and not any(row.get("contributing_components") for row in results)
        if no_scoreable:
            results = []
        st.session_state["results"] = results
        st.session_state["candidate_count"] = len(candidates)
        st.session_state["no_scoreable_results"] = no_scoreable
        st.session_state["recommendation_error"] = None
    except Exception as exc:  # UI boundary: retain details in logs, show a useful recovery action.
        LOGGER.exception("Recommendation generation failed")
        st.session_state["results"] = []
        st.session_state["no_scoreable_results"] = False
        st.session_state["recommendation_error"] = f"Recommendations could not be generated ({type(exc).__name__}). Check your choices and try again."


def _feedback_action(track_id: str, action: str) -> None:
    state = st.session_state.get("feedback", FeedbackState())
    transitions = {"like": like, "skip": skip, "more": more_like_this}
    st.session_state["feedback"] = transitions[action](state, track_id)
    _rerun_recommendations()


def _toggle_variety() -> None:
    st.session_state["feedback"] = more_variety(
        st.session_state.get("feedback", FeedbackState()), st.session_state.get("more_variety_control", False))
    _rerun_recommendations()


def _reset() -> None:
    st.session_state["feedback"] = reset_feedback()
    st.session_state["results"] = []
    st.session_state["profile"] = None
    st.session_state["recommendation_error"] = None
    st.session_state["no_scoreable_results"] = False
    reset_keys = {"current_state", "goal", "activity", "genres", "genre_filter_label", "count",
                  "more_variety_control", "weight-target", "weight-preference", "weight-discovery", "variety"}
    reset_keys.update(key for key in st.session_state
                      if key.startswith(("target_features-", "target-", "feature-weight-")))
    for key in reset_keys:
        st.session_state.pop(key, None)


def _valid_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or "\\" in candidate or any(char.isspace() or ord(char) < 0x20 for char in candidate):
        return None
    try:
        parsed = urlparse(candidate)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None):
            return None
        _ = parsed.port  # Validate malformed and out-of-range ports.
    except ValueError:
        return None
    return candidate


def _fmt_feature(name: str, value: float) -> str:
    return f"{value:.1f} BPM" if name == "tempo" else f"{value:.3f}"


def _render_card(row: dict, rank: int) -> None:
    with st.container(border=True):
        left, main, score_col = st.columns([0.7, 5, 1.5], vertical_alignment="center")
        left.markdown(f"### {rank:02d}")
        main.markdown(f"### {_plain_markdown(row.get('track_name') or 'Untitled')}")
        main.markdown(f"**{_plain_markdown(row.get('artist_name') or 'Unknown artist')}** · {_plain_markdown(row.get('genre') or 'Genre unavailable')}")
        score_col.metric("Relevance", f"{row['overall_score']:.3f}")
        st.caption(f"Track ID {_plain_markdown(row['track_id'])} · algorithmic relevance, not a probability")

        if row.get("image_url"):
            image_url = _valid_url(row["image_url"])
            if image_url:
                st.image(image_url, width=120)
        else:
            st.caption("Artwork unavailable in this catalogue.")
        link = _valid_url(row.get("track_url"))
        if link:
            st.link_button("Open track", link)
        else:
            st.caption("No listening link is available in this catalogue.")

        scores = row.get("component_weights", {})
        score_cols = st.columns(max(1, len(scores)))
        for col, name in zip(score_cols, ("target", "preference", "discovery")):
            if name in scores:
                value = row.get(f"{name}_score")
                col.metric(name.title(), f"{value:.3f}" if value is not None else "—",
                           help=f"Contribution weight {scores[name]:.2f}")
        st.caption(f"Original relevance: {row['original_ranking_score']:.3f} · Diversity-adjusted ranking: {row['final_reranking_score']:.3f}")

        with st.expander("Audio features"):
            available = [(name, row.get(name)) for name in FEATURE_LABELS if row.get(name) is not None]
            if available:
                st.write(" · ".join(f"{FEATURE_LABELS[name]}: {_fmt_feature(name, value)}" for name, value in available))
            else:
                st.info("No supported audio-feature measurements are available for this track.")
        with st.expander("Why this track?"):
            explanation = row.get("explanation", {})
            if explanation.get("summary"):
                st.text(explanation["summary"])
            for evidence in explanation.get("evidence", []):
                st.markdown(f"- {_plain_markdown(evidence['text'])}")
            for limitation in explanation.get("limitations", []):
                st.caption(_plain_markdown(limitation))
            if not explanation.get("evidence"):
                st.caption("The engine returned no explanatory evidence for this result.")

        actions = st.columns(3)
        for col, action, label in zip(actions, ("like", "skip", "more"), ("Like", "Skip", "More like this")):
            col.button(label, key=f"feedback-{action}-{row['track_id']}",
                       on_click=_feedback_action, args=(str(row["track_id"]), action),
                       use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="MoodShift X", page_icon="♫", layout="wide")
    st.title("♫ MoodShift X")
    st.subheader("Find your next listening state.")
    st.write("Build a listening profile and explore tracks ranked from catalogue audio measurements, genre metadata, and your explicit feedback.")
    st.caption("Local FMA catalogue · Goal targets are configurable product defaults, not a measurement of your mood.")

    try:
        data_dir = str(_data_dir())
        get_catalogue(data_dir)
    except CatalogueError:
        LOGGER.exception("Local FMA catalogue is missing or invalid")
        st.error("The local music catalogue could not be loaded.")
        st.markdown(f"Add valid FMA metadata files under `{_plain_markdown(_catalogue_location_label())}/` (tracks.csv and genres.csv are required), then restart the app.")
        st.caption("For audio-goal scoring, provide the optional echonest.csv file as well.")
        return
    except (OSError, ValueError):
        LOGGER.exception("Local FMA catalogue could not be read")
        st.error("The local music catalogue could not be loaded.")
        st.markdown(f"Check the required FMA files under `{_plain_markdown(_catalogue_location_label())}/` and restart the app.")
        st.caption("Check file readability and the documented CSV schema.")
        return

    genres, supported = get_catalogue_options(data_dir)
    goal_names = list(DEFAULT_GOAL_TARGETS)
    if not genres:
        st.warning("This catalogue has no mapped genres. Genre selection is unavailable; clear any old selection and use the metadata baseline.")

    with st.form("preferences"):
        st.markdown("## Your listening profile")
        c1, c2, c3 = st.columns(3)
        current = c1.selectbox("Current listening state", ["Choose a state", "Calm", "Restless", "Low-key", "Focused", "Open to anything"], key="current_state")
        goal = c2.selectbox("Desired listening experience", goal_names, key="goal")
        activity = c3.selectbox("Activity", ["Everyday listening", "Working", "Studying", "Traveling", "Unwinding", "Moving"], key="activity")
        selected_genres = st.multiselect("Genres", genres, key="genres", help="Options come from the loaded catalogue.", disabled=not genres)
        filter_label = st.radio("Genre matching", ["Soft preference", "Strict filter"], horizontal=True, key="genre_filter_label")
        count = st.slider("Tracks to show", min_value=1, max_value=30, value=10, key="count")

        with st.expander("Advanced recommendation controls"):
            target_weight = st.slider("Goal match importance", 0.0, 1.0, .60, .05, help=WEIGHT_HELP["target"], key="weight-target")
            preference_weight = st.slider("Preference importance", 0.0, 1.0, .25, .05, help=WEIGHT_HELP["preference"], key="weight-preference")
            discovery_weight = st.slider("Discovery importance", 0.0, 1.0, .15, .05, help=WEIGHT_HELP["discovery"], key="weight-discovery")
            st.caption("Weights are normalized by the engine for each track's supported components.")
            goal_features = list(DEFAULT_GOAL_TARGETS[goal])
            feature_options = [name for name in goal_features if name in supported]
            if feature_options:
                selected_features = st.multiselect("Audio features used for this goal", feature_options, default=feature_options, key=f"target_features-{goal}")
                if len(selected_features) != len(feature_options):
                    st.caption("Tracks missing any selected goal measurement are left out so every displayed goal score is supported.")
            else:
                selected_features = []
                st.warning("This catalogue cannot score the chosen goal's audio features. Recommendations will use supported genre and metadata evidence only.")
            feature_weights = {}
            target_overrides = {}
            if selected_features:
                with st.expander("Tune target values and feature importance"):
                    for feature in selected_features:
                        default = DEFAULT_GOAL_TARGETS[goal][feature]
                        hi = 250.0 if feature == "tempo" else 1.0
                        step = 1.0 if feature == "tempo" else .01
                        target_overrides[feature] = st.slider(f"Target {FEATURE_LABELS[feature]}", 0.0, hi, float(default), step=step, key=f"target-{goal}-{feature}")
                        feature_weights[feature] = st.slider(f"{FEATURE_LABELS[feature]} feature weight", 0.0, 2.0, 1.0, .1, key=f"feature-weight-{goal}-{feature}")
        variety = st.slider("Variety in results", 0.0, 1.0, .35, .05, key="variety")
        submitted = st.form_submit_button("Find my tracks", type="primary", use_container_width=True)

    if submitted:
        values = {"current_state": "" if current == "Choose a state" else current,
                  "goal": goal, "activity": activity, "genres": selected_genres,
                  "genre_filter": "strict" if filter_label == "Strict filter" else "soft",
                  "count": count, "weights": {"target": target_weight, "preference": preference_weight, "discovery": discovery_weight},
                  "target_features": selected_features, "target_overrides": target_overrides,
                  "feature_weights": feature_weights, "variety": variety}
        try:
            profile = build_profile(values, supported)
            st.session_state["profile"] = profile
            st.session_state.setdefault("feedback", FeedbackState())
            _rerun_recommendations()
        except (TypeError, ValueError) as exc:
            st.session_state["results"] = []
            st.session_state["recommendation_error"] = f"Those preferences are not valid: {exc}"

    if "profile" in st.session_state and st.session_state["profile"] is not None:
        controls = st.columns([2, 1, 1])
        controls[0].checkbox("More variety", key="more_variety_control", on_change=_toggle_variety,
                             help="Raises the engine's discovery emphasis and diversity reranking.")
        controls[2].button("Reset session", on_click=_reset, use_container_width=True)
        if st.session_state.get("candidate_count") is not None:
            st.caption(f"Ranking across {st.session_state['candidate_count']:,} candidate tracks based on your selected features.")
    error = st.session_state.get("recommendation_error")
    if error:
        st.error(error)
    results = st.session_state.get("results", [])
    if results:
        st.markdown("## Your recommendations")
        for index, row in enumerate(results, 1):
            _render_card(row, index)
    elif st.session_state.get("profile") is not None and not error:
        if st.session_state.get("no_scoreable_results"):
            st.info("The engine found no supported scoring evidence for these tracks. Choose a goal with available measurements or add usable genre metadata.")
        elif st.session_state.get("candidate_count") == 0:
            st.info("No tracks have all selected audio measurements. Choose fewer target features or clear the feature selection.")
        else:
            st.info("No matching tracks were found. Try a soft genre preference, another genre, or a metadata-only search.")


if __name__ == "__main__":
    main()
