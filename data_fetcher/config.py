"""
Config & paths for the data-fetcher pipeline.
"""
import os
from pathlib import Path

# Base directories
ROOT = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = ROOT / "data" / "parquet"
CACHE_DIR = ROOT / "data" / "cache"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Rate limiting / throttling
REQUEST_DELAY = 0.5  # seconds between requests
BATCH_SIZE = 50
BATCH_PAUSE = 30  # seconds between batches

# OpenAvanza (Swedish stocks)
OPENAVANGA_API = "https://api.openavanza.se"
# Default Swedish universe — top活跃 by volume/market cap
DEFAULT_SE_TICKERS = [
    "AFA", "ALFA", "AMERA", "ATTICON-A", "ATTICON-B", "AXFO", "BEAKER-A",
    "BECH", "BIOKN", "BKFC-A", "BKFC-B", "BOL", "BOX", "BRF A", "BRF B",
    "CALIF", "CAP", "COMHEM", "CONNOVER-A", "CONNOVER-B", "COSMOS", "CYSEC",
    "DIAN", "ELECTROLUX-A", "ELECTROLUX-B", "ESSITY-A", "ESSITY-B", "FABIAN",
    "FAH", "FAROT", "FARSTAGROW", "FIB", "FJO", "GASKR", "GET", "GLEN",
    "GMLA", "GSM", "HALOF", "HEX A", "HEX B", "HM", "HOTNORD", "HTG B",
    "IFU", "IKANO-A", "IKANO-B", "ISS-A", "ISS-B", "JAV", "JCC", "KIRK",
    "L M Ericsson-A", "L M Ericsson-B", "LANTMEST", "LUMI", "MALT",
    "MAP", "MATTEUS", "MECO", "MERIAN", "MIM", "MODI", "MOB", "MONOLIT",
    "NORDEA-A", "NORDEA-B", "NPI", "NTEST", "OLIN", "OMX", "OP", "ORION",
    "PEAB A", "PEAB B", "PHARMEC", "PILED", "PREMIER", "PYRO", "QVI B",
    "REJLUNDS", "RICCO", "SAB", "SANDESK A", "SANDESK B", "SKF-B",
    "SKF-B", "SEB-A", "SEB-B", "SECO", "SELA", "SIG", "SIR", "SND",
    "SOLID", "SQC", "STORA", "STEN", "SWED B", "SYN", "TANGEN",
    "TDF", "TDC", "TERN", "TNL", "TOBB", "TSLA", "UNIBANE", "UNILAND",
    "VISKING A", "VOLVO-A", "VOLVO-B", "WAVE", "ZINC",
]

# US universe — large/mid caps (the ones we care about)
DEFAULT_US_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA", "BRK-B",
    "UNH", "JNJ", "V", "WMT", "LLY", "XOM", "JPM", "PG", "MA", "HD",
    "CVX", "MRK", "ABBV", "COST", "PEP", "KO", "AVGO", "ADBE", "MCD",
    "TMO", "CSCO", "ACN", "ABT", "CRM", "NFLX", "AMD", "DHR", "VZ",
    "INTC", "CMCSA", "NKE", "TXN", "QCOM", "PM", "DIS", "UNP", "RTX",
    "HON", "NEE", "UPS", "LOW", "SBUX", "INTU", "AMGN", "BLK", "BA",
    "ISRG", "GE", "AXP", "DE", "NOW", "BKNG", "TJX", "GILD", "LMT",
    "SPGI", "MDLZ", "CVS", "MMM", "CI", "MO", "ZTS", "SCHW", "SYK",
    "BDX", "TMUS", "CB", "SO", "DUK", "F", "GM", "AEP", "PEAK",
    "CSX", "EOG", "USB", "ITW", "NSC", "SHW", "CL", "APD", "FCX",
    "ICE", "CME", "NSC", "MMC", "PSA", "ADP", "EQIX", "COF", "TGT",
    "SLB", "PGR", "TRV", "FDX", "WFC", "AMAT", "MCO", "PSX",
    "HUM", "EMR", "GM", "F", "PYPL", "SQ", "SHOP", "UBER", "LYFT",
    "SNAP", "PINS", "ROKU", "ZM", "DOCU", "CRWD", "NET", "DDOG",
    "SNOW", "PLTR", "COIN", "RBLX", "U", "DKNG",
]

