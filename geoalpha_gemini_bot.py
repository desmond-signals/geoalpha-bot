"""
╔══════════════════════════════════════════════════════════════╗
║     GEOALPHA · KASPAROV BOT — Version 4.0 CONSEIL DE GUERRE ║
║  RSS News + 3 Agents IA + Alertes mondiales temps réel       ║
╚══════════════════════════════════════════════════════════════╝
"""

import requests
import schedule
import time
import json
import os
import yfinance as yf
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


# ══════════════════════════════════════════════════════════════
# 🔑  CONFIGURATION
# ══════════════════════════════════════════════════════════════

TELEGRAM_TOKEN   = "8954725433:AAF_WORnnP1Xeo2rRiACneHN0mGxsG_oIc0"
TELEGRAM_CHAT_ID = "976026689"
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL       = "llama-3.3-70b-versatile"

# ══════════════════════════════════════════════════════════════
# ⚙️  PARAMÈTRES
# ══════════════════════════════════════════════════════════════

WATCHLIST = {
    "NVDA":    "NVIDIA · AI Chips",
    "TSLA":    "Tesla · EV/Robotics",
    "META":    "Meta · Social AI",
    "MSFT":    "Microsoft · Cloud AI",
    "AMZN":    "Amazon · Cloud",
    "AMD":     "AMD · Semis",
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "GLD":     "Gold ETF",
    "UCO":     "Pétrole x2 ETF",
    "LMT":     "Lockheed · Défense",
    "LLY":     "Eli Lilly · Biotech",
}

