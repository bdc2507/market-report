#!/usr/bin/env python3
"""
Market Report Generator
Fetches financial data, gets AI commentary via Claude Haiku,
generates HTML email and updates web app.
"""

import os
import json
import smtplib
import datetime
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
import urllib.request
import urllib.parse

# ── ASSETS CONFIG ──────────────────────────────────────────────────────────────
ASSETS = [
    # Equities / ETF
    {"symbol": "^GSPC",   "name": "S&P 500",       "category": "equity",    "emoji": "🇺🇸"},
    {"symbol": "IWDA.AS", "name": "MSCI World",     "category": "equity",    "emoji": "🌍"},
    {"symbol": "EIMI.AS", "name": "EIMI EM",        "category": "equity",    "emoji": "🌏"},
    {"symbol": "XDWT.DE", "name": "XDWT Tech",      "category": "equity",    "emoji": "💻"},
    # Commodities
    {"symbol": "CL=F",    "name": "Petrolio WTI",   "category": "commodity", "emoji": "🛢️"},
    {"symbol": "GC=F",    "name": "Oro",             "category": "commodity", "emoji": "🥇"},
    {"symbol": "SI=F",    "name": "Argento",         "category": "commodity", "emoji": "🥈"},
    # Crypto
    {"symbol": "BTC-USD", "name": "Bitcoin",         "category": "crypto",    "emoji": "₿"},
    {"symbol": "SOL-USD", "name": "Solana",          "category": "crypto",    "emoji": "◎"},
    # Forex / Macro
    {"symbol": "EURUSD=X","name": "EUR/USD",         "category": "forex",     "emoji": "💶"},
    {"symbol": "^TNX",    "name": "Bond US 10Y",     "category": "bond",      "emoji": "📊"},
]

# ── FETCH MARKET DATA ──────────────────────────────────────────────────────────
def fetch_quote(symbol):
    """Fetch quote data from Yahoo Finance v8 API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=1mo"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        result = data["chart"]["result"][0]
        meta   = result["meta"]
        closes = result["indicators"]["quote"][0]["close"]
        # Filter out None values
        closes = [c for c in closes if c is not None]
        if len(closes) < 2:
            return None

        current   = meta.get("regularMarketPrice") or closes[-1]
        prev_day  = closes[-2]
        week_ago  = closes[-6]  if len(closes) >= 6  else closes[0]
        month_ago = closes[0]

        def pct(a, b):
            return round((a - b) / b * 100, 2) if b else 0.0

        return {
            "symbol":    symbol,
            "current":   round(current, 4),
            "day_pct":   pct(current, prev_day),
            "week_pct":  pct(current, week_ago),
            "month_pct": pct(current, month_ago),
            "currency":  meta.get("currency", ""),
            "history":   closes[-20:],  # last 20 closes for sparkline
        }
    except Exception as e:
        print(f"  ⚠ Error fetching {symbol}: {e}")
        return None


def fetch_all_assets():
    results = []
    for asset in ASSETS:
        print(f"  Fetching {asset['name']} ({asset['symbol']})…")
        quote = fetch_quote(asset["symbol"])
        if quote:
            quote.update({"name": asset["name"], "category": asset["category"], "emoji": asset["emoji"]})
            results.append(quote)
        else:
            results.append({
                "symbol": asset["symbol"], "name": asset["name"],
                "category": asset["category"], "emoji": asset["emoji"],
                "current": None, "day_pct": None, "week_pct": None,
                "month_pct": None, "currency": "", "history": [],
            })
    return results


# ── CLAUDE AI COMMENTARY ───────────────────────────────────────────────────────
def get_ai_commentary(market_data, api_key):
    """Call Claude Haiku to get a brief market commentary."""
    summary_lines = []
    for d in market_data:
        if d["current"] is not None:
            summary_lines.append(
                f"{d['name']}: {d['current']} {d['currency']} | "
                f"giorno {d['day_pct']:+.2f}% | settimana {d['week_pct']:+.2f}% | mese {d['month_pct']:+.2f}%"
            )
    summary = "\n".join(summary_lines)

    now = datetime.datetime.now()
    session = "mattina" if now.hour < 13 else "pomeriggio"

    prompt = f"""Sei un analista finanziario conciso. Analizza questi dati di mercato del {session} del {now.strftime('%d/%m/%Y')}:

{summary}

