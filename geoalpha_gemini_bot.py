"""
╔══════════════════════════════════════════════════════════════╗
║        GEOALPHA · KASPAROV BOT — Version Gemini              ║
║  Yahoo Finance + Gemini IA → Telegram push instantané        ║
╚══════════════════════════════════════════════════════════════╝

INSTALLATION :
    pip install google-generativeai requests schedule yfinance

DÉMARRAGE :
    python geoalpha_gemini_bot.py
"""

import requests
import schedule
import time
import json
import yfinance as yf
from datetime import datetime
import google.generativeai as genai


# ══════════════════════════════════════════════════════════════
# 🔑  CONFIGURATION
# ══════════════════════════════════════════════════════════════

TELEGRAM_TOKEN   = "8954725433:AAF_WORnnP1Xeo2rRiACneHN0mGxsG_oIc0"
TELEGRAM_CHAT_ID = "976026689"
GEMINI_API_KEY   = "AIzaSyAx-BUJm14KFqVOg24j4PB6fY33lNE8WTA"

# Configuration Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash-latest")


# ══════════════════════════════════════════════════════════════
# ⚙️  PARAMÈTRES DU BOT
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

ALERT_THRESHOLD_PCT = 2.5   # Alerte si mouvement > 2.5%
PRICE_SCAN_INTERVAL = 15    # Scan toutes les 15 min
_last_prices        = {}
_last_update_id     = 0


# ══════════════════════════════════════════════════════════════
# 📱  TELEGRAM
# ══════════════════════════════════════════════════════════════

def send(text, chat_id=None):
    cid = chat_id or TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": cid, "text": text,
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
    """Récupère tous les prix et retourne un résumé pour l'IA."""
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


def scan_alerts():
    """Détecte les mouvements anormaux."""
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
# 🧠  GEMINI IA — Génération des signaux
# ══════════════════════════════════════════════════════════════

def call_gemini(prompt):
    """Appel Gemini avec parsing JSON robuste."""
    try:
        response = model.generate_content(prompt)
        text  = response.text
        clean = text.replace("```json", "").replace("```", "").strip()
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(clean[start:end])
    except json.JSONDecodeError as e:
        print(f"[JSON ERROR] {e}")
        return None
    except Exception as e:
        print(f"[GEMINI ERROR] {e}")
        return None


def generate_signals(market_data, session_label):
    """Génère 3 signaux basés sur les prix réels + contexte géopolitique."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    prompt = f"""Tu es GeoAlpha Kasparov, le meilleur système d'analyse financière et géopolitique au monde.
Date et heure : {now}
Session : {session_label}

Voici les données de marché en temps réel :
{json.dumps(market_data, indent=2)}

En te basant sur ces prix réels ET sur ton analyse géopolitique actuelle (actualité mondiale, banques centrales, tensions géopolitiques, flux institutionnels), génère exactement 3 signaux de trading chirurgicaux.

Réponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant ou après :
{{
  "context": "Contexte marché + géopolitique en 1 phrase percutante",
  "polymarket": "Probabilité géopolitique ou événement macro clé du moment",
  "signals": [
    {{
      "ticker": "TICKER",
      "name": "Nom complet",
      "action": "LONG ou SHORT",
      "montant_eur": "35€ ou 30% du capital",
      "levier": "x1",
      "entree": "Prix ou condition précise",
      "stop_loss": "-X% ou prix stop",
      "target": "+X%",
      "horizon": "1-3j ou 1sem",
      "raison": "Raison géopolitique ou technique précise en 1 phrase",
      "conviction": 85
    }},
    {{
      "ticker": "TICKER",
      "name": "Nom complet",
      "action": "LONG ou SHORT",
      "montant_eur": "30€",
      "levier": "x1",
      "entree": "Prix ou condition",
      "stop_loss": "-X%",
      "target": "+X%",
      "horizon": "1-3j",
      "raison": "Raison courte",
      "conviction": 78
    }},
    {{
      "ticker": "TICKER",
      "name": "Nom complet",
      "action": "LONG ou SHORT",
      "montant_eur": "25€",
      "levier": "x1",
      "entree": "Prix ou condition",
      "stop_loss": "-X%",
      "target": "+X%",
      "horizon": "1sem",
      "raison": "Raison courte",
      "conviction": 72
    }}
  ],
  "alerte": "Risque principal à surveiller maintenant",
  "cash_reserve": "Garder X€ en cash"
}}"""

    return call_gemini(prompt)


def analyze_movement(ticker, name, price, change):
    """Analyse rapide d'un mouvement anormal."""
    direction = "hausse" if change > 0 else "baisse"
    prompt = f"""Tu es GeoAlpha Kasparov. {ticker} ({name}) vient de faire une {direction} de {abs(change):.1f}% à {price:.2f}$.

Analyse ce mouvement et génère un signal d'investissement immédiat.

Réponds UNIQUEMENT en JSON valide :
{{
  "catalyseur": "Raison probable de ce mouvement",
  "action": "LONG ou SHORT ou HOLD",
  "conviction": 80,
  "entree": "Prix optimal d'entrée",
  "stop_loss": "-X%",
  "target": "+X%",
  "horizon": "intraday ou 1-3j",
  "raison": "Thèse d'investissement en 1 phrase"
}}"""

    return call_gemini(prompt)


