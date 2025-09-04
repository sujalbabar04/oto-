import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler
)

# ------------------- CONFIG -------------------
BOT_TOKEN = "7940607419:AAHmVBXOccZ5fWkE7HxGK42ij8zSFr8lBAk"
MODERATOR_GROUP_ID = -4687499589  # replace with your group ID
MINI_APP_URL = "https://oto-tournament.vercel.app"  # replace with your frontend link

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ------------------- STATES -------------------
ASK_NAME, ASK_GAME_ID, ASK_LEVEL, ASK_STATE = range(4)

# ------------------- START -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"👋 Hello {user.first_name or 'Gamer'}!\n\n"
        "Welcome to **OTO Tournament Bot** 🎮\n\n"
        "Use this bot to:\n"
        "🏆 Join tournaments\n"
        "💰 Manage your wallet\n"
        "🛒 Shop in the store\n"
        "🥇 View leaderboard\n"
        "⭐ Get VIP perks\n\n"
        "Choose from the menu below 👇"
    )

    keyboard = [
        [InlineKeyboardButton("🎮 Create Profile", callback_data="create_profile")],
        [InlineKeyboardButton("🏆 View Tournaments", url=MINI_APP_URL + "/tournaments")],
        [InlineKeyboardButton("💰 Wallet", url=MINI_APP_URL + "/wallet")],
        [InlineKeyboardButton("🛒 Store", url=MINI_APP_URL + "/store")],
        [InlineKeyboardButton("🥇 Leaderboard", url=MINI_APP_URL + "/leaderboard")],
        [InlineKeyboardButton("⭐ VIP Membership", url=MINI_APP_URL + "/vip")],
        [InlineKeyboardButton("🎁 Referral Program", callback_data="referral")],
        [InlineKeyboardButton("📞 Contact Us", callback_data="contact")]
    ]

    if update.message:
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# ------------------- CREATE PROFILE -------------------
async def create_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("👤 Let's create your profile!\n\nWhat's your **Name**?")
    return ASK_NAME

async def ask_game_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("🎮 Enter your **Game ID**:")
    return ASK_GAME_ID

async def ask_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["game_id"] = update.message.text
    await update.message.reply_text("🔥 Enter your **Level**:")
    return ASK_LEVEL

async def ask_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["level"] = update.message.text
    await update.message.reply_text("🌍 Enter your **State**:")
    return ASK_STATE

async def save_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = update.message.text

    profile_text = (
        "✅ *Profile Created!*\n\n"
        f"👤 Name: {context.user_data['name']}\n"
        f"🎮 Game ID: {context.user_data['game_id']}\n"
        f"🔥 Level: {context.user_data['level']}\n"
        f"🌍 State: {context.user_data['state']}\n"
    )

    # Send to user
    await update.message.reply_text(profile_text, parse_mode="Markdown")

    # Forward to Moderator Group
    await context.bot.send_message(
        chat_id=MODERATOR_GROUP_ID,
        text=f"📥 *New Profile Created!*\n\n{profile_text}",
        parse_mode="Markdown"
    )

    return ConversationHandler.END

# ------------------- CONTACT -------------------
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📞 For support:\n\nTelegram: @yourusername\nEmail: support@ototournament.com"
    )

# ------------------- REFERRAL -------------------
async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    referral_link = f"https://t.me/{context.bot.username}?start={user.id}"
    await query.message.reply_text(
        f"🎁 *Referral Program*\n\n"
        f"Share this link with friends:\n{referral_link}\n\n"
        f"👉 Earn OTO Coins when they join!",
        parse_mode="Markdown"
    )

# ------------------- CANCEL -------------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Profile creation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ------------------- ALIVE CHECK -------------------
async def alive(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=MODERATOR_GROUP_ID, text="✅ OTO Bot is Alive!")

# ------------------- MAIN -------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Start command
    app.add_handler(CommandHandler("start", start))

    # Contact handler
    app.add_handler(CallbackQueryHandler(contact, pattern="contact"))

    # Referral handler
    app.add_handler(CallbackQueryHandler(referral, pattern="referral"))

    # Profile creation handler
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_profile_start, pattern="create_profile")],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_game_id)],
            ASK_GAME_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_level)],
            ASK_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_state)],
            ASK_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_profile)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)

    # Auto alive job (every 10 mins)
    job_queue = app.job_queue
    job_queue.run_repeating(alive, interval=600, first=5)

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
