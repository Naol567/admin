"""
Forex Channel Repost Bot
========================
Monitors source channels → filters → cleans → rewrites → posts to your channel.
"""

import asyncio
import logging
import os
import re
from telethon import TelegramClient, events
from telethon.tl.types import (
    MessageEntityUrl,
    MessageEntityTextUrl,
    MessageEntityMention,
    MessageEntityEmail,
)
import google.generativeai as genai

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ─── Config (from environment variables) ────────────────────────────────────
API_ID          = int(os.environ["TELEGRAM_API_ID"])
API_HASH        = os.environ["TELEGRAM_API_HASH"]
BOT_TOKEN       = os.environ["BOT_TOKEN"]            # Your bot token (admin of your channel)
GEMINI_API_KEY  = os.environ["GEMINI_API_KEY"]

# Your output channel (username or numeric ID)
MY_CHANNEL      = os.environ["MY_CHANNEL"]           # e.g. "@Squad_4xx" or "-100xxxxxxxxxx"

# Comma-separated list of source channel usernames/IDs to monitor
SOURCE_CHANNELS_RAW = os.environ.get("SOURCE_CHANNELS", "")
SOURCE_CHANNELS = [c.strip() for c in SOURCE_CHANNELS_RAW.split(",") if c.strip()]

# ─── Gemini Setup ───────────────────────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ─── Gemini Prompt ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are the Expert Owner and Lead Editor of a premium Forex Analysis Telegram channel.
Your job is to process incoming market news and rewrite it in your unique, professional brand voice.
You are NOT an assistant — you are the original creator.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 1 — CONTENT FILTER:
Only process HIGH-IMPACT fundamental Forex news:
  ✅ CPI, NFP, Interest Rate Decisions, FOMC, GDP, PMI, Unemployment, Geopolitical events
  ❌ Price charts, candlestick patterns, indicators, trading signals, buy/sell entries
  ❌ Ads, promotions, referral links, giveaways, channel invitations
  ❌ General chatter, opinions with no data

If the input is a chart image, marketing ad, signal, or irrelevant content → reply with only: IGNORE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 2 — ZERO-TRACE ANONYMIZATION:
Act as if YOU found this data yourself. REMOVE:
  - All @username mentions or channel names
  - All links: http, https, t.me, bit.ly, any URL
  - "Forwarded from", "Source:", "Via:" references
  - Promotional watermarks or "Join here" text

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 3 — ETHIOPIAN TIME CONVERSION:
The source timezone is GMT+3 (same as Ethiopian Standard Time).
Convert any timestamps to 12-hour Ethiopian local time format:
  - 8:00 PM → 2:00 ሰዓት ማታ
  - 11:30 AM → 5:30 ሰዓት ቀን
  - 1:00 AM → 7:00 ሰዓት ሌሊት
  - 4:00 PM → 10:00 ሰዓት ቀን
  Ethiopian 12-hour clock starts at 6:00 AM (Ethiopian 12:00).
  Subtract 6 hours from standard time, wrap around at 12.
  Label: ሌሊት (night 12am-6am), ቀን (day 6am-6pm), ማታ (evening 6pm-12am)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 4 — OUTPUT FORMAT:
Reply ONLY with this exact format (no extra text before or after):

🔴 High-Impact Market News Update

