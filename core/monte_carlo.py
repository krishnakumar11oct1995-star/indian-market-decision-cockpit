import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from typing import Dict, Any, List

def run_monte_carlo_simulation(
    df: pd.DataFrame,
    days: int = 7,
    simulations: int = 5000,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Executes a 5,000-path Monte Carlo price trajectory simulation
    and clusters terminal price endpoints using K-Means into 3 archetypes:
    Bear, Base, and Bull.
    """
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
        
    close = pd.to_numeric(close, errors='coerce').dropna()
    last_price = float(close.iloc[-1])
    
    returns = close.pct_change().dropna()
    mu = float(returns.mean())
    sigma = float(returns.std())
    
    # Avoid zero volatility edge case
    if sigma <= 0.0001:
        sigma = 0.015  # Fallback 1.5% daily volatility
        
    np.random.seed(seed)
    
    # Vectorized path generation
    # shape: (simulations, days + 1)
    daily_shocks = np.random.normal(mu, sigma, (simulations, days))
    price_multipliers = np.cumprod(1 + daily_shocks, axis=1)
    
    # Prepend starting price
    sim_paths = np.empty((simulations, days + 1))
    sim_paths[:, 0] = last_price
    sim_paths[:, 1:] = last_price * price_multipliers
    
    final_prices = sim_paths[:, -1]
    
    # KMeans Clustering into 3 Archetypes
    data = final_prices.reshape(-1, 1)
    kmeans = KMeans(n_clusters=3, random_state=seed, n_init=10).fit(data)
    centers = sorted(kmeans.cluster_centers_.flatten())
    
    bear_target = float(centers[0])
    base_target = float(centers[1])
    bull_target = float(centers[2])
    
    # Extract 3 representative paths closest to cluster centers
    representative_paths = {}
    archetypes = ["Bear_Path", "Base_Path", "Bull_Path"]
    for i, center in enumerate(centers):
        closest_idx = int(np.argmin(np.abs(final_prices - center)))
        representative_paths[archetypes[i]] = sim_paths[closest_idx].tolist()
        
    # Sample subset of 100 paths for Plotly chart background rendering
    sample_background_paths = sim_paths[:60].tolist()
    
    return {
        "Last_Price": last_price,
        "Daily_Volatility_Pct": round(sigma * 100, 2),
        "Annualized_Vol_Pct": round(sigma * np.sqrt(252) * 100, 2),
        "Target_Bear": round(bear_target, 2),
        "Target_Base": round(base_target, 2),
        "Target_Bull": round(bull_target, 2),
        "Bear_Return_Pct": round(((bear_target - last_price) / last_price) * 100, 2),
        "Base_Return_Pct": round(((base_target - last_price) / last_price) * 100, 2),
        "Bull_Return_Pct": round(((bull_target - last_price) / last_price) * 100, 2),
        "Representative_Paths": representative_paths,
        "Sample_Paths": sample_background_paths,
        "Simulation_Days": days
    }
