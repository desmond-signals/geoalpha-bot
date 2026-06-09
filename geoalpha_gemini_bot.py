"""
╔══════════════════════════════════════════════════════════════╗
║     GEOALPHA · KASPAROV BOT — Version 5.0 AUTO               ║
║  Prix réels Yahoo Finance + Groq → Signal auto 15min         ║
║  100% automatique · Aucune source bloquée                    ║
╚══════════════════════════════════════════════════════════════╝
"""

import requests
import schedule
import time
import json
import os
import yfinance as yf
from datetime import datetime


# ══════════════════════════════════════════════════════════════
# 🔑  CONFIGURATION
# ══════════════════════════════════════════════════════════════

TELEGRAM_TOKEN   = "8954725433:AAF_WORnnP1Xeo2rRiACneHN0mGxsG_oIc0"
TELEGRAM_CHAT_ID = "976026689"
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL       = "llama-3.3-70b-versatile"

# Fréquence du scan automatique (minutes)
AUTO_SCAN_INTERVAL = 15

# Heures d'envoi automatique (UTC) — le marché US ouvre 13h30 UTC
# Sénégal = UTC+0 / France = UTC+2
ACTIVE_HOURS = range(7, 23)  # 7h-23h UTC


# ══════════════════════════════════════════════════════════════
# ⚙️  WATCHLIST
# ══════════════════════════════════════════════════════════════

WATCHLIST = {
    "NVDA":    "NVIDIA · AI Chips",
    "TSLA":    "Tesla · EV/Robotics",
    "META":    "Meta · Social AI",
    "MSFT":    "Microsoft · Cloud AI",
    "AMZN":    "Amazon · Cloud",
    "AMD":     "AMD · Semis",
    "GOOGL":   "Google · Search/AI",
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "SOL-USD": "Solana",
    "GLD":     "Gold ETF",
    "UCO":     "Pétrole x2 ETF",
    "LMT":     "Lockheed · Défense",
    "LLY":     "Eli Lilly · Biotech",
}

_last_update_id = 0
_last_signal    = {"ticker": None, "time": None}


# ══════════════════════════════════════════════════════════════
# 📱  TELEGRAM
# ══════════════════════════════════════════════════════════════

def send(text, chat_id=None):
    cid = chat_id or TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        if len(text) > 4000:
            text = text[:4000]
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
        r = requests.get(url, params={"offset": _last_update_id + 1, "timeout": 5}, timeout=10)
        if r.status_code == 200:
            return r.json().get("result", [])
    except:
        pass
    return []


# ══════════════════════════════════════════════════════════════
# 📊  PRIX RÉELS — Yahoo Finance
# ══════════════════════════════════════════════════════════════

def get_market_data():
    """Récupère les vrais prix + variations + indicateurs techniques."""
    data, pulse = [], []
    for ticker, name in WATCHLIST.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d", interval="1h")
            if hist.empty or len(hist) < 5:
                continue

            current = float(hist["Close"].iloc[-1])
            prev    = float(hist["Close"].iloc[-2])
            day_ago = float(hist["Close"].iloc[-min(24, len(hist))])
            change_1h  = ((current - prev) / prev) * 100
            change_24h = ((current - day_ago) / day_ago) * 100

            # RSI simplifié sur les dernières heures
            closes = hist["Close"].values[-14:]
            deltas = [closes[i+1]-closes[i] for i in range(len(closes)-1)]
            gains  = sum(d for d in deltas if d > 0)
            losses = abs(sum(d for d in deltas if d < 0))
            rsi    = 100 - (100 / (1 + (gains/losses))) if losses > 0 else 50

            data.append({
                "ticker": ticker,
                "name": name,
                "price": round(current, 2),
                "change_1h": round(change_1h, 2),
                "change_24h": round(change_24h, 2),
                "rsi": round(rsi, 1),
            })

            arrow = "▲" if change_24h >= 0 else "▼"
            sign  = "+" if change_24h >= 0 else ""
            pulse.append(f"  {arrow} <b>{ticker}</b>  {sign}{change_24h:.2f}%  ({current:.2f})")
        except Exception as e:
            print(f"  [PRICE ERROR] {ticker}: {e}")
        time.sleep(0.2)
    return data, "\n".join(pulse)


# ══════════════════════════════════════════════════════════════
# 🧠  GROQ — Appel de base
# ══════════════════════════════════════════════════════════════

def call_groq(system, prompt):
    try:
        if not GROQ_API_KEY:
            print("[GROQ ERROR] Clé API vide !")
            return None

        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.6,
                "max_tokens": 900,
            },
            timeout=30,
        )
        data = r.json()

        # Log erreur Groq si pas de choices
        if "choices" not in data:
            print(f"[GROQ RESPONSE ERROR] {json.dumps(data)[:300]}")
            return None

        text  = data["choices"][0]["message"]["content"]
        clean = text.replace("```json", "").replace("```", "").strip()
        s, e  = clean.find("{"), clean.rfind("}") + 1
        if s == -1 or e == 0:
            return None
        return json.loads(clean[s:e])
    except Exception as ex:
        print(f"[GROQ ERROR] {ex}")
        return None


