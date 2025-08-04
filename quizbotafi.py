
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPoll, ReplyInlineMarkup
import logging, sys, os
from flask import Flask
import threading, asyncio, time
import re
import requests
import json

api_id = 14505668
api_hash = '261ac36c87abce0e7f47504070b14dc2'
session_name = 'quiz_logic_bot'
SOURCE_GROUP_USERNAME = 'FUNToken_OfficialChat'
TARGET_CHANNEL_ID = -1002730596164
QUIZ_IDENTIFIERS = [
    '🧠 quick quiz! – answer within',
    '🧩 emoji puzzle! – answer within',
    'reward: 1 wheel of fortune',
    'choose the correct option below'
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('quiz_detection.log'), logging.StreamHandler(sys.stdout)]
)

client = TelegramClient(session_name, api_id, api_hash)

async def get_ai_answer(question, options):
    """Get AI answer using Gemini HTTP API"""
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logging.error("GEMINI_API_KEY not found in environment")
            return None
            
        prompt = f"""
        You are an expert quiz solver. Answer this quiz question by selecting the most accurate option.
        
        Question: {question}
        
        Options:
        {chr(10).join([f"{chr(65+i)}) {opt}" for i, opt in enumerate(options)])}
        
        Provide your answer in this exact format:
        ANSWER: [Letter] - [Option text]
        EXPLANATION: [Brief explanation why this is correct]
        
        Be confident and choose the best answer.
        """
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if 'candidates' in data and len(data['candidates']) > 0:
                content = data['candidates'][0]['content']['parts'][0]['text']
                return content.strip()
            else:
                logging.error("No candidates in Gemini response")
                return None
        else:
            logging.error(f"Gemini API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logging.error(f"AI answer generation failed: {e}")
        return None

async def extract_and_send_quiz(event, source):
    global bot_status
    bot_status["last_activity"] = time.time()
    
    msg = event.message
    raw = msg.raw_text or ''
    unwanted = ['reward:', 'make sure you add', 'please do not share answers']
    question_lines = [l for l in raw.splitlines() if not any(p in l.lower() for p in unwanted)]
    question = '\n'.join(question_lines).strip()

    options = []
    if msg.reply_markup and isinstance(msg.reply_markup, ReplyInlineMarkup):
        for row in msg.reply_markup.rows:
            for btn in row.buttons:
                if hasattr(btn, 'text') and btn.text.strip():
                    options.append(btn.text.strip())
    elif isinstance(msg.media, MessageMediaPoll) and msg.media.poll.quiz:
        for opt in msg.media.poll.options:
            options.append(opt.text)

    prefixes = ['🅐','🅑','🅒','🅓','🅔','🅕','🅖','🅗']
    clean_opts = []
    for opt in options:
        t = opt.strip()
        while any(t.startswith(p) for p in prefixes):
            t = t[1:].lstrip()
        if t:
            clean_opts.append(t)

    if len(clean_opts) < 2:
        logging.warning(f"Quiz ID={msg.id} skipped: only {len(clean_opts)} option(s)")
        return

    formatted = '\n'.join(f"{prefixes[i]}  {opt}" for i, opt in enumerate(clean_opts))
    quiz_msg = (
        "🧩 QUIZ AGYAAAAA 🏃🏻🏃🏼‍♀️\n"
        f"📝 Question:\n{question}\n\n"
        f"📋 Options:\n{formatted}\n\n"
        f"🔗 View Original: https://t.me/{SOURCE_GROUP_USERNAME}/{msg.id}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🕊️ AFFIYA COMMUNITY 🕊️ | 🤖 AFIYA ROBOT 🤖"
    )

    await client.send_message(TARGET_CHANNEL_ID, quiz_msg, link_preview=True)
    bot_status["total_quizzes"] += 1
    logging.info(f"Quiz ID={msg.id} reposted [source={source}]")

    # Get AI answer
    ai_response = await get_ai_answer(question, clean_opts)
    
    if ai_response:
        # Wait 5 seconds before posting answer
        await asyncio.sleep(5)
        
        # Extract answer from AI response
        answer_match = re.search(r'ANSWER:\s*([A-H])\s*-\s*(.*?)(?:\n|$)', ai_response, re.IGNORECASE)
        explanation_match = re.search(r'EXPLANATION:\s*(.*?)(?:\n|$)', ai_response, re.IGNORECASE | re.DOTALL)
        
        if answer_match:
            letter = answer_match.group(1).upper()
            option_text = answer_match.group(2).strip()
            
            answer_msg = (
                "ANSWER PROVIDED BY GEMINI AI⚡️\n\n"
                f"✅️ 𝐂𝐨𝐫𝐫𝐞𝐜𝐭 𝐂𝐡𝐨𝐢𝐜𝐞: ({letter}) {option_text}\n\n"
                "●⁠♡A⁠♡ㅤAFFI KI COMMUNITY ●⁠♡A⁠♡"
            )
            
            await client.send_message(TARGET_CHANNEL_ID, answer_msg)
            logging.info(f"AI Answer posted for Quiz ID={msg.id}: {letter}")
        else:
            # Fallback answer format
            answer_msg = (
                "ANSWER PROVIDED BY GEMINI AI⚡️\n\n"
                f"🤖 AI Analysis:\n{ai_response}\n\n"
                "●⁠♡A⁠♡ㅤAFFI KI COMMUNITY ●⁠♡A⁠♡"
            )
            await client.send_message(TARGET_CHANNEL_ID, answer_msg)
            logging.info(f"AI Analysis posted for Quiz ID={msg.id}")

@client.on(events.NewMessage(chats=SOURCE_GROUP_USERNAME))
async def handler(event):
    msg = event.message
    text = (msg.raw_text or '').lower()
    has_buttons = bool(msg.reply_markup)
    has_poll = isinstance(msg.media, MessageMediaPoll)
    if has_poll and msg.media.poll.quiz:
        await extract_and_send_quiz(event, 'poll')
    elif has_buttons and sum(kw in text for kw in QUIZ_IDENTIFIERS) >= 2:
        await extract_and_send_quiz(event, 'buttons')
    elif all(kw in text for kw in QUIZ_IDENTIFIERS):
        await extract_and_send_quiz(event, 'text')

async def run_bot():
    global bot_status
    
    await client.connect()
    if not await client.is_user_authorized():
        phone = os.getenv('TG_PHONE')
        if not phone:
            logging.error("TG_PHONE environment variable not set")
            bot_status["errors"] += 1
            return
        
        # For production, session should be pre-authenticated
        # Run this once interactively to create session, then deploy
        logging.error("Bot not authorized. Please authenticate session first.")
        bot_status["errors"] += 1
        return
    
    bot_status["connected"] = True
    bot_status["last_activity"] = time.time()
    print('🤖 AI Quiz Bot started with auto-answering!')
    
    try:
        await client.run_until_disconnected()
    finally:
        bot_status["connected"] = False

async def safe_run_bot():
    retry_count = 0
    max_retries = 5
    
    while True:
        try:
            print('🔄 AI Quiz Bot thread launched')
            await run_bot()
            retry_count = 0  # Reset on successful run
        except Exception as e:
            retry_count += 1
            wait_time = min(60, 10 * retry_count)  # Exponential backoff, max 60s
            logging.error(f"Bot crashed (attempt {retry_count}): {e}")
            
            if retry_count >= max_retries:
                logging.critical(f"Bot failed {max_retries} times, waiting 5 minutes...")
                await asyncio.sleep(300)  # Wait 5 minutes before trying again
                retry_count = 0
            else:
                logging.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)

def start_bot():
    asyncio.run(safe_run_bot())

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ AI Quiz Bot is alive and auto-answering!"

bot_status = {
    "connected": False,
    "last_activity": None,
    "total_quizzes": 0,
    "errors": 0
}

@app.route('/status')
def status():
    return {
        "status": "running" if bot_status["connected"] else "disconnected",
        "features": ["quiz_detection", "ai_answering", "self_healing"],
        "ai_model": "gemini-1.5-flash",
        "bot_connected": bot_status["connected"],
        "last_activity": bot_status["last_activity"],
        "total_quizzes_processed": bot_status["total_quizzes"],
        "total_errors": bot_status["errors"]
    }

@app.route('/health')
def health():
    if bot_status["connected"]:
        return {"status": "healthy"}, 200
    else:
        return {"status": "unhealthy", "reason": "bot_disconnected"}, 503

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == '__main__':
    threading.Thread(target=start_bot).start()
    run_flask()
