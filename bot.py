import logging
import os
import re
import sqlite3
from datetime import datetime
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
# Use environment variables in production (e.g., Render)
BOT_TOKEN = os.getenv("BOT_TOKEN", "7940607419:AAHmVBXOccZ5fWkE7HxGK42ij8zSFr8lBAk")
MODERATOR_GROUP_ID = int(os.getenv("MODERATOR_GROUP_ID", "-4687499589"))
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://oto-tournament.vercel.app")

# Admin user IDs (replace with actual admin Telegram IDs)
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else [123456789]

# Database file
DB_PATH = os.getenv("DB_PATH", "data.db")

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

# ------------------- DB HELPERS -------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # users: id (auto), telegram_id (unique), oto_id (unique), name, game_id, level, state, username, created_at
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            oto_id TEXT UNIQUE,
            name TEXT,
            game_id TEXT,
            level INTEGER,
            state TEXT,
            username TEXT,
            created_at TEXT
        )
        """
    )
    # tournaments: id (auto), name, game_type, map, game_mode, date, time, entry_fee, prize_pool, created_at
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            game_type TEXT,
            map TEXT,
            game_mode TEXT,
            date TEXT,
            time TEXT,
            entry_fee INTEGER,
            prize_pool INTEGER,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

def get_user_by_telegram_id(telegram_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, telegram_id, oto_id, name, game_id, level, state, username, created_at FROM users WHERE telegram_id=?", (telegram_id,))
    row = c.fetchone()
    conn.close()
    return row

def create_user(telegram_id, name, game_id, level, state, username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    # Insert without oto_id first to get autoincrement id
    try:
        c.execute(
            "INSERT INTO users (telegram_id, name, game_id, level, state, username, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (telegram_id, name, game_id, level, state, username, created_at)
        )
        user_row_id = c.lastrowid
        # Generate OTO ID: OTO + zero-padded user_row_id (6 digits)
        oto_id = f"OTO{str(user_row_id).zfill(6)}"
        c.execute("UPDATE users SET oto_id=? WHERE id=?", (oto_id, user_row_id))
        conn.commit()
        # Return the full user row
        c.execute("SELECT id, telegram_id, oto_id, name, game_id, level, state, username, created_at FROM users WHERE id=?", (user_row_id,))
        new_row = c.fetchone()
        conn.close()
        return new_row
    except sqlite3.IntegrityError as e:
        conn.rollback()
        conn.close()
        raise

def save_tournament_to_db(t):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    c.execute(
        """INSERT INTO tournaments (name, game_type, map, game_mode, date, time, entry_fee, prize_pool, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (t["name"], t["game_type"], t["map"], t["game_mode"], t["date"], t["time"], t["entry_fee"], t["prize_pool"], created_at)
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id

def get_recent_tournaments(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, game_type, map, game_mode, date, time, entry_fee, prize_pool FROM tournaments ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

# ------------------- VALIDATIONS -------------------
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
    if len(game_id.strip()) > 30:
        return False, "Game ID cannot exceed 30 characters"
    if not re.match("^[a-zA-Z0-9_]+$", game_id.strip()):
        return False, "Game ID can only contain letters, numbers, and underscores"
    return True, ""

def validate_level(level):
    try:
        level_num = int(level.strip())
        if level_num < 1 or level_num > 1000:
            return False, "Level must be between 1 and 1000"
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

# ------------------- BOT HANDLERS -------------------
async def build_main_menu_for_user(telegram_id, user_obj=None):
    """
    Build a menu. If user_obj is None -> user doesn't have a profile yet.
    """
    keyboard = []
    if user_obj:
        # user has profile
        keyboard.append([InlineKeyboardButton("🏆 View Tournaments", url=f"{MINI_APP_URL}/tournaments")])
        keyboard.append([InlineKeyboardButton("👤 View Profile", callback_data="view_profile")])
        keyboard.append([InlineKeyboardButton("💰 Wallet", url=f"{MINI_APP_URL}/wallet")])
        keyboard.append([InlineKeyboardButton("🛒 Store", url=f"{MINI_APP_URL}/store")])
        keyboard.append([InlineKeyboardButton("🥇 Leaderboard", url=f"{MINI_APP_URL}/leaderboard")])
        keyboard.append([InlineKeyboardButton("🎁 Referral Program", callback_data="referral")])
        keyboard.append([InlineKeyboardButton("📞 Contact Us", callback_data="contact")])
    else:
        # new user -> show create profile and the other links but encourage profile creation
        keyboard.append([InlineKeyboardButton("🎮 Create Profile", callback_data="create_profile")])
        keyboard.append([InlineKeyboardButton("🏆 View Tournaments (Login required)", url=f"{MINI_APP_URL}/tournaments")])
        keyboard.append([InlineKeyboardButton("📞 Contact Us", callback_data="contact")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        # check if user exists
        user_row = get_user_by_telegram_id(user.id)
        welcome_text = (
            f"👋 Hello {user.first_name or 'Gamer'}!\n\n"
            "Welcome to *OTO Tournament Bot* 🎮\n\n"
            "Use this bot to join tournaments, manage wallet, shop in the store, and view leaderboards.\n\n"
            "Choose from the menu below 👇"
        )

        # Add admin panel button for admins if this is an admin
        reply_markup = await build_main_menu_for_user(user.id, user_row)

        if user.id in ADMIN_IDS:
            # insert admin panel button at top if admin
            admin_button = [InlineKeyboardButton("🛠️ Admin Panel", callback_data="admin_panel")]
            # Put at the beginning by rebuilding markup
            buttons = [[admin_button[0]]] + reply_markup.inline_keyboard
            reply_markup = InlineKeyboardMarkup(buttons)

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
        logger.exception("Error in start handler: %s", e)

# ------------------- ADMIN PANEL -------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user

    if user.id not in ADMIN_IDS:
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
    await update.message.reply_text("🎮 Select game type:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_GAME_TYPE

async def admin_handle_game_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_map = {"game_freefire": "Free Fire", "game_bgmi": "BGMI", "game_codm": "COD Mobile", "game_valorant": "Valorant Mobile"}
    context.user_data["game_type"] = game_map.get(query.data, "Unknown")
    # maps selection
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

    await query.message.edit_text("🗺️ Select map:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_MAP

async def admin_handle_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    map_names = {
        "map_bermuda": "Bermuda", "map_purgatory": "Purgatory", "map_kalahari": "Kalahari", "map_alpine": "Alpine",
        "map_erangel": "Erangel", "map_miramar": "Miramar", "map_sanhok": "Sanhok", "map_vikendi": "Vikendi"
    }
    context.user_data["map"] = map_names.get(query.data, "Unknown")
    keyboard = [
        [InlineKeyboardButton("👥 Squad (4 players)", callback_data="mode_squad")],
        [InlineKeyboardButton("👫 Duo (2 players)", callback_data="mode_duo")],
        [InlineKeyboardButton("👤 Solo (1 player)", callback_data="mode_solo")],
        [InlineKeyboardButton("🔥 Custom", callback_data="mode_custom")]
    ]
    await query.message.edit_text("🎯 Select game mode:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_GAME_MODE

async def admin_handle_game_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode_names = {"mode_squad": "Squad (4v4)", "mode_duo": "Duo (2v2)", "mode_solo": "Solo (1v1)", "mode_custom": "Custom"}
    context.user_data["game_mode"] = mode_names.get(query.data, "Custom")
    await query.message.reply_text("📅 Enter tournament date (YYYY-MM-DD format):\n\nExample: 2025-09-15")
    return ADMIN_DATE

async def admin_ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_input = update.message.text.strip()
    is_valid, error_msg = validate_date(date_input)
    if not is_valid:
        await update.message.reply_text(f"❌ {error_msg}\n\nPlease enter a valid date:")
        return ADMIN_DATE
    context.user_data["date"] = date_input
    await update.message.reply_text("⏰ Enter tournament time (HH:MM format):\n\nExample: 18:30")
    return ADMIN_TIME

async def admin_ask_entry_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_input = update.message.text.strip()
    is_valid, error_msg = validate_time(time_input)
    if not is_valid:
        await update.message.reply_text(f"❌ {error_msg}\n\nPlease enter a valid time:")
        return ADMIN_TIME
    context.user_data["time"] = time_input
    await update.message.reply_text("💰 Enter entry fee (in ₹):\n\nExample: 10")
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
    await update.message.reply_text("🏆 Enter total prize pool (in ₹):\n\nExample: 500")
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

    tournament = {
        "name": context.user_data["tournament_name"],
        "game_type": context.user_data["game_type"],
        "map": context.user_data["map"],
        "game_mode": context.user_data["game_mode"],
        "date": context.user_data["date"],
        "time": context.user_data["time"],
        "entry_fee": context.user_data["entry_fee"],
        "prize_pool": context.user_data["prize_pool"]
    }

    # save to DB
    try:
        new_id = save_tournament_to_db(tournament)
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
            f"🆔 *Tournament ID:* {new_id}"
        )
        await update.message.reply_text(summary_text, parse_mode="Markdown")
        # notify moderator group
        try:
            await context.bot.send_message(chat_id=MODERATOR_GROUP_ID, text=f"🏆 *New Tournament Created!*\n\n{summary_text}", parse_mode="Markdown")
        except Exception:
            logger.exception("Failed to notify moderator group about new tournament")
    except Exception:
        logger.exception("Failed to save tournament to DB")
        await update.message.reply_text("❌ Failed to create tournament, try again later.")
    context.user_data.clear()
    return ConversationHandler.END

async def admin_view_tournaments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rows = get_recent_tournaments(limit=10)
    if not rows:
        await query.message.edit_text("📋 *No tournaments found*\n\nCreate your first tournament using the admin panel!", parse_mode="Markdown")
        return
    tournaments_text = "📋 *Active Tournaments:*\n\n"
    for row in rows:
        tid, name, game_type, map_name, game_mode, date, time, entry_fee, prize_pool = row
        tournaments_text += (
            f"🏆 *{name}* (ID: {tid})\n"
            f"🎮 {game_type} | 🗺️ {map_name}\n"
            f"📅 {date} at {time}\n"
            f"💰 ₹{entry_fee} | 🏆 ₹{prize_pool}\n\n"
        )
    keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]]
    await query.message.edit_text(tournaments_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ------------------- PROFILE CREATION FLOW -------------------
async def create_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    # If user already has profile, skip creation
    existing = get_user_by_telegram_id(user.id)
    if existing:
        await query.message.reply_text("✅ You already have a profile. Use /profile to view it or click View Tournaments.")
        # show normal menu
        reply_markup = await build_main_menu_for_user(user.id, existing)
        await query.message.reply_text("Main Menu:", reply_markup=reply_markup)
        return ConversationHandler.END

    await query.message.reply_text(
        "👤 *Create your profile*\n\nWhat's your *Name*? (2-30 letters)",
        parse_mode="Markdown"
    )
    return ASK_NAME

async def ask_game_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    is_valid, error_msg = validate_name(name)
    if not is_valid:
        await update.message.reply_text(f"❌ {error_msg}\n\nPlease enter a valid name:")
        return ASK_NAME
    context.user_data["name"] = name.strip().title()
    await update.message.reply_text("🎮 *Enter your Game ID:* (6-30 chars, letters/numbers/underscore)", parse_mode="Markdown")
    return ASK_GAME_ID

async def ask_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_id = update.message.text
    is_valid, error_msg = validate_game_id(game_id)
    if not is_valid:
        await update.message.reply_text(f"❌ {error_msg}\n\nPlease enter a valid Game ID:")
        return ASK_GAME_ID
    context.user_data["game_id"] = game_id.strip()
    await update.message.reply_text("🔥 *Enter your Level:* (number)", parse_mode="Markdown")
    return ASK_LEVEL

async def ask_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    level = update.message.text
    is_valid, error_msg = validate_level(level)
    if not is_valid:
        await update.message.reply_text(f"❌ {error_msg}\n\nPlease enter a valid level:")
        return ASK_LEVEL
    context.user_data["level"] = int(level.strip())
    await update.message.reply_text("🌍 *Enter your State:* (e.g., Maharashtra)", parse_mode="Markdown")
    return ASK_STATE

async def save_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = update.message.text
    is_valid, error_msg = validate_state(state)
    if not is_valid:
        await update.message.reply_text(f"❌ {error_msg}\n\nPlease enter a valid state name:")
        return ASK_STATE
    context.user_data["state"] = state.strip().title()
    user = update.effective_user

    # Create user in DB (this also generates unique OTO ID)
    try:
        new_user = create_user(user.id, context.user_data["name"], context.user_data["game_id"],
                               context.user_data["level"], context.user_data["state"], user.username or "")
        # new_user = (id, telegram_id, oto_id, name, game_id, level, state, username, created_at)
        oto_id = new_user[2]
        profile_text = (
            "✅ *Profile Created Successfully!*\n\n"
            f"👤 *Name:* {new_user[3]}\n"
            f"🎮 *Game ID:* {new_user[4]}\n"
            f"🔥 *Level:* {new_user[5]}\n"
            f"🌍 *State:* {new_user[6]}\n"
            f"🆔 *OTO ID:* {oto_id}\n"
            f"👥 *Telegram ID:* {user.id}\n"
            f"📱 *Username:* @{user.username or 'N/A'}"
        )
        await update.message.reply_text(profile_text, parse_mode="Markdown")

        # Send to moderator group
        try:
            await context.bot.send_message(chat_id=MODERATOR_GROUP_ID, text=f"📥 *New Profile Created!*\n\n{profile_text}", parse_mode="Markdown")
        except Exception:
            logger.exception("Failed to notify moderator group about new profile")

        # show main menu now that profile exists
        reply_markup = await build_main_menu_for_user(user.id, new_user)
        await update.message.reply_text("🎉 You're all set! Use the menu below:", reply_markup=reply_markup)
    except sqlite3.IntegrityError:
        # If duplicate telegram_id somehow
        await update.message.reply_text("❌ It seems you already have a profile or there was an error. Use /profile to view your profile.")
    except Exception:
        logger.exception("Error saving profile")
        await update.message.reply_text("❌ Failed to create profile, please try again later.")

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
    except Exception:
        referral_link = "Contact admin for referral link"
    referral_text = (
        "🎁 *Referral Program*\n\n"
        f"Share this link with friends:\n`{referral_link}`\n\n"
        "💰 *Benefits:*\n"
        "• Earn OTO Coins for each referral\n"
        "• Get bonus rewards"
    )
    await query.message.reply_text(referral_text, parse_mode="Markdown")

async def view_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    row = get_user_by_telegram_id(user.id)
    if not row:
        await query.message.reply_text("You don't have a profile yet. Click Create Profile to get started.")
        return
    # row = (id, telegram_id, oto_id, name, game_id, level, state, username, created_at)
    profile_text = (
        f"👤 *Name:* {row[3]}\n"
        f"🎮 *Game ID:* {row[4]}\n"
        f"🔥 *Level:* {row[5]}\n"
        f"🌍 *State:* {row[6]}\n"
        f"🆔 *OTO ID:* {row[2]}\n"
        f"📱 *Username:* @{row[7] or 'N/A'}\n"
        f"🕒 *Joined:* {row[8]}"
    )
    await query.message.reply_text(profile_text, parse_mode="Markdown")

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    row = get_user_by_telegram_id(user.id)
    if not row:
        await update.message.reply_text("You don't have a profile yet. Click Create Profile to get started.")
        return
    profile_text = (
        f"👤 *Name:* {row[3]}\n"
        f"🎮 *Game ID:* {row[4]}\n"
        f"🔥 *Level:* {row[5]}\n"
        f"🌍 *State:* {row[6]}\n"
        f"🆔 *OTO ID:* {row[2]}\n"
        f"📱 *Username:* @{row[7] or 'N/A'}\n"
        f"🕒 *Joined:* {row[8]}"
    )
    await update.message.reply_text(profile_text, parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Operation cancelled.\n\nUse /start to return to main menu.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

# ------------------- MAIN -------------------
def main():
    try:
        init_db()
        logger.info("Starting OTO Tournament Bot...")
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_error_handler(error_handler)

        # Core handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("profile", cmd_profile))

        application.add_handler(CallbackQueryHandler(contact, pattern="^contact$"))
        application.add_handler(CallbackQueryHandler(referral, pattern="^referral$"))
        application.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
        application.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
        application.add_handler(CallbackQueryHandler(view_profile_callback, pattern="^view_profile$"))

        # Profile conversation
        profile_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(create_profile_start, pattern="^create_profile$")],
            states={
                ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_game_id)],
                ASK_GAME_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_level)],
                ASK_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_state)],
                ASK_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_profile)]
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            per_message=True
        )
        application.add_handler(profile_conv_handler)

        # Tournament creation conversation (admin)
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
            per_message=True
        )
        application.add_handler(tournament_conv_handler)

        logger.info("🤖 Bot is starting...")
        print("🤖 OTO Tournament Bot is running!")
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.exception("Critical error starting bot: %s", e)
        print(f"❌ Failed to start bot: {e}")

if __name__ == "__main__":
    main()
