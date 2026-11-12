import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import os
import sys

# Ensure local modules are accessible
sys.path.insert(0, os.path.dirname(__file__))

import config
from core.pipeline import run_screener_pipeline, process_single_ticker
from core.screener import fetch_batch_ohlcv
from core.debugger import audit_and_debug_predictions
from core.ipo_radar import fetch_active_and_upcoming_ipos, fetch_ipo_news_and_reviews, generate_ipo_verdict
from core.institutional_flow import fetch_fii_dii_cash_flows, fetch_sector_rotation_matrix
from core.earnings_engine import fetch_earnings_calendar, analyze_quarterly_financials, detect_pead_candidates
from core.broker_executor import generate_broker_action_html, generate_broker_links
from core.delivery_deals import fetch_nse_bulk_deals
from core.options_strategy import construct_defined_risk_spread, generate_payoff_figure
from core.alerts_bot import send_telegram_notification, format_trade_alert, format_ipo_alert
from reports.pdf_generator import generate_pdf_dossier
import db.storage as storage

st.set_page_config(
    page_title="Indian Market Decision Cockpit",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern FinTech UI & high-contrast typography
st.html("""
<style>
    .trade-card {
        background: #1E293B !important;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        color: #F8FAFC !important;
    }
    .badge-buy {
        background-color: #065F46 !important;
        color: #6EE7B7 !important;
        padding: 6px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.9rem;
        display: inline-block;
    }
    .badge-sell {
        background-color: #7F1D1D !important;
        color: #FCA5A5 !important;
        padding: 6px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.9rem;
        display: inline-block;
    }
    .badge-neutral {
        background-color: #374151 !important;
        color: #D1D5DB !important;
        padding: 6px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.9rem;
        display: inline-block;
    }
    .news-pill {
        background: #0F766E !important;
        color: #CCFBF1 !important;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 0px;
    }
    .metric-bubble {
        background: #0F172A !important;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
        color: #F8FAFC !important;
    }
    .pillar-box {
        background: #0F172A !important;
        border-left: 4px solid #38BDF8;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
        color: #F1F5F9 !important;
    }
    .guide-box {
        background: #1E293B !important;
        border: 1px solid #475569;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 16px;
        color: #F1F5F9 !important;
    }
    .guide-box h4 {
        color: #38BDF8 !important;
        margin-top: 0;
    }
    .guide-box ol, .guide-box li {
        color: #E2E8F0 !important;
        margin-bottom: 6px;
    }
</style>
""")

# Session state initialization
if "screener_df" not in st.session_state:
    st.session_state["screener_df"] = None
if "last_scan_time" not in st.session_state:
    st.session_state["last_scan_time"] = None
if "single_stock_dict" not in st.session_state:
    st.session_state["single_stock_dict"] = {}
if "active_deep_dive_ticker" not in st.session_state:
    st.session_state["active_deep_dive_ticker"] = None
if "ipo_list" not in st.session_state:
    st.session_state["ipo_list"] = []
if "ipo_verdicts" not in st.session_state:
    st.session_state["ipo_verdicts"] = {}

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.title("🎯 Cockpit Controls")
    
    st.subheader("⚙️ Trade & AI Settings")
    risk_budget = st.slider("Your Max ₹ Risk per Trade", min_value=1000, max_value=25000, value=5000, step=500)
    enable_ai = st.toggle("Enable Gemini 2.5 Flash Synthesis", value=True)
    
    st.markdown("---")
    # Universal Ticker Search
    st.subheader("🔍 Search ANY NSE Ticker")
    search_query = st.text_input("Symbol", placeholder="e.g. TATAPOWER, ZOMATO, SUZLON, HAL")
    search_btn = st.button("⚡ Analyze Stock Now", type="secondary", use_container_width=True)
    
    if search_btn and search_query.strip():
        raw_sym = search_query.strip().upper()
        candidates_to_try = [raw_sym] if "." in raw_sym else [f"{raw_sym}.NS", f"{raw_sym}.BO"]
        
        found = False
        with st.spinner(f"Running full 4-Pillar & News analysis for {raw_sym}..."):
            ohlcv_map = fetch_batch_ohlcv(candidates_to_try, period="6mo")
            for clean_sym in candidates_to_try:
                if clean_sym in ohlcv_map and not ohlcv_map[clean_sym].empty:
                    res = process_single_ticker(clean_sym, ohlcv_map[clean_sym], enable_ai=enable_ai, max_risk_inr=float(risk_budget))
                    if res:
                        st.session_state["single_stock_dict"][clean_sym] = res
                        st.session_state["active_deep_dive_ticker"] = clean_sym
                        storage.record_prediction(
                            ticker=res['Ticker'],
                            cmp_at_pred=res['CMP'],
                            signal=res['Signal'],
                            conviction_score=res['Conviction_Score'],
                            stop_loss=res['Stop_Loss'],
                            target_base=res['Target_Base'],
                            target_bull=res['Target_Bull'],
                            risk_reward=res['Risk_Reward'],
                            thesis=res['Thesis']
                        )
                        st.success(f"Analyzed {clean_sym}! View details below or in Deep-Dive tab.")
                        found = True
                        break
            if not found:
                st.error(f"Could not fetch data for '{raw_sym}'. Please verify the NSE/BSE symbol.")
                
    st.markdown("---")
    st.subheader("📊 Universe Screener")
    universe_choice = st.selectbox(
        "Screening Universe",
        ["Nifty 50 (Top Liquid)", "🪙 Liquid Penny & Sub-₹50 Turnaround", "Nifty IT", "Nifty Private Bank", "Custom Basket"]
    )
    
    if universe_choice == "Nifty 50 (Top Liquid)":
        tickers = config.NIFTY_50_TICKERS
    elif universe_choice == "🪙 Liquid Penny & Sub-₹50 Turnaround":
        tickers = config.PENNY_STOCK_TICKERS
    elif universe_choice == "Nifty IT":
        tickers = ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS", "LTIM.NS"]
    elif universe_choice == "Nifty Private Bank":
        tickers = ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS"]
    else:
        custom_input = st.text_area("Enter NSE symbols (comma-separated)", "RELIANCE.NS, TCS.NS, HDFCBANK.NS, INFY.NS")
        tickers = [s.strip().upper() for s in custom_input.split(",") if s.strip()]
        
    strategy = st.selectbox(
        "Screening Strategy",
        ["all", "momentum", "breakout", "dip_buy"],
        format_func=lambda x: {
            "all": "⚡ Full Market Scan",
            "momentum": "🚀 Momentum & Trend Alignment",
            "breakout": "🔥 Volume & Range Breakout",
            "dip_buy": "🛡️ 200 EMA Pullback / Dip"
        }.get(x, x)
    )
    
    scan_btn = st.button("🚀 Run Screening Cockpit", type="primary", use_container_width=True)
    
    st.markdown("---")
    st.caption("⚙️ **Engine:** Python 3.14 + Gemini 2.5 Flash + SQLite")

# --- MAIN DASHBOARD HEADER ---
st.title("📈 Indian Market Decision Support & Screening Cockpit")
st.markdown("Quantitative Screener • Live Indian News & Catalysts • 4 Pillars of Evidence • Stop Loss & Target Rationale")
st.caption("⚠️ Educational/informational tool only. Not investment advice. The author is not a SEBI-registered investment adviser or research analyst. Do your own research and consult a registered adviser before trading.")

# --- INTERACTIVE HOW-TO GUIDE ACCORDION ---
with st.expander("💡 How to Understand & Trade with This Cockpit (Trader's Guide)", expanded=False):
    st.html("""<div class="guide-box">
<h4>🎯 4-Step Rule for Every Trade:</h4>
<ol>
    <li><b>Check the Verdict & Conviction:</b> Look for <code>🟢 SWING BUY</code> cards with Conviction Score ≥ 60. This means technical trend, options open interest, and fundamentals all align in the same direction.</li>
    <li><b>Check the News & Catalyst:</b> Understand <i>why</i> the stock is in the news today. Earnings beat? Large contract? Sector rally? Never buy a stock without knowing its catalyst.</li>
    <li><b>Observe the Entry Zone & Stop-Loss:</b> Always enter within the suggested Entry Zone. Place the Stop-Loss in your broker terminal immediately. The Stop-Loss is calculated 1.5x ATR below support to prevent false morning intraday shakeouts.</li>
    <li><b>Execute the Profit-Taking Rule:</b> When <b>Target 1</b> is hit, book 50% profit. Immediately move your Stop-Loss on remaining shares to your Entry Price (Cost). This guarantees zero risk on the remaining runner targeting Target 2!</li>
</ol>
</div>""")

# --- EXECUTION TRIGGER ---
if scan_btn:
    progress_bar = st.progress(0.0)
    status_text = st.empty()
    
    def on_progress(pct, msg):
        progress_bar.progress(pct)
        status_text.text(msg)
        
    with st.spinner("Executing quantitative analysis, news synthesis, and rationale pipeline..."):
        df_result = run_screener_pipeline(
            tickers=tickers,
            strategy=strategy,
            enable_ai=enable_ai,
            max_risk_inr=float(risk_budget),
            progress_callback=on_progress
        )
        st.session_state["screener_df"] = df_result
        st.session_state["last_scan_time"] = datetime.now().strftime("%I:%M:%S %p IST")
        progress_bar.empty()
        status_text.empty()
        st.success(f"Scan complete for {len(tickers)} stocks at {st.session_state['last_scan_time']}!")

df = st.session_state.get("screener_df")

# Top KPI Metric Strip
if df is not None and not df.empty:
    col1, col2, col3, col4, col5 = st.columns(5)
    total_stocks = len(df)
    bull_count = int((df['Signal'].isin(['Strong Buy', 'Buy'])).sum())
    bear_count = int((df['Signal'].isin(['Strong Sell', 'Sell'])).sum())
    top_pick = df.iloc[0]['Ticker']
    top_conviction = df.iloc[0]['Conviction_Score']
    
    with col1:
        st.metric("Total Analyzed", f"{total_stocks} Stocks")
    with col2:
        st.metric("Bullish Setups", f"{bull_count}", delta=f"{round(bull_count/total_stocks*100)}%")
    with col3:
        st.metric("Bearish Setups", f"{bear_count}", delta=f"-{round(bear_count/total_stocks*100)}%", delta_color="inverse")
    with col4:
        st.metric("Top Setup", top_pick)
    with col5:
        st.metric("Top Conviction", f"{top_conviction}/100")

# --- TABS INTERFACE ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "🎯 Actionable Trade Cards",
    "🔬 Stock Deep-Dive & Charts",
    "📊 Institutional Data Table",
    "🎲 Prediction Debugger & Self-Calibration",
    "💼 Watchlist & Paper Trades",
    "🚀 IPO Radar & Reviews",
    "🏛️ Institutional Flows & Heatmap",
    "📅 Earnings & PEAD Radar",
    "📦 Bulk Deals Tracker",
    "🔔 Telegram Alert Station"
])

