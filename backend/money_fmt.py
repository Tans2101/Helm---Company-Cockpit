"""Currency symbols and compact money formatting for Helm.

Add new codes to CURRENCY_SYMBOLS later without changing call sites elsewhere —
callers pass the workspace's financial_settings.currency (default usd).
"""
from __future__ import annotations

# More codes can be added to this table later without code changes elsewhere.
CURRENCY_SYMBOLS = {
    "usd": "$",
    "php": "₱",
    "eur": "€",
    "gbp": "£",
    "sgd": "S$",
    "inr": "₹",
}

DEFAULT_CURRENCY = "usd"


def normalize_currency(code) -> str:
    c = (str(code or DEFAULT_CURRENCY)).strip().lower()
    return c if c in CURRENCY_SYMBOLS else DEFAULT_CURRENCY


def currency_symbol(code="usd") -> str:
    return CURRENCY_SYMBOLS.get(normalize_currency(code), CURRENCY_SYMBOLS[DEFAULT_CURRENCY])


def fmt_money(n, currency="usd") -> str:
    """Format a number with the workspace currency symbol (compact K/M style)."""
    n = float(n or 0)
    neg = n < 0
    a = abs(n)
    sym = currency_symbol(currency)
    if a >= 1_000_000:
        s = f"{sym}{a / 1_000_000:.2f}M"
    elif a >= 999_500:
        # Keep $999,999 from rendering as "$1000K"
        s = f"{sym}{a / 1_000_000:.2f}M"
    elif a >= 1_000:
        # One decimal keeps $1.5K from rounding to $2K
        rounded = round(a / 1_000, 1)
        if rounded >= 1000:
            s = f"{sym}{a / 1_000_000:.2f}M"
        elif rounded == int(rounded):
            s = f"{sym}{int(rounded)}K"
        else:
            s = f"{sym}{rounded:.1f}K"
    else:
        s = f"{sym}{a:,.0f}"
    return f"-{s}" if neg else s


def fmt_money_plain(n, currency="usd") -> str:
    """Full-precision amount with symbol (for signal detail strings)."""
    n = float(n or 0)
    neg = n < 0
    a = abs(n)
    sym = currency_symbol(currency)
    s = f"{sym}{a:,.0f}"
    return f"-{s}" if neg else s
