import requests
import json
from typing import Dict, Any, Tuple
import config

_THESIS_CACHE: Dict[str, Tuple[str, str]] = {}

def generate_ai_thesis(
    ticker: str,
    cmp: float,
    signal: str,
    technical_score: int,
    supertrend: str,
    rsi: float,
    pcr: float,
    stop_loss: float,
    target_base: float,
    risk_reward: float
) -> Tuple[str, str]:
    """
    Calls Gemini 2.5 Flash to synthesize an execution thesis and an adversarial audit risk.
    Returns: (Thesis_1_Sentence, Adversarial_Risk_1_Sentence)
    """
    clean_ticker = ticker.replace(".NS", "")
    cache_key = f"{clean_ticker}_{signal}_{round(cmp, 1)}"
    if cache_key in _THESIS_CACHE:
        return _THESIS_CACHE[cache_key]
        
    prompt = f"""
You are a senior quantitative risk auditor and institutional strategist specializing in the Indian stock market (NSE).
Analyze the following parameters for {clean_ticker}:
- Current Price: ₹{cmp:.2f}
- Algorithmic Signal: {signal} (Conviction: {technical_score}/100)
- Supertrend: {supertrend}
- RSI (14): {rsi}
- Option Put-Call Ratio (PCR): {pcr}
- ATR Stop Loss: ₹{stop_loss:.2f}
- Monte Carlo Target: ₹{target_base:.2f} (R:R: {risk_reward:.2f}:1)

Deliver EXACTLY two concise items in valid JSON format:
{{
  "thesis": "A single professional, high-impact sentence summarizing the core technical and order flow trade thesis.",
  "adversarial_risk": "A single sharp, contrarian sentence highlighting the exact fatal flaw or systemic risk that could invalidate this trade."
}}
Return ONLY the raw JSON object, no markdown, no explanations.
"""
    try:
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json"
            }
        }
        res = requests.post(config.GEMINI_ENDPOINT, json=payload, timeout=8)
        if res.status_code == 200:
            data = res.json()
            raw_text = data['candidates'][0]['content']['parts'][0]['text']
            parsed = json.loads(raw_text)
            thesis = parsed.get("thesis", f"Favorable momentum setup for {clean_ticker} targeting ₹{target_base:.2f}.")
            risk = parsed.get("adversarial_risk", f"Break below ₹{stop_loss:.2f} invalidates the setup.")
            _THESIS_CACHE[cache_key] = (thesis, risk)
            return thesis, risk
    except Exception as e:
        pass
        
    # Calibrated deterministic fallback
    fallback_thesis = (
        f"{clean_ticker} shows {signal.lower()} momentum with RSI at {rsi:.1f} and R:R of {risk_reward:.1f}x targeting ₹{target_base:.2f}."
    )
    fallback_risk = (
        f"A decisive daily close below dynamic stop-loss ₹{stop_loss:.2f} signals trend reversal and invalidates position."
    )
    _THESIS_CACHE[cache_key] = (fallback_thesis, fallback_risk)
    return fallback_thesis, fallback_risk
