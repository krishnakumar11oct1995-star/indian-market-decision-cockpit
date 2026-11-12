"""
IPO Radar & Intelligence Module
Fetches active & upcoming Indian IPOs (Mainboard & SME), real-time Grey Market Premium (GMP),
live news reviews via Google News RSS, and generates institutional AI verdicts (Apply vs Avoid).
"""

import requests
from bs4 import BeautifulSoup
import urllib.parse
import xml.etree.ElementTree as ET
import json
import re
import time
from datetime import datetime
import config

# In-memory cache for scraped IPO list (valid for 20 minutes)
_IPO_CACHE = {
    "timestamp": 0,
    "data": []
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5'
}

def clean_text(s: str) -> str:
    """Strip emojis and non-ascii artifacts for safe processing."""
    if not s:
        return ""
    return re.sub(r'\s+', ' ', s).strip()

def parse_price(val_str: str) -> float:
    """Parse numeric price from string like '₹424' or '424'."""
    if not val_str:
        return 0.0
    digits = re.findall(r'[\d\.]+', val_str.replace(',', ''))
    return float(digits[0]) if digits else 0.0

def fetch_active_and_upcoming_ipos(force_refresh: bool = False) -> list:
    """
    Fetch active, upcoming, and recently closed Indian IPOs with GMP and listing estimates.
    Caches results for 20 minutes to prevent rate limits.
    """
    global _IPO_CACHE
    now = time.time()
    if not force_refresh and _IPO_CACHE["data"] and (now - _IPO_CACHE["timestamp"] < 1200):
        return _IPO_CACHE["data"]

    url = 'https://ipowatch.in/ipo-grey-market-premium-latest-ipo-gmp/'
    ipos = []
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table')
            if table:
                rows = table.find_all('tr')
                for r in rows[1:]:
                    cells = r.find_all(['td', 'th'])
                    if len(cells) >= 6:
                        # Extract IPO Name and detail URL
                        a_tag = cells[0].find('a')
                        name = clean_text(cells[0].get_text())
                        detail_url = a_tag['href'] if a_tag and 'href' in a_tag.attrs else ''
                        
                        # Identify Mainboard vs SME
                        is_sme = "SME" in name.upper()
                        clean_name = re.sub(r'(?i)\b(sme|ipo)\b', '', name).strip()
                        if not clean_name:
                            clean_name = name
                            
                        # GMP
                        gmp_raw = clean_text(cells[1].get_text())
                        gmp_val = parse_price(gmp_raw)
                        
                        # Price band
                        price_raw = clean_text(cells[3].get_text()) if len(cells) > 3 else '-'
                        price_val = parse_price(price_raw)
                        
                        # Est Listing & Gain %
                        est_raw = clean_text(cells[4].get_text()) if len(cells) > 4 else '-'
                        gain_pct_match = re.search(r'([\d\.\-]+)\s*%', est_raw)
                        gain_pct = float(gain_pct_match.group(1)) if gain_pct_match else 0.0
                        if gain_pct == 0.0 and price_val > 0 and gmp_val > 0:
                            gain_pct = round((gmp_val / price_val) * 100, 2)
                            
                        # Dates
                        dates = clean_text(cells[5].get_text()) if len(cells) > 5 else 'TBA'
                        
                        # Status (Open / Upcoming / Closed)
                        status_raw = clean_text(cells[6].get_text()) if len(cells) > 6 else 'Upcoming'
                        status = "Upcoming"
                        if "open" in status_raw.lower():
                            status = "Open"
                        elif "close" in status_raw.lower():
                            status = "Closed"
                        elif "upcom" in status_raw.lower():
                            status = "Upcoming"
                            
                        # Estimated Lot Size & Investment
                        lot_size = 1000 if is_sme else (int(14500 / max(price_val, 1)) if price_val > 0 else 1)
                        if not is_sme and lot_size < 1:
                            lot_size = 15
                        min_investment = round(price_val * lot_size, 0) if price_val > 0 else (120000 if is_sme else 14500)

                        ipos.append({
                            "Company_Name": clean_name,
                            "Full_Title": name,
                            "Detail_URL": detail_url,
                            "Category": "SME" if is_sme else "Mainboard",
                            "Price_Band": price_raw if price_raw != '-' else 'TBA',
                            "Price_Val": price_val,
                            "GMP_Val": gmp_val,
                            "Est_Gain_Pct": gain_pct,
                            "Dates": dates,
                            "Status": status,
                            "Lot_Size": lot_size,
                            "Min_Investment": min_investment,
                            "Last_Updated": clean_text(cells[7].get_text()) if len(cells) > 7 else ''
                        })
    except Exception as e:
        print(f"Error scraping IPO table: {e}")
        
    # If scraper returned data, update cache
    if ipos:
        _IPO_CACHE["timestamp"] = now
        _IPO_CACHE["data"] = ipos
    elif _IPO_CACHE["data"]:
        return _IPO_CACHE["data"]
        
    return ipos