Scrivi UN commento di massimo 3 frasi (80 parole max) in italiano, come se lo spiegassi a un ragazzo di 14 anni che non conosce la finanza. Usa metafore semplici. Evidenzia il trend più importante. Niente tecnicismi. Niente elenchi puntati. Solo testo fluente."""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 200,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"  ⚠ Claude API error: {e}")
        return "Dati di mercato aggiornati. Analisi AI temporaneamente non disponibile."


# ── HTML GENERATION ────────────────────────────────────────────────────────────
def pct_color(val):
    if val is None: return "#888888"
    if val > 0:     return "#1a7a4a"
    if val < 0:     return "#c0392b"
    return "#888888"

def pct_arrow(val):
    if val is None: return "–"
    if val > 0:     return f"▲ +{val:.2f}%"
    if val < 0:     return f"▼ {val:.2f}%"
    return f"→ {val:.2f}%"

CATEGORY_LABELS = {
    "equity":    "📈 Azioni &amp; ETF",
    "commodity": "🏭 Materie Prime",
    "crypto":    "🔗 Crypto",
    "forex":     "💱 Forex &amp; Macro",
    "bond":      "💱 Forex &amp; Macro",
}

def build_html_report(market_data, commentary, is_email=True):
    now = datetime.datetime.now()
    session = "🌅 Apertura" if now.hour < 13 else "🌆 Chiusura"
    date_str = now.strftime("%A %d %B %Y – %H:%M")

    from collections import OrderedDict
    groups = OrderedDict()
    for d in market_data:
        label = CATEGORY_LABELS.get(d["category"], d["category"])
        groups.setdefault(label, []).append(d)

    sections_html = ""
    for group_label, items in groups.items():
        rows = ""
        for d in items:
            price_str = f"{d['current']:,.4g} {d['currency']}" if d["current"] else "N/D"
            day_col   = pct_color(d["day_pct"])
            week_col  = pct_color(d["week_pct"])
            month_col = pct_color(d["month_pct"])
            rows += f"""
      <tr style="border-bottom:1px solid #eeeeee;">
        <td style="padding:13px 8px; font-size:18px; width:30px; text-align:center;">{d['emoji']}</td>
        <td style="padding:13px 6px;">
          <div style="font-size:14px; font-weight:600; color:#111111; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:120px;">{d['name']}</div>
          <div style="font-family:'Courier New',monospace; font-size:11px; color:#888888; margin-top:2px;">{price_str}</div>
        </td>
        <td style="padding:13px 6px; text-align:right; white-space:nowrap;">
          <div style="font-size:17px; font-weight:600; color:{day_col};">{pct_arrow(d['day_pct'])}</div>
          <div style="font-family:'Courier New',monospace; font-size:11px; margin-top:3px;">
            <span style="color:{week_col};">{pct_arrow(d['week_pct'])}</span>
            <span style="color:#aaaaaa;"> 7d</span>
            &nbsp;
            <span style="color:{month_col};">{pct_arrow(d['month_pct'])}</span>
            <span style="color:#aaaaaa;"> 30d</span>
          </div>
        </td>
      </tr>"""

        sections_html += f"""
    <tr>
      <td colspan="3" style="padding:14px 8px 5px; font-family:'Courier New',monospace;
          font-size:10px; letter-spacing:2px; text-transform:uppercase;
          color:#888888; border-bottom:1px solid #dddddd;">
        {group_label}
      </td>
    </tr>
    {rows}"""

    web_app_link = os.environ.get("WEB_APP_URL", "#")
    link_section = f'<p style="text-align:center; margin-top:20px;"><a href="{web_app_link}" style="color:#b8860b; font-family:\'Courier New\',monospace; font-size:11px; letter-spacing:2px;">→ APRI WEB APP ←</a></p>' if is_email else ""

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Market Report – {date_str}</title>
</head>
<body style="margin:0; padding:0; background:#f5f5f3; font-family:Arial,sans-serif;">
<div style="max-width:560px; margin:0 auto; padding:16px;">

  <!-- HEADER -->
  <div style="background:#ffffff; border-bottom:3px solid #b8860b; padding:18px 20px 14px; margin-bottom:3px;">
    <div style="font-family:'Courier New',monospace; font-size:10px; letter-spacing:3px; color:#b8860b; text-transform:uppercase; margin-bottom:6px;">
      Market Pulse
    </div>
    <div style="font-size:20px; font-weight:600; color:#111111;">
      {session} Mercati
    </div>
    <div style="font-family:'Courier New',monospace; font-size:11px; color:#888888; margin-top:3px; text-transform:capitalize;">
      {date_str}
    </div>
  </div>

  <!-- MARKET TABLE -->
  <div style="background:#ffffff; margin-bottom:3px; padding:0 12px 8px;">
    <table style="width:100%; border-collapse:collapse;">
      {sections_html}
    </table>
  </div>

  <!-- AI COMMENTARY -->
  <div style="background:#fffdf5; border-left:3px solid #b8860b; padding:16px 18px; margin-bottom:3px;">
    <div style="font-family:'Courier New',monospace; font-size:10px; letter-spacing:2px; color:#b8860b; text-transform:uppercase; margin-bottom:8px;">
      ◈ Analisi AI
    </div>
    <p style="margin:0; font-size:14px; line-height:1.7; color:#111111; font-style:italic;">
      {commentary}
    </p>
    {link_section}
  </div>

  <!-- LEGEND -->
  <div style="padding:10px 12px;">
    <span style="font-family:'Courier New',monospace; font-size:10px; color:#aaaaaa; letter-spacing:0.5px;">
      <span style="color:#1a7a4a;">▲</span> rialzo &nbsp;|&nbsp;
      <span style="color:#c0392b;">▼</span> ribasso &nbsp;|&nbsp;
      dati: Yahoo Finance
    </span>
  </div>

</div>
</body>
</html>"""
    return html


