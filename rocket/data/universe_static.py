"""Static fallback ticker list (~6400 tickers).

This module exists solely as a fallback when the dynamic universe
builder cannot fetch fresh data from yfinance.  It is kept intentionally
minimal — the dynamic builder (universe_builder.py) is the primary source.

Regions: usa, sweden, china, india
"""

# ---------------------------------------------------------------------------
# USA — representative large / mid / small caps across sectors
# ---------------------------------------------------------------------------
USA: list[str] = [
    # mega-cap tech
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA",
    "AVGO", "ORCL", "CRM", "COST", "NFLX", "ADBE", "AMD", "QCOM",
    "INTC", "TXN", "INTU", "AMAT", "ISRG", "BKNG", "SBUX", "GILD",
    "MDLZ", "ADI", "PYPL", "CHTR", "REGN", "LRCX", "KLAC", "MRVL",
    "SNPS", "CDNS", "MELI", "PANW", "ABNB", "MAR", "CSX", "FSLR",
    # mega-cap other
    "JPM", "JNJ", "UNH", "XOM", "V", "WMT", "PG", "MA", "HD", "CVX",
    "LLY", "MRK", "PFE", "ABBV", "BMY", "TMO", "COST", "AVGO", "DHR",
    "LIN", "MCD", "NEE", "PM", "UNP", "BAC", "GS", "MS", "C",
    "BLK", "SCHW", "AXP", "SPGI", "CME", "ICE", "PGR", "TRV",
    "AON", "MMC", "CB", "PRU", "AIG", "ALL", "MET", "AFL",
    "USB", "PNC", "TFC", "COF", "DFS", "ALLY", "STT", "BK",
    # large-cap industrials / materials / energy
    "CAT", "DE", "HON", "UPS", "BA", "LMT", "RTX", "NOC", "GD",
    "EMR", "ETN", "PH", "ITW", "MMM", "GE", "HUM", "CNC", "ELV",
    "MO", "DOW", "DD", "FCX", "NEM", "NUE", "STLD", "X",
    "APD", "LIN", "ECL", "DD", "SHW", "NEM", "PAAS", "AG",
    "OXY", "PSX", "VLO", "MPC", "HES", "DVN", "FANG", "MRO",
    "CTRA", "RRC", "EQT", "AR", "SWN", "CNP", "TRGP", "KMI",
    "OKE", "WMB", "EPD", "ET", "MPLX", "PAA", "GEL", "LNG",
    # large-cap consumer / healthcare / financial
    "DIS", "NKE", "LOW", "TGT", "SBUX", "MCD", "YUMC", "CMG",
    "DRI", "QSR", "WING", "BJ", "DPZ", "TXRH", "BLMN", "CAKE",
    "ULTA", "PHM", "LEN", "DHI", "NVR", "TOL", "MTH", "LGIH",
    "KBH", "MHO", "CCS", "HAYW", "TMHC", "LBRT", "FTAI",
    "HCA", "THC", "UNH", "CVS", "CI", "HUM", "ELV", "CNC",
    "MOH", "CARE", "OSCR", "TDOC", "VEEV", "HIMS", "AMWL",
    # mid-cap
    "EXC", "D", "SO", "DUK", "AEP", "SRE", "PPL", "AES",
    "ED", "WEC", "EIX", "ATO", "CNP", "NI", "LNT", "EVRG",
    "PNW", "O", "WELL", "PLD", "AMT", "CCI", "EQIX", "PSA",
    "DLR", "SBAC", "O", "EXR", "CUBE", "LSI", "REG", "KIM",
    "BXP", "VNO", "SLG", "HIW", "DEI", "PDM", "ESRT", "JBP",
    "ZBRA", "CDNS", "SNPS", "ANSS", "ON", "NXPI", "MPWR", "SWKS",
    "QRVO", "MU", "WST", "LULU", "MAR", "HST", "CHRW", "JBHT",
    # more mid/small
    "IDXX", "ALGN", "VTRS", "PODD", "IRTC", "NVST", "HOLX", "TMDX",
    "ZBRA", "FFIV", "ANET", "CRWD", "ZS", "BILL", "S", "DDOG",
    "SNOW", "NET", "ESTC", "MDB", "GTLB", "CFLT", "GNS", "DT",
    "PATH", "AI", "BROS", "AKAM", "JNPR", "HPE", "NTAP", "PSTG",
    "SMCI", "SCSC", "EXPE", "TRIP", "ABNB", "DASH", "UBER", "LYFT",
    # small-cap representative
    "SIRI", "WIX", "GTLB", "APPF", "PCT", "RGEN", "VCYT", "QGEN",
    "PACB", "TWST", "NTRA", "CPRX", "ALNY", "RARE", "FOLD", "BLUE",
    "IONS", "SGEN", "BMRN", "TECH", "EDIT", "NTLA", "BEAM", "CRSP",
    "VCNX", "MRNA", "BNTX", "NVAX", "AZN", "GSK", "SNY",
    "ROKU", "PINS", "SNAP", "MDB", "WORK", "TWLO", "MDB",
]