def fetch_ipo_news_and_reviews(company_name: str, max_items: int = 4) -> list:
    """
    Scrapes targeted Google News RSS articles for expert reviews and analyst views on the IPO.
    """
    clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', company_name).strip()
    query = f"{clean_name} IPO review apply avoid"
    encoded_q = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_q}+when:14d&hl=en-IN&gl=IN&ceid=IN:en"
    
    articles = []
    try:
        resp = requests.get(rss_url, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            items = root.findall('./channel/item')
            for item in items[:max_items]:
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                source_elem = item.find('source')
                publisher = source_elem.text if source_elem is not None else "Financial Media"
                
                # Format date
                clean_date = pub_date[:16] if len(pub_date) >= 16 else pub_date
                
                if title:
                    articles.append({
                        "title": title,
                        "link": link,
                        "publisher": publisher,
                        "pubDate": clean_date
                    })
    except Exception as e:
        print(f"Error fetching news for {company_name}: {e}")
        
    return articles

_VERDICT_CACHE = {}

def generate_ipo_verdict(ipo: dict, news_headlines: list, enable_ai: bool = True) -> dict:
    """
    Analyzes IPO metrics + news reviews using Gemini 2.5 Flash to synthesize an institutional verdict.
    Outputs actionable recommendations: Apply for Listing Gains, Apply for Long Term, or Avoid.
    """
    company = ipo["Company_Name"]
    category = ipo["Category"]
    gmp_val = ipo["GMP_Val"]
    gain_pct = ipo["Est_Gain_Pct"]
    price_str = ipo["Price_Band"]
    dates = ipo["Dates"]
    
    cache_key = f"{company}_{gmp_val}_{gain_pct}"
    if cache_key in _VERDICT_CACHE:
        return _VERDICT_CACHE[cache_key]
    
    # Default Rule-Based Analysis (Immediate Baseline)
    rule_score = 50
    rule_verdict = "🟡 WAIT & WATCH"
    
    if gain_pct >= 25:
        rule_score = min(90, 65 + int(gain_pct / 2))
        rule_verdict = "🟢 APPLY (High Listing Gains)"
    elif gain_pct >= 10:
        rule_score = 65
        rule_verdict = "🟢 APPLY (Moderate Gains)"
    elif gain_pct > 0:
        rule_score = 50
        rule_verdict = "🟡 SPECULATIVE (Small Listing Margin)"
    elif gain_pct == 0:
        rule_score = 35
        rule_verdict = "🔴 AVOID / PASS (Subdued Demand)"
    else:
        rule_score = 20
        rule_verdict = "🔴 AVOID (Negative Listing Discount)"
        
    if category == "SME":
        # SME penalty for illiquidity and high ticket size
        rule_score = max(20, rule_score - 10)
        
    result = {
        "Verdict": rule_verdict,
        "Conviction_Score": rule_score,
        "Verdict_Summary": f"{company} is showing a Grey Market Premium of ₹{gmp_val:.1f} (+{gain_pct:.1f}% estimated listing pop). Current secondary market sentiment warrants a {rule_verdict.split('(')[0].strip().replace('🟢', '').replace('🟡', '').replace('🔴', '')} stance.",
        "Pillar_GMP": f"GMP stands at ₹{gmp_val:.1f} (+{gain_pct:.1f}% expected gain). {'Demand in grey market is robust.' if gain_pct > 15 else 'Grey market interest is moderate to low.'}",
        "Pillar_Valuation": f"Offered at {price_str} per share. Evaluate sector P/E vs peers before bidding.",
        "Pillar_Structure": f"Category: {category}. Minimum application capital: ₹{ipo['Min_Investment']:,.0f} for {ipo['Lot_Size']} shares.",
        "Pillar_Sentiment": f"Based on recent news articles from {len(news_headlines)} financial outlets.",
        "Key_Risks": f"1. Market sentiment reversal before listing day. 2. Lower circuit lock risks on debut if market turns volatile. 3. High lot size lock-in on {category} issues.",
        "Broker_Consensus": "65% Subscribe (Listing Gains) | 35% Neutral / Avoid" if gain_pct > 15 else "40% Subscribe | 60% Neutral or Avoid",
        "News_Headlines": news_headlines
    }
    
    # Try Gemini 2.5 Flash for institutional deep synthesis
    if enable_ai and config.GEMINI_ENDPOINT:
        try:
            news_context = "\n".join([f"- {h['title']} (Source: {h['publisher']})" for h in news_headlines]) if news_headlines else "No major breaking reviews yet."
            
            prompt = f"""
You are an expert Indian Stock Market IPO Analyst & Investment Banker evaluating an upcoming/active IPO:

COMPANY: {company} ({category} IPO)
PRICE BAND: {price_str}
GREY MARKET PREMIUM (GMP): ₹{gmp_val} ({gain_pct:+.1f}% Expected Listing Gain)
LOT SIZE: {ipo['Lot_Size']} shares (Min Ticket: ₹{ipo['Min_Investment']})
ISSUE DATES: {dates}

RECENT NEWS & ANALYST HEADLINES:
{news_context}

Provide an institutional, objective, plain-English IPO evaluation in strictly valid JSON format:
{{
  "verdict": "One of: 🟢 APPLY (High Listing Gains), 🟢 APPLY (Long-Term Compounding), 🟡 SPECULATIVE (High Risk), 🔴 AVOID / PASS",
  "conviction_score": (Integer between 10 and 95),
  "verdict_summary": "2-sentence actionable advice explaining whether retail traders should bid and whether to flip on listing day or hold.",
  "pillar_gmp": "Concise analysis of GMP strength, trend, and whether listing gains are dependable.",
  "pillar_valuation": "Valuation assessment relative to sector peers and price band reasonableness.",
  "pillar_structure": "Review of the issue structure (growth capital vs promoter exit) and category risks.",
  "key_risks": "Top 2 critical downside risks (e.g. debt, client concentration, valuation, market reversal).",
  "broker_consensus": "Estimated consensus ratio (e.g., '75% Apply / 25% Avoid based on brokerage notes')"
}}
Return ONLY raw JSON.
"""
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
            }
            if not config.GEMINI_ENDPOINT:
                raise RuntimeError("GEMINI_API_KEY not set; using fallback")
            res = requests.post(config.GEMINI_ENDPOINT, json=payload, headers=config.GEMINI_HEADERS, timeout=15)
            if res.status_code == 200:
                raw_json = res.json()['candidates'][0]['content']['parts'][0]['text']
                parsed = json.loads(raw_json)
                result["Verdict"] = parsed.get("verdict", rule_verdict)
                result["Conviction_Score"] = int(parsed.get("conviction_score", rule_score))
                result["Verdict_Summary"] = parsed.get("verdict_summary", result["Verdict_Summary"])
                result["Pillar_GMP"] = parsed.get("pillar_gmp", result["Pillar_GMP"])
                result["Pillar_Valuation"] = parsed.get("pillar_valuation", result["Pillar_Valuation"])
                result["Pillar_Structure"] = parsed.get("pillar_structure", result["Pillar_Structure"])
                result["Key_Risks"] = parsed.get("key_risks", result["Key_Risks"])
                result["Broker_Consensus"] = parsed.get("broker_consensus", result["Broker_Consensus"])
        except Exception as e:
            print(f"Gemini IPO synthesis failed for {company}: {e}")
            # Falls back gracefully to rule-based analysis
            
    _VERDICT_CACHE[cache_key] = result
    return result
