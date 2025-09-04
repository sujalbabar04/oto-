import logging
import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler
)

# ------------------- CONFIG -------------------
BOT_TOKEN = "7940607419:AAHmVBXOccZ5fWkE7HxGK42ij8zSFr8lBAk"
MODERATOR_GROUP_ID = -4687499589
MINI_APP_URL = "https://oto-tournament.vercel.app"

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------- STATES -------------------
ASK_NAME, ASK_GAME_ID, ASK_LEVEL, ASK_STATE = range(4)

# ------------------- START -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        welcome_text = (
            f"👋 Hello {user.first_name or 'Gamer'}!\n\n"
            "Welcome to *OTO Tournament Bot* 🎮\n\n"
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
            [InlineKeyboardButton("🏆 View Tournaments", url=f"{MINI_APP_URL}/tournaments")],
            [InlineKeyboardButton("💰 Wallet", url=f"{MINI_APP_URL}/wallet")],
            [InlineKeyboardButton("🛒 Store", url=f"{MINI_APP_URL}/store")],
            [InlineKeyboardButton("🥇 Leaderboard", url=f"{MINI_APP_URL}/leaderboard")],
            [InlineKeyboardButton("⭐ VIP Membership", url=f"{MINI_APP_URL}/vip")],
            [InlineKeyboardButton("🎁 Referral Program", callback_data="referral")],
            [InlineKeyboardButton("📞 Contact Us", callback_data="contact")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.message:
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        elif update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.edit_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error in start function: {e}")

# ------------------- CREATE PROFILE -------------------
async def create_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "👤 Let's create your profile!\n\nWhat's your *Name*?",
        parse_mode="Markdown"
    )
    return ASK_NAME

async def ask_game_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("🎮 Enter your *Game ID*:", parse_mode="Markdown")
    return ASK_GAME_ID

async def ask_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["game_id"] = update.message.text.strip()
    await update.message.reply_text("🔥 Enter your *Level*:", parse_mode="Markdown")
    return ASK_LEVEL

async def ask_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["level"] = update.message.text.strip()
    await update.message.reply_text("🌍 Enter your *State*:", parse_mode="Markdown")
    return ASK_STATE

async def save_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["state"] = update.message.text.strip()
        user = update.effective_user

        profile_text = (
            "✅ *Profile Created Successfully!*\n\n"
            f"👤 *Name:* {context.user_data.get('name', 'N/A')}\n"
            f"🎮 *Game ID:* {context.user_data.get('game_id', 'N/A')}\n"
            f"🔥 *Level:* {context.user_data.get('level', 'N/A')}\n"
            f"🌍 *State:* {context.user_data.get('state', 'N/A')}\n"
            f"👤 *User ID:* {user.id}\n"
            f"📱 *Username:* @{user.username or 'N/A'}"
        )

        # Send confirmation to user
        await update.message.reply_text(profile_text, parse_mode="Markdown")

        # Try to forward to moderator group
        try:
            await context.bot.send_message(
                chat_id=MODERATOR_GROUP_ID,
                text=f"📥 *New Profile Created!*\n\n{profile_text}",
                parse_mode="Markdown"
            )
        except Exception as mod_error:
            logger.error(f"Failed to send message to moderator group: {mod_error}")

        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in save_profile: {e}")
        return ConversationHandler.END

# ------------------- CONTACT -------------------
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    contact_text = (
        "📞 *Contact Support*\n\n"
        "For any questions or issues:\n\n"
        "📱 Telegram: @yourusername\n"
        "📧 Email: support@ototournament.com\n"
        "🕒 Support Hours: 9 AM - 6 PM (Mon-Fri)"
    )
    await query.message.reply_text(contact_text, parse_mode="Markdown")

# ------------------- REFERRAL -------------------
async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    
    try:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        referral_link = f"https://t.me/{bot_username}?start={user.id}"
    except:
        referral_link = "Contact admin for referral link"
        
    referral_text = (
        "🎁 *Referral Program*\n\n"
        f"Share this link with friends:\n`{referral_link}`\n\n"
        "💰 *Benefits:*\n"
        "• Earn OTO Coins for each referral\n"
        "• Get bonus rewards\n"
        "• Unlock exclusive tournaments\n\n"
        "👉 Start sharing and earning now!"
    )
    await query.message.reply_text(referral_text, parse_mode="Markdown")

# ------------------- CANCEL -------------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Profile creation cancelled.\n\nUse /start to return to main menu.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# ------------------- ERROR HANDLER -------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

# ------------------- MAIN -------------------
def main():
    try:
        logger.info("Starting OTO Tournament Bot...")
        
        # Create application using ApplicationBuilder (older method that works better on some platforms)
        application = ApplicationBuilder().token(BOT_TOKEN).build()

        # Add error handler
        application.add_error_handler(error_handler)

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        
        # Add callback query handlers
        application.add_handler(CallbackQueryHandler(contact, pattern="^contact$"))
        application.add_handler(CallbackQueryHandler(referral, pattern="^referral$"))

        # Add conversation handler for profile creation
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(create_profile_start, pattern="^create_profile$")],
            states={
                ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_game_id)],
                ASK_GAME_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_level)],
                ASK_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_state)],
                ASK_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_profile)]
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )
        application.add_handler(conv_handler)

        # Start the bot
        logger.info("🤖 Bot is starting...")
        print("🤖 OTO Tournament Bot is running!")
        
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"Critical error starting bot: {e}")
        print(f"❌ Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()
