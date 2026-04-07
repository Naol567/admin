"""
Forex Channel Repost Bot — StringSession Edition
=================================================
Railway-ready. Uses SESSION_STRING env var (no .session file needed).
"""

import asyncio
import logging
import os
import re

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import (
    MessageEntityUrl,
    MessageEntityTextUrl,
    MessageEntityEmail,
)
import google.generativeai as genai

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ─── Config ─────────────────────────────────────────────────────────────────
API_ID         = int(os.environ["TELEGRAM_API_ID"])
API_HASH       = os.environ["TELEGRAM_API_HASH"]
BOT_TOKEN      = os.environ["BOT_TOKEN"]
SESSION_STRING = os.environ["SESSION_STRING"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MY_CHANNEL     = os.environ["MY_CHANNEL"]

SOURCE_CHANNELS = [
    c.strip()
    for c in os.environ.get("SOURCE_CHANNELS", "").split(",")
    if c.strip()
]

# ─── Gemini Setup ───────────────────────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ─── Gemini System Prompt ───────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are the Expert Owner and Lead Editor of a premium Forex Analysis Telegram channel.
Your job is to process incoming market news and rewrite it in your unique, professional brand voice.
You are NOT an assistant — you are the original creator of this content.

RULE 1 — CONTENT FILTER:
Only process HIGH-IMPACT fundamental Forex news:
  ALLOWED: CPI, NFP, Interest Rate Decisions, FOMC, GDP, PMI, Unemployment, Geopolitical events
  REJECT: Price charts, candlestick patterns, indicators, trading signals, buy/sell entries
  REJECT: Ads, promotions, referral links, giveaways, channel invitations
  REJECT: General chatter, opinions with no economic data

If the input is a chart image, marketing ad, signal, or irrelevant content reply with ONLY the word: IGNORE

RULE 2 — ZERO-TRACE ANONYMIZATION:
Act as if YOU found this data yourself. REMOVE everything:
  - All @username mentions or channel names
  - All links: http, https, t.me, bit.ly, any URL
  - "Forwarded from", "Source:", "Via:" references
  - Promotional watermarks or "Join here" / "Join us" text

RULE 3 — ETHIOPIAN TIME CONVERSION:
The source timezone is GMT+3 (same as Ethiopian Standard Time, no conversion needed).
Convert any timestamps to 12-hour Ethiopian local time format.
Ethiopian clock = Standard time minus 6 hours (wrap at 12).
  - 6:00 AM  becomes 12:00 ሰዓት ቀን
  - 8:30 AM  becomes 2:30 ሰዓት ቀን
  - 12:00 PM becomes 6:00 ሰዓት ቀን
  - 2:00 PM  becomes 8:00 ሰዓት ቀን
  - 6:00 PM  becomes 12:00 ሰዓት ማታ
  - 8:00 PM  becomes 2:00 ሰዓት ማታ
  - 11:30 PM becomes 5:30 ሰዓት ማታ
  - 1:00 AM  becomes 7:00 ሰዓት ሌሊት
Labels: ቀን = 6am to 6pm | ማታ = 6pm to midnight | ሌሊት = midnight to 6am
If no time is mentioned in the input, omit the Local Time line entirely.

RULE 4 — OUTPUT FORMAT:
Reply ONLY with this exact format. No extra words before or after:

🔴 High-Impact Market News Update

📌 Event: [Clear, concise summary of the news event in English]
⏰ Local Time: [Ethiopian time — only include this line if a time was mentioned]
⚠️ Impact Level: [High Impact / Medium Impact — specify affected pairs e.g. USD, GOLD, EUR/USD]
📝 Analysis: [One confident, professional sentence on how this may affect the market]

RULE 5 — TONE AND QUALITY:
Be precise, confident, and authoritative. No filler phrases.
Never say "I think" or "possibly". State market implications directly.
Write like a seasoned market analyst who owns the channel.
"""

# ─── Helpers ─────────────────────────────────────────────────────────────────

def has_hidden_links(message) -> bool:
    if not message.entities:
        return False
    blocked = (MessageEntityUrl, MessageEntityTextUrl, MessageEntityEmail)
    for entity in message.entities:
        if isinstance(entity, blocked):
            return True
    return False


def strip_links_from_text(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"t\.me/\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"(?i)forwarded from.*", "", text)
    text = re.sub(r"(?i)(source|via|join|channel)\s*:.*", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_clean_text(message) -> str:
    raw = message.raw_text or ""
    return strip_links_from_text(raw)


async def ask_gemini(text: str, image_bytes=None) -> str:
    try:
        prompt = SYSTEM_PROMPT + "\n\nINPUT TO PROCESS:\n" + text
        parts = [prompt]
        if image_bytes:
            import PIL.Image, io
            img = PIL.Image.open(io.BytesIO(image_bytes))
            parts.append(img)
        response = model.generate_content(parts)
        return response.text.strip()
    except Exception as e:
        log.error(f"Gemini error: {e}")
        return "IGNORE"


# ─── Main ────────────────────────────────────────────────────────────────────

async def main():
    log.info("Starting Forex Repost Bot (StringSession)...")

    # User client — monitors source channels
    user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await user_client.connect()

    if not await user_client.is_user_authorized():
        log.error("SESSION_STRING is invalid or expired. Please regenerate it.")
        return

    me = await user_client.get_me()
    log.info(f"Logged in as: {me.first_name} (@{me.username})")

    # Bot client — posts to your channel
    bot_client = TelegramClient("bot_poster", API_ID, API_HASH)
    await bot_client.start(bot_token=BOT_TOKEN)
    log.info("Bot poster ready.")
    log.info(f"Monitoring {len(SOURCE_CHANNELS)} channel(s): {SOURCE_CHANNELS}")
    log.info(f"Output: {MY_CHANNEL}")

    @user_client.on(events.NewMessage(chats=SOURCE_CHANNELS))
    async def handler(event):
        msg = event.message
        preview = str(msg.raw_text or "")[:80].replace("\n", " ")
        log.info(f"New message from {event.chat_id}: {preview}")

        # 1. Hidden link check
        if has_hidden_links(msg):
            log.info("Hidden link detected — dropped.")
            return

        # 2. Clean text
        clean_text = extract_clean_text(msg)

        # 3. Download image if present
        image_bytes = None
        if msg.photo:
            try:
                image_bytes = await msg.download_media(bytes)
                log.info("Image found — sending to Gemini.")
            except Exception as e:
                log.warning(f"Image download failed: {e}")

        # 4. Skip if nothing to process
        if not clean_text and not image_bytes:
            log.info("Empty message — skipped.")
            return

        # 5. Ask Gemini
        result = await ask_gemini(clean_text, image_bytes)
        log.info(f"Gemini result: {result[:100]}")

        # 6. IGNORE check
        if result.strip().upper().startswith("IGNORE"):
            log.info("Gemini says IGNORE — not reposting.")
            return

        # 7. Final safety strip
        result = strip_links_from_text(result)

        # 8. Post to channel
        try:
            await bot_client.send_message(MY_CHANNEL, result)
            log.info(f"Posted to {MY_CHANNEL}")
        except Exception as e:
            log.error(f"Failed to post: {e}")

    log.info("Listening for new messages...")
    await user_client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