# Sources RSS d'actualités mondiales — gratuites
RSS_SOURCES = [
    {"name": "Reuters Business",    "url": "https://feeds.reuters.com/reuters/businessNews"},
    {"name": "Reuters World",       "url": "https://feeds.reuters.com/Reuters/worldNews"},
    {"name": "CNBC Markets",        "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
    {"name": "MarketWatch",         "url": "https://feeds.marketwatch.com/marketwatch/topstories"},
    {"name": "BBC Business",        "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"name": "Financial Times",     "url": "https://www.ft.com/rss/home"},
    {"name": "Bloomberg Markets",   "url": "https://feeds.bloomberg.com/markets/news.rss"},
    {"name": "Investing.com",       "url": "https://www.investing.com/rss/news.rss"},
]

# Mots-clés qui déclenchent une alerte immédiate
ALERT_KEYWORDS = [
    # Politique & Géopolitique
    "trump", "war", "guerre", "conflict", "sanction", "attack", "attaque",
    "missile", "nuclear", "nucléaire", "coup", "crisis", "crise", "invasion",
    "election", "élection", "assassination", "attentat", "terror",
    # Finance & Économie
    "crash", "collapse", "effondrement", "bankruptcy", "faillite", "default",
    "recession", "récession", "fed", "rate", "taux", "inflation", "powell",
    "lagarde", "ecb", "bce", "emergency", "urgence", "bailout",
    # Marchés
    "surge", "plunge", "rally", "selloff", "circuit breaker", "halt",
    "ipo", "acquisition", "merger", "scandal", "fraud", "fraude",
    # Tech & IA
    "openai", "nvidia", "apple", "microsoft", "google", "amazon", "meta",
    "ai", "artificial intelligence", "chip", "semiconductor", "ban", "interdiction",
    # Énergie & Matières premières
    "oil", "pétrole", "opec", "gold", "or", "bitcoin", "crypto",
    "supply chain", "shortage", "pénurie", "pipeline", "energy",
    # Catastrophes
    "earthquake", "hurricane", "pandemic", "outbreak", "disaster",
]

ALERT_THRESHOLD_PCT = 2.5
PRICE_SCAN_INTERVAL = 15
NEWS_SCAN_INTERVAL  = 10  # Scan news toutes les 10 minutes
_last_prices        = {}
_last_update_id     = 0
_seen_news          = set()  # Éviter d'envoyer la même news 2 fois


# ══════════════════════════════════════════════════════════════
# 📱  TELEGRAM
# ══════════════════════════════════════════════════════════════

def send(text, chat_id=None):
    cid = chat_id or TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        # Telegram limite à 4096 caractères
        if len(text) > 4000:
            text = text[:4000] + "\n...(suite)"
        r = requests.post(url, json={
            "chat_id": cid,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")
        return False


def get_updates():
    global _last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={
            "offset": _last_update_id + 1, "timeout": 5
        }, timeout=10)
        if r.status_code == 200:
            return r.json().get("result", [])
    except:
        pass
    return []


# ══════════════════════════════════════════════════════════════
# 📰  SCANNER RSS — Actualités mondiales
# ══════════════════════════════════════════════════════════════

def fetch_rss(source):
    """Récupère les dernières news d'une source RSS."""
    try:
        r = requests.get(source["url"], timeout=8,
            headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return []

        root = ET.fromstring(r.content)
        items = []

        # Chercher les items dans le flux RSS
        for item in root.iter("item"):
            title = item.find("title")
            desc  = item.find("description")
            link  = item.find("link")
            pub   = item.find("pubDate")

            if title is not None and title.text:
                items.append({
                    "source": source["name"],
                    "title":  title.text.strip(),
                    "desc":   desc.text.strip()[:200] if desc is not None and desc.text else "",
                    "link":   link.text.strip() if link is not None and link.text else "",
                    "time":   pub.text.strip() if pub is not None and pub.text else "",
                })

        return items[:5]  # Max 5 items par source
    except Exception as e:
        print(f"  [RSS ERROR] {source['name']}: {e}")
        return []


def scan_news():
    """Scanne toutes les sources RSS et retourne les news importantes."""
    print(f"[{datetime.now().strftime('%H:%M')}] 📰 Scan news...")
    all_news = []

    for source in RSS_SOURCES:
        items = fetch_rss(source)
        all_news.extend(items)
        time.sleep(0.5)

    # Filtrer les news importantes avec les mots-clés
    important = []
    for news in all_news:
        text_lower = (news["title"] + " " + news["desc"]).lower()
        matches = [kw for kw in ALERT_KEYWORDS if kw in text_lower]

        if matches and news["title"] not in _seen_news:
            news["keywords"] = matches
            news["score"]    = len(matches)  # Plus de mots-clés = plus important
            important.append(news)
            _seen_news.add(news["title"])

    # Trier par score d'importance
    important.sort(key=lambda x: x["score"], reverse=True)
    print(f"  → {len(important)} news importantes détectées")
    return important[:3]  # Max 3 news les plus importantes


# ══════════════════════════════════════════════════════════════
# 📊  MARCHÉ — Prix Yahoo Finance
# ══════════════════════════════════════════════════════════════

def get_price(ticker):
    try:
        hist = yf.Ticker(ticker).history(period="2d", interval="1h")
        if hist.empty or len(hist) < 2:
            return None, None
        current = float(hist["Close"].iloc[-1])
        prev    = float(hist["Close"].iloc[-2])
        change  = ((current - prev) / prev) * 100
        return current, change
    except:
        return None, None


def get_market_snapshot():
    data, pulse_lines = [], []
    for ticker, name in WATCHLIST.items():
        price, change = get_price(ticker)
        if price and change is not None:
            data.append({
                "ticker": ticker, "name": name,
                "price": round(price, 2),
                "change_pct": round(change, 2),
            })
            arrow = "▲" if change >= 0 else "▼"
            sign  = "+" if change >= 0 else ""
            pulse_lines.append(
                f"  {arrow} <b>{ticker}</b>  {sign}{change:.2f}%  ({price:.2f})"
            )
        time.sleep(0.3)
    return data, "\n".join(pulse_lines)


def scan_price_alerts():
    global _last_prices
    alerts = []
    hour = datetime.now().hour
    if not (8 <= hour <= 22):
        return alerts
    for ticker, name in WATCHLIST.items():
        price, change = get_price(ticker)
        if price is None:
            continue
        if _last_prices.get(ticker) and abs(change) >= ALERT_THRESHOLD_PCT:
            alerts.append({
                "ticker": ticker, "name": name,
                "price": price, "change": change,
            })
        _last_prices[ticker] = price
        time.sleep(0.2)
    return alerts


# ══════════════════════════════════════════════════════════════
# 🧠  GROQ IA — Appel de base
# ══════════════════════════════════════════════════════════════

def call_groq(system_prompt, user_prompt):
    """Appel Groq avec parsing JSON robuste."""
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 800,
            },
            timeout=30,
        )
        data  = r.json()
        text  = data["choices"][0]["message"]["content"]
        clean = text.replace("```json", "").replace("```", "").strip()
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(clean[start:end])
    except Exception as e:
        print(f"[GROQ ERROR] {e}")
        return None


# ══════════════════════════════════════════════════════════════
# ⚔️  CONSEIL DE GUERRE — 3 Agents IA
# ══════════════════════════════════════════════════════════════

def agent_technique(market_data, context):
    """Agent 1 : Analyse technique des prix."""
    return call_groq(
        "Tu es un analyste technique expert. Tu analyses UNIQUEMENT les prix, volumes et indicateurs techniques. Tu réponds en JSON uniquement.",
        f"""Contexte: {context}

Données de marché: {json.dumps(market_data, indent=2)}

Analyse technique et donne ta recommandation:
{{
  "agent": "TECHNIQUE",
  "ticker": "TICKER le plus pertinent",
  "action": "LONG ou SHORT",
  "raison": "Raison technique en 1 phrase",
  "conviction": 0-100,
  "entree": "Prix",
  "stop_loss": "-X%",
  "target": "+X%"
}}"""
    )


def agent_geopolitique(news_context, context):
    """Agent 2 : Analyse géopolitique et fondamentale."""
    return call_groq(
        "Tu es un expert en géopolitique et analyse fondamentale des marchés. Tu analyses les événements mondiaux et leur impact sur les marchés. Tu réponds en JSON uniquement.",
        f"""Contexte événement: {context}
Actualités récentes: {news_context}

Analyse géopolitique et donne ta recommandation:
{{
  "agent": "GÉOPOLITIQUE",
  "ticker": "TICKER le plus impacté",
  "action": "LONG ou SHORT",
  "raison": "Raison géopolitique en 1 phrase",
  "conviction": 0-100,
  "secteurs_impactes": ["secteur1", "secteur2"],
  "horizon": "intraday ou 1-3j ou 1sem"
}}"""
    )


def agent_risque(tech_analysis, geo_analysis, market_data):
    """Agent 3 : Analyse du risque et arbitrage final."""
    return call_groq(
        "Tu es un gestionnaire de risque expert. Tu évalues les recommandations des autres agents et détermines si le trade est viable. Tu réponds en JSON uniquement.",
        f"""Analyse technique: {json.dumps(tech_analysis)}
Analyse géopolitique: {json.dumps(geo_analysis)}
Données marché: {json.dumps(market_data[:3])}

Évalue le risque et donne ton verdict:
{{
  "agent": "RISQUE",
  "verdict": "APPROUVÉ ou REJETÉ ou ATTENDRE",
  "ticker": "TICKER final recommandé",
  "action": "LONG ou SHORT",
  "taille_position": "X% du capital",
  "stop_loss": "-X%",
  "target": "+X%",
  "raison_risque": "Justification en 1 phrase",
  "conviction_finale": 0-100
}}"""
    )


def conseil_de_guerre(market_data, context, news_context="Pas de news spécifique"):
    """
    Lance le conseil de guerre avec 3 agents IA.
    Retourne le signal final seulement si consensus.
    """
    print(f"  ⚔️ Conseil de guerre en cours...")

    # Agent 1 — Technique
    print(f"    🔬 Agent Technique analyse...")
    tech = agent_technique(market_data, context)
    time.sleep(1)

    # Agent 2 — Géopolitique
    print(f"    🌍 Agent Géopolitique analyse...")
    geo = agent_geopolitique(news_context, context)
    time.sleep(1)

    # Agent 3 — Risque (arbitre final)
    print(f"    ⚖️ Agent Risque tranche...")
    risque = agent_risque(tech, geo, market_data)
    time.sleep(1)

    return tech, geo, risque


def fmt_conseil_de_guerre(tech, geo, risque, context):
    """Formate le message du conseil de guerre."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Déterminer le consensus
    actions = []
    if tech   and tech.get("action"):   actions.append(tech["action"])
    if geo    and geo.get("action"):    actions.append(geo["action"])
    if risque and risque.get("action"): actions.append(risque["action"])

    consensus = max(set(actions), key=actions.count) if actions else "HOLD"
    votes_pour = actions.count(consensus)
    verdict    = risque.get("verdict", "ATTENDRE") if risque else "ATTENDRE"

    icon_verdict = "✅" if verdict == "APPROUVÉ" else "⏳" if verdict == "ATTENDRE" else "❌"
    icon_action  = "🟢" if consensus == "LONG" else "🔴"

    msg = (
        f"🚨 <b>ALERTE KASPAROV — ÉVÉNEMENT MAJEUR</b>\n"
        f"📅 {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📌 <b>ÉVÉNEMENT DÉTECTÉ</b>\n"
        f"{context}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚔️ <b>CONSEIL DE GUERRE</b>\n\n"
    )

    if tech:
        t_icon = "✅" if tech.get("action") == consensus else "⚠️"
        msg += (
            f"🔬 <b>Agent Technique</b> {t_icon}\n"
            f"   → {tech.get('action','?')} {tech.get('ticker','?')}\n"
            f"   {tech.get('raison','—')}\n"
            f"   Conviction: {tech.get('conviction','?')}%\n\n"
        )

    if geo:
        g_icon = "✅" if geo.get("action") == consensus else "⚠️"
        msg += (
            f"🌍 <b>Agent Géopolitique</b> {g_icon}\n"
            f"   → {geo.get('action','?')} {geo.get('ticker','?')}\n"
            f"   {geo.get('raison','—')}\n"
            f"   Conviction: {geo.get('conviction','?')}%\n\n"
        )

    if risque:
        msg += (
            f"⚖️ <b>Agent Risque</b> {icon_verdict}\n"
            f"   → Verdict: <b>{verdict}</b>\n"
            f"   {risque.get('raison_risque','—')}\n\n"
        )

    msg += (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🗳️ <b>VOTE : {votes_pour}/3 agents → {consensus}</b>\n\n"
    )

    if verdict == "APPROUVÉ" and risque:
        conv  = risque.get("conviction_finale", 0)
        bars  = "█" * (conv // 10) + "░" * (10 - conv // 10)
        ticker = risque.get("ticker", "?")
        msg += (
            f"{icon_action} <b>SIGNAL FINAL : {consensus} {ticker}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Entrée    : {risque.get('entree', tech.get('entree','—') if tech else '—')}\n"
            f"🛑 Stop-loss : {risque.get('stop_loss','—')}\n"
            f"🚀 Target    : {risque.get('target','—')}\n"
            f"💰 Position  : {risque.get('taille_position','—')}\n"
            f"🧠 Conviction: {bars} {conv}%\n"
        )
    elif verdict == "ATTENDRE":
        msg += f"⏳ <b>SIGNAL : ATTENDRE</b> — Pas assez de confluence\n"
    else:
        msg += f"❌ <b>SIGNAL REJETÉ</b> — Risque trop élevé\n"

    msg += f"\n<i>⚠️ Analyse uniquement — Pas de conseil financier</i>"
    return msg


# ══════════════════════════════════════════════════════════════
# 🔔  SCAN NEWS AUTOMATIQUE
# ══════════════════════════════════════════════════════════════

def news_scan():
    """Scanne les news et déclenche le conseil de guerre si nécessaire."""
    important_news = scan_news()

    if not important_news:
        return

    # Prendre la news la plus importante
    top_news = important_news[0]
    context  = f"{top_news['source']}: {top_news['title']}"
    news_ctx = "\n".join([f"- {n['title']}" for n in important_news])

    print(f"  🚨 News importante: {top_news['title'][:60]}...")
    send(f"📰 <b>NEWS DÉTECTÉE — Analyse en cours...</b>\n\n{context}\n\n⚔️ Conseil de guerre lancé...")

    # Récupérer les prix
    market_data, _ = get_market_snapshot()

    # Lancer le conseil de guerre
    tech, geo, risque = conseil_de_guerre(market_data, context, news_ctx)

    # Envoyer le résultat
    msg = fmt_conseil_de_guerre(tech, geo, risque, context)
    send(msg)


# ══════════════════════════════════════════════════════════════
# 📊  SCAN PRIX AUTOMATIQUE
# ══════════════════════════════════════════════════════════════

def price_scan():
    """Scanne les prix et déclenche le conseil de guerre si mouvement anormal."""
    print(f"[{datetime.now().strftime('%H:%M')}] 📡 Scan prix...")
    alerts = scan_price_alerts()

    for alert in alerts:
        ticker   = alert["ticker"]
        name     = alert["name"]
        price    = alert["price"]
        change   = alert["change"]
        direction = "hausse" if change > 0 else "baisse"

        print(f"  🚨 Mouvement: {ticker} {change:+.2f}%")
        context = f"{ticker} ({name}) — {direction} brutale de {change:+.2f}% à {price:.2f}$"
        send(f"⚡ <b>MOUVEMENT DÉTECTÉ — {ticker}</b>\n{change:+.2f}% à {price:.2f}$\n\n⚔️ Conseil de guerre lancé...")

        market_data, _ = get_market_snapshot()
        tech, geo, risque = conseil_de_guerre(market_data, context)
        msg = fmt_conseil_de_guerre(tech, geo, risque, context)
        send(msg)
        time.sleep(3)


# ══════════════════════════════════════════════════════════════
# ⏰  SESSIONS PLANIFIÉES
# ══════════════════════════════════════════════════════════════

def session_scan(label):
    """Session planifiée avec conseil de guerre complet."""
    print(f"\n[{datetime.now().strftime('%H:%M')}] 🔄 Session {label}")
    send(f"⏳ <b>GEOALPHA</b> — Session <b>{label}</b>\nConseil de guerre en cours...")

    market_data, _ = get_market_snapshot()
    important_news = scan_news()
    news_ctx = "\n".join([f"- {n['title']}" for n in important_news]) if important_news else "Pas de news majeure"
    context  = f"Session de trading {label} — {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    tech, geo, risque = conseil_de_guerre(market_data, context, news_ctx)
    msg = fmt_conseil_de_guerre(tech, geo, risque, context)
    send(msg)
    print(f"✅ Session {label} envoyée")


def morning_session():   session_scan("OUVERTURE EUROPE 09H00")
def afternoon_session(): session_scan("PRÉ-OUVERTURE NY 15H25")
def evening_session():   session_scan("BILAN SOIR 22H00")


# ══════════════════════════════════════════════════════════════
# 💬  COMMANDES TELEGRAM
# ══════════════════════════════════════════════════════════════

def handle_commands():
    global _last_update_id
    updates = get_updates()
    for update in updates:
        _last_update_id = update["update_id"]
        msg     = update.get("message", {})
        text    = msg.get("text", "").strip().lower()
        chat_id = str(msg.get("chat", {}).get("id", TELEGRAM_CHAT_ID))
        if not text:
            continue
        print(f"[CMD] {text}")

        if text in ("/signal", "/signaux", "/trade", "/guerre"):
            send("⚔️ Conseil de guerre en cours... (30-45 secondes)", chat_id)
            market_data, _ = get_market_snapshot()
            important_news = scan_news()
            news_ctx = "\n".join([f"- {n['title']}" for n in important_news]) if important_news else "Pas de news majeure"
            context  = f"Signal on demand — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            tech, geo, risque = conseil_de_guerre(market_data, context, news_ctx)
            msg_out = fmt_conseil_de_guerre(tech, geo, risque, context)
            send(msg_out, chat_id)

        elif text in ("/news", "/actualites"):
            send("📰 Scan des actualités mondiales...", chat_id)
            important_news = scan_news()
            if important_news:
                msg_out = "📰 <b>ACTUALITÉS IMPORTANTES</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                for i, n in enumerate(important_news[:5], 1):
                    msg_out += f"{i}. <b>{n['source']}</b>\n{n['title']}\n\n"
                send(msg_out, chat_id)
            else:
                send("Aucune actualité majeure détectée pour le moment.", chat_id)

        elif text in ("/pulse", "/market", "/prix"):
            send("📡 Collecte des prix...", chat_id)
            _, pulse = get_market_snapshot()
            now = datetime.now().strftime("%H:%M")
            send(
                f"📊 <b>MARKET PULSE — {now}</b>\n"
                f"━━━━━━━━━━━━━━━━━\n{pulse}\n━━━━━━━━━━━━━━━━━",
                chat_id
            )

        elif text in ("/status", "/info"):
            now = datetime.now().strftime("%d/%m/%Y %H:%M")
            send(
                f"🤖 <b>GEOALPHA KASPAROV v4.0 — STATUS</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Bot actif · {now}\n"
                f"🧠 IA : Groq LLaMA 3.3 70B\n"
                f"📊 Tickers surveillés : {len(WATCHLIST)}\n"
                f"📰 Sources news : {len(RSS_SOURCES)}\n"
                f"🔔 Seuil prix : ±{ALERT_THRESHOLD_PCT}%\n"
                f"⏱ Scan news : toutes les {NEWS_SCAN_INTERVAL} min\n\n"
                f"⚔️ Conseil de guerre : 3 agents IA\n\n"
                f"💬 /signal · /news · /pulse · /status",
                chat_id
            )

        elif text in ("/start", "/help", "/aide"):
            send(
                f"🤖 <b>GEOALPHA KASPAROV BOT v4.0</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"IA de trading géopolitique · 3 agents IA\n\n"
                f"<b>COMMANDES :</b>\n"
                f"• /signal → Conseil de guerre + signal\n"
                f"• /news   → Actualités mondiales live\n"
                f"• /pulse  → Prix marché en temps réel\n"
                f"• /status → État du bot\n\n"
                f"<b>AUTOMATIQUE :</b>\n"
                f"• 📰 Scan news toutes les {NEWS_SCAN_INTERVAL} min\n"
                f"• ⚡ Alerte si mouvement prix > ±{ALERT_THRESHOLD_PCT}%\n"
                f"• 📅 Signaux planifiés : 09h · 15h25 · 22h",
                chat_id
            )


# ══════════════════════════════════════════════════════════════
# 🚀  DÉMARRAGE
# ══════════════════════════════════════════════════════════════

def main():
    print("🤖 GEOALPHA KASPAROV BOT v4.0 — Conseil de Guerre Edition")

    send(
        "🚀 <b>GEOALPHA KASPAROV BOT v4.0 — ACTIF</b>\n\n"
        "⚔️ Système <b>Conseil de Guerre</b> activé\n"
        "3 agents IA analysent chaque événement ensemble\n\n"
        "📰 <b>Surveillance mondiale active :</b>\n"
        f"• {len(RSS_SOURCES)} sources d'actualités mondiales\n"
        f"• {len(WATCHLIST)} marchés surveillés\n"
        f"• Scan toutes les {NEWS_SCAN_INTERVAL} minutes\n\n"
        "🔔 <b>Alertes automatiques pour :</b>\n"
        "• Événements géopolitiques majeurs\n"
        "• Mouvements de marchés anormaux\n"
        "• Actualités financières critiques\n\n"
        "📅 Signaux planifiés : 09h · 15h25 · 22h\n\n"
        "💬 /signal · /news · /pulse · /status\n\n"
        "<i>Le conseil de guerre veille sur vos investissements 24h/24 📈</i>"
    )

    # Planification
    schedule.every().day.at("09:00").do(morning_session)
    schedule.every().day.at("15:25").do(afternoon_session)
    schedule.every().day.at("22:00").do(evening_session)
    schedule.every(NEWS_SCAN_INTERVAL).minutes.do(news_scan)
    schedule.every(PRICE_SCAN_INTERVAL).minutes.do(price_scan)
    schedule.every(3).seconds.do(handle_commands)

    # Initialisation
    print("📡 Initialisation des prix...")
    scan_price_alerts()
    print("✅ Prix initialisés")
    print("📰 Premier scan news...")
    news_scan()
    print("✅ Bot opérationnel — surveillance mondiale active\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Bot arrêté")
        send("🛑 <b>GEOALPHA</b> — Bot mis en veille.")


if __name__ == "__main__":
    main()
