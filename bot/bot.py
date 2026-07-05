import os
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_GROUP_ID = int(os.environ.get("ADMIN_GROUP_ID", "0"))

ASSETS_DIR = Path(__file__).parent / "assets"
BANNER_IMAGE = ASSETS_DIR / "banner.jpg"

WELCOME_CAPTION = (
    "🚛 *Welcome to HAT — Hire A Trucker*\n"
    "_Driver Marketplace · Connecting Truckers & Carriers in US Logistics · No Middleman Fees_\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "📦 *For Carriers*\n"
    "Browse your preferred driver from the driver board. "
    "Post your job offers, dedicated lanes and get matched with verified, experienced drivers quickly and efficiently.\n\n"
    "🧑‍✈️ *For Drivers*\n"
    "Just sign up and be listed on the available drivers board that carriers search. "
    "Browse hundreds of real, up-to-date job offers — see how much carriers pay, home time, equipment type, bonuses, and more *before* you apply. "
    "No more cold calling for outdated positions.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "💬 *Need support?* Send us a message — our team is here to help.\n"
    "📢 *Stay updated* — follow our official channel for the latest news and offers."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Our Channel", url="https://t.me/Hireatrucker")],
        [InlineKeyboardButton("📞 Contact Support", callback_data="support")],
    ])

    if BANNER_IMAGE.exists():
        with open(BANNER_IMAGE, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=WELCOME_CAPTION,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
    else:
        await update.message.reply_text(
            WELCOME_CAPTION,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📋 *Available Commands*\n\n"
        "/start — Welcome message & platform overview\n"
        "/help — Show this help menu\n\n"
        "You can also send us any message and our support team will get back to you shortly.",
        parse_mode="Markdown",
    )


async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await update.message.reply_text(f"Chat ID: `{chat.id}`", parse_mode="Markdown")


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ADMIN_GROUP_ID:
        logger.warning("ADMIN_GROUP_ID is not set — cannot forward messages.")
        await update.message.reply_text(
            "⚠️ Our support system is temporarily unavailable. Please try again later."
        )
        return

    user = update.effective_user
    msg = update.message

    username_line = f"@{user.username}\n" if user.username else ""
    header = (
        f"👤 *User:* [{user.full_name}](tg://user?id={user.id})\n"
        f"🆔 ID: `{user.id}`\n"
        f"{username_line}"
    )

    forwarded = None

    if msg.text:
        forwarded = await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=f"{header}\n💬 {msg.text}",
            parse_mode="Markdown",
        )
    elif msg.photo:
        forwarded = await context.bot.send_photo(
            chat_id=ADMIN_GROUP_ID,
            photo=msg.photo[-1].file_id,
            caption=f"{header}\n📷 Photo" + (f"\n{msg.caption}" if msg.caption else ""),
            parse_mode="Markdown",
        )
    elif msg.video:
        forwarded = await context.bot.send_video(
            chat_id=ADMIN_GROUP_ID,
            video=msg.video.file_id,
            caption=f"{header}\n🎥 Video" + (f"\n{msg.caption}" if msg.caption else ""),
            parse_mode="Markdown",
        )
    elif msg.document:
        forwarded = await context.bot.send_document(
            chat_id=ADMIN_GROUP_ID,
            document=msg.document.file_id,
            caption=f"{header}\n📎 File" + (f"\n{msg.caption}" if msg.caption else ""),
            parse_mode="Markdown",
        )
    elif msg.voice:
        forwarded = await context.bot.send_voice(
            chat_id=ADMIN_GROUP_ID,
            voice=msg.voice.file_id,
            caption=f"{header}\n🎤 Voice message",
            parse_mode="Markdown",
        )
    elif msg.sticker:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=f"{header}\n🎯 Sent a sticker",
            parse_mode="Markdown",
        )
        forwarded = await context.bot.send_sticker(
            chat_id=ADMIN_GROUP_ID,
            sticker=msg.sticker.file_id,
        )
    else:
        logger.info(f"Unsupported message type from user {user.id}")
        return

    if forwarded:
        context.bot_data[forwarded.message_id] = user.id

    await msg.reply_text(
        "✅ Your message has been received. Our support team will get back to you shortly."
    )


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message

    if msg.chat.id != ADMIN_GROUP_ID:
        return
    if not msg.reply_to_message:
        return

    replied_id = msg.reply_to_message.message_id
    user_id = context.bot_data.get(replied_id)

    if not user_id:
        return

    admin = update.effective_user
    logger.info(f"Admin '{admin.full_name}' replied to user {user_id}")

    if msg.text:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📩 *Support Team:*\n\n{msg.text}",
            parse_mode="Markdown",
        )
    elif msg.photo:
        await context.bot.send_photo(
            chat_id=user_id,
            photo=msg.photo[-1].file_id,
            caption="📩 *Support Team:*" + (f"\n{msg.caption}" if msg.caption else ""),
            parse_mode="Markdown",
        )
    elif msg.video:
        await context.bot.send_video(
            chat_id=user_id,
            video=msg.video.file_id,
            caption="📩 *Support Team:*" + (f"\n{msg.caption}" if msg.caption else ""),
            parse_mode="Markdown",
        )
    elif msg.document:
        await context.bot.send_document(
            chat_id=user_id,
            document=msg.document.file_id,
            caption="📩 *Support Team:*" + (f"\n{msg.caption}" if msg.caption else ""),
            parse_mode="Markdown",
        )
    elif msg.voice:
        await context.bot.send_voice(chat_id=user_id, voice=msg.voice.file_id)
    elif msg.sticker:
        await context.bot.send_sticker(chat_id=user_id, sticker=msg.sticker.file_id)


def main() -> None:
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("chatid", chatid_command))

    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & ~filters.COMMAND,
        handle_user_message,
    ))

    if ADMIN_GROUP_ID:
        app.add_handler(MessageHandler(
            filters.Chat(ADMIN_GROUP_ID) & filters.REPLY & ~filters.COMMAND,
            handle_admin_reply,
        ))

    logger.info(f"Bot started. Admin group: {ADMIN_GROUP_ID or 'NOT SET'}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
