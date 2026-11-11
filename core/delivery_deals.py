"""
NSE Bulk & Block Deals Engine
Fetches official real-time bulk and block transactions from the National Stock Exchange of India (NSE).
"""

import requests
import pandas as pd
import time
from typing import Dict, Any, List

_DEALS_CACHE = {
    "timestamp": 0,
    "deals": []
}

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

def fetch_nse_bulk_deals(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Fetches real-time official Bulk Deals reported to NSE/SEBI.
    """
    global _DEALS_CACHE
    now = time.time()
    if not force_refresh and _DEALS_CACHE["deals"] and (now - _DEALS_CACHE["timestamp"] < 900):
        return _DEALS_CACHE["deals"]

    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    
    deals_list = []
    try:
        session.get('https://www.nseindia.com', timeout=8)
        session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.nseindia.com/'
        })
        resp = session.get('https://www.nseindia.com/api/snapshot-capital-market-largedeal', timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            raw_deals = data.get('BULK_DEALS_DATA', [])
            
            for d in raw_deals:
                client = d.get('clientName', '').strip()
                sec_name = d.get('name', '').strip()
                action = d.get('buySell', '').upper()
                qty = int(str(d.get('quantity', 0)).replace(',', ''))
                price = float(str(d.get('tradePrice', 0.0)).replace(',', ''))
                val_cr = round((qty * price) / 1e7, 2)
                d_date = d.get('date', '')
                
                deals_list.append({
                    "Date": d_date,
                    "Security": sec_name,
                    "Client_Name": client,
                    "Action": action,
                    "Quantity": qty,
                    "Trade_Price": price,
                    "Turnover_INR_Cr": val_cr
                })
                
            if deals_list:
                deals_list.sort(key=lambda x: x["Turnover_INR_Cr"], reverse=True)
                _DEALS_CACHE["deals"] = deals_list
                _DEALS_CACHE["timestamp"] = now
                return deals_list
    except Exception as e:
        print(f"Error fetching NSE Bulk Deals: {e}")

    if _DEALS_CACHE["deals"]:
        return _DEALS_CACHE["deals"]
        
    return []
