import asyncio
import logging
import threading
import sqlite3
from flask_cors import CORS
from flask import Flask, jsonify, request
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ConversationHandler, CallbackQueryHandler
)
from config import BOT_TOKEN, DB_NAME
from database.db import init_db
from handlers.start import start, choose_role, enter_password
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
from handlers.delivery import (
    start_add_delivery, d_get_client_name, d_get_client_phone,
    d_get_from_address, d_get_to_address,
    show_delivery_orders, delivery_admin_callback,
    delivery_start, delivery_finish,
    handle_live_location, my_deliveries
)
from handlers.owner import (
    add_admin_start, add_admin_id, WAIT_ADMIN_ID,
    remove_admin_start, remove_admin_id, REMOVE_ADMIN_ID,
    cmd_admins,
    cmd_setpassword, cmd_settings
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════
# FLASK
# ═══════════════════════════════════════════════════
flask_app = Flask(__name__)
CORS(flask_app)

def db_query(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_execute(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    conn.close()


@flask_app.route('/')
def home():
    return "Bot is running!"


@flask_app.route('/api/stats')
def api_stats():
    stats = db_query("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='new' THEN 1 ELSE 0 END) as new_orders,
            SUM(CASE WHEN status='assigned' THEN 1 ELSE 0 END) as assigned,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) as cancelled,
            COALESCE(SUM(CASE WHEN status='completed' THEN amount ELSE 0 END), 0) as total_amount
        FROM orders
    """)
    return jsonify(stats[0] if stats else {})


@flask_app.route('/api/orders')
def api_orders():
    status = request.args.get('status', 'new')
    orders = db_query("""
        SELECT o.*, u.first_name as courier_name, u.username as courier_username
        FROM orders o
        LEFT JOIN users u ON o.courier_id = u.user_id
        WHERE o.status = ?
        ORDER BY o.created_at DESC
    """, (status,))
    return jsonify(orders)


@flask_app.route('/api/couriers')
def api_couriers():
    couriers = db_query("""
        SELECT u.*,
            COUNT(o.order_id) as total_orders,
            SUM(CASE WHEN o.status='completed' THEN 1 ELSE 0 END) as completed,
            COALESCE((SELECT SUM(amount) FROM deposits WHERE courier_id=u.user_id), 0)
            - COALESCE((SELECT SUM(commission) FROM transactions WHERE courier_id=u.user_id), 0) as balance
        FROM users u
        LEFT JOIN orders o ON u.user_id = o.courier_id
        WHERE u.role = 'courier'
        GROUP BY u.user_id
    """)
    return jsonify(couriers)


@flask_app.route('/api/order/assign', methods=['POST'])
def api_assign_order():
    data = request.json
    order_id = data.get('order_id')
    courier_id = data.get('courier_id')
    if not order_id or not courier_id:
        return jsonify({'error': 'order_id va courier_id kerak'}), 400
    db_execute("""
        UPDATE orders SET courier_id=?, status='assigned',
        assigned_at=CURRENT_TIMESTAMP WHERE order_id=?
    """, (courier_id, order_id))
    return jsonify({'success': True})


@flask_app.route('/api/order/cancel', methods=['POST'])
def api_cancel_order():
    data = request.json
    order_id = data.get('order_id')
    if not order_id:
        return jsonify({'error': 'order_id kerak'}), 400
    db_execute("""
        UPDATE orders SET status='cancelled',
        cancelled_at=CURRENT_TIMESTAMP,
        cancel_reason='Админ томонидан бекор қилинди'
        WHERE order_id=?
    """, (order_id,))
    return jsonify({'success': True})


@flask_app.route('/api/courier/orders')
def api_courier_orders():
    courier_id = request.args.get('courier_id')
    status = request.args.get('status', 'assigned')
    if not courier_id:
        return jsonify({'error': 'courier_id kerak'}), 400
    orders = db_query("""
        SELECT * FROM orders
        WHERE courier_id=? AND status=?
        ORDER BY created_at DESC
    """, (courier_id, status))
    return jsonify(orders)


@flask_app.route('/api/courier/stats')
def api_courier_stats():
    courier_id = request.args.get('courier_id')
    if not courier_id:
        return jsonify({'error': 'courier_id kerak'}), 400
    stats = db_query("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) as cancelled,
            COALESCE(SUM(CASE WHEN status='completed' THEN amount ELSE 0 END), 0) as total_amount
        FROM orders WHERE courier_id=?
    """, (courier_id,))
    balance = db_query("""
        SELECT
            COALESCE((SELECT SUM(amount) FROM deposits WHERE courier_id=?), 0)
            - COALESCE((SELECT SUM(commission) FROM transactions WHERE courier_id=?), 0) as balance
    """, (courier_id, courier_id))
    result = stats[0] if stats else {}
    result['balance'] = balance[0]['balance'] if balance else 0
    return jsonify(result)


# ═══════════════════════════════════════════════════
# DELIVERY API ENDPOINTS
# ═══════════════════════════════════════════════════

@flask_app.route('/api/delivery/orders')
def api_delivery_orders():
    """Курьернинг юк заказларини олиш"""
    courier_id = request.args.get('courier_id')
    status = request.args.get('status', 'assigned')
    if not courier_id:
        return jsonify({'error': 'courier_id kerak'}), 400
    orders = db_query("""
        SELECT * FROM delivery_orders
        WHERE courier_id=? AND status=?
        ORDER BY created_at DESC
    """, (courier_id, status))
    return jsonify(orders)


@flask_app.route('/api/delivery/start', methods=['POST'])
def api_delivery_start():
    """Юк заказни бошлаш"""
    data = request.json
    delivery_id = data.get('delivery_id')
    lat = data.get('lat')
    lon = data.get('lon')
    if not delivery_id:
        return jsonify({'error': 'delivery_id kerak'}), 400
    db_execute("""
        UPDATE delivery_orders
        SET status='active', start_lat=?, start_lon=?,
            started_at=CURRENT_TIMESTAMP
        WHERE delivery_id=?
    """, (lat, lon, delivery_id))
    return jsonify({'success': True})


@flask_app.route('/api/delivery/finish', methods=['POST'])
def api_delivery_finish():
    """Юк заказни тугатиш ва нарх ҳисоблаш"""
    data = request.json
    delivery_id = data.get('delivery_id')
    total_km = data.get('total_km', 0)
    wait_minutes = data.get('wait_minutes', 0)
    lat = data.get('lat', 0)
    lon = data.get('lon', 0)

    if not delivery_id:
        return jsonify({'error': 'delivery_id kerak'}), 400

    # Sozlamalarni olish
    settings = db_query("SELECT key, value FROM settings")
    s = {}
    for row in settings:
        try:
            s[row['key']] = float(row['value'])
        except (ValueError, TypeError):
            s[row['key']] = row['value'] if row['value'] else 0

    km_price = s.get('km_price', 2000)
    wait_free = s.get('wait_free_minutes', 5)
    wait_price = s.get('wait_price_per_minute', 500)
    commission_pct = s.get('commission_percent', 15)

    km_cost = total_km * km_price
    billable_wait = max(0, wait_minutes - wait_free)
    wait_cost = billable_wait * wait_price
    total_price = km_cost + wait_cost
    commission = total_price * commission_pct / 100

    db_execute("""
        UPDATE delivery_orders
        SET status='completed', end_lat=?, end_lon=?,
            total_km=?, wait_minutes=?, total_price=?,
            finished_at=CURRENT_TIMESTAMP
        WHERE delivery_id=?
    """, (lat, lon, total_km, wait_minutes, total_price, delivery_id))

    return jsonify({
        'success': True,
        'total_km': total_km,
        'km_cost': km_cost,
        'wait_minutes': wait_minutes,
        'billable_wait': billable_wait,
        'wait_cost': wait_cost,
        'total_price': total_price,
        'commission': commission,
        'commission_percent': commission_pct
    })


@flask_app.route('/api/delivery/track', methods=['POST'])
def api_delivery_track():
    """Локацияни кузатиш"""
    data = request.json
    delivery_id = data.get('delivery_id')
    lat = data.get('lat')
    lon = data.get('lon')
    speed = data.get('speed', 0)
    mode = data.get('mode', 'moving')

    if not delivery_id:
        return jsonify({'error': 'delivery_id kerak'}), 400

    db_execute("""
        INSERT INTO delivery_tracking
        (delivery_id, latitude, longitude, speed, mode)
        VALUES (?, ?, ?, ?, ?)
    """, (delivery_id, lat, lon, speed, mode))

    return jsonify({'success': True})


@flask_app.route('/api/order/complete', methods=['POST'])
def api_complete_order():
    """Оддий заказни тугатиш"""
    data = request.json
    order_id = data.get('order_id')
    if not order_id:
        return jsonify({'error': 'order_id kerak'}), 400
    db_execute("""
        UPDATE orders SET status='completed',
        completed_at=CURRENT_TIMESTAMP
        WHERE order_id=?
    """, (order_id,))
    return jsonify({'success': True})


def run_flask():
    flask_app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)


# ═══════════════════════════════════════════════════
# TELEGRAM BOT
# ═══════════════════════════════════════════════════
def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())
    logger.info("База тайёр!")

    app = Application.builder().token(BOT_TOKEN).build()

    # ─── 0. Админни ўчириш ConversationHandler ───
    remove_admin_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗑 Админни ўчириш$"), remove_admin_start)],
        states={
            REMOVE_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin_id)],
        },
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(remove_admin_conv)

    # ─── 1. Админ қўшиш ConversationHandler ───
    add_admin_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👑 Админ қўшиш$"), add_admin_start)],
        states={
            WAIT_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_id)],
        },
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(add_admin_conv)

    # ─── 2. Start ConversationHandler ───
    start_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            20: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_role)],
            21: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_password)],
        },
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(start_conv)

    # ─── 3. Owner командалари ───
    app.add_handler(CommandHandler("admins", cmd_admins))
    app.add_handler(CommandHandler("setpassword", cmd_setpassword))
    app.add_handler(CommandHandler("settings", cmd_settings))

    # ─── 4. Курьер меню ───
    app.add_handler(MessageHandler(filters.Regex("^📦 Фаол заказларим$"), my_active_orders))
    app.add_handler(MessageHandler(filters.Regex("^📋 Барча заказларим$"), my_all_orders))
    app.add_handler(MessageHandler(filters.Regex("^✅ Бажарилганлар$"), my_completed_orders))
    app.add_handler(MessageHandler(filters.Regex("^❌ Рад этилганлар$"), my_rejected_orders))
    app.add_handler(MessageHandler(filters.Regex("^📊 Статистикам$"), my_stats))
    app.add_handler(MessageHandler(filters.Regex("^💰 Баланс$"), show_balance))
    app.add_handler(MessageHandler(filters.Regex("^🚛 Юк ташишларим$"), my_deliveries))

    # ─── 5. Админ меню ───
    app.add_handler(MessageHandler(filters.Regex("^📋 Янги заказлар$"), show_orders))
    app.add_handler(MessageHandler(filters.Regex("^🔄 Жараёндагилар$"), show_orders))
    app.add_handler(MessageHandler(filters.Regex("^✅ Бажарилган$"), show_orders))
    app.add_handler(MessageHandler(filters.Regex("^❌ Бекор қилинган$"), show_orders))
    app.add_handler(MessageHandler(filters.Regex("^👥 Курьерлар$"), show_couriers))
    app.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), show_stats))
    app.add_handler(MessageHandler(filters.Regex("^📥 Excel отчёт$"), send_excel))
    app.add_handler(MessageHandler(filters.Regex("^💳 Депозитлар$"), show_deposits))
    app.add_handler(MessageHandler(filters.Regex("^🚛 Юк заказлари$"), show_delivery_orders))

    # ─── 6. ConversationHandler: заказ қўшиш ───
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

    # ─── 7. ConversationHandler: депозит қўшиш ───
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

    # ─── 8. ConversationHandler: юк заказ қўшиш ───
    add_delivery_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🚛 Янги юк заказ$"), start_add_delivery)],
        states={
            10: [MessageHandler(filters.TEXT & ~filters.COMMAND, d_get_client_name)],
            11: [MessageHandler(filters.TEXT & ~filters.COMMAND, d_get_client_phone)],
            12: [MessageHandler(filters.TEXT & ~filters.COMMAND, d_get_from_address)],
            13: [MessageHandler(filters.TEXT & ~filters.COMMAND, d_get_to_address)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^🚫 Бекор қилиш$"), start),
            CommandHandler("start", start)
        ]
    )
    app.add_handler(add_delivery_conv)

    # ─── 9. Live Location ───
    app.add_handler(MessageHandler(filters.LOCATION, handle_live_location))

    # ─── 10. Delivery callback'лар ───
    app.add_handler(CallbackQueryHandler(
        delivery_admin_callback,
        pattern="^(delivery_assign_|delivery_to_|delivery_cancel_)"
    ))
    app.add_handler(CallbackQueryHandler(
        delivery_start,
        pattern="^delivery_start_"
    ))
    app.add_handler(CallbackQueryHandler(
        delivery_finish,
        pattern="^delivery_finish_"
    ))

    # ─── 11. Асосий callback handler'лар ───
    app.add_handler(CallbackQueryHandler(
        admin_callback,
        pattern="^(select_courier_|assign_to_|assign_all|cancel_order$|cancel_|approve_|reject_user_|deposit_|block_courier_|unblock_courier_)"
    ))
    app.add_handler(CallbackQueryHandler(
        courier_callback,
        pattern="^(done_|reject_|call_|map_|accept_)"
    ))

    # Flask алоҳида threadда
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server ишга тушди! (http://0.0.0.0:8080)")

    logger.info("Бот ишга тушди!")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()