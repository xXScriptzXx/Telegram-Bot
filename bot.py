import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

from config import BOT_TOKEN, CRYPTO_BOT_TOKEN, ADMIN_IDS, CRYPTO_ASSET
from cryptbot import CryptoBotClient
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database("shop.db")
crypto = CryptoBotClient(CRYPTO_BOT_TOKEN)

# ───────────────────────── CONFIG ─────────────────────────
CRYPTO_OPTIONS = ["USDT", "BTC", "TON", "ETH"]


# ───────────────────────── HELPERS ─────────────────────────
def is_admin(user_id: int):
    return user_id in ADMIN_IDS


def main_keyboard(user_id: int):
    keyboard = [
        [InlineKeyboardButton("🛒 Shop", callback_data="shop")],
        [InlineKeyboardButton("💰 Balance", callback_data="balance")],
        [InlineKeyboardButton("➕ Add Money", callback_data="addmoney")],
        [InlineKeyboardButton("📦 Orders", callback_data="orders")]
    ]

    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin", callback_data="admin")])

    return InlineKeyboardMarkup(keyboard)


# ───────────────────────── START ─────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.username)

    balance = db.get_balance(user.id)

    await update.message.reply_text(
        f"Welcome {user.first_name}\n\n💰 Balance: ${balance:.2f}",
        reply_markup=main_keyboard(user.id)
    )


# ───────────────────────── HOME ─────────────────────────
async def home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    balance = db.get_balance(user.id)

    await query.edit_message_text(
        f"🏠 Main Menu\n\n💰 Balance: ${balance:.2f}",
        reply_markup=main_keyboard(user.id)
    )


# ───────────────────────── SHOP ─────────────────────────
async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    products = db.get_products()

    if not products:
        await query.edit_message_text("No products available.")
        return

    keyboard = [
        [InlineKeyboardButton(
            f"{p['emoji']} {p['name']} - ${p['price']:.2f}",
            callback_data=f"product_{p['id']}"
        )]
        for p in products
    ]

    keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="home")])

    await query.edit_message_text(
        "🛒 Shop:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ───────────────────────── PRODUCT ─────────────────────────
async def product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pid = int(query.data.split("_")[1])
    p = db.get_product(pid)

    if not p:
        await query.edit_message_text("Product not found.")
        return

    await query.edit_message_text(
        f"{p['emoji']} {p['name']}\n\n{p['description']}\n\n💰 ${p['price']:.2f}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Buy", callback_data=f"buy_{pid}")],
            [InlineKeyboardButton("⬅️ Back", callback_data="shop")]
        ])
    )


# ───────────────────────── BUY ─────────────────────────
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    pid = int(query.data.split("_")[1])

    p = db.get_product(pid)
    balance = db.get_balance(user_id)

    if not p:
        await query.edit_message_text("Product not found.")
        return

    if balance < p["price"]:
        await query.edit_message_text(
            f"❌ Not enough balance\nNeed ${p['price'] - balance:.2f} more",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Money", callback_data="addmoney")],
                [InlineKeyboardButton("⬅️ Back", callback_data=f"product_{pid}")]
            ])
        )
        return

    db.deduct_balance(user_id, p["price"])
    order_id = db.create_order(user_id, pid, p["price"])

    await query.edit_message_text(
        f"✅ Purchase successful!\n\nOrder #{order_id}\n\n📦 {p['delivery']}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Home", callback_data="home")]
        ])
    )


# ───────────────────────── ADD MONEY (STEP 1) ─────────────────────────
async def addmoney(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton(c, callback_data=f"crypto_{c}")]
        for c in CRYPTO_OPTIONS
    ]

    keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="home")])

    await query.edit_message_text(
        "💰 Select cryptocurrency:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ───────────────────────── ADD MONEY (STEP 2) ─────────────────────────
async def select_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    asset = query.data.split("_")[1]
    user_id = query.from_user.id
    amount = 10  # default top-up

    try:
        invoice = await crypto.create_invoice(
            amount=amount,
            description="Balance top-up",
            payload=str(user_id),
            asset=asset
        )

        db.save_invoice(user_id, invoice["invoice_id"], amount)

        await query.edit_message_text(
            f"💳 Pay with {asset}:\n\n{invoice['bot_invoice_url']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Home", callback_data="home")]
            ])
        )

    except Exception as e:
        await query.edit_message_text(f"❌ Error:\n{e}")


# ───────────────────────── BALANCE ─────────────────────────
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    bal = db.get_balance(query.from_user.id)

    await query.edit_message_text(
        f"💰 Balance: ${bal:.2f}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Money", callback_data="addmoney")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")]
        ])
    )


# ───────────────────────── MAIN ─────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(home, pattern="home"))
    app.add_handler(CallbackQueryHandler(shop, pattern="shop"))
    app.add_handler(CallbackQueryHandler(product, pattern="product_"))
    app.add_handler(CallbackQueryHandler(buy, pattern="buy_"))

    app.add_handler(CallbackQueryHandler(balance, pattern="balance"))
    app.add_handler(CallbackQueryHandler(addmoney, pattern="addmoney"))
    app.add_handler(CallbackQueryHandler(select_crypto, pattern="crypto_"))

    logger.info("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()