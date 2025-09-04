import logging
import os
import re
from datetime import datetime, timedelta
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
MODERATOR_GROUP_ID = -4687499589
MINI_APP_URL = "https://oto-tournament.vercel.app"

# Admin user IDs (replace with actual admin Telegram IDs)
ADMIN_IDS = [5633830334]  # Add your admin user IDs here

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------- STATES -------------------
# Profile creation states
ASK_NAME, ASK_GAME_ID, ASK_LEVEL, ASK_STATE = range(4)

# Admin tournament creation states
ADMIN_TOURNAMENT_NAME, ADMIN_GAME_TYPE, ADMIN_MAP, ADMIN_GAME_MODE, ADMIN_DATE, ADMIN_TIME, ADMIN_ENTRY_FEE, ADMIN_PRIZE = range(8, 16)

# Sample tournament data (in production, use database)
tournaments = []

# ------------------- HELPER FUNCTIONS -------------------
def is_admin(user_id):
    return user_id in ADMIN_IDS

def validate_name(name):
    if not name or len(name.strip()) < 2:
        return False, "Name must be at least 2 characters long"
    if len(name.strip()) > 30:
        return False, "Name cannot exceed 30 characters"
    if not re.match("^[a-zA-Z\\s]+$", name.strip()):
        return False, "Name can only contain letters and spaces"
    return True, ""

def validate_game_id(game_id):
    if not game_id or len(game_id.strip()) < 6:
        return False, "Game ID must be at least 6 characters long"
    if len(game_id.strip()) > 15:
        return False, "Game ID cannot exceed 15 characters"
    if not re.match("^[a-zA-Z0-9_]+$", game_id.strip()):
        return False, "Game ID can only contain letters, numbers, and underscores"
    return True, ""

def validate_level(level):
    try:
        level_num = int(level.strip())
        if level_num < 1 or level_num > 100:
            return False, "Level must be between 1 and 100"
        return True, ""
    except ValueError:
        return False, "Level must be a number"

def validate_state(state):
    valid_states = [
        "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", 
        "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", 
        "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", 
        "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", 
        "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", 
        "Delhi", "Jammu and Kashmir", "Ladakh", "Puducherry", "Chandigarh", 
        "Andaman and Nicobar Islands", "Dadra and Nagar Haveli", "Daman and Diu", "Lakshadweep"
    ]
    if state.strip().title() not in valid_states:
        return False, "Please enter a valid Indian state"
    return True, ""

def validate_date(date_str):
    try:
        tournament_date = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        if tournament_date.date() <= datetime.now().date():
            return False, "Tournament date must be in the future"
        return True, ""
    except ValueError:
        return False, "Date must be in YYYY-MM-DD format (e.g., 2025-09-15)"

def validate_time(time_str):
    try:
        datetime.strptime(time_str.strip(), "%H:%M")
        return True, ""
    except ValueError:
        return False, "Time must be in HH:MM format (e.g., 18:30)"

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

        # Add admin panel button for admins
        if is_admin(user.id):
            keyboard.insert(-2, [InlineKeyboardButton("🛠️ Admin Panel", callback_data="admin_panel")])

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