# --- TAB 1: VISUAL TRADE CARDS ---
with tab1:
    # Combine screener df rows and any individually searched stocks
    cards_list = []
    if df is not None and not df.empty:
        cards_list.extend(df.to_dict(orient='records'))
    for sym, s_data in st.session_state["single_stock_dict"].items():
        if not any(c['Ticker'] == sym for c in cards_list):
            cards_list.insert(0, s_data)
            
    if cards_list:
        st.subheader("Actionable Trade Blueprints")
        
        # Filtering controls
        col_f1, col_f2 = st.columns([2, 2])
        with col_f1:
            filter_sig = st.multiselect(
                "Filter by Verdict",
                ["Strong Buy", "Buy", "Neutral", "Sell", "Strong Sell"],
                default=["Strong Buy", "Buy", "Neutral", "Sell", "Strong Sell"]
            )
        with col_f2:
            min_score = st.slider("Minimum Conviction Score", 0, 100, 40, 5)
            
        filtered_cards = [
            c for c in cards_list 
            if c.get('Signal') in filter_sig and c.get('Conviction_Score', 0) >= min_score
        ]
        
        st.caption(f"Showing {len(filtered_cards)} actionable setups matching your criteria.")
        
        for item in filtered_cards:
            ticker = item['Ticker']
            cmp = item['CMP']
            verdict = item.get('Trade_Verdict', f"{item['Signal']} Setup")
            badge_class = "badge-buy" if "Buy" in item['Signal'] else "badge-sell" if "Sell" in item['Signal'] else "badge-neutral"
            
            # Penny Stock Forensic Warning Box
            penny_banner_html = ""
            if item.get("Is_Penny"):
                penny_banner_html = f"""<div style="background: rgba(220, 38, 38, 0.15); border: 1px solid #EF4444; border-radius: 8px; padding: 10px 14px; margin-bottom: 14px;">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
<span style="color: #F87171; font-weight: 800; font-size: 0.88rem;">🚨 PENNY STOCK CIRCUIT & OPERATOR WARNING</span>
<span style="background: #7F1D1D; color: #FECACA; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700;">{item.get('Circuit_Warning_Badge', 'CIRCUIT SENSITIVE')}</span>
</div>
<span style="color: #FEE2E2; font-size: 0.85rem; line-height: 1.4;">
<b>Crucial Risk:</b> Stop-Loss orders CANNOT execute during Lower Circuit freezes (zero buyers). Never allocate more than 2% to 5% of total capital!
</span><br/>
<div style="margin-top: 6px; font-size: 0.8rem; color: #FCD34D;">
<b>Turnaround Rating:</b> {item.get('Turnaround_Score', 0)}/100 ({item.get('Turnaround_Verdict', 'Speculative')}) | <b>Liquidity:</b> {item.get('Liquidity_Rating', 'Standard')}
</div>
</div>"""
            
            # 1-Click Broker Action Bar
            broker_bar_html = generate_broker_action_html(
                ticker=ticker,
                cmp=cmp,
                position_size=item.get('Position_Size', 10),
                stop_loss=item.get('Stop_Loss', cmp * 0.98),
                target=item.get('Target_Base', cmp * 1.05),
                signal=item.get('Signal', 'BUY')
            )
            
            card_html = f"""<div class="trade-card">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
<div>
<span style="font-size: 1.4rem; font-weight: 800; color: #F8FAFC;">{ticker}</span>
<span style="color: #94A3B8; font-size: 0.9rem; margin-left: 10px;">{item.get('Sector', 'Equities')}</span>
</div>
<div style="text-align: right;">
<span style="font-size: 1.5rem; font-weight: 800; color: #38BDF8;">₹{cmp:,.2f}</span>
</div>
</div>
<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 14px; flex-wrap: wrap;">
<span class="{badge_class}">{verdict}</span>
<span style="background: #334155; color: #F1F5F9; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 0.85rem;">
Conviction: {item['Conviction_Score']}/100
</span>
<span class="news-pill">🔥 {item.get('News_Type', 'Market Move')}</span>
</div>
{penny_banner_html}
<div style="background: rgba(15, 23, 42, 0.6); border-left: 4px solid #F59E0B; padding: 10px 14px; border-radius: 6px; margin-bottom: 14px;">
<span style="color: #FCD34D; font-weight: 700;">📰 Why In The News Today:</span><br/>
<span style="color: #E2E8F0; font-size: 0.9rem;">{item.get('News_Catalyst', item.get('Thesis', 'Tracking index momentum.'))}</span>
</div>
<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px;">
<div class="metric-bubble">
<span style="color: #94A3B8; font-size: 0.75rem;">ENTRY ZONE</span><br/>
<span style="color: #F8FAFC; font-weight: 700; font-size: 0.95rem;">{item.get('Entry_Zone', f'₹{cmp:.1f}')}</span>
</div>
<div class="metric-bubble">
<span style="color: #F87171; font-size: 0.75rem;">STOP LOSS</span><br/>
<span style="color: #EF4444; font-weight: 700; font-size: 0.95rem;">₹{item['Stop_Loss']:,.1f} (-{item.get('SL_Pct', 2.0)}%)</span>
</div>
<div class="metric-bubble">
<span style="color: #34D399; font-size: 0.75rem;">BASE TARGET</span><br/>
<span style="color: #10B981; font-weight: 700; font-size: 0.95rem;">₹{item['Target_Base']:,.1f} (+{item.get('Target_Base_Pct', 5.0)}%)</span>
</div>
<div class="metric-bubble">
<span style="color: #38BDF8; font-size: 0.75rem;">RISK : REWARD</span><br/>
<span style="color: #38BDF8; font-weight: 700; font-size: 0.95rem;">1 : {item['Risk_Reward']:.2f}x</span>
</div>
</div>
<div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 10px 14px; margin-bottom: 12px;">
<span style="color: #34D399; font-weight: 700;">💰 Sizing for Your ₹{risk_budget:,.0f} Risk Budget:</span>
<span style="color: #F1F5F9; margin-left: 8px;">Buy <b>{item['Position_Size']} shares</b> (Required Capital: ₹{item.get('Total_Capital_Req', item['Position_Size']*cmp):,.0f} | Max Risk if SL hits: ₹{item.get('Max_Risk_INR', risk_budget):,.0f})</span>
</div>
{broker_bar_html}
</div>"""
            
            with st.container():
                st.html(card_html)
                
                # Expandable Deep-Dive Rationale Drawer
                with st.expander(f"🔍 Open Complete Rationale & 4 Pillars Dossier for {ticker}", expanded=False):
                    sub_t1, sub_t2, sub_t3, sub_t4, sub_t5 = st.tabs([
                        "📋 Execution Rules",
                        "📐 The 4 Pillars of Evidence",
                        "🛑 Stop-Loss & Target Math",
                        "📰 Live News Feed",
                        "⛓️ F&O Option Strategy"
                    ])
                    
                    with sub_t1:
                        st.markdown(f"**Action Summary:** {item.get('Action_Summary', 'Follow standard swing guidelines.')}")
                        st.info(f"**Trade Management Rule:**\n\n{item.get('Trade_Management_Rule', 'Book 50% at Target 1; trail SL to entry.')}")
                        st.warning(f"**⚠️ Adversarial Risk Check (What can kill this trade?):**\n\n{item.get('Adversarial_Risk', 'Decisive close below stop loss invalidates trade.')}")
                        
                    with sub_t2:
                        st.markdown("#### Why Was This Stock Picked? (The 4 Pillars)")
                        c_p1, c_p2 = st.columns(2)
                        with c_p1:
                            st.html(f"""<div class="pillar-box">
<b>📊 Pillar 1: Technical Trigger</b><br/>
{item.get('Pillar_Technical', 'Technical indicators aligned.')}
</div>
<div class="pillar-box">
<b>🌊 Pillar 2: Volume & Order Flow</b><br/>
{item.get('Pillar_Volume', 'Normal volume.')}
</div>""")
                        with c_p2:
                            st.html(f"""<div class="pillar-box">
<b>⛓️ Pillar 3: Options Smart Money</b><br/>
{item.get('Pillar_Options', 'Balanced options OI.')}
</div>
<div class="pillar-box">
<b>🏢 Pillar 4: Fundamental Solvency</b><br/>
{item.get('Pillar_Fundamentals', 'Fundamental metrics normal.')}
</div>""")
                            
                    with sub_t3:
                        st.markdown("#### Mathematical Basis for Levels")
                        st.write(item.get('Stop_Loss_Rationale', 'Calculated 1.5x ATR below support.'))
                        st.markdown("---")
                        st.write(item.get('Target_Rationale', 'Derived from Monte Carlo simulation.'))
                        
                    with sub_t4:
                        st.markdown(f"#### Live News Headlines for {ticker}")
                        headlines = item.get('News_Headlines', [])
                        if headlines:
                            for h in headlines:
                                link_html = f"<a href='{h.get('link', '#')}' target='_blank' style='color: #38BDF8; font-weight: 600;'>{h.get('title')}</a>"
                                st.markdown(f"• {link_html} — *{h.get('publisher')}* ({h.get('pubDate', '')})", unsafe_allow_html=True)
                        else:
                            st.write("No major breaking headlines found today.")

                    with sub_t5:
                        st.markdown(f"#### ⛓️ Defined-Risk Multi-Leg F&O Spread: {ticker}")
                        spread_info = construct_defined_risk_spread(
                            ticker=ticker,
                            cmp=cmp,
                            signal=item.get('Signal', 'BUY'),
                            target_price=item.get('Target_Base'),
                            stop_loss=item.get('Stop_Loss')
                        )
                        c_s1, c_s2, c_s3, c_s4 = st.columns(4)
                        with c_s1:
                            st.metric("Setup", spread_info['Strategy_Name'])
                        with c_s2:
                            st.metric("NSE Lot Size", f"{spread_info['Lot_Size']} shares")
                        with c_s3:
                            st.metric("Max Profit", f"₹{spread_info['Max_Profit_INR']:,.0f}", delta=f"R:R 1:{spread_info['Risk_Reward']:.2f}")
                        with c_s4:
                            st.metric("Max Defined Risk", f"₹{spread_info['Max_Loss_INR']:,.0f}", delta_color="inverse")
                            
                        st.html(f"""<div style="background: #0F172A; border: 1px solid #334155; border-radius: 8px; padding: 12px 16px; margin: 10px 0;">
<div style="color: #38BDF8; font-weight: 700; margin-bottom: 6px;">📋 Spread Execution Orders:</div>
<div style="color: #34D399; font-size: 0.92rem; margin-bottom: 4px;">🟢 <b>Leg 1 (Long):</b> {spread_info['Leg_1']}</div>
<div style="color: #F87171; font-size: 0.92rem; margin-bottom: 4px;">🔴 <b>Leg 2 (Short):</b> {spread_info['Leg_2']}</div>
<div style="color: #94A3B8; font-size: 0.82rem; margin-top: 6px;"><b>Net Debit:</b> ₹{spread_info['Net_Debit_INR']:.2f}/share | <b>Break-Even At Expiry:</b> ₹{spread_info['Break_Even']:.2f}</div>
</div>""")
                        
                        payoff_fig = generate_payoff_figure(spread_info)
                        st.plotly_chart(payoff_fig, use_container_width=True)
                        
                # Quick Action Buttons
                c_act1, c_act2 = st.columns([4, 1])
                with c_act2:
                    if st.button(f"🔔 Send Alert", key=f"tg_btn_{ticker}", use_container_width=True):
                        cfg_tg = storage.get_alert_settings()
                        if cfg_tg.get("bot_token") and cfg_tg.get("chat_id"):
                            alert_body = format_trade_alert(item)
                            ok_s, s_info = send_telegram_notification(cfg_tg["bot_token"], cfg_tg["chat_id"], alert_body)
                            if ok_s:
                                st.success(f"Dispatched {ticker} alert to Telegram!")
                            else:
                                st.error(s_info)
                        else:
                            st.warning("Configure Telegram Bot in the 'Telegram Alert Station' tab first.")
                            
                st.html("<div style='height: 10px;'></div>")
    else:
        st.info("👋 Select your universe on the sidebar and click **Run Screening Cockpit**, or search any stock above!")

