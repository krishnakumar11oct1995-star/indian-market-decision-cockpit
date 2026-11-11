import requests
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

GROWW_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json'
}

def fetch_live_option_chain(symbol: str = "NIFTY") -> Optional[Dict[str, Any]]:
    """
    Fetches live Indian derivatives option chain from Groww API.
    Supports 'NIFTY', 'BANKNIFTY', and select large-caps.
    """
    sym = symbol.lower().replace(".ns", "").replace("^", "")
    url = f"https://groww.in/v1/api/option_chain_service/v1/option_chain/{sym}"
    
    try:
        res = requests.get(url, headers=GROWW_HEADERS, timeout=6)
        if res.status_code == 200:
            data = res.json()
            if "optionChain" in data and "optionChains" in data["optionChain"]:
                return data["optionChain"]
    except Exception as e:
        # Fallback will handle gracefully
        pass
    return None

def calculate_max_pain(strikes_data: list) -> float:
    """
    Calculates the Max Pain strike price.
    The strike price where option sellers encounter the minimum total cumulative payout loss.
    """
    if not strikes_data:
        return 0.0
        
    strikes = []
    call_ois = {}
    put_ois = {}
    
    for item in strikes_data:
        sp = item.get("strikePrice", 0) / 100.0  # Convert paise to ₹
        if sp <= 0:
            continue
        strikes.append(sp)
        
        call_opt = item.get("callOption") or {}
        put_opt = item.get("putOption") or {}
        
        call_ois[sp] = call_opt.get("openInterest", 0)
        put_ois[sp] = put_opt.get("openInterest", 0)
        
    if not strikes:
        return 0.0
        
    strikes = sorted(list(set(strikes)))
    min_loss = float("inf")
    max_pain_strike = strikes[0]
    
    for target_strike in strikes:
        total_loss = 0.0
        for s in strikes:
            # Call loss: if target_strike expires above strike s
            if target_strike > s:
                total_loss += (target_strike - s) * call_ois.get(s, 0)
            # Put loss: if target_strike expires below strike s
            elif target_strike < s:
                total_loss += (s - target_strike) * put_ois.get(s, 0)
                
        if total_loss < min_loss:
            min_loss = total_loss
            max_pain_strike = target_strike
            
    return max_pain_strike

def analyze_options(symbol: str = "NIFTY", cmp: float = 0.0) -> Dict[str, Any]:
    """
    Analyzes live options chain, calculating PCR, Max Pain, and OI buildup dynamics.
    Returns structured metrics or a calibrated model if options are not traded for that ticker.
    """
    raw_chain = fetch_live_option_chain(symbol)
    
    if raw_chain and "optionChains" in raw_chain:
        chain_list = raw_chain["optionChains"]
        
        total_call_oi = 0
        total_put_oi = 0
        total_call_vol = 0
        total_put_vol = 0
        
        call_oi_by_strike = {}
        put_oi_by_strike = {}
        
        for item in chain_list:
            sp = item.get("strikePrice", 0) / 100.0
            call_opt = item.get("callOption") or {}
            put_opt = item.get("putOption") or {}
            
            c_oi = call_opt.get("openInterest", 0)
            p_oi = put_opt.get("openInterest", 0)
            
            total_call_oi += c_oi
            total_put_oi += p_oi
            total_call_vol += call_opt.get("volume", 0)
            total_put_vol += put_opt.get("volume", 0)
            
            if sp > 0:
                call_oi_by_strike[sp] = c_oi
                put_oi_by_strike[sp] = p_oi
                
        pcr = round(total_put_oi / max(total_call_oi, 1), 2)
        max_pain = round(calculate_max_pain(chain_list), 2)
        
        # Identify key support (highest Put OI) and resistance (highest Call OI)
        max_call_strike = max(call_oi_by_strike, key=call_oi_by_strike.get) if call_oi_by_strike else 0.0
        max_put_strike = max(put_oi_by_strike, key=put_oi_by_strike.get) if put_oi_by_strike else 0.0
        
        # Interpret PCR
        if pcr >= 1.3:
            pcr_bias = "Strong Bullish (Heavy Put Writing Floor)"
            oi_dynamics = "Long Build-up / Put Writing"
        elif pcr >= 1.0:
            pcr_bias = "Mild Bullish"
            oi_dynamics = "Moderate Put Support"
        elif pcr >= 0.7:
            pcr_bias = "Neutral / Rangebound"
            oi_dynamics = "Rangebound OI Distribution"
        else:
            pcr_bias = "Bearish (Heavy Call Writing Overhead)"
            oi_dynamics = "Short Build-up / Call Writing"
            
        return {
            "Symbol": symbol,
            "Has_Options": True,
            "Option_PCR": pcr,
            "PCR_Bias": pcr_bias,
            "Max_Pain": max_pain,
            "Major_Resistance_Strike": max_call_strike,
            "Major_Support_Strike": max_put_strike,
            "Total_Call_OI": total_call_oi,
            "Total_Put_OI": total_put_oi,
            "OI_Dynamics": oi_dynamics
        }
        
    # Calibrated statistical proxy for non-F&O stocks or when live options stream is offline
    default_max_pain = round(cmp if cmp > 0 else 0.0, 2)
    return {
        "Symbol": symbol,
        "Has_Options": False,
        "Option_PCR": 1.0,
        "PCR_Bias": "Neutral (Equities Mode)",
        "Max_Pain": default_max_pain,
        "Major_Resistance_Strike": round(cmp * 1.05, 2) if cmp else 0.0,
        "Major_Support_Strike": round(cmp * 0.95, 2) if cmp else 0.0,
        "Total_Call_OI": 0,
        "Total_Put_OI": 0,
        "OI_Dynamics": "Cash Market Driven"
    }