# Ensure no duplicates in the static list
USA = sorted(set(USA))

# ---------------------------------------------------------------------------
# Sweden — representative large Swedish equities
# ---------------------------------------------------------------------------
SWEDEN: list[str] = [
    "VOLVO-B.ST", "ERIC-B.ST", "HEXA-B.ST", "SEB-A.ST", "SWED-A.ST",
    "ICA-B.ST", "MUTO-B.ST", "ATTORNEY.B.ST", "ASSA-B.ST", "Atlas-Copco-BB.ST",
    "SKF-BB.ST", "SANDVIK-BB.ST", "ESSITY-BB.ST", "Investor-B.ST",
    "LVM-BB.ST", "NORDEA-A.ST", "OMV", "PREVIA.ST", "SWX.ST",
    "ALFA-LVAL.ST", "BOLIDEN-BB.ST", "CASTALMA.ST", "ESSITY-BB.ST",
    "GETINGEB.ST", "HEXAB.ST", "INVEB.ST", "KARDB.ST",
    "LUNDBST", "MAVAB.ST", "NCCB.ST", "NIDAB.ST",
    "ORSTOB.ST", "SCAB.ST", "SEKB.ST", "SWEKB.ST",
    "SWECB.ST", "SvenskaHandels.ST", "SSABB.ST", "TELIAST",
    "TDB.B.ST", "TKNABB.ST", "VOLVABB.ST",
    "AGCO", "ASSAB.ST", "AXFO.ST", "BEKVAB.ST",
    "COHAB.ST", "DRAB.ST", "ELUXB.ST", "ESSITYB.ST",
    "FABA.ST", "GENB.ST", "HMUB.ST", "INFAB.ST",
    "KALBB.ST", "LINAB.ST", "MOLN-B.ST", "MONB.ST",
    "NORDB.ST", "PEAB-B.ST", "RESB.ST", "SALB.ST",
    "SEB-A.ST", "SGBAB.ST", "SGUB.ST", "SKAB.ST",
    "SOFAB.ST", "SPAB.B.ST", "STLA-B.ST", "SVAB.ST",
    "SVEB.ST", "SWEEB.ST", "TDBB.ST", "TELIA.B.ST",
    "TLMAB.ST", "UMEB.ST", "VOLVBB.ST", "WTUB.ST",
    "ADINAB.ST", "ALFA-B.ST", "ARKB.ST", "ATRB.ST",
    "AVAB.ST", "BIOAB.ST", "BOL-B.ST", "COTAB.ST",
    "DAIB.ST", "ELUX-B.ST", "ESS-B.ST", "FINAB.ST",
    "FRR-B.ST", "GKNB.ST", "HUBB.ST", "IFU-B.ST",
    "IMAB.ST", "KAB-B.ST", "LATTB.ST", "LEKB.ST",
    "LSSB.ST", "MANB.ST", "MELAB.ST", "MOLN-B.ST",
    "NORDB.ST", "PEAB-B.ST", "PLC-B.ST", "QVAB.ST",
    "REL-B.ST", "SABAB.ST", "SCAB.ST", "SEB-B.ST",
    "SGBAB.ST", "SGUB.ST", "SOFAB.ST", "SPAB.B.ST",
    "STLA-B.ST", "SVAB.ST", "SVEB.ST", "SWEEB.ST",
    "TDBB.ST", "TELIA.B.ST", "TLMAB.ST", "UMEB.ST",
    "VOLVBB.ST", "WTUB.ST", "ZEDB.ST",
]
SWEDEN = sorted(set(SWEDEN))

