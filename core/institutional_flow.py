"""
Institutional Flow & Sector Rotation Engine
Fetches official NSE daily FII / DII Cash Market flows and computes 9-Sector relative momentum matrix.
"""

import requests
import pandas as pd
import numpy as np
import yfinance as yf
import time
from datetime import datetime
from typing import Dict, Any, List

_FLOW_CACHE = {
    "timestamp": 0,
    "fii_dii": [],
    "sectors": {}
}

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

SECTOR_MAP = {
    "Nifty IT": "^CNXIT",
    "Nifty Bank": "^NSEBANK",
    "Nifty Auto": "^CNXAUTO",
    "Nifty Pharma": "^CNXPHARMA",
    "Nifty FMCG": "^CNXFMCG",
    "Nifty Metal": "^CNXMETAL",
    "Nifty Energy": "^CNXENERGY",
    "Nifty Realty": "^CNXREALTY",
    "Nifty Infra": "^CNXINFRA"
}

def fetch_fii_dii_cash_flows(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Fetches official daily FII and DII Cash Market data from NSE India.
    Returns: List of records with Category, Buy Value, Sell Value, Net Value (₹ Cr), and Date.
    """
    global _FLOW_CACHE
    now = time.time()
    if not force_refresh and _FLOW_CACHE["fii_dii"] and (now - _FLOW_CACHE["timestamp"] < 900):
        return _FLOW_CACHE["fii_dii"]

    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    
    try:
        # Establish session cookies with NSE home
        session.get('https://www.nseindia.com', timeout=8)
        session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.nseindia.com/'
        })
        
        resp = session.get('https://www.nseindia.com/api/fiidiiTradeReact', timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                cleaned = []
                for item in data:
                    cat = item.get('category', '')
                    buy = float(str(item.get('buyValue', 0)).replace(',', ''))
                    sell = float(str(item.get('sellValue', 0)).replace(',', ''))
                    net = float(str(item.get('netValue', 0)).replace(',', ''))
                    date_str = item.get('date', '')
                    cleaned.append({
                        "Category": "FII / FPI" if "FII" in cat.upper() else "DII (Mutual Funds/Ins.)",
                        "Gross_Buy_INR_Cr": buy,
                        "Gross_Sell_INR_Cr": sell,
                        "Net_Inflow_INR_Cr": net,
                        "Trade_Date": date_str
                    })
                _FLOW_CACHE["fii_dii"] = cleaned
                _FLOW_CACHE["timestamp"] = now
                return cleaned
    except Exception as e:
        print(f"Error fetching NSE FII/DII data: {e}")

    # Fallback to cache if available
    if _FLOW_CACHE["fii_dii"]:
        return _FLOW_CACHE["fii_dii"]
        
    return []

def fetch_sector_rotation_matrix(period: str = "1mo") -> pd.DataFrame:
    """
    Fetches real-time performance for core NSE sector indices:
    - Current LTP
    - 1-Day Return (%)
    - 30-Day Return (%)
    - 365-Day Return (%)
    - Relative Momentum Status: Inflow (Leading) vs Outflow (Lagging)
    """
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    
    # 1. Try official NSE allIndices endpoint
    try:
        session.get('https://www.nseindia.com', timeout=8)
        session.headers.update({
            'Accept': 'application/json',
            'Referer': 'https://www.nseindia.com/'
        })
        resp = session.get('https://www.nseindia.com/api/allIndices', timeout=8)
        if resp.status_code == 200:
            all_idx = resp.json().get('data', [])
            target_sectors = {
                "NIFTY IT": "Information Technology",
                "NIFTY BANK": "Banking & Financials",
                "NIFTY AUTO": "Automobile",
                "NIFTY PHARMA": "Pharmaceuticals",
                "NIFTY FMCG": "Fast Moving Consumer Goods",
                "NIFTY METAL": "Metals & Mining",
                "NIFTY ENERGY": "Oil, Gas & Power",
                "NIFTY PSU BANK": "Public Sector Banks",
                "NIFTY PRIVATE BANK": "Private Sector Banks",
                "NIFTY REALTY": "Real Estate",
                "NIFTY INFRASTRUCTURE": "Infrastructure"
            }
            
            rows = []
            for item in all_idx:
                idx_name = item.get('index', '').upper()
                if idx_name in target_sectors:
                    ret_1d = float(item.get('percentChange', 0.0))
                    ret_30d = float(item.get('perChange30d', 0.0))
                    ret_365d = float(item.get('perChange365d', 0.0))
                    ltp = float(item.get('last', 0.0))
                    
                    if ret_1d > 0.8 and ret_30d > -2.0:
                        status = "🔥 LEADING (Active Inflow)"
                    elif ret_1d > 0:
                        status = "🟢 ACCUMULATING"
                    elif ret_1d < -0.8 and ret_30d < -5.0:
                        status = "🚨 LAGGING (Distribution / Outflow)"
                    else:
                        status = "🟡 CONSOLIDATING"
                        
                    rows.append({
                        "Sector": idx_name.replace("NIFTY ", "Nifty "),
                        "Theme": target_sectors[idx_name],
                        "Current_Index": ltp,
                        "Return_1D_Pct": round(ret_1d, 2),
                        "Return_1M_Pct": round(ret_30d, 2),
                        "Return_1Y_Pct": round(ret_365d, 2),
                        "Rotation_Status": status
                    })
                    
            if rows:
                df = pd.DataFrame(rows)
                df = df.sort_values(by="Return_1D_Pct", ascending=False).reset_index(drop=True)
                return df
    except Exception as e:
        print(f"NSE allIndices failed: {e}")
        
    return pd.DataFrame()
