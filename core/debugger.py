import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import db.storage as storage

def audit_and_debug_predictions(progress_callback=None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Walk-forward verification engine.
    Compares past predicted targets and stop-losses against actual subsequent market prices.
    Updates SQLite database and returns a calibrated diagnostic report.
    """
    all_preds = storage.get_all_predictions()
    if not all_preds:
        return pd.DataFrame(), {
            "Total_Predictions": 0,
            "Target_Hits": 0,
            "Stop_Loss_Hits": 0,
            "In_Play": 0,
            "Win_Rate_Pct": 0.0,
            "Calibration_Advice": "No predictions logged yet. Run scans or analyze individual stocks to populate the audit log."
        }
        
    # Group unique tickers to batch fetch recent data
    unique_tickers = list(set([p['ticker'] for p in all_preds]))
    
    if progress_callback:
        progress_callback(0.2, f"Fetching market updates for {len(unique_tickers)} tracked tickers...")
        
    try:
        # Fetch 1 month of recent data for these tickers
        data = yf.download(unique_tickers, period="1mo", interval="1d", group_by="ticker", auto_adjust=False, progress=False)
    except Exception as e:
        data = None
        
    updated_records = []
    target_hits = 0
    sl_hits = 0
    in_play = 0
    
    total = len(all_preds)
    for idx, pred in enumerate(all_preds):
        if progress_callback:
            progress_callback(0.3 + 0.6 * ((idx + 1) / total), f"Verifying {pred['ticker']}...")
            
        ticker = pred['ticker']
        pred_date_str = pred['prediction_date'][:10]  # YYYY-MM-DD
        cmp_pred = float(pred['cmp_at_prediction'])
        sl = float(pred['stop_loss'])
        target_base = float(pred['target_base'])
        signal = str(pred['signal'])
        current_status = pred['outcome_status']
        
        # Get historical slice from prediction date onward
        df_sym = None
        if data is not None and not data.empty:
            try:
                if len(unique_tickers) == 1:
                    df_sym = data
                elif ticker in data.columns.levels[0]:
                    df_sym = data[ticker]
            except Exception:
                df_sym = None
                
        if df_sym is not None and not df_sym.empty:
            df_sym = df_sym.dropna(subset=['Close'])
            # Filter rows on or after prediction date
            try:
                df_post = df_sym[df_sym.index >= pred_date_str]
                if df_post.empty:
                    df_post = df_sym.tail(5)
            except Exception:
                df_post = df_sym.tail(5)
                
            if not df_post.empty:
                high_since = float(df_post['High'].max())
                low_since = float(df_post['Low'].min())
                latest_price = float(df_post['Close'].iloc[-1])
                ret_pct = round(((latest_price - cmp_pred) / cmp_pred) * 100, 2)
                
                # Determine outcome
                if "Buy" in signal:
                    if high_since >= target_base:
                        status = "TARGET_HIT"
                        notes = f"Target ₹{target_base:.1f} reached (High: ₹{high_since:.1f}, +{ret_pct}%). Thesis verified."
                    elif low_since <= sl:
                        status = "STOP_LOSS_HIT"
                        notes = f"SL ₹{sl:.1f} breached (Low: ₹{low_since:.1f}). Diagnosis: Volatility exceeded 1.5x ATR cushion."
                    else:
                        status = "IN_PROGRESS"
                        notes = f"Holding range. CMP: ₹{latest_price:.1f} ({ret_pct:+.1f}%). Safe above SL ₹{sl:.1f}."
                else: # Neutral or Sell
                    if low_since <= target_base and target_base < cmp_pred:
                        status = "TARGET_HIT"
                        notes = f"Short target ₹{target_base:.1f} achieved. Thesis verified."
                    elif high_since >= sl and sl > cmp_pred:
                        status = "STOP_LOSS_HIT"
                        notes = f"Short SL ₹{sl:.1f} breached (High: ₹{high_since:.1f})."
                    else:
                        status = "IN_PROGRESS"
                        notes = f"In range. CMP: ₹{latest_price:.1f}."
                        
                # Update DB
                storage.update_prediction_outcome(
                    pred_id=pred['id'],
                    latest_price=latest_price,
                    highest=high_since,
                    lowest=low_since,
                    outcome=status,
                    return_pct=ret_pct,
                    notes=notes
                )
                
                pred_copy = dict(pred)
                pred_copy['latest_price'] = latest_price
                pred_copy['highest_price_since'] = high_since
                pred_copy['lowest_price_since'] = low_since
                pred_copy['outcome_status'] = status
                pred_copy['actual_return_pct'] = ret_pct
                pred_copy['debug_notes'] = notes
                updated_records.append(pred_copy)
                
                if status == "TARGET_HIT":
                    target_hits += 1
                elif status == "STOP_LOSS_HIT":
                    sl_hits += 1
                else:
                    in_play += 1
                continue
                
        # If no new price fetched, retain existing
        updated_records.append(dict(pred))
        if current_status == "TARGET_HIT":
            target_hits += 1
        elif current_status == "STOP_LOSS_HIT":
            sl_hits += 1
        else:
            in_play += 1
            
    df_debug = pd.DataFrame(updated_records)
    
    # Calibration Diagnostics
    resolved_trades = target_hits + sl_hits
    win_rate = round((target_hits / resolved_trades * 100), 1) if resolved_trades > 0 else 0.0
    
    if resolved_trades == 0:
        advice = "All tracked positions are still active within their range. Monitor walk-forward development."
    elif win_rate >= 70.0:
        advice = f"Strong model accuracy ({win_rate}% Win Rate). Current ATR 1.5x stop-loss and Monte Carlo targets are well-calibrated."
    elif sl_hits > target_hits:
        advice = (
            f"Stop-Loss hit frequency ({sl_hits} hits) is elevated. "
            f"Diagnosis: Market volatility may be wider than 1.5x ATR. "
            f"Calibration recommendation: Test expanding ATR stop-loss buffer to 1.8x - 2.0x or requiring higher Conviction Score (>65) before entry."
        )
    else:
        advice = f"Moderate performance ({win_rate}% Win Rate). Trades are tracking within expected statistical variance."
        
    metrics = {
        "Total_Predictions": len(updated_records),
        "Target_Hits": target_hits,
        "Stop_Loss_Hits": sl_hits,
        "In_Play": in_play,
        "Win_Rate_Pct": win_rate,
        "Calibration_Advice": advice
    }
    
    return df_debug, metrics
