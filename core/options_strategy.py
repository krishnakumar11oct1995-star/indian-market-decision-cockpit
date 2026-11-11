"""
Multi-Leg Defined-Risk F&O Option Strategy Engine
Constructs Bull Call Spreads & Bear Put Spreads and generates interactive Plotly Payoff Curves.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any, Optional
from core.options import fetch_live_option_chain

# Standard NSE F&O Lot Sizes
F_O_LOT_SIZES = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "RELIANCE": 250,
    "TCS": 175,
    "HDFCBANK": 550,
    "INFY": 400,
    "ICICIBANK": 700,
    "SBIN": 1500,
    "BHARTIARTL": 475,
    "LT": 175,
    "TATAMOTORS": 1425,
    "MARUTI": 50,
    "BAJFINANCE": 125,
    "AXISBANK": 625,
    "KOTAKBANK": 400,
    "TITAN": 175
}

def construct_defined_risk_spread(
    ticker: str,
    cmp: float,
    signal: str = "BUY",
    target_price: Optional[float] = None,
    stop_loss: Optional[float] = None
) -> Dict[str, Any]:
    """
    Constructs an optimal 2-leg defined-risk options spread (Bull Call or Bear Put).
    """
    clean_sym = ticker.replace(".NS", "").replace(".BO", "")
    lot_size = F_O_LOT_SIZES.get(clean_sym, 250)
    is_bullish = "BUY" in signal.upper()
    
    # 1. Fetch Option Chain
    raw_opt = fetch_live_option_chain(clean_sym)
    strikes = []
    if raw_opt and "optionChains" in raw_opt:
        strikes = [item.get("strikePrice", 0) / 100.0 for item in raw_opt["optionChains"] if item.get("strikePrice", 0) > 0]
    
    if not strikes:
        # Generate synthetic strikes based on CMP
        step = 50 if cmp > 1000 else (20 if cmp > 300 else 5)
        atm_strike = round(cmp / step) * step
        otm_strike = atm_strike + (step * 2 if is_bullish else -step * 2)
        atm_prem = round(cmp * 0.025, 1) # Estimated 2.5% premium
        otm_prem = round(cmp * 0.010, 1) # Estimated 1.0% premium
    else:
        # Find closest ATM strike
        atm_strike = min(strikes, key=lambda x: abs(x - cmp))
        if is_bullish:
            otm_candidates = [s for s in strikes if s > atm_strike]
            target_strike = target_price if target_price else (cmp * 1.05)
            otm_strike = min(otm_candidates, key=lambda x: abs(x - target_strike)) if otm_candidates else atm_strike + 50
        else:
            otm_candidates = [s for s in strikes if s < atm_strike]
            target_strike = target_price if target_price else (cmp * 0.95)
            otm_strike = min(otm_candidates, key=lambda x: abs(x - target_strike)) if otm_candidates else atm_strike - 50
            
        atm_prem = round(cmp * 0.022, 1)
        otm_prem = round(cmp * 0.009, 1)

    # Strategy Calculations
    strategy_name = "Bull Call Spread" if is_bullish else "Bear Put Spread"
    net_debit = max(0.5, atm_prem - otm_prem)
    strike_diff = abs(otm_strike - atm_strike)
    
    max_loss_per_share = net_debit
    max_profit_per_share = max(0.1, strike_diff - net_debit)
    
    total_max_loss = max_loss_per_share * lot_size
    total_max_profit = max_profit_per_share * lot_size
    
    break_even = (atm_strike + net_debit) if is_bullish else (atm_strike - net_debit)
    rr_ratio = round(total_max_profit / total_max_loss, 2) if total_max_loss > 0 else 1.0

    return {
        "Ticker": clean_sym,
        "CMP": cmp,
        "Strategy_Name": strategy_name,
        "Lot_Size": lot_size,
        "Is_Bullish": is_bullish,
        "Leg_1": f"BUY Strike {atm_strike:.0f} {'CE' if is_bullish else 'PE'} @ ₹{atm_prem:.1f}",
        "Leg_2": f"SELL Strike {otm_strike:.0f} {'CE' if is_bullish else 'PE'} @ ₹{otm_prem:.1f}",
        "ATM_Strike": atm_strike,
        "OTM_Strike": otm_strike,
        "Net_Debit_INR": net_debit,
        "Break_Even": break_even,
        "Max_Loss_INR": total_max_loss,
        "Max_Profit_INR": total_max_profit,
        "Risk_Reward": rr_ratio
    }

def generate_payoff_figure(spread_data: Dict[str, Any]) -> go.Figure:
    """
    Generates an interactive Plotly graph showing P&L at expiration across stock prices.
    """
    cmp = spread_data["CMP"]
    atm_s = spread_data["ATM_Strike"]
    otm_s = spread_data["OTM_Strike"]
    lot = spread_data["Lot_Size"]
    debit = spread_data["Net_Debit_INR"]
    is_bull = spread_data["Is_Bullish"]
    
    # Generate price range +/- 10% around CMP
    prices = np.linspace(cmp * 0.88, cmp * 1.12, 100)
    pnl = []
    
    for p in prices:
        if is_bull:
            # Bull Call Spread payoff: Long Call + Short Call - Debit
            payoff_long = max(0, p - atm_s)
            payoff_short = max(0, p - otm_s)
            total_share_pnl = payoff_long - payoff_short - debit
        else:
            # Bear Put Spread payoff: Long Put + Short Put - Debit
            payoff_long = max(0, atm_s - p)
            payoff_short = max(0, otm_s - p)
            total_share_pnl = payoff_long - payoff_short - debit
            
        pnl.append(total_share_pnl * lot)
        
    pnl = np.array(pnl)
    
    fig = go.Figure()
    
    # Zero line
    fig.add_hline(y=0, line_dash="dash", line_color="#94A3B8", opacity=0.7)
    
    # Current CMP vertical line
    fig.add_vline(x=cmp, line_dash="dot", line_color="#38BDF8", annotation_text=f"CMP ₹{cmp:.1f}", annotation_position="top left")
    
    # Break Even vertical line
    be = spread_data["Break_Even"]
    fig.add_vline(x=be, line_dash="dot", line_color="#FCD34D", annotation_text=f"BE ₹{be:.1f}", annotation_position="bottom right")

    # Payoff line
    fig.add_trace(go.Scatter(
        x=prices,
        y=pnl,
        mode="lines",
        name=spread_data["Strategy_Name"],
        line=dict(color="#10B981" if is_bull else "#EF4444", width=3),
        fill='tozeroy',
        fillcolor="rgba(16, 185, 129, 0.1)" if is_bull else "rgba(239, 68, 68, 0.1)"
    ))
    
    fig.update_layout(
        template="plotly_dark",
        title=f"Defined-Risk Expiration Payoff: {spread_data['Strategy_Name']} ({spread_data['Ticker']})",
        xaxis_title="Stock Price at Expiration (₹)",
        yaxis_title="Total Profit / Loss (₹)",
        height=320,
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=False
    )
    
    return fig
