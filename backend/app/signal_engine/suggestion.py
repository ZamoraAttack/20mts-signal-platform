from dataclasses import dataclass
from typing import Optional

from ..models.signal import SignalOutcome

# The user's actual historical profit target: a ~$1.50 move on a $250-650
# share-price stock (their real screening criteria for "a stock I can use"),
# i.e. roughly a 3% move. Used only to compute an objective, displayed-not-
# saved suggestion -- never to filter/gate signals.
TARGET_GAIN_PCT = 3.0


def bucket_u_shape(seconds_to_peak: Optional[float]) -> Optional[str]:
    """Maps seconds_to_peak onto the same none/sub_1min/1min/2min/3min
    categories already used by the manual U-Shape Type dropdown."""
    if seconds_to_peak is None:
        return None
    if seconds_to_peak <= 0:
        return "none"
    if seconds_to_peak < 60:
        return "sub_1min"
    if seconds_to_peak < 120:
        return "1min"
    if seconds_to_peak < 180:
        return "2min"
    return "3min"


@dataclass
class SuggestionResult:
    profitable_at_20min: Optional[bool]
    hit_target: Optional[bool]
    suggested_was_red_herring: Optional[bool]
    suggested_u_shape_type: Optional[str]
    classification: Optional[str]
    notes: str


def classify(profitable_at_20min: bool, hit_target: bool) -> str:
    """
    Tri-state read of profitable_at_20min/hit_target, the same two numbers
    already used for the (still-displayed) individual suggestions -- no new
    threshold invented:
      - likely_success: hit the real 3% target AND ended positive
      - likely_failure: ended at/below entry by the 20min mark, regardless
        of any intermediate peak -- a pop that fully round-tripped isn't a win
      - needs_review: ended positive but never reached the 3% target --
        the genuinely ambiguous case most worth a human's eyes
    """
    if not profitable_at_20min:
        return "likely_failure"
    if hit_target:
        return "likely_success"
    return "needs_review"


def suggest_outcome(outcome: Optional[SignalOutcome]) -> SuggestionResult:
    """
    Computes objective, advisory-only suggestions from an already-tracked
    SignalOutcome. Never writes anything -- the caller must never persist
    these directly into was_successful/was_red_herring/u_shape_type without
    an explicit human save. `was_successful` itself is deliberately NOT
    suggested as a raw boolean: profitable_at_20min and hit_target are
    shown separately (and folded into `classification` for convenience)
    so the human can see which bar drove the call.
    """
    if outcome is None or outcome.max_gain_pct is None:
        return SuggestionResult(
            profitable_at_20min=None,
            hit_target=None,
            suggested_was_red_herring=None,
            suggested_u_shape_type=None,
            classification=None,
            notes="Outcome not yet tracked",
        )

    max_gain_pct = float(outcome.max_gain_pct)
    gain_at_20min_pct = float(outcome.gain_at_20min_pct) if outcome.gain_at_20min_pct is not None else None
    seconds_to_peak = float(outcome.seconds_to_peak) if outcome.seconds_to_peak is not None else None
    max_drawdown_pct = float(outcome.max_drawdown_pct) if outcome.max_drawdown_pct is not None else None
    seconds_to_trough = float(outcome.seconds_to_trough) if outcome.seconds_to_trough is not None else None

    profitable_at_20min = gain_at_20min_pct is not None and gain_at_20min_pct > 0
    hit_target = max_gain_pct >= TARGET_GAIN_PCT
    suggested_was_red_herring = max_gain_pct <= 0
    suggested_u_shape_type = bucket_u_shape(seconds_to_peak)
    classification = classify(profitable_at_20min, hit_target)

    gain_note = f"{gain_at_20min_pct:+.2f}%" if gain_at_20min_pct is not None else "n/a"
    peak_note = f"{seconds_to_peak:.0f}s" if seconds_to_peak is not None else "n/a"
    notes = f"peak {max_gain_pct:+.2f}% at {peak_note}"
    if max_drawdown_pct is not None and seconds_to_trough is not None:
        notes += f", drawdown {max_drawdown_pct:+.2f}% at {seconds_to_trough:.0f}s"
    notes += f"; ended {gain_note} at 20min"

    return SuggestionResult(
        profitable_at_20min=profitable_at_20min,
        hit_target=hit_target,
        suggested_was_red_herring=suggested_was_red_herring,
        suggested_u_shape_type=suggested_u_shape_type,
        classification=classification,
        notes=notes,
    )
