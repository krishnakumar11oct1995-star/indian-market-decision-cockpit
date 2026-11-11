import sqlite3
import os
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "market.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initializes SQLite database tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Watchlist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watchlist (
        ticker TEXT PRIMARY KEY,
        added_date TEXT,
        target_price REAL,
        stop_loss REAL,
        notes TEXT
    )
    """)
    
    # 2. Paper Trades
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS paper_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT,
        entry_date TEXT,
        entry_price REAL,
        quantity INTEGER,
        stop_loss REAL,
        target_price REAL,
        current_status TEXT DEFAULT 'OPEN',
        exit_date TEXT,
        exit_price REAL,
        pnl_inr REAL DEFAULT 0.0
    )
    """)
    
    # 3. Screener Run History
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scan_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_timestamp TEXT,
        universe TEXT,
        total_stocks INTEGER,
        bullish_count INTEGER,
        bearish_count INTEGER,
        top_picks_json TEXT
    )
    """)
    
    # 4. Walk-Forward Prediction & Debug Audit
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prediction_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prediction_date TEXT,
        ticker TEXT,
        cmp_at_prediction REAL,
        signal TEXT,
        conviction_score INTEGER,
        stop_loss REAL,
        target_base REAL,
        target_bull REAL,
        risk_reward REAL,
        thesis TEXT,
        last_checked_date TEXT,
        latest_price REAL,
        highest_price_since REAL,
        lowest_price_since REAL,
        outcome_status TEXT DEFAULT 'IN_PROGRESS',
        actual_return_pct REAL DEFAULT 0.0,
        debug_notes TEXT
    )
    """)
    
    # 5. IPO Applications Tracker
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ipo_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_date TEXT,
        company_name TEXT,
        category TEXT,
        price_applied REAL,
        lot_size INTEGER,
        total_amount REAL,
        dates TEXT,
        verdict TEXT,
        allotment_status TEXT DEFAULT 'APPLIED',
        notes TEXT
    )
    """)
    
    # 6. Telegram Alert Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alert_settings (
        id INTEGER PRIMARY KEY,
        bot_token TEXT,
        chat_id TEXT,
        auto_alerts INTEGER DEFAULT 0
    )
    """)
    
    conn.commit()
    conn.close()

# Watchlist CRUD
def add_to_watchlist(ticker: str, target: float = 0.0, sl: float = 0.0, notes: str = "") -> bool:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO watchlist (ticker, added_date, target_price, stop_loss, notes) VALUES (?, ?, ?, ?, ?)",
            (ticker, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), target, sl, notes)
        )
        conn.commit()
        return True
    finally:
        conn.close()

def get_watchlist() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM watchlist ORDER BY added_date DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def remove_from_watchlist(ticker: str) -> bool:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
        conn.commit()
        return True
    finally:
        conn.close()

# Paper Trading CRUD
def open_paper_trade(ticker: str, entry_price: float, quantity: int, sl: float, tp: float) -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO paper_trades 
               (ticker, entry_date, entry_price, quantity, stop_loss, target_price, current_status) 
               VALUES (?, ?, ?, ?, ?, ?, 'OPEN')""",
            (ticker, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), entry_price, quantity, sl, tp)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def get_paper_trades() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM paper_trades ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# Save Screener Audit
def record_scan_audit(universe: str, total: int, bull: int, bear: int, top_picks: List[Dict[str, Any]]):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO scan_history 
               (scan_timestamp, universe, total_stocks, bullish_count, bearish_count, top_picks_json) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), universe, total, bull, bear, json.dumps(top_picks))
        )
        conn.commit()
    finally:
        conn.close()

# Prediction Audit CRUD
def record_prediction(
    ticker: str,
    cmp_at_pred: float,
    signal: str,
    conviction_score: int,
    stop_loss: float,
    target_base: float,
    target_bull: float,
    risk_reward: float,
    thesis: str
) -> int:
    conn = get_connection()
    try:
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO prediction_audit 
               (prediction_date, ticker, cmp_at_prediction, signal, conviction_score, 
                stop_loss, target_base, target_bull, risk_reward, thesis, 
                last_checked_date, latest_price, highest_price_since, lowest_price_since, 
                outcome_status, actual_return_pct, debug_notes) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'IN_PROGRESS', 0.0, 'Awaiting next market session.')""",
            (today_str, ticker, cmp_at_pred, signal, conviction_score, 
             stop_loss, target_base, target_bull, risk_reward, thesis, 
             today_str, cmp_at_pred, cmp_at_pred, cmp_at_pred)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def get_all_predictions() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM prediction_audit ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_active_predictions() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM prediction_audit WHERE outcome_status = 'IN_PROGRESS' ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def update_prediction_outcome(
    pred_id: int,
    latest_price: float,
    highest: float,
    lowest: float,
    outcome: str,
    return_pct: float,
    notes: str
):
    conn = get_connection()
    try:
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """UPDATE prediction_audit 
               SET last_checked_date = ?, latest_price = ?, highest_price_since = ?, 
                   lowest_price_since = ?, outcome_status = ?, actual_return_pct = ?, debug_notes = ? 
               WHERE id = ?""",
            (today_str, latest_price, highest, lowest, outcome, return_pct, notes, pred_id)
        )
        conn.commit()
    finally:
        conn.close()

def record_ipo_application(
    company_name: str,
    category: str,
    price_applied: float,
    lot_size: int,
    total_amount: float,
    dates: str,
    verdict: str,
    notes: str = ""
) -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """INSERT INTO ipo_applications 
               (application_date, company_name, category, price_applied, lot_size, total_amount, dates, verdict, allotment_status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'APPLIED', ?)""",
            (today_str, company_name, category, price_applied, lot_size, total_amount, dates, verdict, notes)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def get_all_ipo_applications() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM ipo_applications ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def update_ipo_status(app_id: int, status: str, notes: str = ""):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE ipo_applications SET allotment_status = ?, notes = ? WHERE id = ?",
            (status, notes, app_id)
        )
        conn.commit()
    finally:
        conn.close()

def delete_ipo_application(app_id: int):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM ipo_applications WHERE id = ?", (app_id,))
        conn.commit()
    finally:
        conn.close()

def save_alert_settings(bot_token: str, chat_id: str, auto_alerts: int = 0):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO alert_settings (id, bot_token, chat_id, auto_alerts) VALUES (1, ?, ?, ?)",
            (bot_token.strip(), chat_id.strip(), auto_alerts)
        )
        conn.commit()
    finally:
        conn.close()

def get_alert_settings() -> Dict[str, Any]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM alert_settings WHERE id = 1").fetchone()
        if row:
            return dict(row)
        return {"bot_token": "", "chat_id": "", "auto_alerts": 0}
    finally:
        conn.close()

# Auto-initialize on import
init_database()
