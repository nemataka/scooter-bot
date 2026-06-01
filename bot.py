import asyncio
import logging
import threading
from flask import Flask
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ConversationHandler, CallbackQueryHandler
)
from config import BOT_TOKEN
from database.db import init_db
from handlers.start import start
from handlers.admin import (
    start_add_order, get_client_name, get_client_phone,
    get_address, get_details, get_amount,
    show_orders, admin_callback, show_couriers,
    show_stats, send_excel, show_deposits,
    add_deposit_for_courier_start, handle_admin_deposit_amount
)
from handlers.courier import (
    my_active_orders, my_all_orders, my_completed_orders,
    my_rejected_orders, my_stats, courier_callback, show_balance
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Flask (Render port учун) ───
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())
    logger.info("База тайёр!")

    app = Application.builder().token(BOT_TOKEN).build()

    # ─── 1. /start ───
    app.add_handler(CommandHandler("start", start))

    # ─── 2. Курьер меню ───
    app.add_handler(MessageHandler(filters.Regex("^📦 Фаол заказларим$"), my_active_orders))
    app.add_handler(MessageHandler(filters.Regex("^📋 Барча заказларим$"), my_all_orders))
    app.add_handler(MessageHandler(filters.Regex("^✅ Бажарилганлар$"), my_completed_orders))
    app.add_handler(MessageHandler(filters.Regex("^❌ Рад этилганлар$"), my_rejected_orders))
    app.add_handler(MessageHandler(filters.Regex("^📊 Статистикам$"), my_stats))
    app.add_handler(MessageHandler(filters.Regex("^💰 Баланс$"), show_balance))

    # ─── 3. Админ меню ───
    app.add_handler(MessageHandler(filters.Regex("^📋 Янги заказлар$"), show_orders))
    app.add_handler(MessageHandler(filters.Regex("^🔄 Жараёндагилар$"), show_orders))
    app.add_handler(MessageHandler(filters.Regex("^✅ Бажарилган$"), show_orders))
    app.add_handler(MessageHandler(filters.Regex("^❌ Бекор қилинган$"), show_orders))
    app.add_handler(MessageHandler(filters.Regex("^👥 Курьерлар$"), show_couriers))
    app.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), show_stats))
    app.add_handler(MessageHandler(filters.Regex("^📥 Excel отчёт$"), send_excel))
    app.add_handler(MessageHandler(filters.Regex("^💳 Депозитлар$"), show_deposits))

    # ─── 4. ConversationHandler: заказ қўшиш ───
    add_order_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🆕 Янги заказ қўшиш$"), start_add_order)],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_client_name)],
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_client_phone)],
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_details)],
            4: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^🚫 Бекор қилиш$"), start),
            CommandHandler("start", start)
        ]
    )
    app.add_handler(add_order_conv)

    # ─── 5. ConversationHandler: депозит қўшиш ───
    deposit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💰 Депозит қўшиш$"), add_deposit_for_courier_start)],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_deposit_amount)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^🚫 Бекор қилиш$"), start),
            CommandHandler("start", start)
        ],
        per_message=False
    )
    app.add_handler(deposit_conv)

    # ─── 6. Callback handler'лар ───
    app.add_handler(CallbackQueryHandler(
        admin_callback,
        pattern="^(select_courier_|assign_to_|assign_all|cancel_order$|cancel_|approve_|reject_user_|deposit_|block_courier_|unblock_courier_)"
    ))
    app.add_handler(CallbackQueryHandler(
        courier_callback,
        pattern="^(done_|reject_|call_|map_|accept_)"
    ))

    # Flask ni alohida threadda ishga tushirish
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server ишга тушди!")

    logger.info("Бот ишга тушди!")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
