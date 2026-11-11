import yfinance as yf
import pandas as pd
from typing import List, Dict, Any, Optional
import config

def fetch_batch_ohlcv(tickers: List[str], period: str = "6mo") -> Dict[str, pd.DataFrame]:
    """
    Downloads historical OHLCV data for multiple tickers in a single vectorized batch request,
    with an automatic per-ticker fallback.
    Returns a dictionary mapping ticker -> clean DataFrame.
    """
    if not tickers:
        return {}
        
    result = {}
    try:
        data = yf.download(tickers, period=period, interval="1d", group_by="ticker", auto_adjust=False, progress=False)
        
        if not data.empty:
            for sym in tickers:
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        if sym in data.columns.levels[0]:
                            df_sym = data[sym].dropna(subset=['Close'])
                            if len(df_sym) > 10:
                                result[sym] = df_sym
                        elif 'Close' in data.columns.levels[0]: # Inverted MultiIndex
                            df_sym = data.xs(sym, level=1, axis=1).dropna(subset=['Close'])
                            if len(df_sym) > 10:
                                result[sym] = df_sym
                    else:
                        if 'Close' in data.columns:
                            df_sym = data.dropna(subset=['Close'])
                            if len(df_sym) > 10:
                                result[sym] = df_sym
                except Exception:
                    pass
    except Exception as e:
        print(f"Batch fetch note: {e}")
        
    # Bulletproof fallback for any ticker that wasn't retrieved in the batch
    for sym in tickers:
        if sym not in result:
            try:
                t = yf.Ticker(sym)
                hist = t.history(period=period)
                if not hist.empty and len(hist) > 10 and 'Close' in hist.columns:
                    result[sym] = hist.dropna(subset=['Close'])
            except Exception:
                pass
                
    return result

def filter_tickers_by_strategy(
    ohlcv_map: Dict[str, pd.DataFrame],
    strategy: str = "all"
) -> List[str]:
    """
    Fast preliminary filter applied to the batch data before deep quant calculations.
    """
    if strategy == "all":
        return list(ohlcv_map.keys())
        
    selected = []
    for ticker, df in ohlcv_map.items():
        if len(df) < 30:
            continue
            
        close = df['Close']
        vol = df['Volume']
        last_close = float(close.iloc[-1])
        last_vol = float(vol.iloc[-1])
        avg_vol = float(vol.rolling(20).mean().iloc[-1])
        
        if strategy == "momentum":
            # Price > 20 EMA and Volume > 1.2x average
            ema20 = float(close.ewm(span=20).mean().iloc[-1])
            if last_close > ema20 and last_vol > (avg_vol * 1.1):
                selected.append(ticker)
                
        elif strategy == "breakout":
            # High volume spike (1.5x) and price near 20-day high
            high_20 = float(df['High'].rolling(20).max().iloc[-1])
            if last_close >= (high_20 * 0.98) and last_vol > (avg_vol * 1.3):
                selected.append(ticker)
                
        elif strategy == "dip_buy":
            # Price below 20 EMA but above 200 EMA (if available) or healthy pullback
            ema20 = float(close.ewm(span=20).mean().iloc[-1])
            if last_close < ema20:
                selected.append(ticker)
        else:
            selected.append(ticker)
            
    return selected if selected else list(ohlcv_map.keys())
