import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

import config
from core.technical import analyze_technical
from core.options import analyze_options
from core.monte_carlo import run_monte_carlo_simulation
from core.risk_manager import calculate_risk_profile
from core.fundamental import analyze_fundamentals
from core.ai_agent import generate_ai_thesis
from core.screener import fetch_batch_ohlcv, filter_tickers_by_strategy
from core.news_engine import analyze_news_catalyst
from core.rationale_engine import generate_trade_rationale
from core.penny_radar import analyze_penny_risk
from db.storage import record_scan_audit

def process_single_ticker(
    ticker: str,
    df: pd.DataFrame,
    enable_ai: bool = True,
    max_risk_inr: float = 5000.0
) -> Optional[Dict[str, Any]]:
    """
    Executes the full Council of Experts analysis pipeline for a single stock.
    """
    try:
        if len(df) < 25:
            return None
            
        # 1. Technical Analysis
        tech = analyze_technical(df)
        cmp = tech["CMP"]
        
        # 2. Options / Derivatives Analysis
        opts = analyze_options(ticker, cmp=cmp)
        pcr = opts["Option_PCR"]
        
        # 3. Monte Carlo 5000-Path Simulation + KMeans
        mc = run_monte_carlo_simulation(df, days=7, simulations=3000)
        target_base = mc["Target_Base"]
        target_bull = mc["Target_Bull"]
        
        # 4. Risk Profile & Sizing
        risk = calculate_risk_profile(
            cmp=cmp,
            atr=tech["ATR_14"],
            target_base=target_base,
            target_bull=target_bull,
            supertrend_level=tech["Supertrend_Level"],
            supertrend_trend=tech["Supertrend_Trend"],
            tech_score=tech["Technical_Score"],
            pcr=pcr,
            max_risk_inr=max_risk_inr
        )
        
        # 5. Fundamentals & News Catalyst
        fund = analyze_fundamentals(ticker)
        news = analyze_news_catalyst(ticker) if enable_ai else {
            "Headlines": [],
            "Catalyst_Summary": "News analysis paused in fast mode.",
            "Catalyst_Type": "Routine",
            "News_Sentiment": "Neutral",
            "Top_Headline": f"{ticker} market data"
        }
        
        # 6. Plain-English Trade Rationale & 4 Pillars of Evidence
        rationale = generate_trade_rationale(
            ticker=ticker,
            cmp=cmp,
            signal=risk["Signal"],
            conviction_score=risk["Conviction_Score"],
            tech_data=tech,
            options_data=opts,
            mc_data=mc,
            risk_data=risk,
            fund_data=fund,
            news_data=news
        )
        
        # 7. Forensic Penny Stock & Circuit Risk Analysis
        penny_info = analyze_penny_risk(
            ticker=ticker,
            cmp=cmp,
            df=df,
            fund_data=fund,
            tech_data=tech
        )
        
        # 8. AI Synthesis (Gemini 2.5 Flash)
        if enable_ai and risk["Conviction_Score"] >= 50:
            thesis, adv_risk = generate_ai_thesis(
                ticker=ticker,
                cmp=cmp,
                signal=risk["Signal"],
                technical_score=risk["Conviction_Score"],
                supertrend=tech["Supertrend_Status"],
                rsi=tech["RSI_14"],
                pcr=pcr,
                stop_loss=risk["Stop_Loss"],
                target_base=target_base,
                risk_reward=risk["Risk_Reward_Base"]
            )
        else:
            thesis = f"Momentum score {tech['Technical_Score']}/100 with R:R {risk['Risk_Reward_Base']}x targeting ₹{target_base:.1f}."
            adv_risk = f"Daily close below ₹{risk['Stop_Loss']:.1f} invalidates setup."
            
        sector = config.SECTOR_MAPPINGS.get(ticker, fund.get("Sector", "Indian Equities"))
        
        return {
            "Ticker": ticker,
            "Sector": sector,
            "CMP": round(cmp, 2),
            "Signal": risk["Signal"],
            "Conviction_Score": risk["Conviction_Score"],
            "Trade_Verdict": rationale["Trade_Verdict"],
            "Action_Summary": rationale["Action_Summary"],
            "Entry_Zone": rationale["Entry_Zone"],
            "Trade_Management_Rule": rationale["Trade_Management_Rule"],
            "Stop_Loss": risk["Stop_Loss"],
            "Stop_Loss_Rationale": rationale["Stop_Loss_Rationale"],
            "Target_Base": target_base,
            "Target_Bull": target_bull,
            "Target_Rationale": rationale["Target_Rationale"],
            "Risk_Reward": risk["Risk_Reward_Base"],
            "Position_Size": risk["Position_Quantity"],
            "Risk_Per_Share": rationale["Risk_Per_Share_INR"],
            "Total_Capital_Req": risk["Total_Capital_Req"],
            "Max_Risk_INR": risk["Max_Risk_INR"],
            "SL_Pct": rationale["SL_Pct"],
            "Target_Base_Pct": rationale["Target_Base_Pct"],
            "Target_Bull_Pct": rationale["Target_Bull_Pct"],
            "Pillar_Technical": rationale["Pillar_Technical"],
            "Pillar_Volume": rationale["Pillar_Volume"],
            "Pillar_Options": rationale["Pillar_Options"],
            "Pillar_Fundamentals": rationale["Pillar_Fundamentals"],
            "News_Catalyst": news["Catalyst_Summary"],
            "News_Type": news["Catalyst_Type"],
            "News_Sentiment": news["News_Sentiment"],
            "News_Headlines": news["Headlines"],
            "Top_Headline": news.get("Top_Headline", ""),
            "Is_Penny": penny_info["Is_Penny"],
            "Circuit_Risk": penny_info["Circuit_Risk"],
            "Circuit_Warning_Badge": penny_info["Circuit_Warning_Badge"],
            "Liquidity_Rating": penny_info["Liquidity_Rating"],
            "Turnaround_Score": penny_info["Turnaround_Score"],
            "Turnaround_Verdict": penny_info["Turnaround_Verdict"],
            "Penny_Trap_Warning": penny_info["Trap_Warning"],
            "Penny_Allocation_Guidance": penny_info["Max_Allocation_Guidance"],
            "Supertrend": tech["Supertrend_Status"],
            "RSI_14": tech["RSI_14"],
            "EMA_Alignment": tech["EMA_Alignment"],
            "Option_PCR": pcr,
            "Max_Pain": opts["Max_Pain"],
            "OI_Dynamics": opts["OI_Dynamics"],
            "Thesis": thesis,
            "Adversarial_Risk": adv_risk,
            "_raw_mc": mc,
            "_raw_tech": tech,
            "_raw_fund": fund,
            "_raw_news": news,
            "_raw_penny": penny_info,
            "_raw_df": df
        }
    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")
        return None

