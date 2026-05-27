"""
╔══════════════════════════════════════════════════════════════╗
║        GEOALPHA · KASPAROV BOT — Version 3.0                 ║
║  Nouvelle librairie google-genai + Telegram push             ║
╚══════════════════════════════════════════════════════════════╝
"""

import requests
import schedule
import time
import json
import yfinance as yf
from datetime import datetime
from google import genai


# ══════════════════════════════════════════════════════════════
# 🔑  CONFIGURATION
# ══════════════════════════════════════════════════════════════

TELEGRAM_TOKEN   = "8954725433:AAF_WORnnP1Xeo2rRiACneHN0mGxsG_oIc0"
TELEGRAM_CHAT_ID = "976026689"
GEMINI_API_KEY   = "AIzaSyAvBUlAHcpJT0kdhiAt-uFBoGUBmpILrvk"

# Nouvelle librairie google-genai
client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-2.0-flash"


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

ALERT_THRESHOLD_PCT = 2.5
PRICE_SCAN_INTERVAL = 15
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
# 📊  MARCHÉ
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
                "ticker": ticker,
                "name": name,
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
# 🧠  GEMINI IA — Nouvelle librairie google-genai
# ══════════════════════════════════════════════════════════════

def call_gemini(prompt):
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
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
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    prompt = f"""Tu es GeoAlpha Kasparov, le meilleur système d'analyse financière et géopolitique au monde.
Date et heure : {now}
Session : {session_label}

Voici les données de marché en temps réel :
{json.dumps(market_data, indent=2)}

Génère exactement 3 signaux de trading chirurgicaux basés sur ces prix et ton analyse géopolitique.

Réponds UNIQUEMENT en JSON valide sans markdown :
{{
  "context": "Contexte marché en 1 phrase",
  "polymarket": "Signal géopolitique clé du moment",
  "signals": [
    {{
      "ticker": "TICKER",
      "name": "Nom complet",
      "action": "LONG ou SHORT",
      "montant_eur": "35€",
      "levier": "x1",
      "entree": "Prix ou condition",
      "stop_loss": "-X%",
      "target": "+X%",
      "horizon": "1-3j",
      "raison": "Raison en 1 phrase",
      "conviction": 85
    }},
    {{
      "ticker": "TICKER",
      "name": "Nom",
      "action": "LONG",
      "montant_eur": "30€",
      "levier": "x1",
      "entree": "Prix",
      "stop_loss": "-X%",
      "target": "+X%",
      "horizon": "1-3j",
      "raison": "Raison",
      "conviction": 78
    }},
    {{
      "ticker": "TICKER",
      "name": "Nom",
      "action": "LONG",
      "montant_eur": "25€",
      "levier": "x1",
      "entree": "Prix",
      "stop_loss": "-X%",
      "target": "+X%",
      "horizon": "1sem",
      "raison": "Raison",
      "conviction": 72
    }}
  ],
  "alerte": "Risque principal",
  "cash_reserve": "10€"
}}"""
    return call_gemini(prompt)


def analyze_movement(ticker, name, price, change):
    direction = "hausse" if change > 0 else "baisse"
    prompt = f"""Tu es GeoAlpha Kasparov. {ticker} ({name}) vient de faire une {direction} de {abs(change):.1f}% à {price:.2f}$.

Réponds UNIQUEMENT en JSON valide :
{{
  "catalyseur": "Raison probable",
  "action": "LONG ou SHORT ou HOLD",
  "conviction": 80,
  "entree": "Prix optimal",
  "stop_loss": "-X%",
  "target": "+X%",
  "horizon": "intraday ou 1-3j",
  "raison": "Thèse en 1 phrase"
}}"""
    return call_gemini(prompt)


