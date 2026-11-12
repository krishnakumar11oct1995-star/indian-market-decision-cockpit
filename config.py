import os

# Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or None
GEMINI_MODEL = "gemini-2.5-flash"
# Endpoint is None when no key is configured; callers must skip AI calls and use fallbacks.
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    if GEMINI_API_KEY else None
)
# Send the key as a header instead of a URL query param.
GEMINI_HEADERS = {"x-goog-api-key": GEMINI_API_KEY} if GEMINI_API_KEY else {}

# Nifty 50 Tickers (Yahoo Finance format with .NS)
NIFTY_50_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "BHARTIARTL.NS", "SBIN.NS", "ITC.NS", "LICI.NS", "HINDUNILVR.NS",
    "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TATAMOTORS.NS", "KOTAKBANK.NS", "ONGC.NS", "NTPC.NS", "AXISBANK.NS",
    "TITAN.NS", "ADANIENT.NS", "ADANIPORTS.NS", "COALINDIA.NS", "POWERGRID.NS",
    "ULTRACEMCO.NS", "BAJAJFINSV.NS", "M&M.NS", "ASIANPAINT.NS", "WIPRO.NS",
    "JSWSTEEL.NS", "TATASTEEL.NS", "SIEMENS.NS", "GRASIM.NS", "TECHM.NS",
    "NESTLEIND.NS", "INDUSINDBK.NS", "HINDALCO.NS", "CIPLA.NS", "DRREDDY.NS",
    "BRITANNIA.NS", "EICHERMOT.NS", "APOLLOHOSP.NS", "TATACONSUM.NS", "DIVISLAB.NS",
    "BPCL.NS", "SBILIFE.NS", "BAJAJ-AUTO.NS", "SHRIRAMFIN.NS", "HEROMOTOCO.NS"
]

# Liquid Penny & Sub-₹50 Turnaround Tickers (NSE)
PENNY_STOCK_TICKERS = [
    "SUZLON.NS", "IDEA.NS", "YESBANK.NS", "SOUTHBANK.NS", "JPPOWER.NS",
    "RTNPOWER.NS", "UCOBANK.NS", "INFIBEAM.NS", "ALOKINDS.NS", "GMRAIRPORT.NS",
    "IOB.NS", "CENTRALBK.NS", "RENUKA.NS", "HCC.NS", "RPOWER.NS",
    "DISHTV.NS", "SUBEXLTD.NS", "URJA.NS", "GTLINFRA.NS", "MOREPENLAB.NS"
]

# Popular Indian Sectors
SECTOR_MAPPINGS = {
    "RELIANCE.NS": "Energy / Conglomerate",
    "TCS.NS": "Information Technology",
    "HDFCBANK.NS": "Private Banking",
    "INFY.NS": "Information Technology",
    "ICICIBANK.NS": "Private Banking",
    "BHARTIARTL.NS": "Telecom",
    "SBIN.NS": "Public Banking",
    "ITC.NS": "FMCG / Diversified",
    "LICI.NS": "Life Insurance",
    "HINDUNILVR.NS": "FMCG",
    "LT.NS": "Infrastructure / EPC",
    "BAJFINANCE.NS": "NBFC / Lending",
    "HCLTECH.NS": "Information Technology",
    "MARUTI.NS": "Automobile",
    "SUNPHARMA.NS": "Pharmaceuticals",
    "TATAMOTORS.NS": "Automobile / EV",
    "KOTAKBANK.NS": "Private Banking",
    "ONGC.NS": "Oil and Gas",
    "NTPC.NS": "Power Generation",
    "AXISBANK.NS": "Private Banking",
    "TITAN.NS": "Consumer / Jewelry",
    "ADANIENT.NS": "Conglomerate",
    "ADANIPORTS.NS": "Infrastructure / Ports",
    "COALINDIA.NS": "Mining and Power",
    "POWERGRID.NS": "Power Transmission",
    "ULTRACEMCO.NS": "Cement",
    "BAJAJFINSV.NS": "Financial Services",
    "M&M.NS": "Automobile / Farm",
    "ASIANPAINT.NS": "Paints and Chemicals",
    "WIPRO.NS": "Information Technology"
}

# Technical Defaults
DEFAULT_SUPERTREND_PERIOD = 10
DEFAULT_SUPERTREND_MULTIPLIER = 3.0
DEFAULT_RSI_PERIOD = 14
DEFAULT_ATR_PERIOD = 14
DEFAULT_MONTE_CARLO_SIMS = 5000
DEFAULT_MONTE_CARLO_DAYS = 7
DEFAULT_RISK_PER_TRADE_INR = 5000.0  # Default ₹5,000 max risk per position