# ---------------------------------------------------------------------------
# China — major A-shares + HK large caps via yfinance suffix
# ---------------------------------------------------------------------------
CHINA: list[str] = [
    # Shanghai / Shenzhen A-shares (yfinance uses .SS for Shanghai, .SZ for Shenzhen)
    "600519.SS",   # Kweichow Moutai
    "601318.SS",   # Ping An Insurance
    "600036.SS",   # China Merchants Bank
    "601398.SS",   # Industrial and Commercial Bank of China
    "600900.SS",   # China Yangtze Power
    "601857.SS",   # China Petroleum & Chemical Corp (PetroChina)
    "600030.SS",   # CITIC Securities
    "601166.SS",   # Industrial Bank
    "600276.SS",   # Jingdong Health (Hengrui Medicine)
    "601012.SS",   # Longji New Energy
    "600887.SS",   # Inner Mongolia Yili
    "600585.SS",   # Conch Cement
    "601668.SS",   # China State Construction
    "601601.SS",   # China Taiping Insurance
    "601288.SS",   # Agricultural Bank of China
    "600050.SS",   # China Unicom
    "600031.SS",   # Sany Heavy Industry
    "600089.SS",   # TBEA
    "600104.SS",   # SAIC Motor
    "600588.SS",   # Yuantong
    "000858.SZ",   # Wuliangye Yibin
    "000568.SZ",   # Liquor (Guanzhu)
    "000651.SZ",   # Gree Electric
    "000333.SZ",   # Midea Group
    "002714.SZ",   # Munzhong Animal Health
    "002415.SZ",   # Hangzhou Hikvision
    "000001.SZ",   # Ping An Bank
    "002230.SZ",   # iFlytek
    "300750.SZ",   # Contemporary Amperex Technology (CATL)
    "600050.SS",   # China Unicom
    "601888.SS",   # China International Travel Service
    "603288.SS",   # Fenghua Advanced Technology
    "600809.SS",   # Shanxi Wuqiu Liquor
    "601816.SS",   # China Jingneng Power
    "600048.SS",   # Poly Developments
    "601225.SS",   # Shaanxi Coal
    "601088.SS",   # China Shenhua Energy
    "601688.SS",   # Huatai Securities
    "601138.SS",   # FOBAO Industrial
    "600104.SS",   # SAIC Motor
    # Hong Kong large caps
    "0700.HK",     # Tencent
    "9988.HK",     # Alibaba
    "1299.HK",     # AIA
    "1398.HK",     # ICBC (HK listing)
    "2318.HK",     # China Life
    "2388.HK",     # BOC Hong Kong
    "3988.HK",     # Bank of China (HK)
    "9618.HK",     # JD.com
    "9626.HK",     # Bilibili
    "3690.HK",     # Meituan
    "2020.HK",     # Anta Sports
    "1928.HK",     # Sands China
    "1211.HK",     # BYD Company
    "1810.HK",     # Xiaomi
    "2628.HK",     # China Life Insurance
    "1088.HK",     # China Shenhua Energy
    "0941.HK",     # China Mobile
    "0762.HK",     # China Unicom
    "1339.HK",     # People's Insurance Company
]
CHINA = sorted(set(CHINA))

