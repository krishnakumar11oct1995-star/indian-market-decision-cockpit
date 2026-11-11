import requests
import xml.etree.ElementTree as ET
import json
import yfinance as yf
from datetime import datetime
from typing import Dict, Any, List, Optional
import config

_NEWS_CACHE: Dict[str, Dict[str, Any]] = {}

def fetch_live_news_headlines(ticker: str, limit: int = 5) -> List[Dict[str, str]]:
    """
    Fetches real-time financial news headlines for an Indian stock ticker
    from Google News RSS and Yahoo Finance.
    """
    clean_sym = ticker.replace(".NS", "").replace(".BO", "").strip()
    headlines = []
    
    # 1. Google News RSS for Indian Equities
    rss_url = f"https://news.google.com/rss/search?q={clean_sym}+share+price+news+OR+{clean_sym}+stock&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        res = requests.get(rss_url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            items = root.findall('.//item')
            for item in items[:limit]:
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                
                # Clean publisher from title (e.g. "Title - Economic Times")
                publisher = "Financial Media"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0]
                    publisher = parts[1]
                    
                if title and len(title) > 15:
                    headlines.append({
                        "title": title,
                        "publisher": publisher,
                        "link": link,
                        "pubDate": pub_date[:16] if pub_date else ""
                    })
    except Exception:
        pass
        
    # 2. Fallback / Supplement with Yahoo Finance News
    if len(headlines) < 3:
        try:
            t = yf.Ticker(ticker)
            yf_news = t.news or []
            for n in yf_news:
                title = n.get('title') or n.get('content', {}).get('title')
                publisher = n.get('publisher') or n.get('content', {}).get('provider', {}).get('displayName', 'Yahoo Finance')
                link = n.get('link') or n.get('content', {}).get('canonicalUrl', {}).get('url', '#')
                if title and not any(h['title'] == title for h in headlines):
                    headlines.append({
                        "title": title,
                        "publisher": publisher,
                        "link": link,
                        "pubDate": "Recent"
                    })
                if len(headlines) >= limit:
                    break
        except Exception:
            pass
            
    return headlines[:limit]

def analyze_news_catalyst(ticker: str) -> Dict[str, Any]:
    """
    Fetches live headlines and uses Gemini 2.5 Flash to synthesize:
    - Why is this stock in the news?
    - What is the primary market catalyst?
    - News sentiment (Bullish / Neutral / Caution)
    """
    clean_sym = ticker.replace(".NS", "").replace(".BO", "")
    today_key = f"{clean_sym}_{datetime.now().strftime('%Y%m%d')}"
    if today_key in _NEWS_CACHE:
        return _NEWS_CACHE[today_key]
        
    headlines = fetch_live_news_headlines(ticker, limit=4)
    
    if not headlines:
        default_res = {
            "Ticker": ticker,
            "Headlines": [],
            "Catalyst_Summary": f"No major company-specific news breaking today for {clean_sym}. Trading is currently driven by broader market indices and sector momentum.",
            "Catalyst_Type": "Broad Market / Sector Momentum",
            "News_Sentiment": "Neutral",
            "Top_Headline": f"{clean_sym} tracking broader index movements"
        }
        _NEWS_CACHE[today_key] = default_res
        return default_res
        
    headlines_text = "\n".join([f"- {h['title']} (Source: {h['publisher']})" for h in headlines])
    top_headline = headlines[0]['title']
    
    prompt = f"""
You are an expert Indian stock market news editor.
Here are recent news headlines for {clean_sym}:
{headlines_text}

Answer in valid JSON format:
{{
  "catalyst_summary": "A 2-sentence clear explanation of WHY this stock is in the news today and what the core catalyst is (earnings, orders, management, sector move, etc.). Written for an active trader.",
  "catalyst_type": "Choose one: Earnings & Financial Results | Order Bagged / Expansion | Block Deal / Institutional Inflow | Regulatory / Policy | Analyst Upgrade | Routine / Technical",
  "news_sentiment": "Bullish | Neutral | Caution"
}}
Return ONLY the JSON object.
"""
    try:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
        }
        res = requests.post(config.GEMINI_ENDPOINT, json=payload, timeout=7)
        if res.status_code == 200:
            parsed = json.loads(res.json()['candidates'][0]['content']['parts'][0]['text'])
            result = {
                "Ticker": ticker,
                "Headlines": headlines,
                "Catalyst_Summary": parsed.get("catalyst_summary", f"{clean_sym} is seeing active discussion in financial media."),
                "Catalyst_Type": parsed.get("catalyst_type", "Routine / Technical"),
                "News_Sentiment": parsed.get("news_sentiment", "Neutral"),
                "Top_Headline": top_headline
            }
            _NEWS_CACHE[today_key] = result
            return result
    except Exception:
        pass
        
    fallback_res = {
        "Ticker": ticker,
        "Headlines": headlines,
        "Catalyst_Summary": f"{clean_sym} is featured in recent reports from {headlines[0]['publisher']}. Top story: '{top_headline}'.",
        "Catalyst_Type": "Financial Media Coverage",
        "News_Sentiment": "Neutral",
        "Top_Headline": top_headline
    }
    _NEWS_CACHE[today_key] = fallback_res
    return fallback_res
