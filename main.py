import os
import asyncio
import re
import google.generativeai as genai
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

# --- CONFIGURATION (Environment Variables) ---
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
SESSION_STRING = os.getenv('SESSION_STRING')
GEMINI_KEY = os.getenv('GEMINI_KEY')
MY_ID = int(os.getenv('MY_ID')) 
MY_CHANNEL = os.getenv('MY_CHANNEL') 

# የሚከታተላቸው ቻናሎች (እዚህ ጋር የቻናሎቹን @username ይጨምሩ)
SOURCE_CHANNELS = ['@forexfactory_news'] 

# Gemini Setup
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def clean_all_entities(event_msg):
    """በቴሌግራም ሲስተም ውስጥ ያሉ ማንኛውንም የተደበቁ ሊንኮችና ምልክቶች ያጠፋል"""
    text = event_msg.text or ""
    entities = event_msg.entities
    if not entities:
        return re.sub(r'(https?://[^\s]+|t\.me/[^\s]+|@[^\s]+)', '', text).strip()
    
    offsets = []
    for ent in entities:
        e_type = type(ent).__name__
        if any(x in e_type for x in ['Url', 'Mention', 'BotCommand']):
            offsets.append((ent.offset, ent.length))
            
    chars = list(text)
    for offset, length in sorted(offsets, reverse=True):
        chars[offset : offset + length] = ""
    
    return re.sub(r'\s+', ' ', "".join(chars)).strip()

async def get_ai_decision(cleaned_text, message_obj):
    """የተስተካከለው የእንግሊዝኛ Prompt"""
    prompt = """
    Act as the Expert Owner and Lead Editor of a premium Forex Analysis channel. 
    Your goal is to process incoming market news and rewrite them in your unique, professional brand voice.

    ### CRITICAL RULES:
    1. **Content Filtering:**
       - ONLY allow high-impact fundamental news (e.g., CPI, Interest Rates, FOMC, Geopolitical events, NFP).
       - STRICTLY REJECT any posts containing Price Charts, Technical Analysis (Candlesticks/Indicators), or Trading Signals.
       - If the content is not a significant news event, respond only with the word: "IGNORE".

    2. **Zero-Trace Policy (Anonymization):**
       - You must act as the original creator. Remove ALL external references (@usernames, links, source names).

    3. **Time Conversion (Ethiopian Standard):**
       - Detect any timestamps (e.g., EST, GMT, UTC, or AM/PM).
       - Convert the time to the 12-hour Ethiopian local time format (GMT+3).
       - Example: 8:30 PM (20:30) becomes "2:30 ሰዓት". 10:00 AM becomes "4:00 ሰዓት".

    4. **Output Structure:**
       🔴 **High-Impact Market News Update**
       
       📌 **Event:** [Summary of the news]
       ⏰ **Local Time:** [Converted Ethiopian Time]
       ⚠️ **Impact Level:** [High/Medium Impact for USD, GOLD, etc.]
       📝 **Analysis:** [A professional one-sentence explanation]

    If the content is irrelevant, say "IGNORE".
    """
    
    content = [prompt, cleaned_text]
    if message_obj.photo:
        path = await message_obj.download_media()
        image_data = genai.upload_file(path)
        content.append(image_data)
        os.remove(path)
        
    try:
        await asyncio.sleep(2) # ተረጋግቶ እንዲሰራ
        response = model.generate_content(content)
        return None if "IGNORE" in response.text.upper() else response.text
    except:
        return None

@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def main_handler(event):
    # 1. ሊንኮችን በፕሮግራም ማጽዳት
    base_text = clean_all_entities(event.message)
    
    # 2. በ AI ማስፈተሽ
    final_post = await get_ai_decision(base_text, event.message)
    
    if final_post:
        # 3. ለአንተ ለሙከራ መላክ
        btns = [[Button.inline("✅ Post Now", data="pub")], [Button.inline("❌ Discard", data="del")]]
        if event.message.photo:
            await client.send_file(MY_ID, event.message.media, caption=final_post, buttons=btns)
        else:
            await client.send_message(MY_ID, final_post, buttons=btns)

@client.on(events.CallbackQuery)
async def buttons(event):
    if event.sender_id != MY_ID: return
    msg = await event.get_message()
    if event.data == b"pub":
        if msg.photo:
            await client.send_file(MY_CHANNEL, msg.media, caption=msg.text)
        else:
            await client.send_message(MY_CHANNEL, msg.text)
        await event.edit("🚀 Posted to channel!")
    else:
        await event.delete()

print("Owner-Style Bot is running...")
client.start()
client.run_until_disconnected()
