from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import os

# Put your Bot Token here
BOT_TOKEN = "7940607419:AAHmVBXOccZ5fWkE7HxGK42ij8zSFr8lBAk"

# ✅ Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        "Welcome to OTO Tournament Bot 🎮\n"
        "Use this bot to create your profile, join tournaments, "
        "and access the mini app."
    )

# ✅ Auto alive system
async def alive_message(app: Application):
    while True:
        try:
            # Replace with your moderator group/chat ID
            group_id = -1001234567890  
            await app.bot.send_message(
                chat_id=group_id,
                text="✅ Bot is alive and running..."
            )
        except Exception as e:
            print("Alive error:", e)
        await asyncio.sleep(3600)  # sends every 1 hour

# ✅ Main Function
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", start))

    # Run bot
    app.run_polling()

if __name__ == "__main__":
    main()