# ══════════════════════════════════════════════════════════════
# ⚔️  CONSEIL DE GUERRE — 3 Agents
# ══════════════════════════════════════════════════════════════

def conseil_de_guerre(market_data):
    """3 agents analysent les VRAIS prix et votent."""
    # On trie pour donner les mouvements les plus marquants aux agents
    sorted_data = sorted(market_data, key=lambda x: abs(x["change_24h"]), reverse=True)
    top_movers = sorted_data[:6]

    print("    🔬 Agent Technique...")
    tech = call_groq(
        "Tu es analyste technique. Tu analyses prix, RSI, momentum. JSON uniquement.",
        f"""Données réelles de marché (prix live):
{json.dumps(top_movers, indent=2)}

Identifie LA meilleure opportunité technique. RSI<35=survente(LONG), RSI>65=surachat(SHORT).
{{
  "ticker": "TICKER",
  "action": "LONG ou SHORT",
  "raison": "Raison technique précise en 1 phrase",
  "conviction": 0-100,
  "entree": "prix",
  "stop_loss": "-X%",
  "target": "+X%"
}}"""
    )
    time.sleep(1)

    print("    🌍 Agent Macro...")
    geo = call_groq(
        "Tu es expert macro/géopolitique. Tu analyses le contexte global des marchés. JSON uniquement.",
        f"""Données réelles de marché:
{json.dumps(top_movers, indent=2)}

Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}

Selon le contexte macro actuel et ces mouvements, quelle est la meilleure position?
{{
  "ticker": "TICKER",
  "action": "LONG ou SHORT",
  "raison": "Raison macro en 1 phrase",
  "conviction": 0-100,
  "horizon": "intraday ou 1-3j"
}}"""
    )
    time.sleep(1)

    print("    ⚖️ Agent Risque...")
    risque = call_groq(
        "Tu es gestionnaire de risque. Tu valides ou rejettes les trades. JSON uniquement.",
        f"""Analyse technique: {json.dumps(tech)}
Analyse macro: {json.dumps(geo)}

Évalue et tranche:
{{
  "verdict": "APPROUVÉ ou ATTENDRE",
  "ticker": "TICKER final",
  "action": "LONG ou SHORT",
  "entree": "prix",
  "stop_loss": "-X%",
  "target": "+X%",
  "taille_position": "X% du capital",
  "raison": "Justification en 1 phrase",
  "conviction_finale": 0-100
}}"""
    )
    time.sleep(1)

    return tech, geo, risque


