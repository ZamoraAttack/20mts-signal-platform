from typing import Optional

from sqlalchemy import case

# Single source of truth for divergence-duration buckets. Purely a tracked
# metric for later research — never used to filter/suppress signals. The
# user explicitly does not want an invented minimum-duration threshold;
# the goal is to let outcome data reveal whether short divergences actually
# under-perform, not to assume it upfront.
DIVERGENCE_BUCKETS: list[tuple[str, float, Optional[float]]] = [
    ("0-5s", 0.0, 5.0),
    ("5-10s", 5.0, 10.0),
    ("10-15s", 10.0, 15.0),
    ("15s+", 15.0, None),
]


def bucket_for(divergence_seconds: Optional[float]) -> str:
    if divergence_seconds is None:
        return "unknown"
    for label, low, high in DIVERGENCE_BUCKETS:
        if divergence_seconds >= low and (high is None or divergence_seconds < high):
            return label
    return "unknown"


def bucket_case_expr(column):
    """SQLAlchemy case() expression bucketing `column` (a divergence_seconds
    column) per DIVERGENCE_BUCKETS — built from the same constant so SQL and
    Python bucket boundaries never drift apart."""
    branches = [
        (column < high, label) if high is not None else (column >= low, label)
        for label, low, high in DIVERGENCE_BUCKETS
    ]
    return case(*branches, else_="unknown").label("bucket")
