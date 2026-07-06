from datetime import datetime, timezone

from app.models.signal import SignalOutcome
from app.signal_engine.suggestion import TARGET_GAIN_PCT, bucket_u_shape, classify, suggest_outcome


def make_outcome(
    max_gain_pct=None, gain_at_20min_pct=None, seconds_to_peak=None,
    max_drawdown_pct=None, seconds_to_trough=None,
) -> SignalOutcome:
    return SignalOutcome(
        signal_id="sig-1",
        price_at_signal=100.0,
        max_gain_pct=max_gain_pct,
        gain_at_20min_pct=gain_at_20min_pct,
        seconds_to_peak=seconds_to_peak,
        max_drawdown_pct=max_drawdown_pct,
        seconds_to_trough=seconds_to_trough,
        recorded_at=datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
    )


# ── bucket_u_shape ───────────────────────────────────────────────────────

def test_bucket_u_shape_boundaries():
    assert bucket_u_shape(None) is None
    assert bucket_u_shape(0) == "none"
    assert bucket_u_shape(59) == "sub_1min"
    assert bucket_u_shape(60) == "1min"
    assert bucket_u_shape(119) == "1min"
    assert bucket_u_shape(120) == "2min"
    assert bucket_u_shape(179) == "2min"
    assert bucket_u_shape(180) == "3min"
    assert bucket_u_shape(1000) == "3min"


# ── suggest_outcome ──────────────────────────────────────────────────────

def test_suggest_outcome_none_outcome():
    result = suggest_outcome(None)
    assert result.profitable_at_20min is None
    assert result.hit_target is None
    assert result.suggested_was_red_herring is None
    assert result.suggested_u_shape_type is None
    assert result.classification is None
    assert result.notes == "Outcome not yet tracked"


def test_suggest_outcome_not_yet_tracked():
    # OutcomeTracker hasn't finalized (max_gain_pct still null) even though
    # a row exists.
    outcome = make_outcome(max_gain_pct=None)
    result = suggest_outcome(outcome)
    assert result.notes == "Outcome not yet tracked"
    assert result.profitable_at_20min is None


def test_suggest_outcome_profitable_and_hit_target():
    outcome = make_outcome(max_gain_pct=TARGET_GAIN_PCT + 1, gain_at_20min_pct=2.0, seconds_to_peak=90)
    result = suggest_outcome(outcome)
    assert result.profitable_at_20min is True
    assert result.hit_target is True
    assert result.suggested_was_red_herring is False
    assert result.suggested_u_shape_type == "1min"
    assert result.classification == "likely_success"


def test_suggest_outcome_profitable_but_below_target():
    outcome = make_outcome(
        max_gain_pct=0.67, gain_at_20min_pct=0.66, seconds_to_peak=1167,
        max_drawdown_pct=-0.2, seconds_to_trough=30,
    )
    result = suggest_outcome(outcome)
    assert result.profitable_at_20min is True
    assert result.hit_target is False
    assert result.suggested_was_red_herring is False
    assert result.suggested_u_shape_type == "3min"
    assert result.classification == "needs_review"
    assert "drawdown -0.20% at 30s" in result.notes


def test_suggest_outcome_red_herring():
    outcome = make_outcome(max_gain_pct=-0.5, gain_at_20min_pct=-1.2, seconds_to_peak=0)
    result = suggest_outcome(outcome)
    assert result.profitable_at_20min is False
    assert result.hit_target is False
    assert result.suggested_was_red_herring is True
    assert result.suggested_u_shape_type == "none"
    assert result.classification == "likely_failure"


def test_suggest_outcome_handles_missing_gain_at_20min():
    # max_gain_pct tracked but gain_at_20min_pct somehow still null.
    outcome = make_outcome(max_gain_pct=1.0, gain_at_20min_pct=None, seconds_to_peak=30)
    result = suggest_outcome(outcome)
    assert result.profitable_at_20min is False  # can't confirm profitable without the 20min figure
    assert result.classification == "likely_failure"
    assert "n/a" in result.notes


# ── classify ─────────────────────────────────────────────────────────────

def test_classify_likely_success():
    assert classify(profitable_at_20min=True, hit_target=True) == "likely_success"


def test_classify_likely_failure_even_with_a_peak():
    # Hit the target intraday but ended flat/negative -- a round-tripped
    # pop isn't a win.
    assert classify(profitable_at_20min=False, hit_target=True) == "likely_failure"


def test_classify_needs_review():
    assert classify(profitable_at_20min=True, hit_target=False) == "needs_review"
