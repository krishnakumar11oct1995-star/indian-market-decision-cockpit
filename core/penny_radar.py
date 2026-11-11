import pandas as pd
import numpy as np
from typing import Dict, Any

def analyze_penny_risk(
    ticker: str,
    cmp: float,
    df: pd.DataFrame,
    fund_data: Dict[str, Any],
    tech_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Forensic Trap & Circuit Lock Detector for Indian Penny Stocks (Sub-₹50 / Sub-₹100).
    Evaluates:
    - Circuit lock frequency (Lower / Upper circuit freezes)
    - Illiquidity risk (Exit slippage)
    - Zombie balance sheet / insolvency clues
    - Turnaround Quality Score (0-100)
    """
    is_penny = cmp < 75.0
    
    if not is_penny:
        return {
            "Is_Penny": False,
            "Circuit_Risk": "LOW (Normal Liquid Equities)",
            "Liquidity_Rating": "High Institutional Liquidity",
            "Turnaround_Score": 0,
            "Turnaround_Verdict": "Standard Large/Mid-Cap",
            "Trap_Warning": None,
            "Max_Allocation_Guidance": "Standard position sizing applies."
        }
        
    close = df['Close']
    high = df['High']
    low = df['Low']
    vol = df['Volume']
    
    # 1. Circuit Lock Analysis
    # Daily range compression (< 0.5% between High and Low) indicates circuit lock
    daily_range_pct = ((high - low) / close.replace(0, np.nan)).tail(20)
    circuit_days = int((daily_range_pct < 0.006).sum())
    
    if circuit_days >= 5:
        circuit_risk = "🚨 EXTREME (Frequent Circuit Locks)"
        circuit_warning_badge = "🚨 CIRCUIT LOCK RISK (Zero Buyers/Sellers Possible)"
    elif circuit_days >= 2:
        circuit_risk = "⚠️ MODERATE (Occasional Circuit Freezes)"
        circuit_warning_badge = "⚠️ CIRCUIT SENSITIVE"
    else:
        circuit_risk = "🟢 LOW (Continuous Two-Way Trading)"
        circuit_warning_badge = "🟢 LIQUID PENNY STOCK"
        
    # 2. Illiquidity Analysis
    avg_vol_20 = float(vol.rolling(20).mean().iloc[-1]) if len(vol) >= 20 else float(vol.mean())
    if avg_vol_20 < 200000:
        liquidity_rating = "🔴 ILLIQUID TRAP (<2 Lakh Daily Volume)"
    elif avg_vol_20 < 1000000:
        liquidity_rating = "🟡 MODERATE (2-10 Lakh Daily Volume)"
    else:
        liquidity_rating = "🟢 HIGH LIQUIDITY (>10 Lakh Daily Volume)"
        
    # 3. Turnaround Quality Score (0 to 100)
    score = 20  # Base speculative baseline
    
    # Trend Recovery (> 200 EMA)
    ema200 = tech_data.get("EMA_200", 0.0)
    if ema200 > 0 and cmp > ema200:
        score += 30
        trend_note = "Bullish Recovery (Trading ABOVE 200-day EMA)"
    else:
        trend_note = "Downtrend / Below 200-day EMA"
        
    # Moving Average Momentum (20 > 50 EMA)
    ema20 = tech_data.get("EMA_20", 0.0)
    ema50 = tech_data.get("EMA_50", 0.0)
    if ema20 > ema50:
        score += 15
        
    # Fundamental Solvency (Debt/Equity & ROE)
    de = fund_data.get("Debt_to_Equity", 0.0)
    roe = fund_data.get("ROE_Pct", 0.0)
    
    if de < 1.0:
        score += 20
        debt_note = f"Manageable Debt (D/E: {de})"
    elif de > 3.0:
        score -= 15
        debt_note = f"🚨 Heavy Debt Burden (D/E: {de})"
    else:
        debt_note = f"Moderate Leverage (D/E: {de})"
        
    if roe > 0.0:
        score += 15
        profit_note = f"Profitable Operating Cash Flow (ROE: {roe}%)"
    else:
        profit_note = f"Loss-Making / Negative Net Worth (ROE: {roe}%)"
        
    score = max(0, min(100, score))
    
    if score >= 70:
        turnaround_verdict = "✨ GENUINE TURNAROUND CANDIDATE (Trend + Solvency)"
    elif score >= 45:
        turnaround_verdict = "🟡 SPECULATIVE RECOVERY SETUP (High Volatility)"
    else:
        turnaround_verdict = "🚨 HIGH-RISK ZOMBIE / OPERATOR TRAP"
        
    # Circuit-Breaker Stop-Loss Warning
    trap_warning_text = (
        f"🚨 PENNY STOCK RISK NOTICE: On sub-₹50 stocks, Stop-Loss orders CANNOT trigger if the stock opens at a Lower Circuit limit (zero market buyers). "
        f"Circuit status: {circuit_risk}. "
        f"Golden Rule: Never allocate more than 2% to 5% of your total trading capital to this stock!"
    )
    
    return {
        "Is_Penny": True,
        "Circuit_Risk": circuit_risk,
        "Circuit_Warning_Badge": circuit_warning_badge,
        "Liquidity_Rating": liquidity_rating,
        "Turnaround_Score": score,
        "Turnaround_Verdict": turnaround_verdict,
        "Trend_Note": trend_note,
        "Debt_Note": debt_note,
        "Profit_Note": profit_note,
        "Trap_Warning": trap_warning_text,
        "Max_Allocation_Guidance": "Max 2% – 5% of total portfolio capital."
    }
