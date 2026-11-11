from typing import Dict, Any

def calculate_risk_profile(
    cmp: float,
    atr: float,
    target_base: float,
    target_bull: float,
    supertrend_level: float,
    supertrend_trend: int,
    tech_score: int,
    pcr: float,
    max_risk_inr: float = 5000.0
) -> Dict[str, Any]:
    """
    Computes dynamic ATR stop-loss, Risk-to-Reward ratio,
    exact share quantity position sizing, and the final Signal recommendation.
    """
    cmp = float(cmp)
    atr = float(atr)
    target_base = float(target_base)
    target_bull = float(target_bull)
    
    # 1. Dynamic Stop-Loss Calculation
    # If Bullish trend, SL is below CMP.
    # We use 1.5x ATR, while respecting Supertrend trailing support if available.
    atr_buffer = 1.5 * atr
    if supertrend_trend == 1 and supertrend_level < cmp:
        # Use tighter of 1.5x ATR or Supertrend level
        stop_loss = max(cmp - atr_buffer, supertrend_level)
    else:
        stop_loss = cmp - atr_buffer
        
    stop_loss = round(max(stop_loss, 0.05), 2)
    risk_per_share = round(max(cmp - stop_loss, 0.01), 2)
    
    # 2. Risk / Reward Ratios
    base_upside = max(target_base - cmp, 0.0)
    bull_upside = max(target_bull - cmp, 0.0)
    
    rr_base = round(base_upside / risk_per_share, 2)
    rr_bull = round(bull_upside / risk_per_share, 2)
    
    # 3. Position Sizing (Fixed INR Risk Model)
    quantity = int(max_risk_inr // risk_per_share) if risk_per_share > 0 else 0
    total_capital_required = round(quantity * cmp, 2)
    max_capital_at_risk = round(quantity * risk_per_share, 2)
    
    # 4. Multi-Factor Conviction & Signal Determination
    # Factors: Technical score (50%), Option PCR support (25%), R:R Quality (25%)
    conviction = tech_score * 0.5
    
    # Option PCR contribution
    if pcr >= 1.2:
        conviction += 25
    elif pcr >= 0.9:
        conviction += 15
    elif pcr >= 0.7:
        conviction += 5
    else:
        conviction += 0
        
    # R:R contribution
    if rr_base >= 2.5:
        conviction += 25
    elif rr_base >= 1.8:
        conviction += 18
    elif rr_base >= 1.2:
        conviction += 10
    else:
        conviction += 0
        
    conviction = int(round(max(0, min(100, conviction))))
    
    # Final Signal
    if conviction >= 75 and rr_base >= 1.8:
        signal = "Strong Buy"
    elif conviction >= 60 and rr_base >= 1.4:
        signal = "Buy"
    elif conviction <= 30:
        signal = "Strong Sell"
    elif conviction <= 45:
        signal = "Sell"
    else:
        signal = "Neutral"
        
    return {
        "Stop_Loss": stop_loss,
        "Risk_Per_Share": risk_per_share,
        "Risk_Reward_Base": rr_base,
        "Risk_Reward_Bull": rr_bull,
        "Position_Quantity": quantity,
        "Total_Capital_Req": total_capital_required,
        "Max_Risk_INR": max_capital_at_risk,
        "Conviction_Score": conviction,
        "Signal": signal
    }
