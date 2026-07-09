"""
HAT Support Bot — Hire A Trucker Telegram Support Bot

Foydalanuvchilar bilan admin guruhi o'rtasida xabar almashish uchun
support bot. Polling rejimida ishlaydi.
"""

import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Environment variables ───────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_GROUP_ID = int(os.environ.get("ADMIN_GROUP_ID", "0"))
PORT = int(os.environ.get("PORT", "8080"))

# ── Assets ──────────────────────────────────────────────────────────
BANNER_PATH = Path(__file__).parent / "assets" / "banner.jpg"

# ── /start caption (MarkdownV2) ─────────────────────────────────────
START_CAPTION = (
    "🚛 *Welcome to Hire A Trucker \\(HAT\\) Support\\!*\n"
    "\n"
    "HAT — bu carrier kompaniyalar va professional haydovchilarni "
    "oson bog'lovchi platforma\\.\n"
    "\n"
    "🔹 *Carriers uchun:*\n"
    "Ishonchli va tajribali haydovchilarni toping, "
    "flotingizni samarali boshqaring\\.\n"
    "\n"
    "🔹 *Drivers uchun:*\n"
    "Eng yaxshi ish takliflarini toping, "
    "o'z karyerangizni yangi bosqichga olib chiqing\\.\n"
    "\n"
    "Quyidagi tugmalar orqali kanalimizga qo'shiling yoki "
    "support xizmati bilan bog'laning\\. 👇"
)


# ════════════════════════════════════════════════════════════════════
#  Health‑check HTTP server  (threading)
# ════════════════════════════════════════════════════════════════════
class HealthHandler(BaseHTTPRequestHandler):
    """Minimal handler — returns 200 OK on any GET."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    # Suppress default stderr request logging
    def log_message(self, format, *args):  # noqa: A002
        pass


def start_health_server():
    """Start a lightweight HTTP health server in a daemon thread."""
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server listening on port %s", PORT)


# ════════════════════════════════════════════════════════════════════
#  Helper — user info header for admin group
# ════════════════════════════════════════════════════════════════════
def _user_header(user) -> str:
    """Build a human‑readable header with tg deep‑link."""
    full_name = user.full_name or "No Name"
    username = f"@{user.username}" if user.username else "N/A"
    return (
        f"👤 <a href='tg://user?id={user.id}'>{full_name}</a>\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📎 Username: {username}\n"
        f"{'─' * 30}"
    )


# ════════════════════════════════════════════════════════════════════
#  Command Handlers
# ════════════════════════════════════════════════════════════════════
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start — Send banner image with inline buttons."""
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📢 Join Our Channel", url="https://t.me/Hireatrucker"
                ),
                InlineKeyboardButton(
                    "📞 Contact Support", callback_data="contact_support"
                ),
            ]
        ]
    )

    if BANNER_PATH.exists():
        with open(BANNER_PATH, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=START_CAPTION,
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )
    else:
        # Fallback if banner file is missing
        await update.message.reply_text(
            START_CAPTION,
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )


async def contact_support_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handle "Contact Support" inline button press."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "✍️ Iltimos, xabaringizni yozing — support jamoamiz tez orada javob beradi!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help — List available commands."""
    text = (
        "📋 *Mavjud buyruqlar:*\n\n"
        "/start — Botni ishga tushirish va ma'lumot olish\n"
        "/help — Ushbu yordam xabarini ko'rish\n"
        "/chatid — Joriy chat ID ni bilish \\(admin uchun\\)\n\n"
        "✍️ Oddiy xabar yuboring — support jamoamiz javob beradi\\!"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/chatid — Show the current chat ID (useful for admins)."""
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"🆔 Bu chatning ID si: <code>{chat_id}</code>", parse_mode="HTML")


