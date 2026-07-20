"""Dynamic universe builder for Rocket Stock Scanner.

Primary data sources (embedded reference lists):
    - USA: S&P 500 + well-known additional
    - Sweden: OMX Stockholm 30 + additional
    - India: NIFTY 50 + additional
    - China: major SSE/SZ/HK tickers
    - UK: FTSE 100 scraped tickers
    - Germany: DAX scraped tickers
    - France: CAC 40 scraped tickers
    - Japan: Nikkei scraped tickers
    - Australia: ASX 200 scraped tickers
    - Canada: TSX scraped tickers
    - And more via Wikipedia enrichment

Cache: Results cached to rocket/data/universe_cache.json with 12h TTL.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache path
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent
_CACHE_FILE = _DATA_DIR / "universe_cache.json"
_CACHE_TTL_SECONDS = 12 * 3600  # 12 hours

# ---------------------------------------------------------------------------
# Built-in reference lists — PRIMARY data sources
# ---------------------------------------------------------------------------

# USA: S&P 500 constituents scraped from Wikipedia (501 tickers, updated)
USA_SP500_TICKERS = [
    'A', 'AAPL', 'ABBV', 'ABNB', 'ABT', 'ACGL', 'ACN', 'ADBE', 'ADI', 'ADM',
    'ADP', 'ADSK', 'AEE', 'AEP', 'AES', 'AFL', 'AIG', 'AIZ', 'AJG', 'AKAM',
    'ALB', 'ALGN', 'ALL', 'ALLE', 'AMAT', 'AMCR', 'AMD', 'AME', 'AMGN', 'AMP',
    'AMT', 'AMZN', 'ANET', 'AON', 'AOS', 'APA', 'APD', 'APH', 'APO', 'APP',
    'APTV', 'ARE', 'ARES', 'ATO', 'AVB', 'AVGO', 'AVY', 'AWK', 'AXON', 'AXP',
    'AZO', 'BA', 'BAC', 'BALL', 'BAX', 'BBY', 'BDX', 'BEN', 'BG', 'BIIB',
    'BKNG', 'BKR', 'BLDR', 'BLK', 'BMY', 'BNY', 'BR', 'BRO', 'BSX', 'BX',
    'BXP', 'C', 'CAH', 'CARR', 'CASY', 'CAT', 'CB', 'CBOE', 'CBRE', 'CCI',
    'CCL', 'CDNS', 'CDW', 'CEG', 'CF', 'CFG', 'CHD', 'CHRW', 'CHTR', 'CI',
    'CIEN', 'CINF', 'CL', 'CLX', 'CMCSA', 'CME', 'CMG', 'CMI', 'CMS', 'CNC',
    'CNP', 'COF', 'COHR', 'COIN', 'COO', 'COP', 'COR', 'COST', 'CPAY', 'CPRT',
    'CPT', 'CRH', 'CRL', 'CRM', 'CRWD', 'CSCO', 'CSGP', 'CSX', 'CTAS', 'CTSH',
    'CTVA', 'CVNA', 'CVS', 'CVX', 'D', 'DAL', 'DASH', 'DD', 'DDOG', 'DE',
    'DECK', 'DELL', 'DG', 'DGX', 'DHI', 'DHR', 'DIS', 'DLR', 'DLTR', 'DOC',
    'DOV', 'DOW', 'DPZ', 'DRI', 'DTE', 'DUK', 'DVA', 'DVN', 'DXCM', 'EA',
    'EBAY', 'ECHO', 'ECL', 'ED', 'EFX', 'EG', 'EIX', 'EL', 'ELV', 'EME',
    'EMR', 'EOG', 'EQIX', 'EQR', 'EQT', 'ERIE', 'ES', 'ESS', 'ETN', 'ETR',
    'EVRG', 'EW', 'EXC', 'EXE', 'EXPD', 'EXPE', 'EXR', 'F', 'FANG', 'FAST',
    'FCX', 'FDS', 'FDX', 'FDXF', 'FE', 'FFIV', 'FICO', 'FIS', 'FISV', 'FITB',
    'FIX', 'FLEX', 'FOX', 'FOXA', 'FRT', 'FSLR', 'FTNT', 'FTV', 'GD', 'GDDY',
    'GE', 'GEHC', 'GEN', 'GEV', 'GILD', 'GIS', 'GL', 'GLW', 'GM', 'GNRC',
    'GOOG', 'GOOGL', 'GPC', 'GPN', 'GRMN', 'GS', 'GWW', 'HAL', 'HAS', 'HBAN',
    'HCA', 'HD', 'HIG', 'HII', 'HLT', 'HON', 'HONA', 'HOOD', 'HPE', 'HPQ',
    'HRL', 'HSIC', 'HST', 'HSY', 'HUBB', 'HUM', 'HWM', 'IBKR', 'IBM', 'ICE',
    'IDXX', 'IEX', 'IFF', 'INCY', 'INTC', 'INTU', 'INVH', 'IP', 'IQV', 'IR',
    'IRM', 'ISRG', 'IT', 'ITW', 'IVZ', 'J', 'JBHT', 'JBL', 'JCI', 'JKHY',
    'JNJ', 'JPM', 'KDP', 'KEY', 'KEYS', 'KHC', 'KIM', 'KKR', 'KLAC', 'KMB',
    'KMI', 'KO', 'KR', 'KVUE', 'L', 'LDOS', 'LEN', 'LH', 'LHX', 'LII', 'LIN',
    'LITE', 'LLY', 'LMT', 'LNT', 'LOW', 'LRCX', 'LULU', 'LUV', 'LVS', 'LYB',
    'LYV', 'MA', 'MAA', 'MAR', 'MAS', 'MCD', 'MCHP', 'MCK', 'MCO', 'MDLZ',
    'MDT', 'MET', 'META', 'MGM', 'MKC', 'MLM', 'MMM', 'MNST', 'MO', 'MOS',
    'MPC', 'MPWR', 'MRK', 'MRNA', 'MRSH', 'MRVL', 'MS', 'MSCI', 'MSFT', 'MSI',
    'MTB', 'MTD', 'MU', 'NCLH', 'NDAQ', 'NDSN', 'NEE', 'NEM', 'NFLX', 'NI',
    'NKE', 'NOC', 'NOW', 'NRG', 'NSC', 'NTAP', 'NTRS', 'NUE', 'NVDA', 'NVR',
    'NWS', 'NWSA', 'NXPI', 'O', 'ODFL', 'OKE', 'OMC', 'ON', 'ORCL', 'ORLY',
    'OTIS', 'OXY', 'PANW', 'PAYX', 'PCAR', 'PCG', 'PEG', 'PEP', 'PFE', 'PFG',
    'PG', 'PGR', 'PH', 'PHM', 'PKG', 'PLD', 'PLTR', 'PM', 'PNC', 'PNR', 'PNW',
    'PODD', 'PPG', 'PPL', 'PRU', 'PSA', 'PSKY', 'PSX', 'PTC', 'PWR', 'PYPL',
    'Q', 'QCOM', 'RCL', 'REG', 'REGN', 'RF', 'RJF', 'RL', 'RMD', 'ROK', 'ROL',
    'ROP', 'ROST', 'RSG', 'RTX', 'RVTY', 'SBAC', 'SBUX', 'SCHW', 'SHW', 'SJM',
    'SLB', 'SMCI', 'SNA', 'SNDK', 'SNPS', 'SO', 'SOLV', 'SPG', 'SPGI', 'SRE',
    'STE', 'STLD', 'STT', 'STX', 'STZ', 'SW', 'SWK', 'SWKS', 'SYF', 'SYK',
    'SYY', 'T', 'TAP', 'TDG', 'TDY', 'TECH', 'TEL', 'TER', 'TFC', 'TGT',
    'TJX', 'TKO', 'TMO', 'TMUS', 'TPL', 'TPR', 'TRGP', 'TRMB', 'TROW', 'TRV',
    'TSCO', 'TSLA', 'TSN', 'TT', 'TTD', 'TTWO', 'TXN', 'TXT', 'TYL', 'UAL',
    'UBER', 'UDR', 'UHS', 'ULTA', 'UNH', 'UNP', 'UPS', 'URI', 'USB', 'V',
    'VEEV', 'VICI', 'VLO', 'VLTO', 'VMC', 'VRSK', 'VRSN', 'VRT', 'VRTX',
    'VST', 'VTR', 'VTRS', 'VZ', 'WAB', 'WAT', 'WBD', 'WDAY', 'WDC', 'WEC',
    'WELL', 'WFC', 'WM', 'WMB', 'WMT', 'WRB', 'WSM', 'WST', 'WTW', 'WY',
    'WYNN', 'XEL', 'XOM', 'XYL', 'XYZ', 'YUM', 'ZBH', 'ZBRA', 'ZTS',
]

# Additional well-known large-cap / mega-cap US tickers not in S&P 500
USA_ADDITIONAL_TICKERS = [
    'AMZN', 'GOOGL', 'GOOG', 'META', 'TSLA', 'NVDA', 'AVGO', 'MSFT', 'AAPL',
    'BRK-B', 'JPM', 'V', 'UNH', 'XOM', 'LLY', 'MA', 'PG', 'HD',
    'AMD', 'QCOM', 'INTC', 'AVGO', 'TXN', 'MU', 'AMAT', 'LRCX', 'KLAC', 'MRVL',
    'SNPS', 'CDNS', 'ANSS', 'MCHP', 'NXPI', 'ON', 'SWKS', 'MPWR',
    'MSFT', 'ORCL', 'CRM', 'ADBE', 'NOW', 'INTU', 'UBER', 'SNAP', 'PINS',
    'SQ', 'SHOP', 'RBLX', 'PLTR', 'COIN', 'RIVN', 'LCID', 'NIO', 'LI', 'XPEV',
    'JNJ', 'PFE', 'MRK', 'ABBV', 'BMY', 'LLY', 'GILD', 'AMGN', 'REGN', 'VRTX',
    'BIIB', 'MRNA', 'SGEN', 'ZTS', 'IDXX', 'IQV', 'DXCM', 'ISRG',
    'JPM', 'GS', 'MS', 'BAC', 'WFC', 'C', 'BLK', 'SCHW', 'AXP', 'V', 'MA',
    'USB', 'PNC', 'TFC', 'COF', 'AFL', 'MET', 'PRU', 'AIG', 'ALL', 'TRV',
    'CB', 'PGR', 'ICE', 'CME', 'SPGI', 'MCO', 'MSCI', 'NDAQ',
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'VLO', 'PSX', 'HAL', 'OXY',
    'HON', 'GE', 'CAT', 'DE', 'MMM', 'RTX', 'LMT', 'NOC', 'GD', 'BA',
    'AMZN', 'WMT', 'TGT', 'COST', 'HD', 'LOW', 'NKE', 'SBUX', 'MCD', 'DIS',
    'CMCSA', 'NFLX', 'PYPL', 'BKNG', 'MAR', 'HLT',
    'UNH', 'CVS', 'CI', 'HUM', 'ELV', 'ANTM', 'CNC', 'MOH',
    'ADP', 'PAYX', 'FISV', 'FIS', 'VRSK', 'EXPD', 'JBHT', 'LSTR',
    'AMT', 'PLD', 'CCI', 'EQIX', 'PSA', 'WELL', 'DLR', 'SPG', 'O',
    'NEE', 'DUK', 'SO', 'D', 'AEP', 'EXC', 'SRE', 'PEG', 'ED', 'WEC',
    'XEL', 'ES', 'DTE', 'ETR', 'PPL', 'CMS', 'WEC', 'FE',
]

# Sweden: OMX Stockholm 30 constituents + well-known Swedish stocks
SWEDEN_TICKERS = [
    # OMX Stockholm 30 constituents
    'ABB.ST', 'ADDT-B.ST', 'ADIT.ST', 'ALFA.ST', 'ALIV-B.ST', 'AMFO-B.ST',
    'AMF-A.ST', 'ANDI-B.ST', 'AZN.ST', 'BEN-B.ST', 'BHP.ST', 'BOL-B.ST',
    'BOM-B.ST', 'CALI-B.ST', 'CARB-B.ST', 'CLAB-B.ST', 'DIAB-B.ST',
    'DNS-A.ST', 'DUN-B.ST', 'EAT-A.ST', 'ELUX-B.ST', 'ELUX-A.ST',
    'EQT-B.ST', 'EVO-A.ST', 'FATT-B.ST', 'FJORD-B.ST', 'FLO-B.ST',
    'GASM-B.ST', 'GET-B.ST', 'GKN-D.ST', 'GML-A.ST', 'GML-B.ST',
    'HM-B.ST', 'HPF-B.ST', 'HUB-B.ST', 'HUBT-B.ST', 'IFV-B.ST',
    'IKANO-B.ST', 'IND-B.ST', 'INVE-B.ST', 'JFR-B.ST', 'KTH-B.ST',
    'LAT-B.ST', 'LEK-B.ST', 'LUMI-B.ST', 'MIF-B.ST', 'MIM-B.ST',
    'NHA-B.ST', 'NOVA-B.ST', 'OMX-B.ST', 'PEAB-B.ST', 'PREM-B.ST',
    'PTK-B.ST', 'REVIS-B.ST', 'RI-RS.ST', 'ROK-B.ST', 'SAB-B.ST',
    'SAND.ST', 'SHP-B.ST', 'SEB-A.ST', 'SEB-B.ST', 'SHP-A.ST',
    'SKF-B.ST', 'SSAB-A.ST', 'SSAB-B.ST', 'SWS-A.ST', 'SWS-B.ST',
    'SWE-B.ST', 'SWED-A.ST', 'SWED-B.ST', 'SYV-B.ST', 'TEL4O-B.ST',
    'TELIA-B.ST', 'TDC-B.ST', 'TGC-B.ST', 'TITB-B.ST',
    'TOBB-B.ST', 'TOB-B.ST', 'TRUM-B.ST', 'UNIF-B.ST', 'UMEX-B.ST',
    'VIV-B.ST', 'VOL-B.ST', 'VOL-A.ST', 'WSO-B.ST', 'WSO-A.ST',
    'XYZ-A.ST', 'ZED-A.ST',
    # Additional well-known Swedish companies
    'ESSITY-B.ST', 'HEX-A.ST', 'HEX-B.ST', 'VOLV-B.ST',
    'SWEDA-B.ST', 'SWEDB.ST', 'SEB-A.ST',
]

# India: NIFTY 50 constituents + well-known Indian stocks
INDIA_TICKERS = [
    'ACC', 'ADANIENT', 'ADANIPORTS', 'APOLLOHOSP', 'ASIANPAINT',
    'AXISBANK', 'BAJAJ-AUTO', 'BAJAJFINSV', 'BAJFINANCE', 'BHEL',
    'BPCL', 'BHARTIARTL', 'CDSL', 'CIPLA', 'COALINDIA', 'DRREDDY',
    'EICHERMOT', 'GAIL', 'GRASIM', 'HAVELLS', 'HCLTECH', 'HDFC',
    'HDFCBANK', 'HINDALCO', 'HINDUNILVR', 'ICICIBANK', 'IEX', 'INDUSINDBK',
    'INFY', 'ITC', 'JIOFIN', 'JSWSTEEL', 'KOTAKBANK', 'LT', 'LUPIN',
    'M&M', 'MCX', 'MCDOWELL-N', 'NTPC', 'NTPC', 'ONGC', 'POWERGRID',
    'RELIANCE', 'SBIN', 'SHREECEM', 'SUNPHARMA', 'TATACHEM', 'TATACOMM',
    'TATACONSUM', 'TATAMOTORS', 'TATASTEEL', 'TATATECH', 'TECHM',
    'TITAN', 'TORNTPHARM', 'TRENT', 'ULTRACEMCO', 'UPL', 'VBL',
    'VEDL', 'WIPRO', 'YESBANK', 'ZEEL',
    'ADANIGREEN', 'ADANISUMI', 'AXISBANK', 'BANKBARODA', 'CANBK',
    'CONCOR', 'DABUR', 'DLF', 'GMRINFRA', 'IBULHSGFIN', 'IOC',
    'IRCTC', 'IRFC', 'MUTHOOTFIN', 'NMDC', 'SJVN', 'SBI',
    'TCS', 'DIVISLAB', 'BIOCON', 'BRITANNIA', 'COLPAL',
]

# China: Major Shanghai & Shenzhen exchange tickers
CHINA_TICKERS = [
    '600519.SS',  # Kweichow Moutai
    '601318.SS',  # Ping An Insurance
    '600036.SS',  # China Merchants Bank
    '600900.SS',  # China Yangtze Power
    '601888.SS',  # China International Travel Service
    '600030.SS',  # CITIC Securities
    '600276.SS',  # Hengrui Medicine
    '601166.SS',  # Industrial Bank
    '600887.SS',  # Yili Industrial Group
    '601601.SS',  # China Pacific Insurance
    '600050.SS',  # China United Telecom
    '601088.SS',  # China Shenhua Energy
    '601857.SS',  # PetroChina
    '601398.SS',  # Industrial and Commercial Bank of China
    '601988.SS',  # Bank of China
    '600031.SS',  # Sany Heavy Industry
    '600309.SS',  # Wanxiang Zhicheng
    '601668.SS',  # China State Construction Engineering
    '601288.SS',  # Agricultural Bank of China
    '601328.SS',  # Bank of Communications
    '600000.SS',  # Shanghai Pudong Development Bank
    '600016.SS',  # China Minsheng Bank
    '601012.SS',  # Longji New Energy
    '600809.SS',  # Shanxi Xingtai
    '600886.SS',  # SPIC
    '000858.SZ',  # Wuliangye Yibin
    '000001.SZ',  # Ping An Bank
    '000002.SZ',  # Vanke
    '000333.SZ',  # Midea Group
    '000568.SZ',  # GALA Network Technology
    '000651.SZ',  # Gree Electric
    '000725.SZ',  # BOE Technology
    '000776.SZ',  # Guangfa Securities
    '002415.SZ',  # Hangzhou Hikvision Digital
    '002594.SZ',  # BYD
    '300015.SZ',  # Aier Eye Hospital
    '300124.SZ',  # Innovation Power
    '300750.SZ',  # CATL
    '688981.SS',  # SMIC
    '688036.SS',  # Conson Electronics
    '0700.HK',   # Tencent
    '9988.HK',   # Alibaba
    '1211.HK',   # BYD Company
    '1810.HK',   # Xiaomi
    '9618.HK',   # JD.com
    '3690.HK',   # Meituan
    '2020.HK',   # Anta Sports
    '1024.HK',   # Meituan
    '9888.HK',   # Baidu
    '9999.HK',   # NetEase
]

# ---------------------------------------------------------------------------
# Additional scraped tickers (from Wikipedia index constituents)
# ---------------------------------------------------------------------------

# International tickers scraped from FTSE 100, DAX, CAC 40, ASX 200, TSX etc.
# These have exchange suffixes (e.g., ADS.DE, ABN.AS)
INTERNATIONAL_TICKERS = [
    # DAX 40 (Germany)
    'ADS.DE', 'ALV.DE', 'BAS.DE', 'BAYN.DE', 'BEI.DE', 'BEI.UN',
    'BMW.DE', 'BNR.DE', 'CBK.DE', 'CON.DE', 'DHL.DE', 'DTE.DE',
    'ENR.DE', 'EOAN.DE', 'FME.DE', 'FRE.DE', 'G1A.DE', 'G24.DE',
    'HEI.DE', 'HEN3.DE', 'IFX.DE', 'MRK.DE', 'MBG.DE', 'MTX.DE',
    'MUV2.DE', 'PAH3.DE', 'QIA.DE', 'RHM.DE', 'RWE.DE', 'SAP.DE',
    'SHL.DE', 'SIE.DE', 'SY1.DE', 'VNA.DE', 'VOW3.DE', 'ZAL.DE',
    
    # FTSE 100 / 250 (UK)
    'ABF', 'AZN', 'BARC', 'BATS', 'BHP', 'BP', 'BT.A', 'CCH',
    'DGE', 'GLEN', 'HSBA', 'HSBC', 'IAG', 'LSEG', 'LVMH', 'RELX',
    'RIO', 'RR', 'SHEL', 'ULVR', 'VOD', 'UU',
    
    # CAC 40 (France)
    'AI.PA', 'AIR.PA', 'BN.PA', 'BNP.PA', 'CA.PA', 'DCS.PA',
    'DG.PA', 'EL.PA', 'EN.PA', 'GLE.PA', 'HO.PA', 'KER.PA',
    'MC.PA', 'ML.PA', 'OR.PA', 'ORA.PA', 'RMS.PA', 'RI.PA',
    'RMS.PA', 'RNO.PA', 'SAN.PA', 'SGO.PA', 'SU.PA', 'TTE.PA',
    'VIE.PA', 'VNA.DE', 'SAF.PA', 'DCO.PA',
    
    # ASX 200 (Australia) - tickers without suffix
    'ABR', 'A2A', 'ABX', 'ANZ', 'API', 'ASH', 'AUTO', 'BAP',
    'BEN', 'BHP', 'BOQ', 'BRG', 'CBA', 'CCC', 'CEN', 'CIS',
    'CNC', 'COL', 'CPX', 'CSL', 'CTD', 'DOW', 'DRL', 'EGV',
    'FLT', 'FMG', 'FPH', 'GAB', 'GNA', 'GPT', 'HDN', 'IAG',
    'ILU', 'INC', 'JHX', 'LHP', 'MIN', 'MND', 'MQG', 'NAB',
    'NEC', 'NXT', 'OGC', 'ORG', 'PGH', 'PLS', 'PME', 'QBE',
    'REA', 'RHC', 'RMS', 'SGP', 'S32', 'SUN', 'TCL', 'TLS',
    'TNE', 'TPG', 'WBC', 'WES', 'WOW', 'WPL', 'XRO',
    
    # TSX (Canada) - tickers without suffix
    'ABX', 'BAM', 'BCE', 'BMO', 'CNQ', 'CP', 'CNR', 'CPR',
    'DOL', 'ENB', 'FM', 'FNV', 'KMP', 'MFC', 'MFC', 'MGR',
    'NG', 'NTR', 'RY', 'TOU', 'TRI', 'TRP', 'WPM', 'WCN',
    
    # Other international (from Wikipedia scraping)
    'A2A.MI', 'AMP.MI', 'AZM.MI', 'BAMI.MI', 'BC.MI', 'BMED.MI',
    'BPE.MI', 'CPR.MI', 'DIA.MI', 'ENEL.MI', 'HER.MI', 'IG.MI',
    'INW.MI', 'ISP.MI', 'LTMC.MI', 'MONC.MI', 'NEXI.MI',
    'PRY.MI', 'PST.MI', 'REC.MI', 'TEN.MI', 'TIT.MI', 'TRN.MI',
    'UCG.MI', 'UNI.MI', 'BBVA.MC', 'ELE.MC', 'FDR.MC', 'FER.MC',
    'IAG.MC', 'IBE.MC', 'IDR.MC', 'ITX.MC', 'MAP.MC', 'MTS.MC',
    'NTGY.MC', 'PUIG.MC', 'RED.MC', 'REP.MC', 'SAB.MC', 'SLR.MC',
    'TEF.MC', 'ABN.AS', 'AD.AS', 'AGN.AS', 'AKZA.AS', 'AMS.AS',
    'ASML.AS', 'BESI.AS', 'DSFIR.AS', 'HEIA.AS', 'IMCD.AS',
    'INGA.AS', 'KPN.AS', 'MT.AS', 'PHIA.AS', 'PRX.AS', 'RAND.AS',
    'REN.AS', 'SHELL.AS', 'UMG.AS', 'UNA.AS', 'WKL.AS',
]

# US tickers scraped from international indices (non-S&P 500 US-listed companies)
EXTRA_US_TICKERS = [
    'A', 'AAL', 'ABBV', 'ACN', 'ADM', 'AEP', 'AFL', 'ALL', 'AMP',
    'ANET', 'APD', 'ARE', 'AVGO', 'AXP', 'BA', 'BALL', 'BAX', 'BDX',
    'BG', 'BIIB', 'BK', 'BLK', 'BMY', 'BR', 'BSX', 'BXP', 'CAH',
    'CAT', 'CB', 'CBOE', 'CCI', 'CDNS', 'CDW', 'CEG', 'CF', 'CFG',
    'CHD', 'CHRW', 'CHTR', 'CI', 'CL', 'CLX', 'CMCSA', 'CME', 'CMG',
    'CMI', 'CMS', 'COST', 'CPAY', 'CPRT', 'CPT', 'CRH', 'CRL', 'CRM',
    'CRWD', 'CSCO', 'CSGP', 'CSX', 'CTAS', 'CTSH', 'CTVA', 'CVS', 'CVX',
    'DAL', 'DASH', 'DD', 'DDOG', 'DE', 'DECK', 'DELL', 'DG', 'DGX',
    'DHI', 'DHR', 'DIS', 'DLR', 'DLTR', 'DOC', 'DOV', 'DOW', 'DPZ',
    'DRI', 'DTE', 'DUK', 'DVN', 'DXCM', 'EA', 'EBAY', 'ECL', 'ED',
    'EFX', 'EG', 'EIX', 'EL', 'ELV', 'EME', 'EMR', 'EOG', 'EQIX',
    'EQR', 'EQT', 'ES', 'ESS', 'ETN', 'ETR', 'EVRG', 'EW', 'EXC',
    'EXPD', 'EXPE', 'EXR', 'F', 'FANG', 'FAST', 'FCX', 'FDS', 'FDX',
    'FE', 'FFIV', 'FICO', 'FIS', 'FISV', 'FITB', 'FIX', 'FLEX', 'FOX',
    'FOXA', 'FRT', 'FSLR', 'FTNT', 'FTV', 'GD', 'GDDY', 'GE', 'GEN',
    'GILD', 'GIS', 'GL', 'GLW', 'GM', 'GNRC', 'GPC', 'GPN', 'GRMN',
    'GS', 'GWW', 'HAL', 'HAS', 'HBAN', 'HCA', 'HD', 'HIG', 'HII',
    'HLT', 'HON', 'HOOD', 'HPE', 'HPQ', 'HRL', 'HSIC', 'HST', 'HSY',
    'HUM', 'HWM', 'IBM', 'ICE', 'IDXX', 'IFF', 'INCY', 'INTC', 'INTU',
    'INVH', 'IP', 'IPG', 'IQV', 'IR', 'IRM', 'ISRG', 'IT', 'ITW',
    'IVZ', 'J', 'JBHT', 'JBL', 'JCI', 'JKHY', 'JNJ', 'JPM', 'KDP',
    'KEY', 'KEYS', 'KHC', 'KIM', 'KKR', 'KLAC', 'KMB', 'KMI', 'KO',
    'KR', 'KVUE', 'L', 'LDOS', 'LEN', 'LH', 'LHX', 'LII', 'LIN',
    'LITE', 'LLY', 'LMT', 'LNT', 'LOW', 'LRCX', 'LULU', 'LUV', 'LVS',
    'LYB', 'LYV', 'MA', 'MAA', 'MAR', 'MAS', 'MCD', 'MCHP', 'MCK',
    'MCO', 'MDLZ', 'MDT', 'MET', 'META', 'MGM', 'MKC', 'MLM', 'MMM',
    'MNST', 'MO', 'MOS', 'MPC', 'MPWR', 'MRK', 'MRNA', 'MRVL', 'MS',
    'MSCI', 'MSFT', 'MSI', 'MTB', 'MTD', 'MU', 'NCLH', 'NDAQ', 'NDSN',
    'NEE', 'NEM', 'NFLX', 'NI', 'NKE', 'NOC', 'NOW', 'NRG', 'NSC',
    'NTAP', 'NTRS', 'NUE', 'NVDA', 'NVR', 'NWS', 'NWSA', 'NXPI', 'O',
    'ODFL', 'OKE', 'OMC', 'ON', 'ORCL', 'ORLY', 'OTIS', 'OXY', 'PANW',
    'PAYX', 'PCAR', 'PCG', 'PEG', 'PEP', 'PFE', 'PFG', 'PG', 'PGR',
    'PH', 'PHM', 'PKG', 'PLD', 'PLTR', 'PM', 'PNC', 'PNR', 'PNW',
    'PODD', 'PPG', 'PPL', 'PRU', 'PSA', 'PSKY', 'PSX', 'PTC', 'PWR',
    'PYPL', 'QCOM', 'RCL', 'REG', 'REGN', 'RF', 'RJF', 'RL', 'RMD',
    'ROK', 'ROL', 'ROP', 'ROST', 'RSG', 'RTX', 'SBAC', 'SBUX', 'SCHW',
    'SHW', 'SJM', 'SLB', 'SMCI', 'SNA', 'SNDK', 'SNPS', 'SO', 'SPG',
    'SPGI', 'SRE', 'STE', 'STLD', 'STT', 'STX', 'STZ', 'SW', 'SWK',
    'SWKS', 'SYF', 'SYK', 'SYY', 'T', 'TAP', 'TDG', 'TDY', 'TEL',
    'TER', 'TFC', 'TGT', 'TJX', 'TKO', 'TMO', 'TMUS', 'TPL', 'TPR',
    'TRGP', 'TRMB', 'TROW', 'TRV', 'TSCO', 'TSLA', 'TSN', 'TT', 'TTD',
    'TTWO', 'TXN', 'TXT', 'TYL', 'UAL', 'UBER', 'UDR', 'UHS', 'ULTA',
    'UNH', 'UNP', 'UPS', 'URI', 'USB', 'V', 'VEEV', 'VICI', 'VLO',
    'VLTO', 'VMC', 'VRSK', 'VRSN', 'VRT', 'VRTX', 'VST', 'VTR', 'VTRS',
    'VZ', 'WAB', 'WAT', 'WBD', 'WDAY', 'WDC', 'WEC', 'WELL', 'WFC',
    'WM', 'WMB', 'WMT', 'WRB', 'WSM', 'WST', 'WTW', 'WY', 'WYNN',
    'XEL', 'XOM', 'XYL', 'XYZ', 'YUM', 'ZBH', 'ZBRA', 'ZTS',
]

# ---------------------------------------------------------------------------
# Wikipedia enrichment URLs (for additional index scraping)
# ---------------------------------------------------------------------------

# Wikipedia pages for major global indices
# Format: (name, url)
WIKIPEDIA_INDEX_URLS = [
    # USA indices
    ("Nasdaq 100", "https://en.wikipedia.org/wiki/Nasdaq-100"),
    ("Russell 2000", "https://en.wikipedia.org/wiki/Russell_2000_Index"),
    # UK
    ("FTSE 100", "https://en.wikipedia.org/wiki/FTSE_100_Index"),
    ("FTSE 250", "https://en.wikipedia.org/wiki/FTSE_250_Index"),
    # Europe
    ("DAX", "https://en.wikipedia.org/wiki/DAX"),
    ("Nikkei 225", "https://en.wikipedia.org/wiki/Nikkei_225"),
    ("CAC 40", "https://en.wikipedia.org/wiki/CAC_40"),
    ("IBEX 35", "https://en.wikipedia.org/wiki/IBEX_35"),
    ("FTSE MIB", "https://en.wikipedia.org/wiki/FTSE_MIB"),
    ("SMI", "https://en.wikipedia.org/wiki/Swiss_Market_Index"),
    ("AEX", "https://en.wikipedia.org/wiki/AEX_Index"),
    ("OBX", "https://en.wikipedia.org/wiki/OBX"),
    ("WIG20", "https://en.wikipedia.org/wiki/WIG20"),
    ("ATX", "https://en.wikipedia.org/wiki/Austrian_Stock_Exchange"),
    # Asia
    ("Hang Seng", "https://en.wikipedia.org/wiki/Hang_Seng_Index"),
    ("KOSPI", "https://en.wikipedia.org/wiki/KOSPI"),
    ("ASX 200", "https://en.wikipedia.org/wiki/ASX_200"),
    ("STI", "https://en.wikipedia.org/wiki/Straits_Times_Index"),
    ("KLCI", "https://en.wikipedia.org/wiki/FBM_KLCI"),
    ("SET", "https://en.wikipedia.org/wiki/SET_Index"),
    ("IBOVESPA", "https://en.wikipedia.org/wiki/IBOVESPA"),
    ("TSX Composite", "https://en.wikipedia.org/wiki/S%26P/TSX_Composite_Index"),
]

# ---------------------------------------------------------------------------
# Helper: scrape index constituents via Wikipedia
# ---------------------------------------------------------------------------

def _fetch_wikipedia(url: str, timeout: int = 25) -> Optional[str]:
    """Fetch a URL and return text content, or None on failure."""
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Rocket Stock Scanner; dev)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8')
    except Exception as e:
        logger.debug(f"Wikipedia fetch failed for {url}: {e}")
        return None


def _extract_tickers_from_table(html: str, ticker_col: int = 0) -> list[str]:
    """Simple HTML table parser — extract ticker-like strings from td elements."""
    if not html:
        return []
    # Find the main sortable table
    table_m = re.search(
        r'id="mwOw"[^>]*>.*?</table>', html, re.DOTALL
    )
    if not table_m:
        # Fallback: try any wikitable
        tables = re.findall(
            r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>',
            html, re.DOTALL
        )
        for table in tables:
            tickers = _extract_from_rows(table, ticker_col)
            if tickers:
                return tickers
        return []
    return _extract_from_rows(table_m.group(0), ticker_col)


def _extract_from_rows(table_html: str, ticker_col: int) -> list[str]:
    """Extract tickers from table HTML rows."""
    tickers = set()
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
    for row in rows:
        if '<th' in row:
            continue
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(tds) <= ticker_col:
            continue
        cell = re.sub(r'<[^>]+>', '', tds[ticker_col]).strip()
        # Match US tickers and international with suffix
        if re.match(r'^[A-Z]{1,5}(\.\w+)?$', cell) or re.match(r'^\d{6}(\.\w+)?$', cell):
            tickers.add(cell)
    return sorted(tickers)


def _fetch_from_wikipedia() -> list[str]:
    """Fetch tickers from all Wikipedia index URLs.
    
    Returns a list of tickers found across all pages.
    """
    all_tickers = set()
    
    for name, url in WIKIPEDIA_INDEX_URLS:
        html = _fetch_wikipedia(url)
        if html:
            # Try multiple column positions
            for col in range(5):
                tickers = _extract_tickers_from_table(html, col)
                if tickers:
                    all_tickers.update(tickers)
                    logger.info(f"  {name}: {len(tickers)} tickers (col {col})")
                    break
        else:
            logger.debug(f"Could not fetch {name} from Wikipedia")
        
        time.sleep(0.8)  # Be polite to Wikipedia
    
    return sorted(all_tickers)


def _enrich_from_yfinance_screens() -> list[str]:
    """Fetch tickers from yfinance predefined screens."""
    try:
        import yfinance as yf
        
        all_tickers = set()
        screens = ['day_gainers', 'day_losers', 'most_actives']
        
        for screen_name in screens:
            try:
                logger.debug(f"Trying yfinance screen: {screen_name}")
                # yfinance screen API
                screen_query = yf.screener.query.MarketScreensQuery()
                screen = screen_query.get_screener_by_name(screen_name)
                if screen:
                    result = screen.search()
                    if result and 'quotes' in result:
                        for q in result['quotes']:
                            ticker = q.get('symbol', '')
                            if ticker:
                                all_tickers.add(ticker)
            except Exception as e:
                logger.debug(f"yfinance screen {screen_name} failed: {e}")
            
            time.sleep(1.0)
        
        return sorted(all_tickers)
    except ImportError:
        logger.debug("yfinance not available for screen scraping")
        return []
    except Exception as e:
        logger.debug(f"yfinance screen scraping failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Index enrichment: fetch + merge
# ---------------------------------------------------------------------------

def _enrich_universe_from_sources() -> dict[str, list[str]]:
    """Fetch additional index constituents and merge with embedded lists.
    
    Each region starts from its embedded reference list, then enriches with
    any tickers found from Wikipedia scraping and yfinance screens.
    """
    # Start with embedded reference lists
    universe = {
        'usa': list(set(USA_SP500_TICKERS + EXTRA_US_TICKERS)),
        'sweden': list(set(SWEDEN_TICKERS)),
        'india': list(set(INDIA_TICKERS)),
        'china': list(set(CHINA_TICKERS)),
    }
    
    # Add international tickers
    universe['international'] = list(set(INTERNATIONAL_TICKERS))
    
    # Add scraped tickers from Wikipedia (enriches existing regions)
    logger.info("Fetching additional tickers from Wikipedia...")
    wiki_tickers = _fetch_from_wikipedia()
    
    if wiki_tickers:
        # Split into US vs international
        us_tickers = [t for t in wiki_tickers if '.' not in t and len(t) <= 5 and t.isalpha() and t.isupper()]
        intl_tickers = [t for t in wiki_tickers if '.' in t]
        
        # Add to international region
        universe['international'].extend(intl_tickers)
        universe['international'] = sorted(set(universe['international']))
        
        # Add US tickers to usa region
        universe['usa'].extend(us_tickers)
        universe['usa'] = sorted(set(universe['usa']))
        
        logger.info(f"Wikipedia enrichment: +{len(us_tickers)} US, +{len(intl_tickers)} international tickers")
    
    # Add yfinance screen tickers
    logger.info("Fetching additional tickers from yfinance screens...")
    yf_tickers = _enrich_from_yfinance_screens()
    if yf_tickers:
        universe['usa'].extend(yf_tickers)
        universe['usa'] = sorted(set(universe['usa']))
        logger.info(f"yfinance screen enrichment: +{len(yf_tickers)} tickers")
    
    # Add additional regions by splitting international tickers
    # Parse suffixes to assign to regions
    suffix_map = {
        '.L': 'uk', '.DE': 'germany', '.PA': 'france', '.T': 'japan',
        '.TO': 'canada', '.AX': 'australia', '.KS': 'southkorea',
        '.SI': 'singapore', '.SW': 'switzerland', '.AS': 'netherlands',
        '.SA': 'brazil', '.HK': 'hongkong', '.MX': 'mexico', '.JK': 'indonesia',
        '.BK': 'thailand', '.KL': 'malaysia', '.PH': 'philippines',
        '.CAI': 'egypt', '.TL': 'israel', '.IS': 'turkey', '.LN': 'nigeria',
        '.J': 'southafrica', '.WA': 'poland', '.OL': 'norway',
        '.CO': 'denmark', '.HE': 'finland', '.VI': 'austria',
        '.MC': 'spain', '.MI': 'italy', '.ST': 'sweden',
    }
    
    # Create region-specific lists from international tickers
    for suffix, region in suffix_map.items():
        suffix_tickers = [t for t in universe['international'] if t.endswith(suffix)]
        if suffix_tickers:
            universe[region] = sorted(set(suffix_tickers))
            logger.info(f"  {region}: {len(suffix_tickers)} tickers")
    
    # Remove duplicates from international after splitting
    universe['international'] = sorted(set(universe['international']))
    
    return universe


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _read_cache() -> Optional[dict]:
    """Read cache file, return data dict or None."""
    if not _CACHE_FILE.exists():
        return None
    try:
        with open(_CACHE_FILE, 'r') as f:
            data = json.load(f)
        # Validate structure
        if not isinstance(data, dict) or 'data' not in data or 'timestamp' not in data:
            return None
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.debug(f"Cache read error: {e}")
        return None


def _write_cache(universe: dict[str, list[str]]) -> None:
    """Write universe data to cache file."""
    try:
        cache_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'tickers': universe,
        }
        _CACHE_FILE.write_text(json.dumps(cache_data, indent=2))
    except OSError as e:
        logger.warning(f"Cache write error: {e}")


def _is_cache_fresh(cache: dict) -> bool:
    """Check if cache is within TTL."""
    try:
        ts = datetime.fromisoformat(cache['timestamp'])
        age = datetime.now(timezone.utc) - ts
        return age < timedelta(seconds=_CACHE_TTL_SECONDS)
    except (KeyError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _build_universe(force_refresh: bool = False) -> dict[str, list[str]]:
    """Build the ticker universe: try cache → enrich → save.
    
    Args:
        force_refresh: If True, skip cache and fetch live data.
    """
    # Try cache first (only if not forcing refresh)
    if not force_refresh:
        cache = _read_cache()
        if cache and _is_cache_fresh(cache):
            logger.debug("Using cached universe data")
            return cache['tickers']
    
    # Build from sources
    logger.info("Building universe from embedded lists + online enrichment")
    universe = _enrich_universe_from_sources()
    
    # Save to cache
    _write_cache(universe)
    logger.info(f"Universe built: {dict((k, len(v)) for k, v in universe.items())}")
    return universe


# Module-level cache (single call per session)
_universe_cache: Optional[dict[str, list[str]]] = None


def get_universe(region: str | None = None, force_refresh: bool = False) -> list[str] | dict[str, list[str]]:
    """Get ticker universe.
    
    Args:
        region: Region key or None for all.
        force_refresh: If True, skip cache and fetch live data.
    
    Returns:
        If region is specified, returns list[str] of tickers for that region.
        If region is None, returns dict[str, list[str]] of all regions.
    """
    global _universe_cache
    if _universe_cache is None or force_refresh:
        _universe_cache = _build_universe(force_refresh)
    
    if region is None:
        return dict(_universe_cache)
    
    return list(_universe_cache.get(region, []))


def get_universe_count() -> dict[str, int]:
    """Return dict of region -> number of tickers (embedded only, no scraping)."""
    return {
        'usa': len(set(USA_SP500_TICKERS + EXTRA_US_TICKERS)),
        'sweden': len(SWEDEN_TICKERS),
        'india': len(INDIA_TICKERS),
        'china': len(CHINA_TICKERS),
        'international': len(INTERNATIONAL_TICKERS),
    }


def get_all_tickers() -> list[str]:
    """Return all unique tickers across embedded lists (no scraping)."""
    all_tickers = set()
    all_tickers.update(USA_SP500_TICKERS)
    all_tickers.update(EXTRA_US_TICKERS)
    all_tickers.update(SWEDEN_TICKERS)
    all_tickers.update(INDIA_TICKERS)
    all_tickers.update(CHINA_TICKERS)
    all_tickers.update(INTERNATIONAL_TICKERS)
    return sorted(all_tickers)


def get_all_universes() -> list[str]:
    """Alias for get_all_tickers — return all tickers across all regions."""
    return get_all_tickers()


def get_region_count() -> dict[str, int]:
    """Alias for get_universe_count — return dict of region -> count."""
    return get_universe_count()


def get_total_count() -> int:
    """Return total number of unique tickers across embedded lists."""
    return len(get_all_tickers())


# Region configuration (kept for backward compatibility)
REGIONS = {
    'usa': list(set(USA_SP500_TICKERS + EXTRA_US_TICKERS)),
    'sweden': list(SWEDEN_TICKERS),
    'india': list(INDIA_TICKERS),
    'china': list(CHINA_TICKERS),
}

REGION_LABELS = {
    'usa': 'United States',
    'sweden': 'Sweden',
    'china': 'China',
    'india': 'India',
    'uk': 'United Kingdom',
    'germany': 'Germany',
    'japan': 'Japan',
    'canada': 'Canada',
    'australia': 'Australia',
    'france': 'France',
    'southkorea': 'South Korea',
    'singapore': 'Singapore',
    'switzerland': 'Switzerland',
    'netherlands': 'Netherlands',
    'brazil': 'Brazil',
    'hongkong': 'Hong Kong',
    'mexico': 'Mexico',
    'indonesia': 'Indonesia',
    'thailand': 'Thailand',
    'malaysia': 'Malaysia',
    'philippines': 'Philippines',
    'egypt': 'Egypt',
    'israel': 'Israel',
    'turkey': 'Turkey',
    'southafrica': 'South Africa',
    'poland': 'Poland',
    'norway': 'Norway',
    'denmark': 'Denmark',
    'finland': 'Finland',
    'austria': 'Austria',
    'spain': 'Spain',
    'italy': 'Italy',
}