# ══════════════════════════════════════════════════════════════
# 📨  FORMATAGE
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
            f"\n{medals[i]} {icon} <b>{action} {s.get('ticker','')} — {s.get('name','')}</b>\n"
            f"💰 Montant   : <b>{s.get('montant_eur','')}</b>\n"
            f"⚡ Levier    : {s.get('levier','x1')}\n"
            f"🎯 Entrée    : {s.get('entree','—')}\n"
            f"🛑 Stop-loss : {s.get('stop_loss','—')}\n"
            f"🚀 Target    : {s.get('target','—')}\n"
            f"⏱ Horizon   : {s.get('horizon','—')}\n"
            f"📝 {s.get('raison','')}\n"
            f"🧠 Conviction: {bars} {conv}%\n"
        )
    msg += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 <b>CASH</b> : {data.get('cash_reserve','10€')}\n"
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
        f"{icon} <b>ALERTE — {ticker}</b>\n"
        f"📊 {name}\n"
        f"💲 {price:.2f}  |  {'+' if change>0 else ''}{change:.2f}%\n\n"
    )
    if ai:
        conv = ai.get("conviction", 0)
        bars = "█" * (conv // 10) + "░" * (10 - conv // 10)
        msg += (
            f"📌 {ai.get('catalyseur','—')}\n\n"
            f"{color} <b>{action}</b> | Entrée: {ai.get('entree','—')}\n"
            f"🛑 Stop: {ai.get('stop_loss','—')} | 🚀 Target: {ai.get('target','—')}\n"
            f"🧠 {bars} {conv}%\n"
        )
    msg += f"\n<i>⚠️ Information uniquement</i>"
    return msg


# ══════════════════════════════════════════════════════════════
# ⏰  SESSIONS
# ══════════════════════════════════════════════════════════════

def session_scan(label):
    print(f"\n[{datetime.now().strftime('%H:%M')}] 🔄 {label}")
    send(f"⏳ <b>GEOALPHA</b> — Scan <b>{label}</b> en cours...")
    market_data, _ = get_market_snapshot()
    data = generate_signals(market_data, label)
    if data:
        send(fmt_signals(data, label))
        print(f"✅ Signaux envoyés")
    else:
        send(f"⚠️ Erreur analyse — réessayez avec /signal")


def morning_session():   session_scan("OUVERTURE EUROPE 09H00")
def afternoon_session(): session_scan("PRÉ-OUVERTURE NY 15H25")
def evening_session():   session_scan("BILAN SOIR 22H00")


# ══════════════════════════════════════════════════════════════
# 🔔  ALERTES TEMPS RÉEL
# ══════════════════════════════════════════════════════════════

def realtime_scan():
    print(f"[{datetime.now().strftime('%H:%M')}] 📡 Scan...")
    alerts = scan_alerts()
    for alert in alerts:
        print(f"  🚨 {alert['ticker']}: {alert['change']:+.2f}%")
        ai  = analyze_movement(alert["ticker"], alert["name"], alert["price"], alert["change"])
        msg = fmt_alert(alert["ticker"], alert["name"], alert["price"], alert["change"], ai)
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
                f"🤖 <b>GEOALPHA — STATUS</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Bot actif · {now}\n"
                f"🧠 IA : Gemini 2.0 Flash\n"
                f"📊 Tickers : {len(WATCHLIST)}\n"
                f"🔔 Seuil : ±{ALERT_THRESHOLD_PCT}%\n\n"
                f"💬 /signal  /pulse  /status",
                chat_id
            )

        elif text in ("/start", "/help", "/aide"):
            send(
                f"🤖 <b>GEOALPHA KASPAROV BOT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• /signal → 3 signaux maintenant\n"
                f"• /pulse  → Prix marché live\n"
                f"• /status → État du bot\n\n"
                f"Alertes auto si mouvement > ±{ALERT_THRESHOLD_PCT}%\n"
                f"Signaux planifiés : 09h · 15h25 · 22h",
                chat_id
            )


# ══════════════════════════════════════════════════════════════
# 🚀  DÉMARRAGE
# ══════════════════════════════════════════════════════════════

def main():
    print("🤖 GEOALPHA KASPAROV BOT v3.0 — Démarrage...")

    send(
        "🚀 <b>GEOALPHA KASPAROV BOT v3.0 — ACTIF</b>\n\n"
        "IA de trading géopolitique opérationnelle.\n\n"
        "📅 Signaux automatiques :\n"
        "• 🌅 09h00 — Europe\n"
        "• 🌆 15h25 — Wall Street\n"
        "• 🌙 22h00 — Bilan\n\n"
        f"🔔 Alertes si mouvement > ±{ALERT_THRESHOLD_PCT}%\n\n"
        "💬 /signal  /pulse  /status\n\n"
        "<i>Bonne chasse aux alphas ! 📈</i>"
    )

    schedule.every().day.at("09:00").do(morning_session)
    schedule.every().day.at("15:25").do(afternoon_session)
    schedule.every().day.at("22:00").do(evening_session)
    schedule.every(PRICE_SCAN_INTERVAL).minutes.do(realtime_scan)
    schedule.every(3).seconds.do(handle_commands)

    print("📡 Initialisation des prix...")
    scan_alerts()
    print("✅ Prix initialisés")
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
