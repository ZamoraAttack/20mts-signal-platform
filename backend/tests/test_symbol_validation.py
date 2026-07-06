import pytest

from app.engine.symbol_validation import InvalidSymbolError, validate_promotable_symbol


def test_accepts_symbol_present_in_watchlist():
    assert validate_promotable_symbol("AAPL", ["AAPL", "NFLX"]) == "AAPL"


def test_normalizes_case_and_whitespace():
    assert validate_promotable_symbol("  aapl  ", ["AAPL"]) == "AAPL"


def test_accepts_share_class_suffix():
    assert validate_promotable_symbol("BRK.B", ["BRK.B"]) == "BRK.B"


def test_rejects_empty_symbol():
    with pytest.raises(InvalidSymbolError, match="empty"):
        validate_promotable_symbol("", ["AAPL"])


def test_rejects_whitespace_only_symbol():
    with pytest.raises(InvalidSymbolError, match="empty"):
        validate_promotable_symbol("   ", ["AAPL"])


def test_rejects_malformed_symbol():
    with pytest.raises(InvalidSymbolError, match="well-formed"):
        validate_promotable_symbol("NF1X!", ["NF1X!"])


def test_rejects_symbol_not_in_watchlist():
    with pytest.raises(InvalidSymbolError, match="not in the current watchlist"):
        validate_promotable_symbol("ZZZZ", ["AAPL", "NFLX"])


def test_rejects_well_formed_symbol_when_watchlist_empty():
    with pytest.raises(InvalidSymbolError, match="not in the current watchlist"):
        validate_promotable_symbol("AAPL", [])