# ------------------- ADMIN PANEL -------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    
    if not is_admin(user.id):
        await query.answer("⛔ Access Denied! You are not authorized.", show_alert=True)
        return
    
    await query.answer()
    admin_text = (
        "🛠️ *Admin Panel*\n\n"
        "Welcome to the admin control center!\n\n"
        "What would you like to do?"
    )
    
    keyboard = [
        [InlineKeyboardButton("🏆 Create Tournament", callback_data="admin_create_tournament")],
        [InlineKeyboardButton("📋 View Tournaments", callback_data="admin_view_tournaments")],
        [InlineKeyboardButton("🗑️ Delete Tournament", callback_data="admin_delete_tournament")],
        [InlineKeyboardButton("👥 View Users", callback_data="admin_view_users")],
        [InlineKeyboardButton("📊 Analytics", callback_data="admin_analytics")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
    ]
    
    await query.message.edit_text(
        admin_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ------------------- ADMIN TOURNAMENT CREATION -------------------
async def admin_create_tournament_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🏆 *Create New Tournament*\n\nEnter tournament name:",
        parse_mode="Markdown"
    )
    return ADMIN_TOURNAMENT_NAME

async def admin_ask_game_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tournament_name"] = update.message.text.strip()
    
    keyboard = [
        [InlineKeyboardButton("🔥 Free Fire", callback_data="game_freefire")],
        [InlineKeyboardButton("🎯 BGMI", callback_data="game_bgmi")],
        [InlineKeyboardButton("⚔️ COD Mobile", callback_data="game_codm")],
        [InlineKeyboardButton("🎮 Valorant Mobile", callback_data="game_valorant")]
    ]
    
    await update.message.reply_text(
        "🎮 Select game type:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADMIN_GAME_TYPE

async def admin_handle_game_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    game_map = {
        "game_freefire": "Free Fire",
        "game_bgmi": "BGMI",
        "game_codm": "COD Mobile",
        "game_valorant": "Valorant Mobile"
    }
    
    context.user_data["game_type"] = game_map.get(query.data)
    
    # Show map selection based on game
    if query.data == "game_freefire":
        keyboard = [
            [InlineKeyboardButton("🏝️ Bermuda", callback_data="map_bermuda")],
            [InlineKeyboardButton("🌋 Purgatory", callback_data="map_purgatory")],
            [InlineKeyboardButton("⚡ Kalahari", callback_data="map_kalahari")],
            [InlineKeyboardButton("🗺️ Alpine", callback_data="map_alpine")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🗺️ Erangel", callback_data="map_erangel")],
            [InlineKeyboardButton("🏜️ Miramar", callback_data="map_miramar")],
            [InlineKeyboardButton("🌴 Sanhok", callback_data="map_sanhok")],
            [InlineKeyboardButton("❄️ Vikendi", callback_data="map_vikendi")]
        ]
    
    await query.message.edit_text(
        "🗺️ Select map:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADMIN_MAP

async def admin_handle_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    map_names = {
        "map_bermuda": "Bermuda",
        "map_purgatory": "Purgatory", 
        "map_kalahari": "Kalahari",
        "map_alpine": "Alpine",
        "map_erangel": "Erangel",
        "map_miramar": "Miramar",
        "map_sanhok": "Sanhok",
        "map_vikendi": "Vikendi"
    }
    
    context.user_data["map"] = map_names.get(query.data)
    
    keyboard = [
        [InlineKeyboardButton("👥 Squad (4 players)", callback_data="mode_squad")],
        [InlineKeyboardButton("👫 Duo (2 players)", callback_data="mode_duo")],
        [InlineKeyboardButton("👤 Solo (1 player)", callback_data="mode_solo")],
        [InlineKeyboardButton("🔥 Custom", callback_data="mode_custom")]
    ]
    
    await query.message.edit_text(
        "🎯 Select game mode:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADMIN_GAME_MODE

async def admin_handle_game_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    mode_names = {
        "mode_squad": "Squad (4v4)",
        "mode_duo": "Duo (2v2)",
        "mode_solo": "Solo (1v1)",
        "mode_custom": "Custom"
    }
    
    context.user_data["game_mode"] = mode_names.get(query.data)
    
    await query.message.reply_text(
        "📅 Enter tournament date (YYYY-MM-DD format):\n\nExample: 2025-09-15"
    )
    return ADMIN_DATE

async def admin_ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_input = update.message.text.strip()
    is_valid, error_msg = validate_date(date_input)
    
    if not is_valid:
        await update.message.reply_text(f"❌ {error_msg}\n\nPlease enter a valid date:")
        return ADMIN_DATE
    
    context.user_data["date"] = date_input
    await update.message.reply_text(
        "⏰ Enter tournament time (HH:MM format):\n\nExample: 18:30"
    )
    return ADMIN_TIME

async def admin_ask_entry_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_input = update.message.text.strip()
    is_valid, error_msg = validate_time(time_input)
    
    if not is_valid:
        await update.message.reply_text(f"❌ {error_msg}\n\nPlease enter a valid time:")
        return ADMIN_TIME
    
    context.user_data["time"] = time_input
    await update.message.reply_text(
        "💰 Enter entry fee (in ₹):\n\nExample: 10"
    )
    return ADMIN_ENTRY_FEE

async def admin_ask_prize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        entry_fee = int(update.message.text.strip())
        if entry_fee < 0:
            await update.message.reply_text("❌ Entry fee cannot be negative. Please enter a valid amount:")
            return ADMIN_ENTRY_FEE
    except ValueError:
        await update.message.reply_text("❌ Entry fee must be a number. Please enter a valid amount:")
        return ADMIN_ENTRY_FEE
    
    context.user_data["entry_fee"] = entry_fee
    await update.message.reply_text(
        "🏆 Enter total prize pool (in ₹):\n\nExample: 500"
    )
    return ADMIN_PRIZE

async def admin_save_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        prize_pool = int(update.message.text.strip())
        if prize_pool < 0:
            await update.message.reply_text("❌ Prize pool cannot be negative. Please enter a valid amount:")
            return ADMIN_PRIZE
    except ValueError:
        await update.message.reply_text("❌ Prize pool must be a number. Please enter a valid amount:")
        return ADMIN_PRIZE
    
    context.user_data["prize_pool"] = prize_pool
    
    # Create tournament object
    tournament = {
        "id": len(tournaments) + 1,
        "name": context.user_data["tournament_name"],
        "game_type": context.user_data["game_type"],
        "map": context.user_data["map"],
        "game_mode": context.user_data["game_mode"],
        "date": context.user_data["date"],
        "time": context.user_data["time"],
        "entry_fee": context.user_data["entry_fee"],
        "prize_pool": context.user_data["prize_pool"],
        "created_at": datetime.now().isoformat(),
        "participants": []
    }
    
    tournaments.append(tournament)
    
    summary_text = (
        "✅ *Tournament Created Successfully!*\n\n"
        f"🏆 *Name:* {tournament['name']}\n"
        f"🎮 *Game:* {tournament['game_type']}\n"
        f"🗺️ *Map:* {tournament['map']}\n"
        f"🎯 *Mode:* {tournament['game_mode']}\n"
        f"📅 *Date:* {tournament['date']}\n"
        f"⏰ *Time:* {tournament['time']}\n"
        f"💰 *Entry Fee:* ₹{tournament['entry_fee']}\n"
        f"🏆 *Prize Pool:* ₹{tournament['prize_pool']}\n"
        f"🆔 *Tournament ID:* {tournament['id']}"
    )
    
    await update.message.reply_text(summary_text, parse_mode="Markdown")
    
    # Notify moderator group
    try:
        await context.bot.send_message(
            chat_id=MODERATOR_GROUP_ID,
            text=f"🏆 *New Tournament Created!*\n\n{summary_text}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to notify moderator group: {e}")
    
    context.user_data.clear()
    return ConversationHandler.END

# ------------------- VIEW TOURNAMENTS -------------------
async def admin_view_tournaments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not tournaments:
        await query.message.edit_text(
            "📋 *No tournaments found*\n\nCreate your first tournament using the admin panel!",
            parse_mode="Markdown"
        )
        return
    
    tournaments_text = "📋 *Active Tournaments:*\n\n"
    for tournament in tournaments[-5:]:  # Show last 5 tournaments
        tournaments_text += (
            f"🏆 *{tournament['name']}* (ID: {tournament['id']})\n"
            f"🎮 {tournament['game_type']} | 🗺️ {tournament['map']}\n"
            f"📅 {tournament['date']} at {tournament['time']}\n"
            f"💰 ₹{tournament['entry_fee']} | 🏆 ₹{tournament['prize_pool']}\n"
            f"👥 {len(tournament['participants'])} participants\n\n"
        )
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]]
    
    await query.message.edit_text(
        tournaments_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ------------------- PROFILE CREATION WITH VALIDATION -------------------
async def create_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "👤 Let's create your profile!\n\n*What's your Name?*\n\n"
        "ℹ️ _Name should be 2-30 characters, letters only_",
        parse_mode="Markdown"
    )
    return ASK_NAME

async def ask_game_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    is_valid, error_msg = validate_name(name)
    
    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_msg}\n\nPlease enter a valid name:"
        )
        return ASK_NAME
    
    context.user_data["name"] = name.strip().title()
    await update.message.reply_text(
        "🎮 *Enter your Game ID:*\n\n"
        "ℹ️ _Game ID should be 6-15 characters, letters, numbers, and underscores only_",
        parse_mode="Markdown"
    )
    return ASK_GAME_ID

async def ask_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_id = update.message.text
    is_valid, error_msg = validate_game_id(game_id)
    
    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_msg}\n\nPlease enter a valid Game ID:"
        )
        return ASK_GAME_ID
    
    context.user_data["game_id"] = game_id.strip()
    await update.message.reply_text(
        "🔥 *Enter your Level:*\n\n"
        "ℹ️ _Level should be between 1-100_",
        parse_mode="Markdown"
    )
    return ASK_LEVEL