def fmt_signal(tech, geo, risque, auto=False):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    actions = []
    if tech and tech.get("action"):   actions.append(tech["action"])
    if geo and geo.get("action"):     actions.append(geo["action"])
    if risque and risque.get("action"): actions.append(risque["action"])

    if not actions:
        return None  # Pas de réponse des agents

    consensus  = max(set(actions), key=actions.count)
    votes      = actions.count(consensus)
    verdict    = risque.get("verdict", "ATTENDRE") if risque else "ATTENDRE"
    icon_act   = "🟢" if consensus == "LONG" else "🔴"

    header = "🤖 <b>GEOALPHA — SCAN AUTO</b>" if auto else "⚔️ <b>GEOALPHA — CONSEIL DE GUERRE</b>"

    msg = (
        f"{header}\n"
        f"📅 {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚔️ <b>CONSEIL DE GUERRE</b>\n\n"
    )

    if tech:
        ti = "✅" if tech.get("action") == consensus else "⚠️"
        msg += f"🔬 Technique {ti} → {tech.get('action','?')} {tech.get('ticker','?')} ({tech.get('conviction','?')}%)\n   {tech.get('raison','—')}\n\n"
    if geo:
        gi = "✅" if geo.get("action") == consensus else "⚠️"
        msg += f"🌍 Macro {gi} → {geo.get('action','?')} {geo.get('ticker','?')} ({geo.get('conviction','?')}%)\n   {geo.get('raison','—')}\n\n"
    if risque:
        vi = "✅" if verdict == "APPROUVÉ" else "⏳"
        msg += f"⚖️ Risque {vi} → {verdict}\n   {risque.get('raison','—')}\n\n"

    msg += f"━━━━━━━━━━━━━━━━━━━━━━\n🗳️ <b>VOTE : {votes}/3 → {consensus}</b>\n\n"

    if verdict == "APPROUVÉ" and risque:
        conv = risque.get("conviction_finale", 0)
        bars = "█" * (conv // 10) + "░" * (10 - conv // 10)
        msg += (
            f"{icon_act} <b>SIGNAL : {consensus} {risque.get('ticker','?')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Entrée    : {risque.get('entree','—')}\n"
            f"🛑 Stop-loss : {risque.get('stop_loss','—')}\n"
            f"🚀 Target    : {risque.get('target','—')}\n"
            f"💰 Position  : {risque.get('taille_position','—')}\n"
            f"🧠 Conviction: {bars} {conv}%\n"
        )
    else:
        msg += f"⏳ <b>ATTENDRE</b> — Pas assez de confluence pour entrer\n"

    msg += f"\n<i>⚠️ Analyse uniquement — Pas de conseil financier</i>"
    return msg


# ══════════════════════════════════════════════════════════════
# 🔄  SCAN AUTOMATIQUE (toutes les 15 min)
# ══════════════════════════════════════════════════════════════

def auto_scan():
    """Scan automatique : prix réels → conseil de guerre → signal Telegram."""
    hour = datetime.now().hour
    if hour not in ACTIVE_HOURS:
        print(f"[{datetime.now().strftime('%H:%M')}] 💤 Hors heures actives")
        return

    print(f"\n[{datetime.now().strftime('%H:%M')}] 🔄 SCAN AUTO")
    market_data, _ = get_market_data()
    if not market_data:
        print("  ❌ Pas de données prix")
        return

    tech, geo, risque = conseil_de_guerre(market_data)
    msg = fmt_signal(tech, geo, risque, auto=True)
    if msg:
        send(msg)
        print("  ✅ Signal envoyé")
    else:
        print("  ⚠️ Agents sans réponse — pas d'envoi")


# ══════════════════════════════════════════════════════════════
# 💬  COMMANDES TELEGRAM
# ══════════════════════════════════════════════════════════════

def handle_commands():
    global _last_update_id
    for update in get_updates():
        _last_update_id = update["update_id"]
        msg     = update.get("message", {})
        text    = msg.get("text", "").strip().lower()
        chat_id = str(msg.get("chat", {}).get("id", TELEGRAM_CHAT_ID))
        if not text:
            continue
        print(f"[CMD] {text}")

        if text in ("/signal", "/guerre", "/trade"):
            send("⚔️ Conseil de guerre en cours... (30 sec)", chat_id)
            market_data, _ = get_market_data()
            tech, geo, risque = conseil_de_guerre(market_data)
            out = fmt_signal(tech, geo, risque, auto=False)
            send(out or "⚠️ Réessayez dans un instant", chat_id)

        elif text in ("/pulse", "/prix", "/market"):
            send("📡 Collecte des prix réels...", chat_id)
            _, pulse = get_market_data()
            now = datetime.now().strftime("%H:%M")
            send(f"📊 <b>MARKET PULSE — {now}</b>\n━━━━━━━━━━━━━━━━━\n{pulse}\n━━━━━━━━━━━━━━━━━", chat_id)

        elif text in ("/status", "/info"):
            now = datetime.now().strftime("%d/%m/%Y %H:%M")
            send(
                f"🤖 <b>GEOALPHA KASPAROV v5.0</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Bot actif · {now} UTC\n"
                f"🧠 IA : Groq LLaMA 3.3 70B\n"
                f"📊 Marchés : {len(WATCHLIST)}\n"
                f"🔄 Signal auto : toutes les {AUTO_SCAN_INTERVAL} min\n"
                f"⚔️ Conseil de guerre : 3 agents\n\n"
                f"💬 /signal · /pulse · /status", chat_id)

        elif text in ("/start", "/help", "/aide"):
            send(
                f"🤖 <b>GEOALPHA KASPAROV v5.0</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>AUTOMATIQUE :</b>\n"
                f"Signal envoyé toutes les {AUTO_SCAN_INTERVAL} min\n"
                f"basé sur les prix réels + conseil de guerre\n\n"
                f"<b>COMMANDES :</b>\n"
                f"• /signal → Signal immédiat\n"
                f"• /pulse  → Prix réels live\n"
                f"• /status → État du bot", chat_id)


# ══════════════════════════════════════════════════════════════
# 🚀  DÉMARRAGE
# ══════════════════════════════════════════════════════════════

def main():
    print("🤖 GEOALPHA KASPAROV v5.0 — AUTO Edition")

    # Vérification clé Groq
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY est VIDE !")
        print("   Variable Railway manquante ou mal nommée")
        print(f"   Valeur actuelle: '{GROQ_API_KEY}'")
    else:
        print(f"✅ Clé Groq détectée : {GROQ_API_KEY[:8]}...")

    send(
        "🚀 <b>GEOALPHA KASPAROV v5.0 — ACTIF</b>\n\n"
        f"🔄 <b>Signal automatique toutes les {AUTO_SCAN_INTERVAL} min</b>\n"
        "Basé sur les prix réels en temps réel\n"
        "+ conseil de guerre 3 agents IA\n\n"
        f"📊 {len(WATCHLIST)} marchés surveillés en continu\n\n"
        "💬 /signal · /pulse · /status\n\n"
        "<i>Tu n'as rien à faire — les signaux arrivent seuls 📈</i>"
    )

    # Signal auto toutes les 15 min
    schedule.every(AUTO_SCAN_INTERVAL).minutes.do(auto_scan)
    # Écoute commandes
    schedule.every(3).seconds.do(handle_commands)

    print(f"✅ Bot opérationnel — signal auto toutes les {AUTO_SCAN_INTERVAL} min\n")

    # Premier signal immédiat au démarrage
    print("🔄 Premier scan...")
    auto_scan()

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        send("🛑 <b>GEOALPHA</b> — Bot en veille.")


if __name__ == "__main__":
    main()
