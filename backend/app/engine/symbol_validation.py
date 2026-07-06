import re

# Plain US equity ticker shape: 1-5 letters, optionally a share-class suffix
# like BRK.B or BRK-B. This is deliberately scoped to stock symbols only —
# the leader symbol (DIA, MYM.c.0, $DJI, etc.) is never promoted through
# this path, so it doesn't need to accommodate those formats.
_SYMBOL_PATTERN = re.compile(r"^[A-Z]{1,5}([.\-][A-Z]{1,2})?$")


class InvalidSymbolError(ValueError):
    """Raised when a requested active-stock promotion fails validation."""


def validate_promotable_symbol(symbol: str, watchlist: list[str]) -> str:
    """
    Validates a symbol requested for promotion to "active stock". Returns
    the normalized (trimmed, uppercased) symbol on success, or raises
    InvalidSymbolError with a message describing exactly which check failed.

    The engine must never silently switch to an invalid trading symbol, so
    every rejection path here is deliberate and specific rather than a
    catch-all.
    """
    candidate = symbol.strip().upper()

    if not candidate:
        raise InvalidSymbolError("Symbol cannot be empty")

    if not _SYMBOL_PATTERN.match(candidate):
        raise InvalidSymbolError(
            f"'{symbol}' is not a well-formed ticker symbol "
            "(expected 1-5 letters, optionally with a .X or -X share-class suffix)"
        )

    normalized_watchlist = {s.strip().upper() for s in watchlist}
    if candidate not in normalized_watchlist:
        watchlist_display = ", ".join(sorted(normalized_watchlist)) or "(empty)"
        raise InvalidSymbolError(
            f"'{candidate}' is not in the current watchlist [{watchlist_display}] — "
            "add it to the watchlist before promoting it"
        )

    return candidate
