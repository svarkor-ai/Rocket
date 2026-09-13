"""Rocket single source of truth for region metadata (C4).

One registry region->{yahoo_suffixes, label, exchange, tz} from which ALL
consumers derive, so a region key/label/suffix can never drift:
  (a) universe.py REGION_LABELS / REGION_DEFAULTS (label, exchange, tz),
  (b) symbols.py REGION_SUFFIX (yahoo_suffixes) — M3 already extended it with
      .OL/.CO/.HE and kept it in sync with this table manually; see DESIGN F3,
  (c) the 914.1 generator REGION_DISPLAY/ORDER (M7) — label + iteration order.

Scope of THIS card (M4): the sweden/thin regions M4 manages + the new no/dk/fi
trio. Regions out of M4 scope (usa, uk, australia, canada, switzerland, ...) are
listed here too with their existing metadata so the registry is complete and the
I4 validation can cover every cache region key; M4 does not re-derive their lists.

Design: /srv/workspace/rocket-region-universe/architect/DESIGN.md REV 2, C4.
Card 947.5 (T4, M4).
"""

from __future__ import annotations

# region -> {suffixes (tuple, primary first), label, exchange, timezone}
REGION_META: dict[str, dict] = {
    # --- M4-managed regions (sweden/thin lists now generated from raw files) ---
    "sweden":     {"suffixes": (".ST",), "label": "Sverige",   "exchange": "STO",             "timezone": "Europe/Stockholm"},
    "norway":     {"suffixes": (".OL",), "label": "Norge",     "exchange": "OSL",             "timezone": "Europe/Oslo"},
    "denmark":    {"suffixes": (".CO",), "label": "Danmark",   "exchange": "CPH",             "timezone": "Europe/Copenhagen"},
    "finland":    {"suffixes": (".HE",), "label": "Finland",   "exchange": "HEL",             "timezone": "Europe/Helsinki"},
    "germany":    {"suffixes": (".DE",), "label": "Tyskland",  "exchange": "XETRA",           "timezone": "Europe/Berlin"},
    "france":     {"suffixes": (".PA",), "label": "Frankrike", "exchange": "Euronext Paris",  "timezone": "Europe/Paris"},
    "japan":      {"suffixes": (".T",),  "label": "Japan",     "exchange": "TSE",             "timezone": "Asia/Tokyo"},
    "hongkong":   {"suffixes": (".HK",), "label": "Hongkong",  "exchange": "HKEX",            "timezone": "Asia/Hong_Kong"},
    "china":      {"suffixes": (".SS", ".SZ"), "label": "Kina", "exchange": "SSE/SZSE",       "timezone": "Asia/Shanghai"},
    "india":      {"suffixes": (".NS", ".BO"), "label": "Indien", "exchange": "NSE/BSE",      "timezone": "Asia/Kolkata"},
    "korea":      {"suffixes": (".KS", ".KQ"), "label": "Sydkorea", "exchange": "KRX",        "timezone": "Asia/Seoul"},
    # --- Out-of-M4-scope regions (lists untouched this card) ---
    # 'international' is a BACKWARD-COMPATIBILITY aggregate emitted by
    # universe_builder (union of all non-US regions). It is NOT a single market,
    # so it carries no single Yahoo suffix/exchange/tz — None/Global/UTC are
    # descriptors, not market facts. Card 987.2 (B2, M8-unblock): its cache key
    # must resolve in C4 so I4 (no invisible region) holds. Data audit 987.2:
    # 5,595 tickers, of which ~5,559 (99.36%) are byte-identical duplicates of
    # their proper region buckets; the 36 unique members are mis-suffixed Swiss
    # blue-chips (.SZ/.SN/.A) — a data-quality item for a future cleanup card.
    "international": {"suffixes": (None,), "label": "Internationell", "exchange": "Global", "timezone": "UTC"},
    "usa":        {"suffixes": (None,), "label": "USA",        "exchange": "NYSE/NASDAQ",     "timezone": "America/New_York"},
    "uk":         {"suffixes": (".L",), "label": "UK",         "exchange": "LSE",             "timezone": "Europe/London"},
    "australia":  {"suffixes": (".AX",), "label": "Australien", "exchange": "ASX",            "timezone": "Australia/Sydney"},
    "canada":     {"suffixes": (".TO", ".V"), "label": "Kanada", "exchange": "TSX",           "timezone": "America/Toronto"},
    "switzerland":{"suffixes": (".SW",), "label": "Schweiz",   "exchange": "SIX",             "timezone": "Europe/Zurich"},
    "brazil":     {"suffixes": (".SA",), "label": "Brasilien", "exchange": "BOVESPA",         "timezone": "America/Sao_Paulo"},
    "singapore":  {"suffixes": (".SI",), "label": "Singapore", "exchange": "SGX",             "timezone": "Asia/Singapore"},
}

# The M4 DoD canonical suffix set for generated region lists.
DOD_SUFFIXES = {".ST", ".OL", ".CO", ".HE", ".PA", ".DE", ".T",
                ".HK", ".KS", ".NS", ".BO"}
