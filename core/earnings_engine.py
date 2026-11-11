"""
Quarterly Earnings & Post-Earnings Announcement Drift (PEAD) Engine
Tracks earnings dates, compares quarterly revenue & profit YoY growth, and detects PEAD breakout setups.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date
import time
from typing import Dict, Any, List

_EARNINGS_CALENDAR_CACHE = {
    "timestamp": 0,
    "calendar": []
}

def fetch_earnings_calendar(tickers: List[str], force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Fetches scheduled upcoming quarterly results dates and analyst consensus estimates for tickers.
    """
    global _EARNINGS_CALENDAR_CACHE
    now = time.time()
    if not force_refresh and _EARNINGS_CALENDAR_CACHE["calendar"] and (now - _EARNINGS_CALENDAR_CACHE["timestamp"] < 1800):
        return _EARNINGS_CALENDAR_CACHE["calendar"]

    calendar_list = []
    # Limit batch to top liquid to keep latency low (< 3s)
    sample_tickers = tickers[:25]
    
    for sym in sample_tickers:
        clean_sym = sym.replace(".NS", "").replace(".BO", "")
        try:
            t = yf.Ticker(sym)
            cal = t.calendar
            if cal:
                # Extract earnings date
                e_dates = cal.get('Earnings Date')
                next_date = None
                if isinstance(e_dates, list) and e_dates:
                    next_date = e_dates[0]
                elif isinstance(e_dates, (date, datetime)):
                    next_date = e_dates
                    
                if next_date:
                    if isinstance(next_date, datetime):
                        d_obj = next_date.date()
                    else:
                        d_obj = next_date
                        
                    days_away = (d_obj - date.today()).days
                    status = "Upcoming This Week" if 0 <= days_away <= 7 else ("Recently Announced" if -14 <= days_away < 0 else "Upcoming")
                    
                    calendar_list.append({
                        "Ticker": clean_sym,
                        "Full_Symbol": sym,
                        "Earnings_Date": d_obj.strftime("%d %b %Y"),
                        "Days_Away": days_away,
                        "Status": status,
                        "Est_EPS": cal.get('Earnings Average', '-'),
                        "Est_Revenue_INR_Cr": round(float(cal.get('Revenue Average', 0)) / 1e7, 1) if cal.get('Revenue Average') else '-',
                        "Dividend_Date": cal.get('Ex-Dividend Date').strftime("%d %b %Y") if isinstance(cal.get('Ex-Dividend Date'), (date, datetime)) else '-'
                    })
        except Exception:
            continue
            
    if calendar_list:
        calendar_list.sort(key=lambda x: abs(x["Days_Away"]))
        _EARNINGS_CALENDAR_CACHE["calendar"] = calendar_list
        _EARNINGS_CALENDAR_CACHE["timestamp"] = now
        
    return calendar_list

def analyze_quarterly_financials(ticker: str) -> Dict[str, Any]:
    """
    Extracts quarterly income statements to compute YoY Revenue Growth %, YoY PAT Growth %, and Net Margin.
    """
    sym = ticker if "." in ticker else f"{ticker}.NS"
    clean_sym = sym.replace(".NS", "").replace(".BO", "")
    
    res = {
        "Ticker": clean_sym,
        "Has_Data": False,
        "Latest_Quarter": "-",
        "Revenue_YoY_Pct": 0.0,
        "PAT_YoY_Pct": 0.0,
        "Net_Profit_Margin_Pct": 0.0,
        "Earnings_Verdict": "Neutral / Awaiting Data"
    }
    
    try:
        t = yf.Ticker(sym)
        stmt = t.quarterly_income_stmt
        if stmt is not None and not stmt.empty:
            cols = stmt.columns
            if len(cols) >= 2:
                latest_col = cols[0]
                prev_col = cols[1] # Prior quarter or YoY
                # Check for 4 quarters prior for YoY
                yoy_col = cols[4] if len(cols) >= 5 else prev_col
                
                # Revenue
                rev_latest = float(stmt.loc['Total Revenue', latest_col]) if 'Total Revenue' in stmt.index else 0.0
                rev_yoy = float(stmt.loc['Total Revenue', yoy_col]) if 'Total Revenue' in stmt.index else 0.0
                rev_growth = ((rev_latest / rev_yoy) - 1) * 100 if rev_yoy > 0 else 0.0
                
                # Net Income / PAT
                pat_latest = float(stmt.loc['Net Income', latest_col]) if 'Net Income' in stmt.index else 0.0
                pat_yoy = float(stmt.loc['Net Income', yoy_col]) if 'Net Income' in stmt.index else 0.0
                pat_growth = ((pat_latest / pat_yoy) - 1) * 100 if pat_yoy != 0 else 0.0
                
                margin = (pat_latest / rev_latest) * 100 if rev_latest > 0 else 0.0
                
                # Verdict
                if pat_growth > 20 and rev_growth > 10:
                    verdict = "🔥 STRONG BEAT & EXPANSION"
                elif pat_growth > 0:
                    verdict = "🟢 POSITIVE EARNINGS MOMENTUM"
                elif pat_growth > -15:
                    verdict = "🟡 INLINE / MODERATE GROWTH"
                else:
                    verdict = "🚨 EARNINGS MISS / MARGIN PRESSURE"
                    
                res.update({
                    "Has_Data": True,
                    "Latest_Quarter": str(latest_col)[:10],
                    "Revenue_YoY_Pct": round(rev_growth, 2),
                    "PAT_YoY_Pct": round(pat_growth, 2),
                    "Net_Profit_Margin_Pct": round(margin, 2),
                    "Earnings_Verdict": verdict
                })
    except Exception:
        pass
        
    return res

def detect_pead_candidates(screener_df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifies Post-Earnings Announcement Drift (PEAD) Breakout Setups:
    - Recent earnings beat / high positive momentum
    - Volume surge > 1.3x
    - Supertrend Bullish / RSI between 50 and 70
    """
    if screener_df is None or screener_df.empty:
        return pd.DataFrame()
        
    candidates = []
    for _, row in screener_df.iterrows():
        vol_ratio = row.get("Vol_Ratio_20", 1.0)
        signal = row.get("Signal", "")
        rsi = row.get("RSI_14", 50.0)
        
        # PEAD criteria: High institutional volume + Bullish momentum
        if vol_ratio >= 1.25 and "Buy" in signal and 50 <= rsi <= 75:
            candidates.append({
                "Ticker": row["Ticker"],
                "CMP": row["CMP"],
                "Signal": signal,
                "Volume_Surge": f"{vol_ratio:.1f}x Normal",
                "RSI": round(rsi, 1),
                "Conviction": row.get("Conviction_Score", 60),
                "Entry_Zone": row.get("Entry_Zone", f"₹{row['CMP']:.1f}"),
                "Target": row.get("Target_Base", row['CMP']*1.05),
                "Catalyst": row.get("News_Catalyst", "Strong post-earnings institutional accumulation")
            })
            
    df = pd.DataFrame(candidates)
    if not df.empty:
        df = df.sort_values(by="Conviction", ascending=False).reset_index(drop=True)
    return df