# ══════════════════════════════════════════════════════════════
# 📨  FORMATAGE DES MESSAGES
# ══════════════════════════════════════════════════════════════

def fmt_signals(data, session):
    medals = ["🥇", "🥈", "🥉"]
    now    = datetime.now().strftime("%H:%M")

    msg = (
        f"🤖 <b>GEOALPHA · KASPAROV — {session}</b>\n"
        f"📅 {datetime.now().strftime('%d/%m/%Y')} à {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌍 <b>CONTEXTE</b>\n{data.get('context','—')}\n\n"
        f"📊 <b>POLYMARKET</b>\n{data.get('polymarket','—')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>VOS 3 ORDRES KASPAROV</b>\n"
    )

    for i, s in enumerate(data.get("signals", [])[:3]):
        action = s.get("action", "")
        icon   = "🟢" if action == "LONG" else "🔴"
        conv   = s.get("conviction", 0)
        bars   = "█" * (conv // 10) + "░" * (10 - conv // 10)

        msg += (
            f"\n{medals[i]} {icon} <b>{action} {s.get('ticker','')} "
            f"— {s.get('name','')}</b>\n"
            f"💰 Montant   : <b>{s.get('montant_eur','')}</b>\n"
            f"⚡ Levier    : {s.get('levier','x1')}\n"
            f"🎯 Entrée    : {s.get('entree','—')}\n"
            f"🛑 Stop-loss : {s.get('stop_loss','—')} ← PLACER EN MÊME TEMPS\n"
            f"🚀 Target    : {s.get('target','—')}\n"
            f"⏱ Horizon   : {s.get('horizon','—')}\n"
            f"📝 {s.get('raison','')}\n"
            f"🧠 Conviction: {bars} {conv}%\n"
        )

    msg += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 <b>CASH À GARDER</b> : {data.get('cash_reserve','10€')}\n"
        f"⚠️ <b>ALERTE</b> : {data.get('alerte','—')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>⚠️ Analyse uniquement — Pas de conseil financier</i>\n\n"
        f"💬 /signal  /pulse  /status"
    )
    return msg


