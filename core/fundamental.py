import yfinance as yf
from typing import Dict, Any

def analyze_fundamentals(ticker: str) -> Dict[str, Any]:
    """
    Fetches fundamental metrics for Indian stocks via yfinance info.
    Returns valuation, solvency, profitability metrics, and a Fundamental Score (0-100).
    """
    default_res = {
        "Ticker": ticker,
        "Market_Cap_Cr": 0.0,
        "Trailing_PE": 0.0,
        "ROE_Pct": 0.0,
        "Debt_to_Equity": 0.0,
        "Operating_Margin_Pct": 0.0,
        "52W_High": 0.0,
        "52W_Low": 0.0,
        "Sector": "Diversified",
        "Fundamental_Score": 50
    }
    
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        
        mcap = info.get("marketCap", 0)
        mcap_cr = round(mcap / 10000000.0, 2) if mcap else 0.0  # Convert to Crores
        
        pe = round(info.get("trailingPE", 0.0) or 0.0, 2)
        roe = round((info.get("returnOnEquity", 0.0) or 0.0) * 100, 2)
        de = round((info.get("debtToEquity", 0.0) or 0.0) / 100.0, 2)
        op_margin = round((info.get("operatingMargins", 0.0) or 0.0) * 100, 2)
        
        h52 = round(info.get("fiftyTwoWeekHigh", 0.0) or 0.0, 2)
        l52 = round(info.get("fiftyTwoWeekLow", 0.0) or 0.0, 2)
        sector = info.get("sector") or info.get("industry") or "Equities"
        
        # Fundamental Score calculation (0 to 100)
        score = 50
        
        # ROE scoring
        if roe >= 20.0:
            score += 15
        elif roe >= 12.0:
            score += 10
        elif roe < 0.0:
            score -= 15
            
        # Solvency (Debt to Equity)
        if de <= 0.5:
            score += 15
        elif de <= 1.0:
            score += 5
        elif de > 2.0:
            score -= 15
            
        # Operating Margin
        if op_margin >= 20.0:
            score += 10
        elif op_margin >= 10.0:
            score += 5
        elif op_margin < 0.0:
            score -= 10
            
        # Valuation (PE sanity check)
        if 10.0 <= pe <= 35.0:
            score += 10
        elif pe > 60.0:
            score -= 10
            
        score = max(0, min(100, score))
        
        return {
            "Ticker": ticker,
            "Market_Cap_Cr": mcap_cr,
            "Trailing_PE": pe,
            "ROE_Pct": roe,
            "Debt_to_Equity": de,
            "Operating_Margin_Pct": op_margin,
            "52W_High": h52,
            "52W_Low": l52,
            "Sector": sector,
            "Fundamental_Score": score
        }
    except Exception:
        return default_res
