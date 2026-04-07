# 📡 Forex Channel Repost Bot

Automatically monitors source Telegram channels and reposts only high-impact Forex news to your channel — fully anonymized, rewritten in your brand voice.

---

## ✅ What It Does

| Feature | Detail |
|---|---|
| **Monitors** | Multiple Telegram channels simultaneously |
| **Filters** | Only high-impact fundamental news (CPI, NFP, FOMC, etc.) |
| **Rejects** | Charts, signals, ads, spam |
| **Strips** | All visible links, hidden hyperlinks, @mentions, source names |
| **Rewrites** | Via Gemini AI in your professional owner brand voice |
| **Converts** | Timestamps to Ethiopian Standard Time (12-hour format) |
| **Posts** | Clean, professional post to your channel as admin |

---

## 🛡️ Link Detection (Critical)

The bot catches **two types** of links:

1. **Visible links** — Removed via regex (`https://...`, `t.me/...`)
2. **Hidden links (entity-based)** — Telegram allows text like `Click Here` that secretly links to a channel. The bot reads the raw `MessageEntityTextUrl` entities and **drops the entire message** if any hidden link is found.

This makes the bot behave exactly like a trusted admin who never forwards suspicious content.

---

## 🚀 Railway Deployment

### Step 1 — First-Time Session Setup (IMPORTANT)

Because the bot monitors channels (not just receives messages), it needs a **user session**, not just a bot token.

Run this **once on your phone/Termux** to generate the session file:

```bash
pip install telethon
python generate_session.py
```

This creates `forex_repost_bot.session` — upload this to Railway as a persistent file or commit it (keep private!).

### Step 2 — Set Environment Variables on Railway

```
TELEGRAM_API_ID      = your api id
TELEGRAM_API_HASH    = your api hash
BOT_TOKEN            = your bot token
MY_CHANNEL           = @Squad_4xx
SOURCE_CHANNELS      = @channel1,@channel2
GEMINI_API_KEY       = your gemini key
```

### Step 3 — Deploy

```bash
railway up
```

Railway uses `Procfile` → runs `python bot.py` as a worker (no web server needed).

---

## 📁 Files

```
forex-repost-bot/
├── bot.py               # Main bot logic
├── generate_session.py  # One-time session generator
├── requirements.txt     # Python dependencies
├── Procfile             # Railway worker config
└── .env.example         # Environment variable template
```

---

## 📝 Output Format Example

```
🔴 High-Impact Market News Update

📌 Event: U.S. CPI came in at 3.2% YoY for March, above the 3.0% forecast
⏰ Local Time: 3:30 ሰዓት ቀን
⚠️ Impact Level: High Impact — USD, GOLD, EUR/USD
📝 Analysis: A hotter-than-expected CPI print signals persistent inflation, likely delaying Fed rate cuts and strengthening the Dollar against majors.
```