# ── EMAIL SENDER ───────────────────────────────────────────────────────────────
def send_email(html_content, subject, smtp_user, smtp_pass, recipient):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = recipient
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, recipient, msg.as_string())
    print(f"  ✅ Email sent to {recipient}")


# ── WEB APP UPDATER ────────────────────────────────────────────────────────────
def update_web_app(market_data, commentary):
    """Write data.json for GitHub Pages web app to consume directly."""
    import json as _json
    now = datetime.datetime.now()
    payload = {
        "generated_at": now.strftime("%A %d %B %Y \u2013 %H:%M"),
        "session": "apertura" if now.hour < 13 else "chiusura",
        "commentary": commentary,
        "assets": [
            {
                "symbol":    d["symbol"],
                "name":      d["name"],
                "category":  d["category"],
                "emoji":     d["emoji"],
                "current":   d["current"],
                "currency":  d["currency"],
                "day_pct":   d["day_pct"],
                "week_pct":  d["week_pct"],
                "month_pct": d["month_pct"],
            }
            for d in market_data
        ]
    }
    with open("data.json", "w", encoding="utf-8") as f:
        _json.dump(payload, f, ensure_ascii=False, indent=2)
    print("  ✅ data.json updated")


# ── MAIN ───────────────────────────────────────────────────────────────────────
def load_config():
    """Load credentials from config.env (local test) or environment (GitHub Actions)."""
    config_path = os.path.join(os.path.dirname(__file__), "config.env")
    if os.path.exists(config_path):
        print("  📁 Loading credentials from config.env")
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip()
                    # Skip placeholder values
                    if val and not val.startswith("sk-ant-INSERISCI") \
                            and val not in ("xxxxxxxxxxxxxxxx", "tuo-account@gmail.com",
                                            "https://TUO_USERNAME.github.io/market-report"):
                        os.environ.setdefault(key, val)
    else:
        print("  ☁ No config.env found — using environment variables (GitHub Actions mode)")


def main():
    print("=" * 50)
    print(f"  Market Report – {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 50)

    # Load from config.env (local) or env vars (CI)
    load_config()

    # Read secrets from environment (GitHub Actions Secrets)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    smtp_user     = os.environ.get("GMAIL_USER", "")
    smtp_pass     = os.environ.get("GMAIL_APP_PASSWORD", "")
    recipient     = os.environ.get("REPORT_RECIPIENT", smtp_user)

    if not anthropic_key:
        print("⚠  ANTHROPIC_API_KEY mancante → commento AI disabilitato")
        print("   Inseriscila in config.env")
    if not smtp_user or not smtp_pass:
        print("⚠  Credenziali Gmail mancanti → email non inviata")
        print("   Compila GMAIL_USER e GMAIL_APP_PASSWORD in config.env")
    if anthropic_key and smtp_user and smtp_pass:
        print("  ✅ Credenziali OK")

    # 1. Fetch market data
    print("\n[1/3] Fetching market data…")
    market_data = fetch_all_assets()

    # 2. AI commentary
    print("\n[2/3] Generating AI commentary…")
    commentary = get_ai_commentary(market_data, anthropic_key) if anthropic_key else "Analisi AI non disponibile (API key mancante)."
    print(f"  Commentary: {commentary[:80]}…")

    # 3. Build & send email
    now = datetime.datetime.now()
    session_label = "Apertura" if now.hour < 13 else "Chiusura"
    subject = f"📊 Market Pulse – {session_label} {now.strftime('%d/%m/%Y %H:%M')}"

    print("\n[3/3] Building report & sending…")
    html_email = build_html_report(market_data, commentary, is_email=True)

    if smtp_user and smtp_pass:
        try:
            send_email(html_email, subject, smtp_user, smtp_pass, recipient)
        except Exception as e:
            print(f"  ⚠ Email error: {e}")
            traceback.print_exc()

    # 4. Update web app
    update_web_app(market_data, commentary)
    print("\n✅ Done.")


if __name__ == "__main__":
    main()