# Crypto — top coins by market cap
DEFAULT_CRYPTO_COINS = [
    "bitcoin", "ethereum", "binancecoin", "solana", "ripple",
    "cardano", "dogecoin", "polkadot", "litecoin", "chainlink",
    "uniswap", "stellar", "cosmos", "monero", "ethereum-classic",
    "avalanche", "tron", "matic-network", "aave", "algorand",
    "filecoin", "hedera", "vechain", "tezos", "elrond",
    "theta", "axie-infinity", "flow", "gala", "sandbox",
    "decentraland", "shiba-inu", "polygon", "internet-computer",
    "sui", "sei", "kaspa", "aptos", "celestia", "injective",
    "render-token", "fantom", "sonic", "optimism", "arbitrum",
]

# Market-cap based universe extensions
SE_EXTENDED = [
    "AGFO", "AIQ", "ANDER", "ARE", "ASAB", "ASCO", "ATCO-A", "ATCO-B",
    "ATCO-C", "ATCO-D", "AUTUMN", "BAKK", "BANE", "BATH", "BECOTEC",
    "BERN", "BIOVACC", "BIT", "BKT", "BLK", "BOAB", "BON", "BOXO",
    "CITUS", "CLIM", "CNH", "COHANCE", "COM42", "CONCENT", "CRED",
    "DAT", "DB-LAG", "DENS", "DERO", "DIAB", "DING", "DUN", "EASE",
    "EBAB", "EDB", "EG", "EICA", "ELM", "EMT", "ENEA", "ENGO",
    "EQT-A", "EQT-B", "ERST", "ETON", "ETN", "EXE", "FAB", "FALM",
    "FIBO", "FIL", "FINSE", "FJ", "FO", "FRESK", "FRI", "FRIH",
    "FRO", "FSB", "FSA", "FTX", "G", "GAB", "GAS", "GAV", "GDM",
    "GEN", "GET", "GJ", "GLS", "GMG", "GOTH", "GP", "GRE", "GRI",
    "GRO", "GSV", "GUD", "GUN", "GUT", "HAB", "HACK", "HALO", "HANS",
    "HEX-A", "HIQ", "HOF", "HOL", "HUB", "HYG", "ICA", "ICG", "IDA",
    "IFU", "IKT", "ILF", "IM", "IND", "INM", "INT", "IRI", "ISU",
    "IVC", "JAZZ", "JDE", "JEP", "JOH", "JUM", "KAR", "KB", "KIB",
    "KLA", "KN", "KPN", "KRC", "KRZ", "KSM", "KUN", "KYA", "LAD",
    "LAG", "LAND", "LAP", "LB", "LIC", "LIF", "LIN", "LIT", "LMF",
    "LOK", "LUMI", "MAB", "MAD", "MAF", "MAN", "MAS", "MED", "MET",
    "MIO", "MKT", "MLF", "MLT", "MMF", "MOM", "MOT", "MPC", "MPF",
    "MRN", "MTC", "MTG", "MUD", "MUN", "MUS", "MX", "MZA", "MYL",
    "NAT", "NAV", "NEA", "NEO", "NET", "NIB", "NIL", "NJC", "NKT",
    "NOR", "NOR", "NPE", "NPF", "NSC", "NTO", "NUF", "NUT", "NYM",
    "OCC", "ODD", "OMG", "ONE", "OPF", "ORP", "OST", "OXY", "PAR",
    "PEF", "PFA", "PHD", "PIR", "PJF", "PLF", "PO", "PRG", "PRO",
    "PUB", "RAT", "RDF", "REB", "REF", "REG", "REJ", "REL", "RES",
    "RET", "RFF", "RI", "RIM", "RO", "RSC", "RUS", "SAB", "SAB",
    "SAG", "SAL", "SBK", "SCA", "SCO", "SEN", "SEZ", "SIF", "SIR",
    "SKA", "SKF", "SOL", "SON", "SOR", "SOV", "SPE", "SPG", "SRC",
    "STF", "SUN", "SUS", "SVE", "SWF", "SYX", "TAK", "TAL", "TEC",
    "TEF", "TEL", "THG", "TID", "TIM", "TIP", "TKF", "TMR", "TNR",
    "TRA", "TRE", "TRG", "TSA", "TSL", "TUF", "TWR", "TYP", "UBL",
    "UDG", "UND", "UNI", "UPF", "URA", "USF", "UTF", "VAL", "VAR",
    "VAT", "VEO", "VIA", "VID", "VIL", "VIR", "VMC", "VOX", "VPC",
    "VPF", "VRA", "VSE", "WAM", "WIND", "WIT", "WOM", "XPO", "YAK",
    "ZET", "ZINC",
]

# Country codes for yfinance
COUNTRY_CODES = {
    "germany": ".DE",
    "france": ".PA",
    "spain": ".MC",
    "uk": ".L",
    "japan": ".T",
    "australia": ".AX",
    "india": ".NS",
    "canada": ".TO",
    "brazil": ".SA",
    "china": ".SS",
}
