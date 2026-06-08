import sqlite3
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN = "8935997239:AAF8bgGYzXz01NgxUb-0Ebfgdy4pRIyJmVI"

# ================= DATABASE =================
conn = sqlite3.connect("quiz.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    score INTEGER DEFAULT 0
)
""")
conn.commit()

def add_user(uid):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, score) VALUES (?,0)", (uid,))
    conn.commit()

def add_point(uid):
    cursor.execute("UPDATE users SET score = score + 1 WHERE user_id=?", (uid,))
    conn.commit()

def get_score(uid):
    cursor.execute("SELECT score FROM users WHERE user_id=?", (uid,))
    r = cursor.fetchone()
    return r[0] if r else 0

def get_top():
    cursor.execute("SELECT user_id, score FROM users ORDER BY score DESC LIMIT 10")
    return cursor.fetchall()

def get_stats():
    cursor.execute("SELECT COUNT(*), SUM(score), AVG(score) FROM users")
    return cursor.fetchone()

# ================= QUESTIONS =================
questions = [
    {"q": "She ___ her room every day.", "o": ["clean", "cleans", "cleaned", "cleaning"], "c": 1},
    {"q": "They ___ basketball now.", "o": ["play", "plays", "are playing", "played"], "c": 2},
    {"q": "I ___ him yesterday.", "o": ["meet", "met", "meeting", "meets"], "c": 1},
    {"q": "We ___ dinner when he arrived.", "o": ["were having", "have", "had", "having"], "c": 2},
    {"q": "He ___ his homework already.", "o": ["has finished", "finished", "finish", "finishing"], "c": 0},
    {"q": "You ___ wear a seatbelt.", "o": ["must", "can", "may", "could"], "c": 0},
    {"q": "Look! The dog ___.", "o": ["run", "runs", "is running", "ran"], "c": 2},
    {"q": "The train ___ at 8 every morning.", "o": ["leave", "leaves", "left", "leaving"], "c": 1},
]

user_state = {}

# ================= MENU =================
menu = ReplyKeyboardMarkup(
    [
        ["📝 Start Quiz"],
        ["🎯 5 Questions", "🎯 10 Questions"],
        ["🎯 20 Questions", "🎯 All Questions"],
        ["⭐ My Score", "🏆 Top 10"],
        ["📊 Stats"]
    ],
    resize_keyboard=True
)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_user(update.effective_user.id)
    await update.message.reply_text("👋 Welcome to Quiz Bot!", reply_markup=menu)

# ================= HANDLE MENU =================
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    if text == "📝 Start Quiz":
        user_state[uid] = {"i": 0, "s": 0, "q": questions.copy()}
        random.shuffle(user_state[uid]["q"])
        await send_question(update, context)

    elif text.startswith("🎯"):
        num = text.split()[1]
        if num == "All":
            q_list = questions.copy()
        else:
            q_list = questions.copy()[:int(num)]

        random.shuffle(q_list)

        user_state[uid] = {"i": 0, "s": 0, "q": q_list}
        await send_question(update, context)

    elif text == "⭐ My Score":
        await update.message.reply_text(f"⭐ Score: {get_score(uid)}")

    elif text == "🏆 Top 10":
        top = get_top()
        msg = "🏆 TOP USERS\n\n"
        for i, (u, s) in enumerate(top, 1):
            msg += f"{i}. {u} - {s}\n"
        await update.message.reply_text(msg)

    elif text == "📊 Stats":
        u, t, a = get_stats()
        await update.message.reply_text(
            f"📊 STATS\nUsers: {u}\nTotal: {t}\nAvg: {round(a or 0,2)}"
        )

# ================= QUESTION =================
async def send_question(update, context):
    uid = update.effective_user.id
    data = user_state[uid]

    i = data["i"]

    if i >= len(data["q"]):
        score = data["s"]
        add_point(uid)
        await update.message.reply_text(f"🏁 Finished!\nScore: {score}/{len(data['q'])}")
        return

    q = data["q"][i]

    keyboard = [
        [InlineKeyboardButton(opt, callback_data=str(x))]
        for x, opt in enumerate(q["o"])
    ]

    await update.message.reply_text(
        f"❓ Q{i+1}: {q['q']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    asyncio.create_task(timer(uid, context))

# ================= TIMER =================
async def timer(uid, context):
    await asyncio.sleep(15)

    if uid not in user_state:
        return

    data = user_state[uid]

    if "answered" in data and data["answered"]:
        return

    data["i"] += 1
    await context.bot.send_message(uid, "⏰ Time is up!")

    if data["i"] < len(data["q"]):
        await send_next(uid, context)
    else:
        await finish(uid, context)

# ================= ANSWER =================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    data = user_state[uid]

    data["answered"] = True

    i = data["i"]
    question = data["q"][i]

    if int(q.data) == question["c"]:
        data["s"] += 1
        text = "✅ Correct!"
    else:
        text = "❌ Wrong!"

    await q.edit_message_text(text)

    data["i"] += 1

    if data["i"] < len(data["q"]):
        await send_next(uid, context)
    else:
        await finish(uid, context)

# ================= NEXT =================
async def send_next(uid, context):
    data = user_state[uid]
    i = data["i"]
    q = data["q"][i]

    keyboard = [
        [InlineKeyboardButton(opt, callback_data=str(x))]
        for x, opt in enumerate(q["o"])
    ]

    await context.bot.send_message(uid, f"❓ Q{i+1}: {q['q']}", reply_markup=InlineKeyboardMarkup(keyboard))
    asyncio.create_task(timer(uid, context))

# ================= FINISH =================
async def finish(uid, context):
    score = user_state[uid]["s"]
    add_point(uid)
    await context.bot.send_message(uid, f"🏁 Finished!\nScore: {score}/{len(user_state[uid]['q'])}")

# ================= MAIN =================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    app.add_handler(CallbackQueryHandler(button))

    print("🚀 BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
