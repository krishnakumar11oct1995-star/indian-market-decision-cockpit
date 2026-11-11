import pandas as pd
import numpy as np

def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    """Calculates Exponential Moving Average."""
    return series.ewm(span=span, adjust=False).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    # Avoid division by zero
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculates Average True Range (ATR)."""
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr.bfill()

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """
    Calculates Supertrend indicator.
    Returns DataFrame with columns: ['Supertrend', 'Trend'] (1 for Bullish, -1 for Bearish)
    """
    atr = calculate_atr(df, period)
    hl2 = (df['High'] + df['Low']) / 2.0
    
    upper_basic = hl2 + (multiplier * atr)
    lower_basic = hl2 - (multiplier * atr)
    
    upper_band = upper_basic.copy()
    lower_band = lower_basic.copy()
    
    trend = [1] * len(df)
    supertrend = [0.0] * len(df)
    
    close = df['Close'].values
    ub = upper_basic.values
    lb = lower_basic.values
    
    for i in range(1, len(df)):
        # Trailing lower band
        if close[i-1] > lower_band.iloc[i-1]:
            lower_band.iloc[i] = max(lb[i], lower_band.iloc[i-1])
        else:
            lower_band.iloc[i] = lb[i]
            
        # Trailing upper band
        if close[i-1] < upper_band.iloc[i-1]:
            upper_band.iloc[i] = min(ub[i], upper_band.iloc[i-1])
        else:
            upper_band.iloc[i] = ub[i]
            
        # Trend decision
        if close[i] > upper_band.iloc[i-1]:
            trend[i] = 1
        elif close[i] < lower_band.iloc[i-1]:
            trend[i] = -1
        else:
            trend[i] = trend[i-1]
            
        supertrend[i] = lower_band.iloc[i] if trend[i] == 1 else upper_band.iloc[i]
        
    res = pd.DataFrame(index=df.index)
    res['Supertrend'] = supertrend
    res['Trend'] = trend
    res['UpperBand'] = upper_band
    res['LowerBand'] = lower_band
    return res

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Calculates MACD Line, Signal Line, and Histogram."""
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    
    df = pd.DataFrame(index=series.index)
    df['MACD'] = macd_line
    df['Signal'] = signal_line
    df['Hist'] = histogram
    return df

def calculate_bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """Calculates Bollinger Bands and Bandwidth."""
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    bandwidth = (upper - lower) / sma.replace(0, np.nan)
    
    df = pd.DataFrame(index=series.index)
    df['BB_Upper'] = upper
    df['BB_Middle'] = sma
    df['BB_Lower'] = lower
    df['BB_Bandwidth'] = bandwidth
    return df

def analyze_technical(df: pd.DataFrame) -> dict:
    """
    Computes all core technical indicators on historical OHLCV data.
    Returns a structured dictionary of metrics, alignments, and a Technical Score (0-100).
    """
    # Normalize column names if needed
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
        
    df = df.copy()
    close = df['Close']
    last_close = float(close.iloc[-1])
    
    # EMAs
    df['EMA_20'] = calculate_ema(close, 20)
    df['EMA_50'] = calculate_ema(close, 50)
    df['EMA_200'] = calculate_ema(close, 200)
    
    ema20 = float(df['EMA_20'].iloc[-1])
    ema50 = float(df['EMA_50'].iloc[-1])
    ema200 = float(df['EMA_200'].iloc[-1])
    
    if last_close > ema20 > ema50 > ema200:
        ema_alignment = "Bullish (Price > 20 > 50 > 200)"
    elif last_close < ema20 < ema50 < ema200:
        ema_alignment = "Bearish (Price < 20 < 50 < 200)"
    elif last_close > ema200:
        ema_alignment = "Moderate Bullish (> 200 EMA)"
    else:
        ema_alignment = "Neutral / Mixed"
        
    # RSI
    df['RSI'] = calculate_rsi(close, 14)
    last_rsi = round(float(df['RSI'].iloc[-1]), 2)
    
    # Supertrend
    st_df = calculate_supertrend(df, 10, 3.0)
    st_trend = st_df['Trend'].iloc[-1]
    st_val = float(st_df['Supertrend'].iloc[-1])
    st_status = f"Bullish (₹{st_val:.1f})" if st_trend == 1 else f"Bearish (₹{st_val:.1f})"
    
    # ATR
    df['ATR'] = calculate_atr(df, 14)
    last_atr = round(float(df['ATR'].iloc[-1]), 2)
    
    # MACD
    macd_df = calculate_macd(close)
    last_macd_hist = float(macd_df['Hist'].iloc[-1])
    macd_bias = "Bullish" if last_macd_hist > 0 else "Bearish"
    
    # Order Flow & Volume Analysis
    volume = df['Volume']
    avg_vol_20 = float(volume.rolling(20).mean().iloc[-1])
    last_vol = float(volume.iloc[-1])
    vol_ratio = last_vol / max(avg_vol_20, 1.0)
    
    prev_close = float(close.iloc[-2]) if len(close) > 1 else last_close
    if vol_ratio >= 1.5:
        if last_close > prev_close:
            order_flow = "Institutional Accumulation"
        else:
            order_flow = "Institutional Distribution"
    elif vol_ratio >= 1.1:
        order_flow = "Above Average Volume"
    else:
        order_flow = "Normal / Retail Volume"
        
    # Multi-Factor Technical Score (0 to 100)
    score = 50  # Start at neutral baseline
    
    # Trend alignment (max +30 or -30)
    if st_trend == 1:
        score += 15
    else:
        score -= 15
        
    if last_close > ema200:
        score += 10
    else:
        score -= 10
        
    if ema20 > ema50:
        score += 5
    else:
        score -= 5
        
    # RSI Momentum (max +10 or -10)
    if 55 <= last_rsi <= 70:
        score += 10
    elif 40 <= last_rsi < 55:
        score += 0
    elif last_rsi > 70:
        score += 5  # Strong but near overbought
    elif last_rsi < 30:
        score -= 5  # Oversold
    else:
        score -= 10
        
    # MACD
    if macd_bias == "Bullish":
        score += 5
    else:
        score -= 5
        
    # Volume Confirmation
    if order_flow == "Institutional Accumulation":
        score += 5
    elif order_flow == "Institutional Distribution":
        score -= 5
        
    score = max(0, min(100, score))
    
    return {
        "CMP": last_close,
        "EMA_20": ema20,
        "EMA_50": ema50,
        "EMA_200": ema200,
        "EMA_Alignment": ema_alignment,
        "RSI_14": last_rsi,
        "Supertrend_Status": st_status,
        "Supertrend_Trend": st_trend,
        "Supertrend_Level": st_val,
        "ATR_14": last_atr,
        "MACD_Hist": last_macd_hist,
        "MACD_Bias": macd_bias,
        "Volume_Ratio": round(vol_ratio, 2),
        "Order_Flow": order_flow,
        "Technical_Score": score
    }
