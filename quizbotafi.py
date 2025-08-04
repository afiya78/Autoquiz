from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPoll, ReplyInlineMarkup
import logging, sys, os
from flask import Flask, jsonify
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', handlers=[logging.FileHandler('quiz_detection.log'), logging.StreamHandler(sys.stdout)])
client = TelegramClient(session_name, api_id, api_hash)

async def get_ai_answer(question, options):
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logging.error("GEMINI_API_KEY not found")
            return None
        prompt = f"""You are an expert quiz solver. Answer this quiz question by selecting the most accurate option.\nQuestion: {question}\nOptions:\n{chr(10).join([f'{chr(65+i)}) {opt}' for i,opt in enumerate(options)])}\nProvide your answer in this exact format:\nANSWER: [Letter] - [Option text]\nEXPLANATION: [Brief explanation why this is correct]"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        headers = {"Content-Type": "application/json"}
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            d = r.json()
            if 'candidates' in d and d['candidates']:
                return d['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            logging.error(f"Gemini API error: {r.status_code} - {r.text}")
    except Exception as e:
        logging.error(f"AI error: {e}")
    return None

async def extract_and_send_quiz(event, source):
    global bot_status
    bot_status["last_activity"] = time.time()
    m = event.message
    raw = m.raw_text or ''
    unwanted = ['reward:', 'make sure you add', 'please do not share answers']
    question = '\n'.join([l for l in raw.splitlines() if not any(p in l.lower() for p in unwanted)]).strip()
    opts = []
    if m.reply_markup and isinstance(m.reply_markup, ReplyInlineMarkup):
        for row in m.reply_markup.rows:
            for b in row.buttons:
                if hasattr(b, 'text') and b.text.strip():
                    opts.append(b.text.strip())
    elif isinstance(m.media, MessageMediaPoll) and m.media.poll.quiz:
        for o in m.media.poll.options:
            opts.append(o.text)
    pref = ['🅐','🅑','🅒','🅓','🅔','🅕','🅖','🅗']
    clean = []
    for o in opts:
        t = o.strip()
        while any(t.startswith(p) for p in pref):
            t = t[1:].lstrip()
        if t:
            clean.append(t)
    if len(clean) < 2:
        logging.warning(f"Quiz ID={m.id} skipped: only {len(clean)} option(s)")
        return
    formatted = '\n'.join(f"{pref[i]}  {o}" for i,o in enumerate(clean))
    quiz_msg = ("🧩 QUIZ AGYAAAAA 🏃🏻🏃🏼‍♀️\n" f"📝 Question:\n{question}\n\n" f"📋 Options:\n{formatted}\n\n" f"🔗 View Original: https://t.me/{SOURCE_GROUP_USERNAME}/{m.id}\n" "━━━━━━━━━━━━━━━━━━━━━━━\n🕊️ AFFIYA COMMUNITY 🕊️ | 🤖 AFIYA ROBOT 🤖")
    await client.send_message(TARGET_CHANNEL_ID, quiz_msg, link_preview=True)
    bot_status["total_quizzes"] += 1
    logging.info(f"Quiz ID={m.id} reposted")
    ai = await get_ai_answer(question, clean)
    if ai:
        await asyncio.sleep(5)
        match = re.search(r'ANSWER:\s*([A-H])\s*-\s*(.*?)($|\n)', ai, re.IGNORECASE)
        if match:
            l = match.group(1).upper()
            txt = match.group(2).strip()
            ans = f"ANSWER PROVIDED BY GEMINI AI⚡️\n\n✅️ Correct Choice: ({l}) {txt}\n\n●⁠♡A⁠♡ㅤAFFI KI COMMUNITY ●⁠♡A⁠♡"
        else:
            ans = f"ANSWER PROVIDED BY GEMINI AI⚡️\n\n🤖 AI Analysis:\n{ai}\n\n●⁠♡A⁠♡ㅤAFFI KI COMMUNITY ●⁠♡A⁠♡"
        await client.send_message(TARGET_CHANNEL_ID, ans)
        logging.info(f"AI Answer posted for Quiz ID={m.id}")

@client.on(events.NewMessage(chats=SOURCE_GROUP_USERNAME))
async def handler(e):
    t = (e.message.raw_text or '').lower()
    if isinstance(e.message.media, MessageMediaPoll) and e.message.media.poll.quiz:
        await extract_and_send_quiz(e, 'poll')
    elif e.message.reply_markup and sum(k in t for k in QUIZ_IDENTIFIERS) >= 2:
        await extract_and_send_quiz(e, 'buttons')
    elif all(k in t for k in QUIZ_IDENTIFIERS):
        await extract_and_send_quiz(e, 'text')

async def run_bot():
    global bot_status
    await client.connect()
    if not await client.is_user_authorized():
        logging.error("Bot not authorized. Authenticate locally and include session file.")
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
    r = 0
    while True:
        try:
            print('🔄 AI Quiz Bot thread launched')
            await run_bot()
            r = 0
        except Exception as e:
            r += 1
            d = min(60, 10 * r)
            logging.error(f"Bot crashed (attempt {r}): {e}")
            await asyncio.sleep(d if r < 5 else 300)
            if r >= 5:
                r = 0

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ AI Quiz Bot is alive and auto-answering!"

bot_status = {"connected": False, "last_activity": None, "total_quizzes": 0, "errors": 0}

@app.route('/status')
def status():
    return jsonify({
        "status": "running" if bot_status["connected"] else "disconnected",
        "features": ["quiz_detection", "ai_answering", "self_healing"],
        "ai_model": "gemini-1.5-flash",
        "last_activity": bot_status["last_activity"],
        "total_quizzes": bot_status["total_quizzes"],
        "errors": bot_status["errors"]
    })

@app.route('/health')
def health():
    if bot_status["connected"]:
        return jsonify({"status": "healthy"}), 200
    return jsonify({"status": "unhealthy", "reason": "bot_disconnected"}), 503

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    threading.Thread(target=lambda: asyncio.run(safe_run_bot())).start()
    run_flask()
    