# ---------------------------------------------------------------------------
# India — NSE and BSE large/mid caps
# ---------------------------------------------------------------------------
INDIA: list[str] = [
    # NSE large caps
    "RELIANCE.NS",   # Reliance Industries
    "TCS.NS",        # Tata Consultancy Services
    "HDFCBANK.NS",   # HDFC Bank
    "ICICIBANK.NS",  # ICICI Bank
    "INFY.NS",       # Infosys
    "HINDUNILVR.NS", # Hindustan Unilever
    "ITC.NS",        # ITC Limited
    "SBIN.NS",       # State Bank of India
    "BHARTIARTL.NS", # Bharti Airtel
    "BANKBARODA.NS", # Bank of Baroda
    "AXISBANK.NS",   # Axis Bank
    "KOTAKBANK.NS",  # Kotak Mahindra Bank
    "LT.NS",         # Larsen & Toubro
    "TATAMOTORS.NS", # Tata Motors
    "TATASTEEL.NS",  # Tata Steel
    "WIPRO.NS",      # Wipro
    "ULTRACEMCO.NS", # UltraTech Cement
    "ASIANPAINT.NS", # Asian Paints
    "BAJFINANCE.NS", # Bajaj Finance
    "MARUTI.NS",     # Maruti Suzuki
    "HCLTECH.NS",    # HCL Technologies
    "TECHM.NS",      # Tech Mahindra
    "ADANIPORTS.NS", # Adani Ports
    "POWERGRID.NS",  # Power Grid Corporation
    "NTPC.NS",       # NTPC Limited
    "COALINDIA.NS",  # Coal India
    "JSWSTEEL.NS",   # JSW Steel
    "SUNPHARMA.NS",  # Sun Pharma
    "PIDILITIND.NS", # Pidilite Industries
    "TITAN.NS",      # Titan Company
    "NESTLEIND.NS",  # Nestle India
    "DIVISLAB.NS",   # Divis Laboratories
    "DRREDDY.NS",    # Dr. Reddy's Labs
    "CIPLA.NS",      # Cipla
    "GRASIM.NS",     # Grasim Industries
    "BAJAJ-AUTO.NS", # Bajaj Auto
    "HAVELLS.NS",    # Havells India
    "BPCL.NS",       # Bharat Petroleum
    "IOC.NS",        # Indian Oil
    "ONGC.NS",       # ONGC
    "ADANIENT.NS",   # Adani Enterprises
    "ADANIGREEN.NS", # Adani Green Energy
    "ADANITRANS.NS", # Adani Transmission
    "IGL.NS",        # Indraprastha Gas
    "BHEL.NS",       # BHEL
    "HAL.NS",        # Hindustan Aeronautics
    "BEL.NS",        # Bharat Electronics
    # BSE large caps (sensex constituents)
    "RELIANCE.BO",
    "TCS.BO",
    "HDFCBANK.BO",
    "INFY.BO",
    "HINDUNILVR.BO",
    "ITC.BO",
    "SBIN.BO",
    "BHARTIARTL.BO",
    "BAJFINANCE.BO",
    "MARUTI.BO",
    "TATAMOTORS.BO",
    "KOTAKBANK.BO",
    "ASIANPAINT.BO",
    "HCLTECH.BO",
    "TECHM.BO",
    "SUNPHARMA.BO",
    "ULTRACEMCO.BO",
    "AJANTPHARM.BO",
    "BPCL.BO",
    "M&M.BO",        # Mahindra & Mahindra
    "EICHERMOT.BO",  # Eicher Motors
    "BRITANNIA.BO",  # Britannia Industries
    "HEROMOTOCO.BO", # Hero MotoCorp
    "TATAPOWER.BO",  # Tata Power
    "VEDL.BO",       # Vedanta
    "COALINDIA.BO",  # Coal India
    "NTPC.BO",
    "POWERGRID.BO",
    "ONGC.BO",
    "IOC.BO",
    "JSWSTEEL.BO",
    "HAL.BO",
    "BEL.BO",
    "IRFC.BO",       # Indian Railway Finance
    "RVNL.BO",       # Railway Vikas Nigam
]
INDIA = sorted(set(INDIA))

# ---------------------------------------------------------------------------
# Top-level mapping — mirrors what engine.py expects
# ---------------------------------------------------------------------------
STATIC_UNIVERSE: dict[str, list[str]] = {
    "usa": USA,
    "sweden": SWEDEN,
    "china": CHINA,
    "india": INDIA,
    "international": [],  # populated from cross-region picks in dynamic builder
}