# --- TAB 2: DEEP DIVE & CHARTS ---
with tab2:
    available_tickers = []
    if df is not None and not df.empty:
        available_tickers.extend(df['Ticker'].tolist())
    available_tickers.extend(list(st.session_state["single_stock_dict"].keys()))
    available_tickers = list(dict.fromkeys(available_tickers))
    
    if available_tickers:
        default_idx = 0
        if st.session_state["active_deep_dive_ticker"] in available_tickers:
            default_idx = available_tickers.index(st.session_state["active_deep_dive_ticker"])
            
        selected_ticker = st.selectbox("Select Stock for Interactive Visual Charts", available_tickers, index=default_idx)
        
        if df is not None and not df.empty and selected_ticker in df['Ticker'].values:
            row = df[df['Ticker'] == selected_ticker].iloc[0]
        else:
            row = pd.Series(st.session_state["single_stock_dict"][selected_ticker])
            
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("CMP", f"₹{row['CMP']:.2f}")
        with c2:
            st.metric("Verdict", row.get('Signal', 'Buy'), delta=f"{row['Conviction_Score']}/100 Conviction")
        with c3:
            st.metric("Stop Loss", f"₹{row['Stop_Loss']:.2f}", delta=f"-{row.get('SL_Pct', 2.0)}%", delta_color="inverse")
        with c4:
            st.metric("Base Target", f"₹{row['Target_Base']:.2f}", delta=f"+{row.get('Target_Base_Pct', 5.0)}%")
            
        if row.get("Is_Penny"):
            st.error(f"🚨 **PENNY STOCK RISK NOTICE ({row.get('Circuit_Warning_Badge', 'CIRCUIT SENSITIVE')}):**\n\n{row.get('Penny_Trap_Warning')}")
            st.info(f"✨ **Turnaround Assessment:** {row.get('Turnaround_Verdict', 'Speculative')} (Score: {row.get('Turnaround_Score', 0)}/100) | **Liquidity:** {row.get('Liquidity_Rating', 'Standard')}")
            
        # Candlestick Chart
        raw_df = row.get("_raw_df")
        if raw_df is not None and not raw_df.empty:
            st.subheader(f"📈 Candlestick Chart with 20/50/200 EMAs: {selected_ticker}")
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=raw_df.index, open=raw_df['Open'], high=raw_df['High'],
                low=raw_df['Low'], close=raw_df['Close'], name="OHLC"
            ))
            raw_close = raw_df['Close']
            fig.add_trace(go.Scatter(x=raw_df.index, y=raw_close.ewm(span=20).mean(), line=dict(color='#38BDF8', width=1.5), name="EMA 20"))
            fig.add_trace(go.Scatter(x=raw_df.index, y=raw_close.ewm(span=50).mean(), line=dict(color='#F59E0B', width=1.5), name="EMA 50"))
            if len(raw_close) >= 200:
                fig.add_trace(go.Scatter(x=raw_df.index, y=raw_close.ewm(span=200).mean(), line=dict(color='#EC4899', width=2), name="EMA 200"))
                
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=450, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)
            
        # Monte Carlo Simulation Chart
        raw_mc = row.get("_raw_mc")
        if raw_mc:
            st.subheader("🎲 5,000-Path Monte Carlo Price Distribution (7-Day Projection)")
            mc_fig = go.Figure()
            for path in raw_mc.get("Sample_Paths", []):
                mc_fig.add_trace(go.Scatter(y=path, mode="lines", line=dict(color="rgba(100, 116, 139, 0.15)", width=1), showlegend=False))
                
            reps = raw_mc.get("Representative_Paths", {})
            if "Bull_Path" in reps:
                mc_fig.add_trace(go.Scatter(y=reps["Bull_Path"], mode="lines", line=dict(color="#10B981", width=3), name=f"Optimistic Bull (₹{raw_mc['Target_Bull']})"))
            if "Base_Path" in reps:
                mc_fig.add_trace(go.Scatter(y=reps["Base_Path"], mode="lines", line=dict(color="#3B82F6", width=3), name=f"Base Case (₹{raw_mc['Target_Base']})"))
            if "Bear_Path" in reps:
                mc_fig.add_trace(go.Scatter(y=reps["Bear_Path"], mode="lines", line=dict(color="#EF4444", width=3), name=f"Pessimistic Floor (₹{raw_mc['Target_Bear']})"))
                
            mc_fig.update_layout(template="plotly_dark", height=350, xaxis_title="Trading Days", yaxis_title="Price (₹)", margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(mc_fig, use_container_width=True)
    else:
        st.info("Run a screener scan or search any stock in the sidebar to inspect interactive charts.")

# --- TAB 3: INSTITUTIONAL DATA TABLE ---
with tab3:
    if df is not None and not df.empty:
        st.subheader("Sortable Institutional Grid")
        table_cols = [
            "Ticker", "Sector", "CMP", "Signal", "Conviction_Score",
            "Supertrend", "RSI_14", "Option_PCR", "Stop_Loss",
            "Target_Base", "Target_Bull", "Risk_Reward", "Position_Size", "News_Type"
        ]
        st.dataframe(
            df[table_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "CMP": st.column_config.NumberColumn("CMP (₹)", format="₹%.2f"),
                "Stop_Loss": st.column_config.NumberColumn("Stop Loss (₹)", format="₹%.2f"),
                "Target_Base": st.column_config.NumberColumn("Base Target (₹)", format="₹%.2f"),
                "Target_Bull": st.column_config.NumberColumn("Bull Target (₹)", format="₹%.2f"),
                "Risk_Reward": st.column_config.NumberColumn("R:R", format="%.2fx"),
                "Conviction_Score": st.column_config.ProgressColumn("Conviction", min_value=0, max_value=100),
                "Position_Size": st.column_config.NumberColumn("Shares Sizing")
            }
        )
        
        c_ex1, c_ex2 = st.columns(2)
        with c_ex1:
            csv_data = df[table_cols].to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export Table to CSV", csv_data, f"NSE_Cockpit_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
        with c_ex2:
            pdf_path = os.path.join(os.path.dirname(__file__), "reports", "Market_Dossier.pdf")
            if st.button("📄 Generate Institutional PDF Dossier"):
                generate_pdf_dossier(df, output_path=pdf_path)
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button("📥 Download PDF Dossier", pdf_bytes, "Institutional_Market_Dossier.pdf", "application/pdf")
    else:
        st.info("Run a screener scan to populate the institutional table.")

# --- TAB 4: PREDICTION DEBUGGER & SELF-CALIBRATION ---
with tab4:
    st.subheader("🎯 Walk-Forward Prediction Debugger & Model Calibration")
    st.markdown("Track expectations vs reality: Evaluates past Stop-Losses, Targets, and R:R against actual market execution.")
    
    col_v1, col_v2 = st.columns([3, 1])
    with col_v1:
        st.caption("Logs every predicted setup into SQLite and verifies actual price evolution to diagnose model errors.")
    with col_v2:
        verify_btn = st.button("🔄 Verify Predictions Against Market", type="primary", use_container_width=True)
        
    if verify_btn:
        with st.spinner("Fetching latest market prices & auditing walk-forward outcomes..."):
            debug_df, debug_metrics = audit_and_debug_predictions()
            st.session_state["debug_df"] = debug_df
            st.session_state["debug_metrics"] = debug_metrics
            st.success("Prediction verification complete!")
            
    if "debug_df" not in st.session_state:
        d_df, d_metrics = audit_and_debug_predictions()
        st.session_state["debug_df"] = d_df
        st.session_state["debug_metrics"] = d_metrics
        
    debug_df = st.session_state.get("debug_df", pd.DataFrame())
    debug_metrics = st.session_state.get("debug_metrics", {})
    
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Total Tracked", debug_metrics.get("Total_Predictions", 0))
    with m2:
        st.metric("Target Hits 🎯", debug_metrics.get("Target_Hits", 0))
    with m3:
        st.metric("Stop Loss Hits 🛑", debug_metrics.get("Stop_Loss_Hits", 0))
    with m4:
        st.metric("In Play 🔄", debug_metrics.get("In_Play", 0))
    with m5:
        st.metric("Win Rate", f"{debug_metrics.get('Win_Rate_Pct', 0.0)}%")
        
    st.info(f"💡 **Algorithmic Calibration Advisory:**\n\n{debug_metrics.get('Calibration_Advice', 'Awaiting data.')}")
    
    if not debug_df.empty:
        status_filter = st.multiselect(
            "Filter by Outcome Status",
            ["TARGET_HIT", "STOP_LOSS_HIT", "IN_PROGRESS"],
            default=["TARGET_HIT", "STOP_LOSS_HIT", "IN_PROGRESS"]
        )
        filtered_debug = debug_df[debug_df['outcome_status'].isin(status_filter)]
        dbg_cols = [
            "prediction_date", "ticker", "signal", "cmp_at_prediction",
            "stop_loss", "target_base", "latest_price", "highest_price_since",
            "lowest_price_since", "actual_return_pct", "outcome_status", "debug_notes"
        ]
        st.dataframe(
            filtered_debug[dbg_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "prediction_date": "Date Predicted",
                "ticker": "Stock",
                "signal": "Signal",
                "cmp_at_prediction": st.column_config.NumberColumn("Entry (₹)", format="₹%.2f"),
                "stop_loss": st.column_config.NumberColumn("Expected SL (₹)", format="₹%.2f"),
                "target_base": st.column_config.NumberColumn("Expected Target (₹)", format="₹%.2f"),
                "latest_price": st.column_config.NumberColumn("Current CMP (₹)", format="₹%.2f"),
                "highest_price_since": st.column_config.NumberColumn("High Since (₹)", format="₹%.2f"),
                "lowest_price_since": st.column_config.NumberColumn("Low Since (₹)", format="₹%.2f"),
                "actual_return_pct": st.column_config.NumberColumn("Actual P&L (%)", format="%.2f%%"),
                "outcome_status": "Outcome",
                "debug_notes": "Diagnosis & Model Error Notes"
            }
        )
    else:
        st.info("No predictions logged yet. Run a screening scan or search any ticker to begin tracking daily performance.")

# --- TAB 5: WATCHLIST & PAPER TRADES ---
with tab5:
    st.subheader("⭐ Active Watchlist")
    wl = storage.get_watchlist()
    if wl:
        wl_df = pd.DataFrame(wl)
        st.dataframe(wl_df, use_container_width=True, hide_index=True)
        del_ticker = st.selectbox("Remove from Watchlist", [item['ticker'] for item in wl])
        if st.button("Remove Selected"):
            storage.remove_from_watchlist(del_ticker)
            st.rerun()
    else:
        st.info("No stocks currently in watchlist.")
        
    st.markdown("---")
    st.subheader("💼 Active Paper Trades")
    pt = storage.get_paper_trades()
    if pt:
        pt_df = pd.DataFrame(pt)
        st.dataframe(pt_df, use_container_width=True, hide_index=True)
    else:
        st.info("No open paper trades yet.")

# --- TAB 6: IPO RADAR & REVIEWS ---
with tab6:
    st.subheader("🚀 Live Indian IPO Radar & Intelligence Center")
    st.markdown("Track active and upcoming Mainboard & SME IPOs • Real-time Grey Market Premium (GMP) • Broker Consensus & Gemini 2.5 Flash Review")
    
    # Load IPO data if not loaded or force refresh
    if not st.session_state.get("ipo_list"):
        with st.spinner("Fetching real-time Indian IPOs and Grey Market Premium (GMP)..."):
            st.session_state["ipo_list"] = fetch_active_and_upcoming_ipos()
            
    raw_ipos = st.session_state.get("ipo_list", [])
    
    # Filter Bar
    f_c1, f_c2, f_c3, f_c4 = st.columns([2, 2, 3, 2])
    with f_c1:
        status_filter = st.selectbox("Filter by Status", ["All", "Open / Active Now", "Upcoming", "Recently Closed"], index=0)
    with f_c2:
        cat_filter = st.selectbox("Category", ["All", "Mainboard", "SME"], index=0)
    with f_c3:
        ipo_search = st.text_input("Search IPO by Name", placeholder="e.g. Hero Motors, SS Retail, NSE").strip().lower()
    with f_c4:
        st.write("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 Refresh IPOs & GMP", use_container_width=True):
            with st.spinner("Refreshing live IPO data and latest GMP..."):
                st.session_state["ipo_list"] = fetch_active_and_upcoming_ipos(force_refresh=True)
                st.session_state["ipo_verdicts"] = {}
                st.rerun()

    # Filtered list
    display_ipos = raw_ipos
    if status_filter == "Open / Active Now":
        display_ipos = [x for x in display_ipos if x["Status"] == "Open"]
    elif status_filter == "Upcoming":
        display_ipos = [x for x in display_ipos if x["Status"] == "Upcoming"]
    elif status_filter == "Recently Closed":
        display_ipos = [x for x in display_ipos if x["Status"] == "Closed"]
        
    if cat_filter != "All":
        display_ipos = [x for x in display_ipos if x["Category"] == cat_filter]
        
    if ipo_search:
        display_ipos = [x for x in display_ipos if ipo_search in x["Company_Name"].lower() or ipo_search in x["Full_Title"].lower()]
        
    # Top KPI Metrics Strip
    if raw_ipos:
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        open_count = sum(1 for x in raw_ipos if x["Status"] == "Open")
        upcoming_count = sum(1 for x in raw_ipos if x["Status"] == "Upcoming")
        
        # Max gain
        gains = [x["Est_Gain_Pct"] for x in raw_ipos if x["Est_Gain_Pct"] > 0]
        top_gain = max(gains) if gains else 0.0
        top_name = next((x["Company_Name"] for x in raw_ipos if x["Est_Gain_Pct"] == top_gain), "-")
        avg_gain = round(sum(gains) / len(gains), 1) if gains else 0.0
        
        with kpi1:
            st.metric("Active & Upcoming", f"{len(raw_ipos)} Total", delta=f"{open_count} Open Now")
        with kpi2:
            st.metric("Top Listing Gain", f"+{top_gain:.1f}%", delta=top_name)
        with kpi3:
            st.metric("Average Market GMP", f"+{avg_gain:.1f}%")
        with kpi4:
            sme_count = sum(1 for x in raw_ipos if x["Category"] == "SME")
            main_count = len(raw_ipos) - sme_count
            st.metric("Segment Split", f"{main_count} Main / {sme_count} SME")
            
    st.markdown("---")
    
    if not display_ipos:
        st.info("No IPOs match your selected filters.")
    else:
        st.caption(f"Showing {len(display_ipos)} IPO opportunities:")
        
        for ipo in display_ipos:
            comp_name = ipo["Company_Name"]
            cat = ipo["Category"]
            status = ipo["Status"]
            price_str = ipo["Price_Band"]
            gmp_val = ipo["GMP_Val"]
            gain_pct = ipo["Est_Gain_Pct"]
            dates = ipo["Dates"]
            lot_size = ipo["Lot_Size"]
            min_inv = ipo["Min_Investment"]
            
            # Status Badge Class & text
            if status == "Open":
                status_html = '<span style="background: #065F46; color: #6EE7B7; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem;">🟢 OPEN FOR SUBSCRIPTION</span>'
            elif status == "Upcoming":
                status_html = '<span style="background: #854D0E; color: #FEF08A; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem;">⏳ UPCOMING</span>'
            else:
                status_html = '<span style="background: #374151; color: #9CA3AF; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem;">🔒 CLOSED</span>'
                
            cat_html = f'<span style="background: #1E3A8A; color: #93C5FD; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem;">{cat}</span>'
            
            # GMP Badge styling
            if gain_pct >= 20:
                gmp_color = "#10B981"
                gmp_bg = "rgba(16, 185, 129, 0.15)"
                gmp_border = "#10B981"
            elif gain_pct > 0:
                gmp_color = "#F59E0B"
                gmp_bg = "rgba(245, 158, 11, 0.15)"
                gmp_border = "#F59E0B"
            else:
                gmp_color = "#94A3B8"
                gmp_bg = "rgba(100, 116, 139, 0.15)"
                gmp_border = "#475569"
                
            est_listing_price = (ipo["Price_Val"] + gmp_val) if ipo["Price_Val"] > 0 else 0.0
            est_listing_str = f"₹{est_listing_price:,.1f}" if est_listing_price > 0 else "TBA"
            price_display = f"₹{price_str}" if price_str != 'TBA' and not price_str.startswith('₹') else price_str
            
            # Render Clean Card using st.html
            card_html = f"""<div class="trade-card">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
<div>
<span style="font-size: 1.4rem; font-weight: 800; color: #F8FAFC;">{comp_name}</span>
<span style="margin-left: 8px;">{cat_html}</span>
</div>
<div>
{status_html}
</div>
</div>
<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 14px; flex-wrap: wrap;">
<span style="background: {gmp_bg}; color: {gmp_color}; border: 1px solid {gmp_border}; padding: 6px 12px; border-radius: 6px; font-weight: 700; font-size: 0.9rem;">
🔥 GMP: ₹{gmp_val:.1f} ({gain_pct:+.1f}% Est. Pop)
</span>
<span style="color: #94A3B8; font-size: 0.85rem;">
📅 Bidding Dates: <b style="color: #F8FAFC;">{dates}</b>
</span>
</div>
<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px;">
<div class="metric-bubble">
<span style="color: #94A3B8; font-size: 0.75rem;">PRICE BAND</span><br/>
<span style="color: #F8FAFC; font-weight: 700; font-size: 0.95rem;">{price_display}</span>
</div>
<div class="metric-bubble">
<span style="color: #38BDF8; font-size: 0.75rem;">LOT SIZE</span><br/>
<span style="color: #38BDF8; font-weight: 700; font-size: 0.95rem;">{lot_size} Shares</span>
</div>
<div class="metric-bubble">
<span style="color: #FCD34D; font-size: 0.75rem;">MIN INVESTMENT</span><br/>
<span style="color: #F59E0B; font-weight: 700; font-size: 0.95rem;">₹{min_inv:,.0f}</span>
</div>
<div class="metric-bubble">
<span style="color: #34D399; font-size: 0.75rem;">EST. LISTING</span><br/>
<span style="color: #10B981; font-weight: 700; font-size: 0.95rem;">{est_listing_str}</span>
</div>
</div>
</div>"""
            st.html(card_html)
            
            # Interactive Expandable Dossier
            with st.expander(f"🔍 Complete AI Verdict & Expert Reviews for {comp_name}", expanded=False):
                # Check cached verdict or generate on demand
                if comp_name not in st.session_state["ipo_verdicts"]:
                    with st.spinner(f"Analyzing news reviews and synthesizing Gemini verdict for {comp_name}..."):
                        news = fetch_ipo_news_and_reviews(comp_name, max_items=4)
                        verdict_data = generate_ipo_verdict(ipo, news, enable_ai=enable_ai)
                        st.session_state["ipo_verdicts"][comp_name] = verdict_data
                else:
                    verdict_data = st.session_state["ipo_verdicts"][comp_name]
                    
                v_tabs = st.tabs(["🎯 Investment Verdict", "📐 4 Due Diligence Pillars", "📰 Live News Headlines", "📝 Track My Application"])
                
                with v_tabs[0]:
                    v_col1, v_col2 = st.columns([3, 1])
                    with v_col1:
                        st.markdown(f"### {verdict_data['Verdict']}")
                        st.info(f"**Actionable Advice:**\n\n{verdict_data['Verdict_Summary']}")
                    with v_col2:
                        st.metric("Conviction Score", f"{verdict_data['Conviction_Score']}/100")
                        st.caption(f"**Consensus:** {verdict_data.get('Broker_Consensus', 'N/A')}")
                        
                    st.warning(f"**⚠️ Downside Risks / Red Flags:**\n\n{verdict_data.get('Key_Risks', 'Market volatility before listing day.')}")
                    
                with v_tabs[1]:
                    st.markdown("#### The 4 Angles of Due Diligence")
                    dp1, dp2 = st.columns(2)
                    with dp1:
                        st.html(f"""<div class="pillar-box">
<b>🔥 Pillar 1: Grey Market & Demand Pulse</b><br/>
{verdict_data.get('Pillar_GMP', 'GMP reflects current secondary grey market sentiment.')}
</div>
<div class="pillar-box">
<b>⚖️ Pillar 2: Valuation vs Listed Peers</b><br/>
{verdict_data.get('Pillar_Valuation', 'Compare issue P/E with industry averages.')}
</div>""")
                    with dp2:
                        st.html(f"""<div class="pillar-box">
<b>🏢 Pillar 3: Issue Structure & Category Risk</b><br/>
{verdict_data.get('Pillar_Structure', 'Check fresh issue vs OFS cash-out proportion.')}
</div>
<div class="pillar-box">
<b>📊 Pillar 4: Sentiment & Media Reviews</b><br/>
{verdict_data.get('Pillar_Sentiment', 'Derived from analyst recommendations.')}
</div>""")
                        
                with v_tabs[2]:
                    st.markdown(f"#### Live News Headlines for {comp_name} IPO")
                    h_list = verdict_data.get("News_Headlines", [])
                    if h_list:
                        for h in h_list:
                            link_h = f"<a href='{h.get('link', '#')}' target='_blank' style='color: #38BDF8; font-weight: 600;'>{h.get('title')}</a>"
                            st.markdown(f"• {link_h} — *{h.get('publisher')}* ({h.get('pubDate', '')})", unsafe_allow_html=True)
                    else:
                        st.write("No major breaking articles found yet for this issue.")
                        
                with v_tabs[3]:
                    st.markdown(f"#### Record Application for {comp_name}")
                    with st.form(f"ipo_form_{comp_name}"):
                        a_cat = st.selectbox("Application Type", ["Retail (Up to ₹2L)", "sHNI (₹2L - ₹10L)", "bHNI (Above ₹10L)"], key=f"cat_{comp_name}")
                        a_lots = st.number_input("Lots Applied", min_value=1, max_value=50, value=1, key=f"lots_{comp_name}")
                        a_price = st.number_input("Bid Price (₹)", value=float(ipo['Price_Val']) if ipo['Price_Val'] > 0 else 100.0, key=f"price_{comp_name}")
                        total_cost = a_lots * lot_size * a_price
                        st.caption(f"Estimated Total Outlay: **₹{total_cost:,.2f}** ({a_lots * lot_size} shares)")
                        a_notes = st.text_input("Broker / UPI Notes", placeholder="e.g. Applied via Zerodha UPI on Day 1", key=f"notes_{comp_name}")
                        
                        if st.form_submit_button("💾 Record Application"):
                            storage.record_ipo_application(
                                company_name=comp_name,
                                category=cat,
                                price_applied=a_price,
                                lot_size=a_lots * lot_size,
                                total_amount=total_cost,
                                dates=dates,
                                verdict=verdict_data['Verdict'],
                                notes=a_notes
                            )
                            st.success(f"Recorded your application for {comp_name}! Track it below.")
                            st.rerun()

            st.html("<div style='height: 8px;'></div>")

    # Section for user's tracked IPO applications
    st.markdown("---")
    st.subheader("📋 My Recorded IPO Applications & Allotment Tracker")
    my_apps = storage.get_all_ipo_applications()
    if my_apps:
        app_df = pd.DataFrame(my_apps)
        st.dataframe(
            app_df[["id", "application_date", "company_name", "category", "price_applied", "lot_size", "total_amount", "verdict", "allotment_status", "notes"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": "ID",
                "application_date": "Date",
                "company_name": "Company",
                "category": "Segment",
                "price_applied": st.column_config.NumberColumn("Bid (₹)", format="₹%.2f"),
                "lot_size": "Shares",
                "total_amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%,.0f"),
                "verdict": "Recommendation",
                "allotment_status": "Status",
                "notes": "Notes"
            }
        )
        
        # Status updater
        u_col1, u_col2, u_col3 = st.columns([2, 2, 1])
        with u_col1:
            app_to_edit = st.selectbox("Select Application to Update", [f"{a['id']}: {a['company_name']}" for a in my_apps])
        with u_col2:
            new_status = st.selectbox("Update Allotment Status", ["APPLIED", "ALLOTTED", "NOT ALLOTTED", "SOLD ON LISTING DAY", "HOLDING"])
        with u_col3:
            st.write("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("Update Status", use_container_width=True):
                target_id = int(app_to_edit.split(":")[0])
                storage.update_ipo_status(target_id, new_status)
                st.success(f"Application #{target_id} updated to {new_status}!")
                st.rerun()
    else:
        st.info("You have not recorded any IPO bids yet. Use the 'Track My Application' tab inside any IPO card above to track your bids.")

# --- TAB 7: INSTITUTIONAL FLOWS & SECTOR HEATMAP ---
with tab7:
    st.subheader("🏛️ Daily FII / DII Net Cash Flows & Sector Rotation Heatmap")
    st.markdown("Monitor high-frequency institutional money flows directly from the National Stock Exchange (NSE) to detect macro liquidity and leading market themes.")
    
    col_ref1, col_ref2 = st.columns([4, 1])
    with col_ref2:
        refresh_flows = st.button("🔄 Refresh Flows", use_container_width=True)
        
    fii_dii_data = fetch_fii_dii_cash_flows(force_refresh=refresh_flows)
    
    if fii_dii_data:
        st.markdown("#### 🏦 Daily Cash Market Gross & Net Flows")
        
        # Calculate summary totals
        fii_net = sum(d["Net_Inflow_INR_Cr"] for d in fii_dii_data if "FII" in d["Category"])
        dii_net = sum(d["Net_Inflow_INR_Cr"] for d in fii_dii_data if "DII" in d["Category"])
        total_inst_net = fii_net + dii_net
        
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1:
            st.metric(
                "FII / FPI Net Cash Flow",
                f"{'+' if fii_net >= 0 else ''}₹{fii_net:,.1f} Cr",
                delta="Foreign Inflow" if fii_net >= 0 else "Foreign Outflow",
                delta_color="normal" if fii_net >= 0 else "inverse"
            )
        with c_f2:
            st.metric(
                "DII Net Cash Flow",
                f"{'+' if dii_net >= 0 else ''}₹{dii_net:,.1f} Cr",
                delta="Domestic Inflow" if dii_net >= 0 else "Domestic Outflow",
                delta_color="normal" if dii_net >= 0 else "inverse"
            )
        with c_f3:
            st.metric(
                "Combined Institutional Net",
                f"{'+' if total_inst_net >= 0 else ''}₹{total_inst_net:,.1f} Cr",
                delta="Bullish Market Liquidity" if total_inst_net >= 0 else "Bearish Pressure",
                delta_color="normal" if total_inst_net >= 0 else "inverse"
            )
            
        flow_df = pd.DataFrame(fii_dii_data)
        st.dataframe(
            flow_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Category": "Institutional Segment",
                "Gross_Buy_INR_Cr": st.column_config.NumberColumn("Gross Buy (₹ Cr)", format="₹%,.1f"),
                "Gross_Sell_INR_Cr": st.column_config.NumberColumn("Gross Sell (₹ Cr)", format="₹%,.1f"),
                "Net_Inflow_INR_Cr": st.column_config.NumberColumn("Net Cash Flow (₹ Cr)", format="₹%,.1f"),
                "Trade_Date": "Reporting Date"
            }
        )
    else:
        st.info("Live FII/DII data is currently fetching from official NSE feeds. Click Refresh to query exchange endpoints.")
        
    st.markdown("---")
    st.markdown("#### 🗺️ 11-Sector Relative Momentum Heatmap & Rotation Matrix")
    st.caption("Tracks short-term (1D), medium-term (1M), and annual (1Y) performance of official NSE Sectoral Indices.")
    
    sector_df = fetch_sector_rotation_matrix()
    if sector_df is not None and not sector_df.empty:
        bar_colors = ['#10B981' if r >= 0 else '#EF4444' for r in sector_df['Return_1D_Pct']]
        
        fig_sec = go.Figure(go.Bar(
            x=sector_df['Return_1D_Pct'],
            y=sector_df['Sector'],
            orientation='h',
            marker=dict(color=bar_colors),
            text=[f"{r:+.2f}%" for r in sector_df['Return_1D_Pct']],
            textposition='auto'
        ))
        fig_sec.update_layout(
            template="plotly_dark",
            title="Sector 1-Day Inflow vs Outflow Ranking",
            xaxis_title="1-Day Return (%)",
            yaxis_title="",
            yaxis=dict(autorange="reversed"),
            height=380,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_sec, use_container_width=True)
        
        st.dataframe(
            sector_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Sector": "NSE Sector Index",
                "Theme": "Economic Theme",
                "Current_Index": st.column_config.NumberColumn("Index Value", format="%,.1f"),
                "Return_1D_Pct": st.column_config.NumberColumn("1-Day (%)", format="%+.2f%%"),
                "Return_1M_Pct": st.column_config.NumberColumn("1-Month (%)", format="%+.2f%%"),
                "Return_1Y_Pct": st.column_config.NumberColumn("1-Year (%)", format="%+.2f%%"),
                "Rotation_Status": "Institutional Momentum Status"
            }
        )
    else:
        st.info("Sector indices data is updating.")