def fmt_alert(ticker, name, price, change, ai):
    icon   = "🚀" if change > 0 else "💥"
    action = ai.get("action", "HOLD") if ai else "HOLD"
    color  = "🟢" if action == "LONG" else "🔴" if action == "SHORT" else "⚪"

    msg = (
        f"{icon} <b>ALERTE MOUVEMENT — {ticker}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 {name}\n"
        f"💲 Prix     : <b>{price:.2f}</b>\n"
        f"📈 Variation: <b>{'+' if change>0 else ''}{change:.2f}%</b>\n\n"
    )

    if ai:
        conv = ai.get("conviction", 0)
        bars = "█" * (conv // 10) + "░" * (10 - conv // 10)
        msg += (
            f"🧠 <b>ANALYSE IA KASPAROV</b>\n"
            f"📌 Catalyseur : {ai.get('catalyseur','—')}\n\n"
            f"{color} <b>SIGNAL : {action}</b>\n"
            f"🎯 Entrée    : {ai.get('entree','—')}\n"
            f"🛑 Stop-loss : {ai.get('stop_loss','—')}\n"
            f"🚀 Target    : {ai.get('target','—')}\n"
            f"⏱ Horizon   : {ai.get('horizon','—')}\n"
            f"📝 {ai.get('raison','')}\n"
            f"🧠 Conviction: {bars} {conv}%\n"
        )

    msg += f"\n<i>⚠️ Information uniquement — DYOR</i>"
    return msg


# ══════════════════════════════════════════════════════════════
# ⏰  SESSIONS PLANIFIÉES
# ══════════════════════════════════════════════════════════════

def session_scan(label):
    print(f"\n[{datetime.now().strftime('%H:%M')}] 🔄 Session {label}...")
    send(f"⏳ <b>GEOALPHA</b> — Session <b>{label}</b> en cours...\n📡 Collecte des prix + analyse IA Kasparov")

    market_data, _ = get_market_snapshot()
    data = generate_signals(market_data, label)

    if data:
        send(fmt_signals(data, label))
        print(f"[{datetime.now().strftime('%H:%M')}] ✅ Signaux envoyés")
    else:
        send(f"⚠️ Erreur analyse {label} — vérifiez la clé Gemini")


def morning_session():   session_scan("OUVERTURE EUROPE 09H00")
def afternoon_session(): session_scan("PRÉ-OUVERTURE NY 15H25")
def evening_session():   session_scan("BILAN SOIR 22H00")


# ══════════════════════════════════════════════════════════════
# 🔔  SCAN TEMPS RÉEL
# ══════════════════════════════════════════════════════════════

def realtime_scan():
    print(f"[{datetime.now().strftime('%H:%M')}] 📡 Scan prix...")
    alerts = scan_alerts()
    for alert in alerts:
        print(f"  🚨 {alert['ticker']}: {alert['change']:+.2f}%")
        ai  = analyze_movement(alert["ticker"], alert["name"],
                               alert["price"], alert["change"])
        msg = fmt_alert(alert["ticker"], alert["name"],
                        alert["price"], alert["change"], ai)
        send(msg)
        time.sleep(2)


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

        if text in ("/signal", "/signaux", "/trade"):
            send("⏳ Génération des signaux... (20-30 secondes)", chat_id)
            market_data, _ = get_market_snapshot()
            data = generate_signals(market_data, "ON DEMAND")
            if data:
                send(fmt_signals(data, "📡 SIGNAL ON DEMAND"), chat_id)
            else:
                send("❌ Erreur IA — réessayez dans quelques instants", chat_id)

        elif text in ("/pulse", "/market", "/prix"):
            send("📡 Collecte des prix en cours...", chat_id)
            _, pulse = get_market_snapshot()
            now = datetime.now().strftime("%H:%M")
            send(
                f"📊 <b>MARKET PULSE — {now}</b>\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"{pulse}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"<i>Scan toutes les {PRICE_SCAN_INTERVAL} min</i>",
                chat_id
            )

        elif text in ("/status", "/info"):
            now = datetime.now().strftime("%d/%m/%Y %H:%M")
            send(
                f"🤖 <b>GEOALPHA KASPAROV — STATUS</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Bot actif\n"
                f"🕐 Heure : {now}\n"
                f"📊 Tickers : {len(WATCHLIST)}\n"
                f"🔔 Seuil alerte : ±{ALERT_THRESHOLD_PCT}%\n"
                f"⏱ Scan : toutes les {PRICE_SCAN_INTERVAL} min\n"
                f"🧠 IA : Gemini 1.5 Flash (gratuit)\n\n"
                f"📅 Signaux automatiques :\n"
                f"  🌅 09h00 — Europe\n"
                f"  🌆 15h25 — NY\n"
                f"  🌙 22h00 — Bilan\n\n"
                f"💬 /signal  /pulse  /status",
                chat_id
            )

        elif text in ("/start", "/help", "/aide"):
            send(
                f"🤖 <b>GEOALPHA KASPAROV BOT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"IA de trading géopolitique · Gemini powered\n\n"
                f"<b>COMMANDES :</b>\n"
                f"• /signal → 3 signaux maintenant\n"
                f"• /pulse  → Prix marché live\n"
                f"• /status → État du bot\n\n"
                f"<b>AUTOMATIQUE :</b>\n"
                f"• Alertes si mouvement > ±{ALERT_THRESHOLD_PCT}%\n"
                f"• Signaux planifiés 3x/jour",
                chat_id
            )


# ══════════════════════════════════════════════════════════════
# 🚀  DÉMARRAGE
# ══════════════════════════════════════════════════════════════

def main():
    print("""
╔══════════════════════════════════════════════════════╗
║    🤖 GEOALPHA KASPAROV BOT — Gemini Edition        ║
╚══════════════════════════════════════════════════════╝
    """)
    print(f"✅ Gemini API configurée")
    print(f"✅ Telegram configuré → Chat: {TELEGRAM_CHAT_ID}")
    print(f"✅ Watchlist : {len(WATCHLIST)} tickers")
    print(f"✅ Seuil alerte : ±{ALERT_THRESHOLD_PCT}%")

    # Message de bienvenue Telegram
    send(
        "🚀 <b>GEOALPHA KASPAROV BOT — ACTIF</b>\n\n"
        "Votre IA de trading est opérationnelle.\n"
        "Propulsé par <b>Gemini 1.5 Flash</b> (100% gratuit)\n\n"
        "📅 <b>Signaux automatiques :</b>\n"
        "• 🌅 09h00 — Ouverture Europe\n"
        "• 🌆 15h25 — Pré-ouverture Wall Street\n"
        "• 🌙 22h00 — Bilan soir\n\n"
        f"🔔 Alertes instantanées si mouvement > ±{ALERT_THRESHOLD_PCT}%\n\n"
        "💬 <b>Commandes :</b>\n"
        "• /signal → Signaux maintenant\n"
        "• /pulse  → Prix live\n"
        "• /status → État du bot\n\n"
        "<i>Bonne chasse aux alphas ! 📈</i>"
    )

    print("\n✅ Message de bienvenue envoyé sur Telegram")

    # Planification sessions
    schedule.every().day.at("09:00").do(morning_session)
    schedule.every().day.at("15:25").do(afternoon_session)
    schedule.every().day.at("22:00").do(evening_session)

    # Scan prix temps réel
    schedule.every(PRICE_SCAN_INTERVAL).minutes.do(realtime_scan)

    # Écoute commandes
    schedule.every(3).seconds.do(handle_commands)

    # Init prix
    print("📡 Initialisation des prix...")
    scan_alerts()
    print("✅ Prix initialisés\n")
    print(f"✅ Bot opérationnel — Ctrl+C pour arrêter\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Bot arrêté")
        send("🛑 <b>GEOALPHA</b> — Bot mis en veille.")


if __name__ == "__main__":
    main()
