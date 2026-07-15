"""Universe definitions — at least 30 tickers per region."""
from typing import List

# ── SMID (.SE stock exchange) ──────────────────────────────────
SMID_TICKERS = [
    "AFA.ST", "AGVA.ST", "ALFA.ST", "ALICON.ST", "ASSA.ST",
    "AXA.ST", "BENFA.ST", "BEKI.ST", "BITA.ST", "CAST.ST",
    "COSMOO.ST", "ELEKTA.ST", "ELECTRO.ST", "ELFA.ST", "EXCO.ST",
    "FABIO.ST", "FARST.ST", "GETINGE.ST", "HUSQVARNB.ST", "INFRABO.ST",
    "ITAB.ST", "KINV.ST", "KINNEVIK.ST", "LAGUNITA.ST", "LEMMAN.ST",
    "MIMI.ST", "NIBE.ST", "NORDESKY.ST", "PEAB.ST", "SECO.ST",
    "SELA.ST", "SIAB.ST", "SKF.ST", "SPGSUP.ST", "SVEGO.ST",
    "SWEDMON.ST", "SWECO.ST", "SYNTHIA.ST", "TELIA.ST", "VIVALLA.ST",
    "WESTMANN.ST", "WILLIAM.ST", "AKAB.ST",
]

# ── EU ─────────────────────────────────────────────────────────
EU_TICKERS = [
    "SAP.DE", "SIE.DE", "VOW3.DE", "BMW.DE", "BAS.DE",
    "ADS.DE", "ALV.DE", "DTE.DE", "MUV2.DE", "DB1.DE",
    "AIR.PA", "MC.PA", "OR.PA", "SAN.PA", "TTE.PA",
    "BNP.PA", "ACA.PA", "EN.PA", "RI.PA", "SU.PA",
    "ASML.AS", "PHIA.AS", "INGA.AS", "ADEN.AS", "UNA.AS",
    "AAL.BR", "KBE.BR", "GOVL.BR", "VGA.BR", "PFILL.BR",
    "TEF.MC", "IBE.MC", "SAN.MC", "BBVA.MC", "ITX.MC",
    "ENI.MI", "UCG.MI", "STL.MI", "G.MI", "SU8.MI",
    "NOVN.SW", "NESN.SW", "ROG.SW", "UBSG.SW", "ZURN.SW",
]

# ── US ─────────────────────────────────────────────────────────
US_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "BRK-B", "JPM", "JNJ",
    "V", "UNH", "PG", "HD", "MA",
    "DIS", "PYPL", "ADBE", "NFLX", "CRM",
    "INTC", "CSCO", "PEP", "CMCSA", "ABT",
    "TMO", "COST", "AVGO", "MDT", "BMY",
    "QCOM", "TXN", "LIN", "HON", "LOW",
    "AMGN", "BKNG", "SBUX", "GILD", "ISRG",
    "SYK", "ADI", "VRTX", "REGN", "MU",
]

# ── Asia ───────────────────────────────────────────────────────
ASIA_TICKERS = [
    "7203.T", "6758.T", "9984.T", "6861.T", "8306.T",
    "4502.T", "4063.T", "6954.T", "6981.T", "7974.T",
    "005930.KS", "005600.KS", "035420.KS", "068270.KS", "323410.KS",
    "035720.KS", "207940.KS", "105560.KS", "000660.KS", "012340.KS",
    "070350.KS", "003670.KS", "051910.KS", "006400.KS", "066570.KS",
    "282640.KS", "028260.KS", "000100.KS", "000270.KS", "000810.KS",
    "0001.HK", "0005.HK", "1299.HK", "0700.HK", "0941.HK",
    "2318.HK", "1398.HK", "2628.HK", "0017.HK", "0003.HK",
]


def get_universe(region: str) -> List[str]:
    """Return tickers for a single region."""
    region = region.lower()
    if region == "smid":
        return SMID_TICKERS
    elif region == "eu":
        return EU_TICKERS
    elif region == "us":
        return US_TICKERS
    elif region == "asia":
        return ASIA_TICKERS
    else:
        raise ValueError(f"Unknown region: {region}")


def get_all_universes() -> dict:
    """Return all regions and their tickers."""
    return {
        "smid": SMID_TICKERS,
        "eu": EU_TICKERS,
        "us": US_TICKERS,
        "asia": ASIA_TICKERS,
    }