# ════════════════════════════════════════════════════════════════════
#  User → Admin Group  (forwarding messages)
# ════════════════════════════════════════════════════════════════════
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward any user message to admin group with user info header."""
    message = update.message
    user = message.from_user
    chat_id = message.chat_id

    # Only process private chats
    if message.chat.type != "private":
        return

    if not ADMIN_GROUP_ID:
        await message.reply_text("⚠️ Support hozircha mavjud emas. Keyinroq urinib ko'ring.")
        return

    header = _user_header(user)

    # Send header first
    header_msg = await context.bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=header,
        parse_mode="HTML",
    )

    # Forward the actual content based on message type
    forwarded_msg = None

    if message.text:
        forwarded_msg = await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=f"💬 {message.text}",
            reply_to_message_id=header_msg.message_id,
        )
    elif message.photo:
        forwarded_msg = await context.bot.send_photo(
            chat_id=ADMIN_GROUP_ID,
            photo=message.photo[-1].file_id,
            caption=message.caption or "",
            reply_to_message_id=header_msg.message_id,
        )
    elif message.video:
        forwarded_msg = await context.bot.send_video(
            chat_id=ADMIN_GROUP_ID,
            video=message.video.file_id,
            caption=message.caption or "",
            reply_to_message_id=header_msg.message_id,
        )
    elif message.document:
        forwarded_msg = await context.bot.send_document(
            chat_id=ADMIN_GROUP_ID,
            document=message.document.file_id,
            caption=message.caption or "",
            reply_to_message_id=header_msg.message_id,
        )
    elif message.voice:
        forwarded_msg = await context.bot.send_voice(
            chat_id=ADMIN_GROUP_ID,
            voice=message.voice.file_id,
            caption=message.caption or "",
            reply_to_message_id=header_msg.message_id,
        )
    elif message.sticker:
        forwarded_msg = await context.bot.send_sticker(
            chat_id=ADMIN_GROUP_ID,
            sticker=message.sticker.file_id,
            reply_to_message_id=header_msg.message_id,
        )
    else:
        forwarded_msg = await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text="⚠️ Noma'lum xabar turi",
            reply_to_message_id=header_msg.message_id,
        )

    # Save mapping: admin group message ID → user chat ID
    if forwarded_msg:
        context.bot_data[header_msg.message_id] = chat_id
        context.bot_data[forwarded_msg.message_id] = chat_id

    # Confirm to the user
    await message.reply_text(
        "✅ Xabaringiz qabul qilindi! Support jamoamiz tez orada javob beradi."
    )

    logger.info(
        "Message from %s (ID: %s) forwarded to admin group.",
        user.full_name,
        user.id,
    )


# ════════════════════════════════════════════════════════════════════
#  Admin Group → User  (reply‑based)
# ════════════════════════════════════════════════════════════════════
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """When admin replies to a forwarded message, send response back to user."""
    message = update.message

    # Only process messages from the admin group
    if message.chat_id != ADMIN_GROUP_ID:
        return

    # Must be a reply to a forwarded message
    if not message.reply_to_message:
        return

    reply_to_id = message.reply_to_message.message_id

    # Look up the original user's chat ID
    user_chat_id = context.bot_data.get(reply_to_id)
    if not user_chat_id:
        return

    # Send admin's response to the user
    try:
        if message.text:
            await context.bot.send_message(
                chat_id=user_chat_id,
                text=f"📩 *Support Team:*\n\n{message.text}",
                parse_mode="Markdown",
            )
        elif message.photo:
            await context.bot.send_photo(
                chat_id=user_chat_id,
                photo=message.photo[-1].file_id,
                caption=f"📩 Support Team:\n\n{message.caption or ''}",
            )
        elif message.video:
            await context.bot.send_video(
                chat_id=user_chat_id,
                video=message.video.file_id,
                caption=f"📩 Support Team:\n\n{message.caption or ''}",
            )
        elif message.document:
            await context.bot.send_document(
                chat_id=user_chat_id,
                document=message.document.file_id,
                caption=f"📩 Support Team:\n\n{message.caption or ''}",
            )
        elif message.voice:
            await context.bot.send_voice(
                chat_id=user_chat_id,
                voice=message.voice.file_id,
                caption="📩 Support Team:",
            )
        elif message.sticker:
            await context.bot.send_message(
                chat_id=user_chat_id,
                text="📩 *Support Team:*",
                parse_mode="Markdown",
            )
            await context.bot.send_sticker(
                chat_id=user_chat_id,
                sticker=message.sticker.file_id,
            )
        else:
            await context.bot.send_message(
                chat_id=user_chat_id,
                text="📩 *Support Team:*\n\nJavob yuborildi\\.",
                parse_mode="Markdown",
            )

        # Also map this new reply for threading
        context.bot_data[message.message_id] = user_chat_id

        logger.info(
            "Admin reply sent to user chat_id=%s",
            user_chat_id,
        )
    except Exception as e:
        logger.error("Failed to send reply to user %s: %s", user_chat_id, e)
        await message.reply_text(
            f"⚠️ Foydalanuvchiga xabar yuborib bo'lmadi: {e}"
        )


# ════════════════════════════════════════════════════════════════════
#  Error handler
# ════════════════════════════════════════════════════════════════════
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors — suppress Conflict errors, log others."""
    from telegram.error import Conflict

    if isinstance(context.error, Conflict):
        # Conflict means another instance is running; just log once and skip
        logger.debug("Conflict error (another instance running): %s", context.error)
        return

    logger.error("Unhandled exception: %s", context.error, exc_info=context.error)


# ════════════════════════════════════════════════════════════════════
#  Pre‑start cleanup — close any existing sessions
# ════════════════════════════════════════════════════════════════════
def _close_existing_sessions():
    """Call /close and /deleteWebhook before starting polling."""
    import urllib.request
    import json as _json
    import time as _time

    base = f"https://api.telegram.org/bot{BOT_TOKEN}"

    for endpoint in ("deleteWebhook?drop_pending_updates=true", "close"):
        try:
            resp = urllib.request.urlopen(f"{base}/{endpoint}", timeout=10)
            data = _json.loads(resp.read())
            logger.info("Pre-start %s: %s", endpoint.split("?")[0], data)
        except Exception as e:
            logger.warning("Pre-start %s failed: %s", endpoint.split("?")[0], e)

    logger.info("Waiting 5 seconds for Telegram to release session...")
    _time.sleep(5)


# ════════════════════════════════════════════════════════════════════
#  Main
# ════════════════════════════════════════════════════════════════════
def main():
    """Initialize and run the bot."""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
        return

    if not ADMIN_GROUP_ID:
        logger.warning(
            "ADMIN_GROUP_ID is not set. Admin forwarding will be disabled."
        )

    # Start health server
    start_health_server()

    # Close any existing sessions first
    _close_existing_sessions()

    # Build the application
    app = Application.builder().token(BOT_TOKEN).build()

    # Error handler
    app.add_error_handler(error_handler)

    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("chatid", chatid_command))

    # Callback query handler (inline buttons)
    app.add_handler(
        CallbackQueryHandler(contact_support_callback, pattern="^contact_support$")
    )

    # Admin reply handler — must be added BEFORE the general message handler
    # Filters for messages in the admin group that are replies
    app.add_handler(
        MessageHandler(
            filters.Chat(ADMIN_GROUP_ID) & filters.REPLY,
            handle_admin_reply,
        )
    )

    # User message handler — private chats only
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & ~filters.COMMAND
            & (
                filters.TEXT
                | filters.PHOTO
                | filters.VIDEO
                | filters.Document.ALL
                | filters.VOICE
                | filters.Sticker.ALL
            ),
            handle_user_message,
        )
    )

    logger.info("🚛 HAT Support Bot is starting (polling mode)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

