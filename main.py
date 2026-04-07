import os
import asyncio
import re
import google.generativeai as genai
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

# --- CONFIGURATION (Railway Variables) ---
# ቫሪያብሎቹ ባዶ ቢሆኑ እንኳ ቦቱ እንዳይዘጋ ጥንቃቄ ተደርጓል
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

# የሚከታተላቸው ቻናሎች ዝርዝር (እዚህ ጋር ጨምር)
SOURCE_CHANNELS = ['@forexfactory_news'] 

# Gemini Setup
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def clean_all_entities(event_msg):
    """ሁሉንም አይነት የተደበቁ ሊንኮች፣ ዩዘርኔሞች እና ማስታወቂያዎች ያጠፋል"""
    text = event_msg.text or ""
    entities = event_msg.entities
    if not entities:
        return re.sub(r'(https?://[^\s]+|t\.me/[^\s]+|@[^\s]+)', '', text).strip()
    
    offsets = []
    for ent in entities:
        e_type = type(ent).__name__
        # ሊንክ፣ ሜንሽን ወይም ቦት ኮማንድ ካለ ቦታውን ይይዛል
        if any(x in e_type for x in ['Url', 'Mention', 'BotCommand', 'TextUrl']):
            offsets.append((ent.offset, ent.length))
            
    chars = list(text)
    # ጽሁፉ እንዳይዛባ ከበስተጀርባ ወደ ፊት ማጽዳት
    for offset, length in sorted(offsets, reverse=True):
        chars[offset : offset + length] = ""
    
    cleaned = "".join(chars)
    return re.sub(r'\s+', ' ', cleaned).strip()

async def get_ai_decision(cleaned_text, message_obj):
    """የተሟላ የእንግሊዝኛ Prompt - ለተሻለ ውጤት"""
    prompt = """
    Act as the Expert Owner and Lead Editor of a professional Forex Analysis channel.
    Your task is to analyze and rewrite market news as the original author.

    ### STRICT INSTRUCTIONS:
    1. **Content Control:** - ONLY accept high-impact news (CPI, Interest Rates, NFP, etc.).
       - REJECT any Price Charts, Candlestick images, or Trading Signals.
       - If the content is not high-quality news, reply ONLY with "IGNORE".

    2. **Anonymization:** - Remove all source names, watermarks, and @usernames.
       - Do not mention other channels or external links.

    3. **Time Conversion (Ethiopian Standard):**
       - Convert any detected time to Ethiopian 12-hour format (GMT+3).
       - Examples: 8:00 PM -> 2:00 ሰዓት, 9:30 AM -> 3:30 ሰዓት, 1:00 AM -> 7:00 ሰዓት.

    4. **Output Format:**
       🔴 **High-Impact Market Update**
       
       📌 **Event:** [Brief Summary]
       ⏰ **Ethiopian Time:** [Converted Time]
       ⚠️ **Impact:** [High/Medium]
       📝 **Note:** [A short professional insight]
    """
    
    content = [prompt, f"Input Text: {cleaned_text}"]
    
    # ፎቶ ካለው AIው እንዲያነበው መላክ
    if message_obj.photo:
        try:
            path = await message_obj.download_media()
            image_data = genai.upload_file(path)
            content.append(image_data)
            os.remove(path)
        except:
            pass
        
    try:
        await asyncio.sleep(2) # ተረጋግቶ እንዲሰራ
        response = model.generate_content(content)
        res_text = response.text
        if "IGNORE" in res_text.upper():
            return None
        return res_text
    except Exception as e:
        print(f"AI Error: {e}")
        return None

@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def main_handler(event):
    # 1. መጀመሪያ ሊንኮችን በቴሌግራም ሲስተም ማጽዳት
    base_text = clean_all_entities(event.message)
    
    # 2. በ AI ማስገምገም
    print("AI እያረጋገጠ ነው...")
    final_post = await get_ai_decision(base_text, event.message)
    
    if final_post:
        # 3. ለአንተ ለሙከራ ይልካል
        btns = [
            [Button.inline("✅ አጽድቅ (Post)", data="publish")],
            [Button.inline("❌ አትፖስተው (Delete)", data="cancel")]
        ]
        if event.message.photo:
            await client.send_file(MY_ID, event.message.media, caption=final_post, buttons=btns)
        else:
            await client.send_message(MY_ID, final_post, buttons=btns)

@client.on(events.CallbackQuery)
async def callback_handler(event):
    if event.sender_id != MY_ID: return
    
    msg = await event.get_message()
    if event.data == b"publish":
        # ወደ ቻናልህ ፖስት ያደርጋል
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

print("ቦቱ ስራ ጀምሯል። ቻናሎችን እየተከታተለ ነው...")
client.start()
client.run_until_disconnected()