async def ask_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    level = update.message.text
    is_valid, error_msg = validate_level(level)
    
    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_msg}\n\nPlease enter a valid level:"
        )
        return ASK_LEVEL
    
    context.user_data["level"] = int(level.strip())
    await update.message.reply_text(
        "🌍 *Enter your State:*\n\n"
        "ℹ️ _Please enter a valid Indian state name_",
        parse_mode="Markdown"
    )
    return ASK_STATE

async def save_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = update.message.text
    is_valid, error_msg = validate_state(state)
    
    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_msg}\n\nPlease enter a valid state name:"
        )
        return ASK_STATE
    
    context.user_data["state"] = state.strip().title()
    user = update.effective_user

    profile_text = (
        "✅ *Profile Created Successfully!*\n\n"
        f"👤 *Name:* {context.user_data['name']}\n"
        f"🎮 *Game ID:* {context.user_data['game_id']}\n"
        f"🔥 *Level:* {context.user_data['level']}\n"
        f"🌍 *State:* {context.user_data['state']}\n"
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

# ------------------- OTHER HANDLERS -------------------
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

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Operation cancelled.\n\nUse /start to return to main menu.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

# ------------------- MAIN -------------------
def main():
    try:
        logger.info("Starting OTO Tournament Bot...")
        
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .build()
        )

        application.add_error_handler(error_handler)

        # Main handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(contact, pattern="^contact$"))
        application.add_handler(CallbackQueryHandler(referral, pattern="^referral$"))
        application.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))

        # Admin handlers
        application.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
        application.add_handler(CallbackQueryHandler(admin_view_tournaments, pattern="^admin_view_tournaments$"))

        # Profile creation conversation
        profile_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(create_profile_start, pattern="^create_profile$")],
            states={
                ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_game_id)],
                ASK_GAME_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_level)],
                ASK_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_state)],
                ASK_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_profile)]
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )
        application.add_handler(profile_conv_handler)

        # Tournament creation conversation
        tournament_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(admin_create_tournament_start, pattern="^admin_create_tournament$")],
            states={
                ADMIN_TOURNAMENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ask_game_type)],
                ADMIN_GAME_TYPE: [CallbackQueryHandler(admin_handle_game_type, pattern="^game_")],
                ADMIN_MAP: [CallbackQueryHandler(admin_handle_map, pattern="^map_")],
                ADMIN_GAME_MODE: [CallbackQueryHandler(admin_handle_game_mode, pattern="^mode_")],
                ADMIN_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ask_time)],
                ADMIN_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ask_entry_fee)],
                ADMIN_ENTRY_FEE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ask_prize)],
                ADMIN_PRIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_save_tournament)]
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )
        application.add_handler(tournament_conv_handler)

        logger.info("🤖 Bot is starting...")
        print("🤖 OTO Tournament Bot is running!")
        
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False
        )
        
    except Exception as e:
        logger.error(f"Critical error starting bot: {e}")
        print(f"❌ Failed to start bot: {e}")

if __name__ == "__main__":
    main()
