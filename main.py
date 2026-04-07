import os
import asyncio
import re
import google.generativeai as genai
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

# --- CONFIGURATION (Railway Variables) ---
def get_env(name, is_int=False):
    val = os.getenv(name)
    if is_int:
        return int(val) if val and val.isnumeric() else 0
    return val

API_ID = get_env('API_ID', is_int=True)
API_HASH = get_env('API_HASH')
SESSION_STRING = get_env('SESSION_STRING')
GEMINI_KEY = get_env('GEMINI_KEY')
MY_ID = get_env('MY_ID', is_int=True)
MY_CHANNEL = get_env('MY_CHANNEL')

# የሚከታተላቸው ቻናሎች ከ ENV እንዲያነብ (በነጠላ ሰረዝ የተለዩ)
# ምሳሌ፦ @channel1, @channel2, @channel3
sources_raw = os.getenv('SOURCE_CHANNELS', '@forexfactory_news')
SOURCE_CHANNELS = [s.strip() for s in sources_raw.split(',') if s.strip()]

# Gemini Setup
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def clean_all_entities(event_msg):
    """ሁሉንም አይነት የተደበቁ ሊንኮች እና ማስታወቂያዎች ያጠፋል"""
    text = event_msg.text or ""
    entities = event_msg.entities
    if not entities:
        return re.sub(r'(https?://[^\s]+|t\.me/[^\s]+|@[^\s]+)', '', text).strip()
    
    offsets = []
    for ent in entities:
        e_type = type(ent).__name__
        if any(x in e_type for x in ['Url', 'Mention', 'BotCommand', 'TextUrl']):
            offsets.append((ent.offset, ent.length))
            
    chars = list(text)
    for offset, length in sorted(offsets, reverse=True):
        chars[offset : offset + length] = ""
    
    cleaned = "".join(chars)
    return re.sub(r'\s+', ' ', cleaned).strip()

async def get_ai_decision(cleaned_text, message_obj):
    """የባለቤቱን ስታይል የጠበቀ AI Prompt"""
    prompt = """
    Act as the Expert Owner and Lead Editor of a premium Forex news channel.
    Your task: Rewrite incoming high-impact news in your professional brand voice.

    ### MANDATORY RULES:
    1. **Content:** ONLY accept high-impact news (e.g., CPI, NFP, Rates). REJECT charts or signals.
    2. **Zero-Trace:** Remove ALL source names, watermarks, and @usernames.
    3. **Time:** Convert ANY time to Ethiopian local time (12-hour format, GMT+3).
       Example: 8:30 PM -> 2:30 ሰዓት, 11:00 AM -> 5:00 ሰዓት.
    4. **Output Format:**
       🔴 **High-Impact Market Update**
       📌 **Event:** [Summary]
       ⏰ **Ethiopian Time:** [Converted Time]
       ⚠️ **Impact:** [High/Medium]
       📝 **Note:** [Short expert insight]

    Respond ONLY with "IGNORE" if the news is irrelevant or a chart.
    """
    
    content = [prompt, f"Input Text: {cleaned_text}"]
    if message_obj.photo:
        try:
            path = await message_obj.download_media()
            image_data = genai.upload_file(path)
            content.append(image_data)
            os.remove(path)
        except: pass
        
    try:
        await asyncio.sleep(2)
        response = model.generate_content(content)
        return None if "IGNORE" in response.text.upper() else response.text
    except: return None

@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def main_handler(event):
    base_text = clean_all_entities(event.message)
    final_post = await get_ai_decision(base_text, event.message)
    
    if final_post:
        btns = [[Button.inline("✅ አጽድቅ (Post)", data="publish")],
                [Button.inline("❌ ሰርዝ (Reject)", data="cancel")]]
        
        if event.message.photo:
            await client.send_file(MY_ID, event.message.media, caption=final_post, buttons=btns)
        else:
            await client.send_message(MY_ID, final_post, buttons=btns)

@client.on(events.CallbackQuery)
async def callback_handler(event):
    if event.sender_id != MY_ID: return
    msg = await event.get_message()
    if event.data == b"publish":
        try:
            if msg.photo:
                await client.send_file(MY_CHANNEL, msg.media, caption=msg.text)
            else:
                await client.send_message(MY_CHANNEL, msg.text)
            await event.edit("🚀 ዜናው ወደ ቻናልህ ተለጥፏል!")
        except Exception as e:
            await event.respond(f"Error: {e}")
    elif event.data == b"cancel":
        await event.delete()

print(f"ቦቱ {len(SOURCE_CHANNELS)} ቻናሎችን መከታተል ጀምሯል...")
client.start()
client.run_until_disconnected()