# --- TAB 8: EARNINGS & PEAD RADAR ---
with tab8:
    st.subheader("📅 Quarterly Earnings Calendar & Post-Earnings Announcement Drift (PEAD)")
    st.markdown("Harness quarterly reporting catalysts: Identify upcoming earnings announcements, analyze YoY profit/revenue growth, and spot Post-Earnings Announcement Drift (PEAD) setups breaking out on institutional volume.")
    
    pead_tab, cal_tab, fin_tab = st.tabs([
        "🔥 PEAD Breakout Radar",
        "🗓️ Upcoming Results Calendar",
        "🔬 Single-Stock Quarterly Financials"
    ])
    
    with pead_tab:
        st.markdown("#### 🔥 Post-Earnings Announcement Drift (PEAD) Breakout Setups")
        st.caption("Identifies stocks experiencing strong institutional accumulation (Volume surge > 1.25x) after earnings or positive news catalysts.")
        
        pead_candidates = detect_pead_candidates(df)
        if pead_candidates is not None and not pead_candidates.empty:
            st.dataframe(
                pead_candidates,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Ticker": "Symbol",
                    "CMP": st.column_config.NumberColumn("CMP (₹)", format="₹%.2f"),
                    "Volume_Surge": "Volume Expansion",
                    "RSI": "RSI 14",
                    "Conviction": st.column_config.ProgressColumn("Conviction", min_value=0, max_value=100),
                    "Entry_Zone": "Target Entry",
                    "Target": st.column_config.NumberColumn("Target (₹)", format="₹%.2f"),
                    "Catalyst": "Catalyst / Rationale"
                }
            )
        else:
            st.info("No stocks currently meet the strict PEAD breakout criteria (>1.25x volume surge + bullish alignment). Run a screener scan or monitor results below.")
            
        st.html("""<div class="guide-box">
<h4>💡 What is Post-Earnings Announcement Drift (PEAD)?</h4>
PEAD is one of the most rigorously documented anomalies in financial economics. When an Indian company beats quarterly earnings expectations, institutions cannot buy their entire target allocation in a single session without spiking the price. Instead, large mutual funds and FIIs steadily accumulate shares over 10 to 60 trading days, creating a sustained upward price drift.
</div>""")

    with cal_tab:
        st.markdown("#### 🗓️ Scheduled Earnings Releases & Analyst Estimates")
        col_c1, col_c2 = st.columns([3, 1])
        with col_c2:
            fetch_cal_btn = st.button("🔄 Scan Upcoming Dates", use_container_width=True)
            
        universe_tickers = df['Ticker'].tolist() if df is not None and not df.empty else config.DEFAULT_SCREENER_TICKERS
        earnings_cal = fetch_earnings_calendar(universe_tickers, force_refresh=fetch_cal_btn)
        
        if earnings_cal:
            cal_df = pd.DataFrame(earnings_cal)
            st.dataframe(
                cal_df[["Ticker", "Earnings_Date", "Days_Away", "Status", "Est_EPS", "Est_Revenue_INR_Cr", "Dividend_Date"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Ticker": "Stock Symbol",
                    "Earnings_Date": "Expected Results Date",
                    "Days_Away": st.column_config.NumberColumn("Days Away", format="%d d"),
                    "Status": "Time Horizon",
                    "Est_EPS": "Consensus EPS",
                    "Est_Revenue_INR_Cr": st.column_config.NumberColumn("Est. Revenue (₹ Cr)", format="₹%,.1f"),
                    "Dividend_Date": "Ex-Dividend Date"
                }
            )
        else:
            st.info("Click 'Scan Upcoming Dates' to check earnings schedule for watchlist stocks.")

    with fin_tab:
        st.markdown("#### 🔬 Single-Stock Quarterly Financial Statement Audit")
        f_col1, f_col2 = st.columns([2, 1])
        with f_col1:
            audit_ticker = st.text_input("Enter NSE Ticker for Financial Breakdown", value="TCS").strip().upper()
        with f_col2:
            st.write("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            run_fin_btn = st.button("📊 Fetch Financial Growth", use_container_width=True)
            
        if audit_ticker:
            fin_data = analyze_quarterly_financials(audit_ticker)
            if fin_data.get("Has_Data"):
                st.subheader(f"Financial Momentum: {fin_data['Ticker']} (Quarter Ending {fin_data['Latest_Quarter']})")
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("YoY Revenue Growth", f"{fin_data['Revenue_YoY_Pct']:+.1f}%", delta="Top-line" if fin_data['Revenue_YoY_Pct'] > 0 else "Decline")
                with m2:
                    st.metric("YoY PAT (Net Profit) Growth", f"{fin_data['PAT_YoY_Pct']:+.1f}%", delta="Bottom-line" if fin_data['PAT_YoY_Pct'] > 0 else "Decline")
                with m3:
                    st.metric("Net Profit Margin", f"{fin_data['Net_Profit_Margin_Pct']:.1f}%")
                with m4:
                    st.metric("Financial Verdict", fin_data['Earnings_Verdict'])
            else:
                st.warning(f"Could not retrieve quarterly financial statements for {audit_ticker}. Ensure the symbol is listed on NSE.")

# --- TAB 9: BULK DEALS TRACKER ---
with tab9:
    st.subheader("📦 Real-Time Official NSE Bulk & Block Deals Tracker")
    st.markdown("Institutional fund managers and high-net-worth investors (HNIs) are mandated to disclose all single-day transactions exceeding 0.5% of total equity to the National Stock Exchange (NSE). Track real-time institutional footprints here.")
    
    col_d1, col_d2 = st.columns([4, 1])
    with col_d2:
        refresh_deals = st.button("🔄 Refresh Deals", use_container_width=True)
        
    bulk_deals = fetch_nse_bulk_deals(force_refresh=refresh_deals)
    
    if bulk_deals:
        b_df = pd.DataFrame(bulk_deals)
        
        # Summary metrics
        total_deals_count = len(b_df)
        total_turnover = b_df['Turnover_INR_Cr'].sum()
        buy_deals = b_df[b_df['Action'] == 'BUY']
        buy_turnover = buy_deals['Turnover_INR_Cr'].sum()
        sell_turnover = total_turnover - buy_turnover
        
        dm1, dm2, dm3, dm4 = st.columns(4)
        with dm1:
            st.metric("Total Bulk Deals", f"{total_deals_count} Transactions")
        with dm2:
            st.metric("Total Turnover", f"₹{total_turnover:,.1f} Cr")
        with dm3:
            st.metric("Institutional Gross Buys", f"₹{buy_turnover:,.1f} Cr", delta=f"{round(buy_turnover/total_turnover*100 if total_turnover>0 else 0)}% of total")
        with dm4:
            st.metric("Institutional Gross Sells", f"₹{sell_turnover:,.1f} Cr", delta=f"-{round(sell_turnover/total_turnover*100 if total_turnover>0 else 0)}%", delta_color="inverse")
            
        # Top 10 Securities by Turnover Chart
        top_by_sec = b_df.groupby("Security")["Turnover_INR_Cr"].sum().reset_index().sort_values(by="Turnover_INR_Cr", ascending=False).head(10)
        
        fig_deals = go.Figure(go.Bar(
            x=top_by_sec['Turnover_INR_Cr'],
            y=top_by_sec['Security'],
            orientation='h',
            marker=dict(color='#38BDF8'),
            text=[f"₹{t:,.1f} Cr" for t in top_by_sec['Turnover_INR_Cr']],
            textposition='auto'
        ))
        fig_deals.update_layout(
            template="plotly_dark",
            title="Top 10 Stocks with Highest Institutional Deal Value (₹ Cr)",
            xaxis_title="Transaction Turnover (₹ Cr)",
            yaxis=dict(autorange="reversed"),
            height=340,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_deals, use_container_width=True)
        
        # Filter controls
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            action_filter = st.multiselect("Filter by Action", ["BUY", "SELL"], default=["BUY", "SELL"])
        with f_col2:
            search_deal_text = st.text_input("Filter by Stock or Client Name", placeholder="e.g. Goldman, HDFC, Motilal, Tata...")
            
        filtered_b_df = b_df[b_df['Action'].isin(action_filter)]
        if search_deal_text:
            s_q = search_deal_text.strip().upper()
            filtered_b_df = filtered_b_df[filtered_b_df['Security'].str.upper().str.contains(s_q) | filtered_b_df['Client_Name'].str.upper().str.contains(s_q)]
            
        st.dataframe(
            filtered_b_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": "Trade Date",
                "Security": "Security Name",
                "Client_Name": "Institutional Client / Fund",
                "Action": "Transaction",
                "Quantity": st.column_config.NumberColumn("Quantity", format="%,d"),
                "Trade_Price": st.column_config.NumberColumn("Execution Price (₹)", format="₹%.2f"),
                "Turnover_INR_Cr": st.column_config.NumberColumn("Turnover (₹ Cr)", format="₹%,.2f")
            }
        )
    else:
        st.info("Bulk deals data is currently loading from NSE. Click Refresh to query the exchange snapshot.")

# --- TAB 10: TELEGRAM ALERT BOT STATION ---
with tab10:
    st.subheader("🔔 Live Telegram Instant Mobile Alert Bot Station")
    st.markdown("Broadcast high-conviction trade setups and IPO radar updates directly to your personal phone or VIP Telegram trading channel in real-time.")
    
    st.html("""<div class="guide-box">
<h4>⚡ Quick 60-Second Setup Guide:</h4>
<ol>
    <li>Open Telegram and search for <b>@BotFather</b>. Send <code>/newbot</code>, follow the prompts, and copy the <b>Bot Token</b>.</li>
    <li>Start your new bot by pressing <b>Start</b>.</li>
    <li>Search for <b>@userinfobot</b> on Telegram, press Start, and copy your numeric <b>Id</b> (e.g. <code>123456789</code>). If broadcasting to a channel, add the bot as an Admin to your channel and use your channel username (e.g. <code>@MyTradeChannel</code>).</li>
    <li>Paste them below and click <b>Save Bot Credentials</b>.</li>
</ol>
</div>""")

    saved_cfg = storage.get_alert_settings()
    
    with st.form("telegram_config_form"):
        st.markdown("#### 🔑 Telegram Bot Credentials")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            cfg_bot_token = st.text_input("Telegram Bot Token", value=saved_cfg.get("bot_token", ""), type="password", placeholder="e.g. 7123456789:ABCdefGhIJKlmNoPQRstuVWXyz")
        with col_t2:
            cfg_chat_id = st.text_input("Chat ID or Channel Username", value=saved_cfg.get("chat_id", ""), placeholder="e.g. 123456789 or @MyTradeChannel")
            
        cfg_auto = st.checkbox("Automatically broadcast high-conviction (>75/100) setups during screener scans", value=bool(saved_cfg.get("auto_alerts", 0)))
        
        if st.form_submit_button("💾 Save Bot Credentials", type="primary"):
            storage.save_alert_settings(cfg_bot_token, cfg_chat_id, int(cfg_auto))
            st.success("Bot credentials safely persisted in SQLite database!")
            st.rerun()
            
    st.markdown("---")
    st.markdown("#### 📡 Test & Manual Alert Dispatcher")
    
    t_c1, t_c2 = st.columns(2)
    with t_c1:
        st.markdown("##### 🧪 Test Telegram Connectivity")
        if st.button("🚀 Send Test Ping to Telegram", use_container_width=True):
            if saved_cfg.get("bot_token") and saved_cfg.get("chat_id"):
                test_msg = "<b>🟢 PING SUCCESSFUL!</b>\n\nYour <b>Indian Market Decision Cockpit</b> alert dispatcher is now actively linked and ready to deliver real-time trade signals and IPO updates."
                ok, msg_res = send_telegram_notification(saved_cfg["bot_token"], saved_cfg["chat_id"], test_msg)
                if ok:
                    st.success(f"✅ {msg_res}")
                else:
                    st.error(f"❌ {msg_res}")
            else:
                st.warning("Please save your Bot Token and Chat ID above first.")
                
    with t_c2:
        st.markdown("##### 📢 Broadcast Active Stock Setup")
        available_stocks = []
        if df is not None and not df.empty:
            available_stocks = df['Ticker'].tolist()
        if available_stocks:
            target_stock = st.selectbox("Select Stock Setup to Broadcast", available_stocks)
            if st.button("📲 Broadcast Stock Setup Now", use_container_width=True):
                if saved_cfg.get("bot_token") and saved_cfg.get("chat_id"):
                    row_data = df[df['Ticker'] == target_stock].iloc[0].to_dict()
                    msg_txt = format_trade_alert(row_data)
                    ok, msg_res = send_telegram_notification(saved_cfg["bot_token"], saved_cfg["chat_id"], msg_txt)
                    if ok:
                        st.success(f"✅ Dispatched {target_stock} setup to Telegram!")
                    else:
                        st.error(f"❌ {msg_res}")
                else:
                    st.warning("Please save your Bot Token and Chat ID above first.")
        else:
            st.caption("Run a screener scan in the sidebar to populate available stock setups for broadcasting.")
