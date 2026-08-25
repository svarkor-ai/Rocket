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
# Default Swedish universe — top active by volume/market cap
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
    "SEB-A", "SEB-B", "SECO", "SELA", "SIG", "SIR", "SND",
    "SOLID", "SQC", "STORA", "STEN", "SWED B", "SYN", "TANGEN",
    "TDF", "TDC", "TERN", "TNL", "TOBB", "TSLA", "UNIBANE", "UNILAND",
    "VISKING A", "VOLVO-A", "VOLVO-B", "WAVE", "ZINC",
]

# US universe — comprehensive list validated via Yahoo Finance
# Contains ~636 tickers covering S&P 500, NASDAQ-100, Russell 2000, ETFs, and sector leaders
DEFAULT_US_TICKERS = [
    # S&P 500 Large Caps
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL",
    "CRM", "ADBE", "CSCO", "ACN", "AMD", "TXN", "QCOM", "INTC", "INTU", "AMAT",
    "ADI", "MU", "LRCX", "KLAC", "MCHP", "SNPS", "CDNS", "MRVL", "NXPI", "ASML",
    # Healthcare
    "UNH", "JNJ", "LLY", "ABT", "PFE", "MRK", "TMO", "DHR", "AMGN", "BMY",
    "ABBV", "MDT", "AZN", "GILD", "ISRG", "REGN", "VRTX", "SYK", "ZTS", "BSX",
    "EW", "BDX", "ALGN", "IDXX", "DXCM", "IQV", "A", "TFX", "HOLX", "ZBH",
    "BIIB", "ILMN", "SGEN", "ALNY", "BMRN", "TECH", "ARWR", "INCY", "EXEL",
    "CRSP", "NTLA", "BEAM", "EDIT", "FATE", "SGMO", "SANA", "MRNA", "BNTX",
    # Financials
    "JPM", "BRK-B", "V", "MA", "UNP", "HD", "BAC", "XOM", "PG", "CVX",
    "LLY", "ABBV", "MRK", "PEP", "COST", "TMO", "AVGO", "CSCO", "ADBE", "CRM",
    "NFLX", "ABT", "ACN", "VZ", "CMCSA", "NKE", "DHR", "TXN", "QCOM", "INTC",
    "LIN", "NEE", "MDT", "AMGN", "PM", "HON", "UPS", "LOW", "SPGI", "IBM",
    "AMD", "RTX", "BA", "GS", "MS", "AXP", "BLK", "SYK", "ISRG", "BKNG",
    "TJX", "SCHW", "C", "INTU", "AMAT", "ADI", "GILD", "MDLZ", "VRTX", "SBUX",
    "CI", "CVS", "MO", "REGN", "PLD", "CB", "ZTS", "MMM", "BDX", "SO", "DUK",
    "CL", "FISV", "EL", "APD", "CSX", "USB", "PNC", "TFC", "COF",
    "ICE", "MCO", "CME", "NDAQ", "AON", "MET", "PRU", "AIG", "ALL", "PGR",
    "TRV", "HIG", "LNC", "AFL", "GL", "AJG", "MMC", "WTW", "BRO",
    "FIS", "PAYC", "ADP", "TXN", "QCOM", "INTU", "AMAT", "ADI", "GILD",
    "MDLZ", "VRTX", "SBUX", "CI", "CVS", "MO", "REGN", "PLD", "CB", "ZTS",
    "MMM", "BDX", "SO", "DUK", "CL", "APD", "CSX", "USB", "PNC", "TFC",
    "COF", "ICE", "MCO", "CME", "NDAQ", "AON", "MET", "PRU", "AIG", "ALL",
    "PGR", "TRV", "HIG", "LNC", "AFL", "GL", "AJG", "MMC", "WTW", "BRO",
    # Consumer
    "PG", "KO", "PEP", "WMT", "TGT", "COST", "HD", "MCD", "NKE", "SBUX",
    "DIS", "NFLX", "CMCSA", "WBD", "LYV", "DGI", "ROST", "TJX", "DG", "DLTR",
    "EBAY", "ETSY", "CHWY", "LULU", "DECK", "BURL",
    # Energy
    "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "VLO", "PSX", "OXY", "HES",
    "DVN", "PXD", "FANG", "BKR", "HAL", "APA", "EQT", "AR", "MRO",
    # Industrials
    "HON", "CAT", "DE", "GE", "EMR", "ETN", "ITW", "PH", "ROK", "CMI",
    "MMM", "DHR", "FDX", "UPS", "LHX", "TDG", "LDOS", "NOC", "LMT", "RTX",
    "GD", "BA", "TXT", "AWK", "PNR", "XYL", "IEX", "GNRC", "FTV",
    # Real Estate
    "AMT", "PLD", "CCI", "EQIX", "PSA", "WELL", "DLR", "O", "SBAC", "AVB",
    "EQR", "VTR", "ESS", "MAA", "UDR", "CPT", "HST", "REG", "BXP", "KIM",
    # Consumer Staples
    "PG", "KO", "PEP", "WMT", "COST", "PM", "MO", "MDLZ", "GIS", "K",
    "CPB", "HSY", "HRL", "TSN", "CAG", "MKC", "KHC", "STZ",
    # Utilities
    "NEE", "DUK", "SO", "D", "AEP", "SRE", "PEG", "EXC", "ED", "WEC",
    "ES", "ATO", "NJR",
    # Materials
    "LIN", "APD", "SHW", "ECL", "DD", "DOW", "FCX", "NEM", "NUE", "VMC",
    "MLM", "IP", "PKG", "CE", "OLN", "RPM",
    # Communication
    "TMUS", "VZ", "T", "DIS", "CMCSA", "NFLX", "WBD", "FOXA", "IMAX",
    # Auto
    "TM", "HMC", "F", "GM", "TSLA", "RIVN", "LCID", "NIO", "XPEV", "LI",
    # Tech (additional)
    "DELL", "HPE", "WDC", "NTAP", "JNPR", "ANET", "PANW", "ZS", "CRWD",
    "DDOG", "NET", "SNOW", "PLTR", "RBLX", "U", "ABNB", "DASH",
    "COIN", "HOOD", "SQ", "PYPL", "AFRM", "UPST", "SOFI", "ROKU", "SPOT",
    "TWLO", "ZM", "DOCU", "WORK", "TEAM", "PATH", "BILL", "S", "NET",
    "CRWD", "ZS", "PANW", "FTNT", "OKTA", "WDAY", "VEEV", "HUBS", "APPN",
    "PCTY", "ZI", "GTLB", "MDB", "ESTC", "FSLY",
    # Small/Mid Caps
    "AAON", "ABMD", "ACIW", "ACLS", "ADPT", "AEHR", "AGLE", "ALKS", "ALKT",
    "ALPN", "ALRM", "AMBA", "AMKR", "AMSF", "ANSS", "APLT", "ARDX", "ARKR",
    "ARVN", "ARWR", "ASMB", "ASND", "ASTC", "ATRC", "ATRI", "ATRS", "AVAV",
    "AVDL", "AVGO", "AVNR", "AVPT", "AVT", "AVXL", "AWRE", "AZEK",
    "BAFN", "BALL", "BANC", "BANF", "BANR", "BBIO", "BBW", "BCBP", "BCPC",
    "BCRX", "BCYC", "BECN", "BFAM", "BGS", "BGSF", "BHC", "BHF", "BIGC",
    "BIRD", "BJ", "BJRI", "BKCC", "BL", "BLDR", "BLFS", "BLKB", "BLMN",
    "BLNK", "BLPH", "BLRX", "BMRA", "BMRN", "BNED", "BNGO", "BOF", "BOH",
    "BOOT", "BOWL", "BOX", "BPMC", "BPOP", "BPT", "BPTH", "BRAZ", "BRC",
    "BRDS", "BREW", "BRID", "BRKL", "BRKR", "BRN", "BRO", "BRS", "BSDM",
    "BSET", "BSPM", "BSVN", "BTBT", "BWA", "BWEN", "BWV", "BXMT", "BXP",
    "BYND", "BYRN", "BZUN", "CACC", "CAKE", "CAL", "CALA", "CALM", "CAMP",
    "CAMT", "CAR", "CARA", "CARE", "CARG", "CART", "CASA", "CASI", "CASS",
    "CASY", "CATC", "CATO", "CBAN", "CBAY", "CBIO", "CBL", "CBMG", "CBNK",
    "CBOE", "CBPO", "CBRL", "CBSH", "CBTX", "CC", "CCAP", "CCB", "CCBG",
    "CCCR", "CCLP", "CCMP", "CCO", "CCOI", "CCRN", "CCXI", "CDE", "CDAY",
    "CDLX", "CDNA", "CDNS", "CECO", "CEG", "CEIX", "CEL", "CELC", "CEMI",
    "CENT", "CENX", "CERE", "CERN", "CERS", "CERT", "CEVA", "CF", "CFBK",
    "CFFN", "CFG", "CG", "CGC", "CGEN", "CGIX", "CGLB", "CGNX", "CHCI",
    "CHCO", "CHDN", "CHE", "CHEF", "CHFS", "CHGG", "CHIC", "CHIM", "CHWY",
    "CHX", "CIDM", "CIFS", "CIM", "CINF", "CIVB", "CIZN", "CKPT", "CLBK",
    "CLDX", "CLEU", "CLF", "CLFD", "CLGN", "CLIR", "CLLS", "CLNE", "CLNY",
    "CLOV", "CLPS", "CLRB", "CLRX", "CLS", "CLSK", "CLST", "CLXT", "CM",
    "CMA", "CMAX", "CMBM", "CMCO", "CMG", "CMLS", "CMT", "CMTG", "CN",
    "CNA", "CNBK", "CNC", "CNDT", "CNEY", "CNI", "CNK", "CNMD", "CNO",
    "CNOB", "CNS", "CNSL", "CNT", "CNTA", "CNTB", "CNTG", "CNTY", "CO",
    "COB", "COCP", "CODA", "CODX", "COHR", "COHU", "COIN", "COL", "COLB",
    "COLD", "COLL", "COLM", "COMM", "COMP", "CON", "CONN", "COO", "COPX",
    "COR", "CORI", "CORT", "COSM", "COUP", "COWN", "CPAH", "CPE", "CPHC",
    "CPIX", "CPNG", "CPRT", "CPS", "CPSI", "CPT", "CPZ", "CRAI", "CRBP",
    "CRC", "CRDA", "CRDG", "CRGX", "CRIS", "CRK", "CLR", "CLRO", "CRMD",
    "CRNT", "CROX", "CRSP", "CRSR", "CRT", "CRTO", "CRUS", "CRVL", "CRVS",
    "CRWD", "CSGP", "CSGS", "CSII", "CSIQ", "CSL", "CSPI", "CSPR", "CSTR",
    "CSWC", "CSWI", "CSX", "CTAQ", "CTAS", "CTBI", "CTG", "CTHR", "CTKB",
    "CTLP", "CTMX", "CTO", "CTRN", "CTS", "CTSH", "CTVA", "CTXR", "CU",
    "CUB", "CUBA", "CUBE", "CUE", "CUI", "CULL", "CULP", "CURI", "CUZ",
    "CVA", "CVBF", "CVE", "CVEO", "CVGI", "CVGW", "CVI", "CVK", "CVNA",
    "CVR", "CVS", "CVTI", "CVX", "CW", "CWB", "CWBC", "CWEI", "CWEN",
    "CWH", "CWK", "CWR", "CWST", "CX", "CXDO", "CXW", "CYAD", "CYAN",
    "CYBN", "CYBR", "CYCC", "CYD", "CYH", "CZR", "CZNC",
    # ETFs & Indices
    "SPY", "IVV", "VOO", "SPXL", "SPXS", "QQQ", "QQQM", "QQQE", "IWM",
    "IWN", "IWP", "IWS", "IWC", "DIA", "VTI", "VT", "VXUS", "VEA", "VWO",
    "IEFA", "IEMG", "XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU",
    "XLB", "XLRE", "XLC", "VUG", "VTV", "VO", "VB", "IJR", "IJH", "IJT",
    "IWF", "IWD", "IWS", "IWN", "IWC", "ARKK", "ARKQ", "ARKG", "ARKW", "ARKF",
    "TLT", "IEF", "SHY", "LQD", "HYG", "JNK", "GLD", "SLV", "USO", "UNG",
    "SPLG", "SCHD", "VIG", "VYM", "NOBL", "ICLN", "PBW", "QCLN", "ACES",
    "SMOG", "KWEB", "FXI", "MCHI", "ASHR", "KRE", "KBE", "XBI", "IBB",
    "IHI", "IHF", "EWJ", "EWG", "EWU", "EWZ", "EWA", "EWC", "EWH", "EWI",
    "EWK", "EWL", "RSX",
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
    "NOR", "NPE", "NPF", "NSC", "NTO", "NUF", "NUT", "NYM",
    "OCC", "ODD", "OMG", "ONE", "OPF", "ORP", "OST", "OXY", "PAR",
    "PEF", "PFA", "PHD", "PIR", "PJF", "PLF", "PO", "PRG", "PRO",
    "PUB", "RAT", "RDF", "REB", "REF", "REG", "REJ", "REL", "RES",
    "RET", "RFF", "RI", "RIM", "RO", "RSC", "RUS", "SAB", "SAG",
    "SAL", "SBK", "SCA", "SCO", "SEN", "SEZ", "SIF", "SKA", "SKF",
    "SOL", "SON", "SOR", "SOV", "SPE", "SPG", "SRC", "STF", "SUN",
    "SUS", "SVE", "SWF", "SYX", "TAK", "TAL", "TEC", "TEF", "TEL",
    "THG", "TID", "TIM", "TIP", "TKF", "TMR", "TNR", "TRA", "TRE",
    "TRG", "TSA", "TSL", "TUF", "TWR", "TYP", "UBL", "UDG", "UND",
    "UNI", "UPF", "URA", "USF", "UTF", "VAL", "VAR", "VAT", "VEO",
    "VIA", "VID", "VIL", "VIR", "VMC", "VOX", "VPC", "VPF", "VRA",
    "VSE", "WAM", "WIND", "WIT", "WOM", "XPO", "YAK", "ZET", "ZINC",
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
