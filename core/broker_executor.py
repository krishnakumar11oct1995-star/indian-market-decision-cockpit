"""
1-Click Indian Broker Execution Engine
Generates pre-filled, frictionless trade links for Zerodha Kite, Dhan, Upstox, and TradingView India.
"""

import urllib.parse
from typing import Dict, Any

def generate_broker_links(
    ticker: str,
    cmp: float,
    position_size: int,
    stop_loss: float,
    target: float,
    signal: str = "BUY"
) -> Dict[str, str]:
    """
    Generates direct 1-click execution links for major Indian brokers.
    """
    clean_sym = ticker.replace(".NS", "").replace(".BO", "")
    txn_type = "BUY" if "BUY" in signal.upper() else "SELL"
    
    # 1. Zerodha Kite Web Chart & Order Intent
    kite_chart_url = f"https://kite.zerodha.com/chart/ext/tvc/NSE/{clean_sym}"
    # Kite order placement intent parameters
    kite_order_params = {
        "tradingsymbol": clean_sym,
        "exchange": "NSE",
        "transaction_type": txn_type,
        "order_type": "LIMIT",
        "quantity": max(1, position_size),
        "price": f"{cmp:.2f}",
        "trigger_price": f"{stop_loss:.2f}"
    }
    kite_order_url = f"https://kite.zerodha.com/orders/create?{urllib.parse.urlencode(kite_order_params)}"
    
    # 2. Dhan Web Link
    dhan_url = f"https://tradingview.dhan.co/?symbol=NSE:{clean_sym}"
    
    # 3. Upstox Pro Link
    upstox_url = f"https://pro.upstox.com/"
    
    # 4. TradingView India Interactive Chart
    tv_url = f"https://in.tradingview.com/chart/?symbol=NSE:{clean_sym}"
    
    return {
        "Kite_Chart": kite_chart_url,
        "Kite_Order": kite_order_url,
        "Dhan_Chart": dhan_url,
        "Upstox_Pro": upstox_url,
        "TradingView": tv_url
    }

def generate_broker_action_html(
    ticker: str,
    cmp: float,
    position_size: int,
    stop_loss: float,
    target: float,
    signal: str = "BUY"
) -> str:
    """
    Renders styled HTML action buttons for Zerodha, Dhan, Upstox, and TradingView.
    """
    links = generate_broker_links(ticker, cmp, position_size, stop_loss, target, signal)
    
    html = f"""<div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 10px; margin-bottom: 6px;">
    <span style="font-size: 0.78rem; font-weight: 700; color: #94A3B8; text-transform: uppercase;">1-Click Broker Action:</span>
    <a href="{links['Kite_Chart']}" target="_blank" style="background: #E05326; color: #FFFFFF !important; text-decoration: none; padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 0.78rem; display: inline-flex; align-items: center; gap: 4px;">
        ⚡ Zerodha Kite
    </a>
    <a href="{links['Dhan_Chart']}" target="_blank" style="background: #4F46E5; color: #FFFFFF !important; text-decoration: none; padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 0.78rem; display: inline-flex; align-items: center; gap: 4px;">
        ⚡ Dhan TV
    </a>
    <a href="{links['Upstox_Pro']}" target="_blank" style="background: #7C3AED; color: #FFFFFF !important; text-decoration: none; padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 0.78rem; display: inline-flex; align-items: center; gap: 4px;">
        ⚡ Upstox Pro
    </a>
    <a href="{links['TradingView']}" target="_blank" style="background: #0284C7; color: #FFFFFF !important; text-decoration: none; padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 0.78rem; display: inline-flex; align-items: center; gap: 4px;">
        📈 TradingView
    </a>
</div>"""
    return html
