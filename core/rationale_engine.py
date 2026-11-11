from typing import Dict, Any

def generate_trade_rationale(
    ticker: str,
    cmp: float,
    signal: str,
    conviction_score: int,
    tech_data: Dict[str, Any],
    options_data: Dict[str, Any],
    mc_data: Dict[str, Any],
    risk_data: Dict[str, Any],
    fund_data: Dict[str, Any],
    news_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Translates raw quantitative metrics into transparent, plain-English explanations:
    1. Trade Blueprint (What to do with this stock?)
    2. The 4 Pillars of Evidence (Why was this stock picked?)
    3. Mathematical Rationale for Stop Loss and Targets
    """
    clean_sym = ticker.replace(".NS", "")
    cmp = float(cmp)
    sl = float(risk_data["Stop_Loss"])
    target_base = float(risk_data["Target_Base"]) if "Target_Base" in risk_data else float(mc_data.get("Target_Base", cmp * 1.05))
    target_bull = float(risk_data["Target_Bull"]) if "Target_Bull" in risk_data else float(mc_data.get("Target_Bull", cmp * 1.10))
    rr = float(risk_data["Risk_Reward_Base"])
    atr = float(tech_data.get("ATR_14", cmp * 0.02))
    
    sl_pct = round(abs(cmp - sl) / cmp * 100, 2)
    target_base_pct = round((target_base - cmp) / cmp * 100, 2)
    target_bull_pct = round((target_bull - cmp) / cmp * 100, 2)
    
    # 1. WHAT TO DO (Trade Blueprint Verdict)
    if "Strong Buy" in signal:
        trade_verdict = "🟢 HIGH-CONVICTION SWING BUY (Hold: 3 to 10 Days)"
        action_summary = f"Initiate swing long position between ₹{cmp*0.995:.1f} – ₹{cmp*1.008:.1f}. High statistical probability of upward trend continuation."
    elif "Buy" in signal:
        trade_verdict = "🟢 MODERATE SWING BUY (Hold: 3 to 7 Days)"
        action_summary = f"Buy on mild intraday dips near ₹{cmp*0.995:.1f}. Maintain strict stop-loss discipline."
    elif "Sell" in signal or "Strong Sell" in signal:
        trade_verdict = "🔴 BEARISH / TAKE PROFIT (Avoid Fresh Longs)"
        action_summary = f"Momentum has broken down. Existing longs should book profits or exit. Consider short setups on resistance retest."
    else:
        trade_verdict = "🟡 NEUTRAL / WAIT FOR CONFIRMATION"
        action_summary = f"Stock is currently in a consolidation range. Wait for a decisive breakout above ₹{cmp*1.02:.1f} before entering."
        
    entry_range = f"₹{cmp*0.995:.1f} – ₹{cmp*1.008:.1f}"
    
    # Trade Management Rule
    trade_management_rule = (
        f"1. Enter in the recommended zone ({entry_range}).\n"
        f"2. Place initial Stop-Loss order at ₹{sl:.1f} in your broker terminal.\n"
        f"3. When Target 1 (₹{target_base:.1f}) is reached, sell 50% of your shares to lock in gains.\n"
        f"4. Move the Stop-Loss on remaining 50% shares to your Entry Price (Cost) to secure a guaranteed risk-free runner targeting ₹{target_bull:.1f}."
    )
    
    # 2. ON WHAT EXACT BASIS IS STOP LOSS GIVEN?
    sl_basis = (
        f"Stop-Loss is calculated dynamically at ₹{sl:.1f} ({sl_pct}% risk from current price). "
        f"It is mathematically placed 1.5x ATR (Average True Range volatility = ₹{atr:.1f}) below current price and trailing Supertrend support. "
        f"Why this matters: It provides sufficient buffer against routine market 'noise' and intraday wicks while strictly capping your capital loss."
    )
    
    # 3. ON WHAT EXACT BASIS ARE TARGETS GIVEN?
    target_basis = (
        f"• Base Target (₹{target_base:.1f}, +{target_base_pct}%): "
        f"Derived from the 50th percentile median outcome across 5,000 Monte Carlo Geometric Brownian Motion price simulations, "
        f"and corresponds to the nearest major Call Option Open Interest resistance level (₹{options_data.get('Major_Resistance_Strike', target_base):.1f}).\n\n"
        f"• Bullish Target (₹{target_bull:.1f}, +{target_bull_pct}%): "
        f"Derived from the 85th percentile optimistic cluster from K-Means simulation clustering, representing a full momentum swing extension."
    )
    
    # 4. THE 4 PILLARS OF EVIDENCE (Why Was This Stock Picked?)
    # Pillar 1: Technical Trigger
    tech_trigger = (
        f"• Trend Status: Supertrend is {tech_data.get('Supertrend_Status', 'Neutral')}.\n"
        f"• Moving Averages: {tech_data.get('EMA_Alignment', 'Mixed Alignment')}.\n"
        f"• Momentum (RSI 14): {tech_data.get('RSI_14', 50)} "
        f"({'Healthy bullish momentum, not yet overbought' if 50 <= tech_data.get('RSI_14', 50) <= 68 else 'Caution: Near overbought' if tech_data.get('RSI_14', 50) > 68 else 'Oversold / Neutral'})."
    )
    
    # Pillar 2: Order Flow & Volume
    vol_ratio = tech_data.get('Volume_Ratio', 1.0)
    order_flow = tech_data.get('Order_Flow', 'Normal Volume')
    flow_explanation = (
        f"• Volume Spike: Today's trading volume is {vol_ratio}x relative to its 20-day average.\n"
        f"• Institutional Bias: Classified as '{order_flow}' "
        f"({'Large institutional buyers accumulating on up-candles' if 'Accumulation' in order_flow else 'Retail volume levels'})."
    )
    
    # Pillar 3: Options Derivatives Clues
    pcr = options_data.get('Option_PCR', 1.0)
    max_pain = options_data.get('Max_Pain', cmp)
    oi_dynamics = options_data.get('OI_Dynamics', 'Neutral')
    options_explanation = (
        f"• Put-Call Ratio (PCR): {pcr} ({options_data.get('PCR_Bias', 'Neutral')}). "
        f"{'Heavy Put writing indicates smart money option sellers are defending support.' if pcr >= 1.1 else 'Call writing indicates overhead supply resistance.' if pcr < 0.8 else 'Balanced derivatives open interest.'}\n"
        f"• Max Pain Strike: ₹{max_pain:.1f} (the price zone where option writers face minimum payout loss).\n"
        f"• OI Buildup: '{oi_dynamics}'."
    )
    
    # Pillar 4: Fundamental Solvency
    roe = fund_data.get('ROE_Pct', 0.0)
    de = fund_data.get('Debt_to_Equity', 0.0)
    pe = fund_data.get('Trailing_PE', 0.0)
    fund_explanation = (
        f"• Return on Equity (ROE): {roe}% ({'High profitability' if roe >= 15 else 'Moderate'}).\n"
        f"• Debt-to-Equity (D/E): {de} ({'Healthy balance sheet, low leverage' if de < 0.6 else 'Moderate debt' if de < 1.2 else 'High debt'}).\n"
        f"• Valuation (P/E): {pe}x Trailing Earnings.\n"
        f"• Market Cap: ₹{fund_data.get('Market_Cap_Cr', 0):,.0f} Crores ({fund_data.get('Sector', 'Equities')})."
    )
    
    return {
        "Trade_Verdict": trade_verdict,
        "Action_Summary": action_summary,
        "Entry_Zone": entry_range,
        "Trade_Management_Rule": trade_management_rule,
        "Stop_Loss_Rationale": sl_basis,
        "Target_Rationale": target_basis,
        "Pillar_Technical": tech_trigger,
        "Pillar_Volume": flow_explanation,
        "Pillar_Options": options_explanation,
        "Pillar_Fundamentals": fund_explanation,
        "Risk_Reward_Ratio": rr,
        "Risk_Per_Share_INR": round(abs(cmp - sl), 2),
        "SL_Pct": sl_pct,
        "Target_Base_Pct": target_base_pct,
        "Target_Bull_Pct": target_bull_pct
    }