📌 Event: [Clear, concise summary of the news event]
⏰ Local Time: [Ethiopian time in the format: X:XX ሰዓት <period>]
⚠️ Impact Level: [High Impact / Medium Impact — mention affected pairs e.g. USD, GOLD, EUR/USD]
📝 Analysis: [One professional sentence on potential market impact]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 5 — QUALITY:
Be precise, professional, and confident. No filler phrases. No "I think". State facts.
"""

# ─── Helpers ────────────────────────────────────────────────────────────────

def strip_links_from_text(text: str) -> str:
    """Remove all URLs from plain text using regex."""
    # Remove http/https URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove t.me links without protocol
    text = re.sub(r"t\.me/\S+", "", text)
    # Remove @mentions
    text = re.sub(r"@\w+", "", text)
    # Remove "Forwarded from ..." lines
    text = re.sub(r"Forwarded from.*", "", text, flags=re.IGNORECASE)
    # Remove "Source:", "Via:", "Join:"
    text = re.sub(r"(source|via|join)\s*:.*", "", text, flags=re.IGNORECASE)
    # Clean extra whitespace
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def has_hidden_links(message) -> bool:
    """
    Detect hidden hyperlinks (MessageEntityTextUrl) in Telegram message entities.
    These are the sneaky links embedded in display text like [Click here](t.me/spam).
    """
    if not message.entities:
        return False
    dangerous = (MessageEntityUrl, MessageEntityTextUrl, MessageEntityEmail)
    for entity in message.entities:
        if isinstance(entity, dangerous):
            return True
    return False


def extract_clean_text(message) -> str:
    """
    Extract text from message, removing ALL link entities.
    Returns clean plain text with no traceable origin.
    """
    text = message.raw_text or ""
    return strip_links_from_text(text)


async def ask_gemini(text: str, image_bytes: bytes | None = None) -> str:
    """Send text (and optionally image) to Gemini for processing."""
    try:
        parts = [SYSTEM_PROMPT + "\n\nINPUT TO PROCESS:\n" + text]
        if image_bytes:
            import PIL.Image, io
            img = PIL.Image.open(io.BytesIO(image_bytes))
            parts.append(img)

        response = model.generate_content(parts)
        return response.text.strip()
    except Exception as e:
        log.error(f"Gemini error: {e}")
        return "IGNORE"


# ─── Bot ────────────────────────────────────────────────────────────────────

async def main():
    log.info("Starting Forex Repost Bot...")

    # Use bot token for posting (bot must be admin of MY_CHANNEL)
    client = TelegramClient("forex_repost_bot", API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)

    log.info(f"Bot started. Monitoring {len(SOURCE_CHANNELS)} source channel(s).")
    log.info(f"Output channel: {MY_CHANNEL}")

    @client.on(events.NewMessage(chats=SOURCE_CHANNELS))
    async def handler(event):
        msg = event.message
        log.info(f"New message from {event.chat_id}: {str(msg.raw_text or '')[:80]}")

        # ── Step 1: Detect hidden links ──────────────────────────────────
        if has_hidden_links(msg):
            log.info("⚠️  Hidden links detected — message dropped.")
            return

        # ── Step 2: Extract clean text ───────────────────────────────────
        clean_text = extract_clean_text(msg)

        # ── Step 3: Handle media (photo = possible news table or chart) ──
        image_bytes = None
        if msg.photo:
            try:
                image_bytes = await msg.download_media(bytes)
                log.info("📷 Image attached — sending to Gemini for analysis.")
            except Exception as e:
                log.warning(f"Could not download image: {e}")

        # ── Step 4: Skip if empty after cleaning ─────────────────────────
        if not clean_text and not image_bytes:
            log.info("Empty message after cleaning — skipped.")
            return

        # ── Step 5: Send to Gemini ────────────────────────────────────────
        result = await ask_gemini(clean_text, image_bytes)
        log.info(f"Gemini response: {result[:120]}")

        # ── Step 6: Check if Gemini said IGNORE ──────────────────────────
        if result.strip().upper().startswith("IGNORE"):
            log.info("🚫 Gemini classified as IGNORE — not reposting.")
            return

        # ── Step 7: Final safety — strip any links Gemini might have left ─
        result = strip_links_from_text(result)

        # ── Step 8: Post to your channel ─────────────────────────────────
        try:
            await client.send_message(MY_CHANNEL, result, parse_mode="markdown")
            log.info(f"✅ Posted to {MY_CHANNEL}")
        except Exception as e:
            log.error(f"Failed to post: {e}")

    log.info("Listening for new messages...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
