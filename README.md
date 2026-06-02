# 📊 Market Pulse — Automated Financial Report

Report finanziario automatico 2×/giorno via email + web app GitHub Pages.

---

## Stack
- **Python 3.11** — nessuna dipendenza esterna (solo stdlib)
- **Yahoo Finance API** — gratuita, no key richiesta
- **Claude Haiku API** — ~$0.002/report (~$3/anno a 2 report/giorno)
- **Gmail SMTP** — invio email gratuito
- **GitHub Actions** — scheduling gratuito (2000 min/mese free)
- **GitHub Pages** — web app hosting gratuito

---

## Setup (15 minuti)

### 1. Fork / crea il repository

```bash
git init market-report
cd market-report
# copia tutti i file qui
git add .
git commit -m "init"
git remote add origin https://github.com/TUO_USERNAME/market-report.git
git push -u origin main
```

### 2. Abilita GitHub Pages

- Repository → **Settings** → **Pages**
- Source: `Deploy from a branch`
- Branch: `main` / `/ (root)`
- Salva → ottieni URL tipo `https://TUO_USERNAME.github.io/market-report`

### 3. Configura i Secrets

Repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Valore |
|---|---|
| `ANTHROPIC_API_KEY` | La tua API key da console.anthropic.com |
| `GMAIL_USER` | tua-email@gmail.com |
| `GMAIL_APP_PASSWORD` | App password Gmail (vedi sotto) |
| `REPORT_RECIPIENT` | email dove ricevere i report |
| `WEB_APP_URL` | `https://TUO_USERNAME.github.io/market-report` |

### 4. Ottieni Gmail App Password

1. Account Google → **Sicurezza** → **Verifica in due passaggi** (deve essere attiva)
2. Cerca "App password" → **Seleziona app**: Posta → **Seleziona dispositivo**: Altro → dai un nome
3. Copia le 16 cifre generate → incollale come `GMAIL_APP_PASSWORD`

> ⚠ Non usare la tua password Gmail normale. Le App Password sono separate e revocabili.

### 5. Test manuale

- Repository → **Actions** → **Market Report** → **Run workflow**
- Controlla i log per eventuali errori
- Verifica email ricevuta e web app aggiornata

---

## Orari (fuso EU/Roma)

| Cron | Orario CET (inverno) | Orario CEST (estate) |
|---|---|---|
| `30 7 * * 1-5` | 09:30 | 09:30 ✓ |
| `0 13 * * 1-5` | 15:00 | 15:00 ✓ |

> GitHub Actions usa UTC. I cron sono già scritti per UTC+1 (inverno).
> In estate (UTC+2) modifica il workflow: `30 7` → `30 6` e `0 13` → `0 12`.

---

## Struttura file

```
market-report/
├── generate_report.py          # Script principale
├── index.html                  # Web app (auto-aggiornata)
├── .github/
│   └── workflows/
│       └── report.yml          # GitHub Actions scheduler
└── README.md
```

---

## Costi stimati

| Voce | Costo |
|---|---|
| Yahoo Finance API | €0 |
| GitHub Actions | €0 (2000 min/mese gratuiti) |
| GitHub Pages | €0 |
| Gmail SMTP | €0 |
| Claude Haiku (2×/giorno, ~200 token) | ~€2.50/anno |
| **Totale** | **~€2.50/anno** |

---

## Personalizzazione

Per aggiungere/rimuovere asset, modifica la lista `ASSETS` in `generate_report.py`.
Simboli Yahoo Finance: cerca su `finance.yahoo.com` e usa il ticker esatto.

Esempi:
- `VWCE.DE` — Vanguard All-World
- `AGGH.MI` — iShares Core Global Aggregate Bond
- `ETH-USD` — Ethereum
- `NG=F` — Gas naturale