def run_screener_pipeline(
    tickers: Optional[List[str]] = None,
    strategy: str = "all",
    enable_ai: bool = True,
    max_risk_inr: float = 5000.0,
    progress_callback = None
) -> pd.DataFrame:
    """
    Main entry point for screening stocks across the Indian market.
    Returns the comprehensive 17-column Master Pandas DataFrame.
    """
    if tickers is None or len(tickers) == 0:
        tickers = config.NIFTY_50_TICKERS
        
    # Step 1: Batch Download
    if progress_callback:
        progress_callback(0.1, f"Fetching OHLCV candles for {len(tickers)} symbols...")
        
    ohlcv_map = fetch_batch_ohlcv(tickers, period="6mo")
    
    # Step 2: Fast Strategy Filtering
    if progress_callback:
        progress_callback(0.3, f"Applying strategy filter '{strategy}'...")
    candidates = filter_tickers_by_strategy(ohlcv_map, strategy=strategy)
    
    # Step 3: Deep Quant Execution
    results = []
    total = len(candidates)
    
    for idx, sym in enumerate(candidates):
        if progress_callback:
            progress_callback(0.3 + (0.6 * (idx + 1) / total), f"Analyzing {sym} ({idx+1}/{total})...")
            
        df = ohlcv_map.get(sym)
        if df is not None and not df.empty:
            item = process_single_ticker(sym, df, enable_ai=enable_ai, max_risk_inr=max_risk_inr)
            if item:
                results.append(item)
                
    if not results:
        return pd.DataFrame()
        
    # Convert to DataFrame
    df_results = pd.DataFrame(results)
    
    # Sort by Conviction Score and Risk:Reward descending
    df_results = df_results.sort_values(by=["Conviction_Score", "Risk_Reward"], ascending=[False, False]).reset_index(drop=True)
    
    # Record Audit and Individual Predictions to SQLite
    bull_count = int((df_results['Signal'].isin(['Strong Buy', 'Buy'])).sum())
    bear_count = int((df_results['Signal'].isin(['Strong Sell', 'Sell'])).sum())
    top_picks = df_results[['Ticker', 'Signal', 'Conviction_Score', 'CMP', 'Target_Base', 'Stop_Loss']].head(5).to_dict(orient='records')
    
    record_scan_audit(
        universe=f"NIFTY_BASKET ({len(tickers)})",
        total=len(df_results),
        bull=bull_count,
        bear=bear_count,
        top_picks=top_picks
    )
    
    # Save daily prediction baseline for walk-forward verification
    for item in results:
        try:
            from db.storage import record_prediction
            record_prediction(
                ticker=item['Ticker'],
                cmp_at_pred=item['CMP'],
                signal=item['Signal'],
                conviction_score=item['Conviction_Score'],
                stop_loss=item['Stop_Loss'],
                target_base=item['Target_Base'],
                target_bull=item['Target_Bull'],
                risk_reward=item['Risk_Reward'],
                thesis=item['Thesis']
            )
        except Exception as err:
            pass
    
    if progress_callback:
        progress_callback(1.0, "Analysis complete!")
        
    return df_results
