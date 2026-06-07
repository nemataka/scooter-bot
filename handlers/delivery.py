import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database.db import (
    create_delivery_order, get_delivery_order, start_delivery,
    finish_delivery, save_tracking_point, get_active_delivery,
    get_courier_deliveries, get_setting, haversine,
    get_active_couriers, get_admin_ids, update_delivery_status,
    assign_delivery  # ← шуни қўшинг
)
from keyboards.delivery_kb import (
    get_delivery_order_inline, get_delivery_finish_inline,
    get_delivery_admin_inline, get_delivery_courier_list_inline
)
from utils.helpers import format_amount, format_date
from config import OWNER_ID

logger = logging.getLogger(__name__)

# ConversationHandler holatlari
(D_CLIENT_NAME, D_CLIENT_PHONE, D_FROM_ADDRESS, D_TO_ADDRESS) = range(10, 14)


# ─── АДМИН: Янги юк заказ яратиш ───────────────────

async def start_add_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🚛 Янги юк заказ тугмаси"""
    from database.db import get_admin_ids
    admin_ids = await get_admin_ids()
    if update.effective_user.id not in admin_ids and update.effective_user.id != OWNER_ID:
        return ConversationHandler.END

    await update.message.reply_text(
        "🚛 <b>Янги юк заказ</b>\n\n"
        "👤 Мижоз исмини киритинг:",
        parse_mode='HTML'
    )
    return D_CLIENT_NAME


async def d_get_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚫 Бекор қилиш":
        from keyboards.admin_kb import get_admin_menu
        await update.message.reply_text("❌ Бекор қилинди.", reply_markup=get_admin_menu())
        return ConversationHandler.END
    context.user_data['delivery'] = {'client_name': update.message.text}
    await update.message.reply_text("📱 Мижоз телефонини киритинг:")
    return D_CLIENT_PHONE


async def d_get_client_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚫 Бекор қилиш":
        from keyboards.admin_kb import get_admin_menu
        await update.message.reply_text("❌ Бекор қилинди.", reply_markup=get_admin_menu())
        return ConversationHandler.END
    context.user_data['delivery']['client_phone'] = update.message.text
    await update.message.reply_text("📍 Олиш манзилини киритинг:")
    return D_FROM_ADDRESS


async def d_get_from_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚫 Бекор қилиш":
        from keyboards.admin_kb import get_admin_menu
        await update.message.reply_text("❌ Бекор қилинди.", reply_markup=get_admin_menu())
        return ConversationHandler.END
    context.user_data['delivery']['from_address'] = update.message.text
    await update.message.reply_text("📍 Етказиб бериш манзилини киритинг:")
    return D_TO_ADDRESS


async def d_get_to_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚫 Бекор қилиш":
        from keyboards.admin_kb import get_admin_menu
        await update.message.reply_text("❌ Бекор қилинди.", reply_markup=get_admin_menu())
        return ConversationHandler.END

    d = context.user_data['delivery']
    d['to_address'] = update.message.text

    delivery_id = await create_delivery_order(
        courier_id=None,
        admin_id=update.effective_user.id,
        client_name=d['client_name'],
        client_phone=d['client_phone'],
        from_address=d['from_address'],
        to_address=d['to_address']
    )

    context.user_data.clear()

    from keyboards.admin_kb import get_admin_menu
    await update.message.reply_text(
        f"✅ <b>Юк заказ яратилди!</b>\n\n"
        f"🆔 #{delivery_id}\n"
        f"👤 {d['client_name']} | 📱 {d['client_phone']}\n"
        f"📍 {d['from_address']} → {d['to_address']}\n\n"
        f"Курьер белгилаш учун «🚛 Юк заказлари» га ўтинг.",
        reply_markup=get_admin_menu(),
        parse_mode='HTML'
    )
    return ConversationHandler.END


# ─── АДМИН: Юк заказларини кўриш ───────────────────

async def show_delivery_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🚛 Юк заказлари"""
    from database.db import get_admin_ids, get_delivery_orders_by_status
    admin_ids = await get_admin_ids()
    if update.effective_user.id not in admin_ids and update.effective_user.id != OWNER_ID:
        return

    orders = await get_delivery_orders_by_status('new')
    active = await get_delivery_orders_by_status('active')
    orders = orders + active

    if not orders:
        await update.message.reply_text("📭 Юк заказлар йўқ.")
        return

    await update.message.reply_text("🚛 <b>Юк заказлар:</b>\n", parse_mode='HTML')

    for order in orders:
        d_id = order[0]
        courier_id = order[1]
        client = order[3]
        phone = order[4]
        from_addr = order[5]
        to_addr = order[6]
        status = order[7]

        status_icon = "🆕" if status == 'new' else "🔄"

        msg = (
            f"{status_icon} <b>Юк #{d_id}</b>\n"
            f"👤 {client} | 📱 {phone}\n"
            f"📍 {from_addr} → {to_addr}\n"
        )

        if courier_id:
            from database.db import get_user
            courier = await get_user(courier_id)
            if courier:
                msg += f"🚛 Курьер: <b>{courier[2] or courier[1]}</b>\n"

        await update.message.reply_text(
            msg,
            reply_markup=get_delivery_admin_inline(d_id),
            parse_mode='HTML'
        )


# ─── АДМИН: Курьер белгилаш ─────────────────────────

async def delivery_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Юк ташиш админ callback'лари"""
    query = update.callback_query
    await query.answer()
    data = query.data

    from database.db import get_admin_ids
    admin_ids = await get_admin_ids()
    if update.effective_user.id not in admin_ids and update.effective_user.id != OWNER_ID:
        return

    # Курьер белгилаш
    if data.startswith("delivery_assign_"):
        delivery_id = int(data.split("_")[2])
        couriers = await get_active_couriers()
        if not couriers:
            await query.edit_message_text("❌ Фаол курьерлар йўқ!")
            return
        await query.edit_message_text(
            f"🚛 <b>Юк #{delivery_id}</b> учун курьер танланг:",
            reply_markup=get_delivery_courier_list_inline(couriers, delivery_id),
            parse_mode='HTML'
        )
        return

    # Курьерга бириктириш
    if data.startswith("delivery_to_"):
        parts = data.split("_")
        courier_id = int(parts[2])
        delivery_id = int(parts[3])

        await assign_delivery(delivery_id, courier_id)
        order = await get_delivery_order(delivery_id)

        try:
            await context.bot.send_message(
                chat_id=courier_id,
                text=(
                    f"🚛 <b>Янги юк заказ!</b>\n\n"
                    f"🆔 #{delivery_id}\n"
                    f"👤 {order[3]} | 📱 {order[4]}\n"
                    f"📍 {order[5]} → {order[6]}\n\n"
                    f"Тайёр бўлганда Старт босинг!"
                ),
                parse_mode='HTML',
                reply_markup=get_delivery_order_inline(delivery_id)
            )
        except Exception as e:
            logger.error(f"Курьерга хабар юборишда хато: {e}")

        await query.edit_message_text(
            f"✅ Юк #{delivery_id} курьерга бириктирилди!"
        )
        return

    # Бекор қилиш
    if data.startswith("delivery_cancel_"):
        delivery_id = int(data.split("_")[2])
        await update_delivery_status(delivery_id, 'cancelled')
        await query.edit_message_text(f"❌ Юк #{delivery_id} бекор қилинди!")
        return


# ─── КУРЬЕР: Старт ──────────────────────────────────

async def delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """▶️ Старт босилганда"""
    query = update.callback_query
    await query.answer()

    delivery_id = int(query.data.split("_")[2])
    courier_id = update.effective_user.id
    order = await get_delivery_order(delivery_id)

    if not order:
        await query.edit_message_text("❌ Заказ топилмади!")
        return

    context.user_data['active_delivery'] = delivery_id
    context.user_data['delivery_started'] = False
    context.user_data['total_km'] = 0.0
    context.user_data['wait_seconds'] = 0.0
    context.user_data['last_lat'] = None
    context.user_data['last_lon'] = None
    context.user_data['last_time'] = None
    context.user_data['wait_started'] = None

    await query.edit_message_text(
        f"🚛 <b>Юк #{delivery_id}</b>\n\n"
        f"📍 {order[5]} → {order[6]}\n\n"
        f"⚠️ Жорий локациянгизни юборинг:\n"
        f"📎 → Файл юбориш → Локация → <b>Жорий локация юбориш</b>\n\n"
        f"GPS трекинг автоматик бошланади!",
        parse_mode='HTML'
    )


async def handle_live_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Live Location ишлов бериш"""
    if not update.message or not update.message.location:
        return

    courier_id = update.effective_user.id
    location = update.message.location
    lat = location.latitude
    lon = location.longitude

    delivery_id = context.user_data.get('active_delivery')
    if not delivery_id:
        active = await get_active_delivery(courier_id)
        if active:
            delivery_id = active[0]
            context.user_data['active_delivery'] = delivery_id
            context.user_data['delivery_started'] = True
            context.user_data['total_km'] = 0.0
            context.user_data['wait_seconds'] = 0.0
            context.user_data['wait_started'] = None
        else:
            return

    order = await get_delivery_order(delivery_id)
    if not order or order[7] not in ('new', 'active', 'assigned'):
        return

    now = datetime.now()

    # Биринчи локация — Старт
    if not context.user_data.get('delivery_started'):
        await start_delivery(delivery_id, lat, lon)
        context.user_data['delivery_started'] = True
        context.user_data['last_lat'] = lat
        context.user_data['last_lon'] = lon
        context.user_data['last_time'] = now

        await update.message.reply_text(
            f"🟢 <b>Буюртма бошланди!</b>\n\n"
            f"🆔 #{delivery_id}\n"
            f"📍 {order[5]} → {order[6]}\n\n"
            f"🛵 GPS трекинг ишлаяпти...",
            parse_mode='HTML',
            reply_markup=get_delivery_finish_inline(delivery_id)
        )

        # Админга хабар
        admin_ids = await get_admin_ids()
        for admin_id in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"🟢 <b>Юк ташиш бошланди!</b>\n\n"
                        f"🆔 #{delivery_id}\n"
                        f"👤 {order[3]} | 📱 {order[4]}\n"
                        f"📍 {order[5]} → {order[6]}\n"
                        f"🚛 Курьер: {update.effective_user.first_name}"
                    ),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Админга хабар юборишда хато: {e}")
        return

    # Кейинги локациялар
    last_lat = context.user_data.get('last_lat')
    last_lon = context.user_data.get('last_lon')
    last_time = context.user_data.get('last_time')

    if last_lat is None:
        context.user_data['last_lat'] = lat
        context.user_data['last_lon'] = lon
        context.user_data['last_time'] = now
        return

    elapsed = (now - last_time).total_seconds()
    if elapsed <= 0:
        return

    distance_km = haversine(last_lat, last_lon, lat, lon)
    speed_kmh = distance_km / elapsed * 3600

    speed_threshold = float(await get_setting('speed_threshold') or 5)

    if speed_kmh >= speed_threshold:
        mode = 'moving'
        context.user_data['total_km'] += distance_km
        context.user_data['wait_started'] = None
    else:
        mode = 'waiting'
        if context.user_data.get('wait_started') is None:
            context.user_data['wait_started'] = now
        context.user_data['wait_seconds'] += elapsed

    await save_tracking_point(delivery_id, lat, lon, speed_kmh, mode)

    context.user_data['last_lat'] = lat
    context.user_data['last_lon'] = lon
    context.user_data['last_time'] = now


# ─── КУРЬЕР: Тугатиш ────────────────────────────────

async def delivery_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🏁 Тугатиш босилганда"""
    query = update.callback_query
    await query.answer()

    delivery_id = int(query.data.split("_")[2])
    courier_id = update.effective_user.id
    order = await get_delivery_order(delivery_id)

    if not order:
        await query.edit_message_text("❌ Заказ топилмади!")
        return

    total_km = context.user_data.get('total_km', 0)
    wait_seconds = context.user_data.get('wait_seconds', 0)
    wait_minutes = wait_seconds / 60

    last_lat = context.user_data.get('last_lat') or order[8]
    last_lon = context.user_data.get('last_lon') or order[9]

    # Нарх ҳисоблаш
    km_price = float(await get_setting('km_price') or 2000)
    wait_free = float(await get_setting('wait_free_minutes') or 5)
    wait_price = float(await get_setting('wait_price_per_minute') or 500)
    commission_pct = float(await get_setting('commission_percent') or 15)

    km_cost = total_km * km_price
    billable_wait = max(0, wait_minutes - wait_free)
    wait_cost = billable_wait * wait_price
    total_price = km_cost + wait_cost
    commission = total_price * commission_pct / 100

    await finish_delivery(delivery_id, total_km, wait_minutes, total_price, last_lat, last_lon)

    result_text = (
        f"🏁 <b>Юк ташиш якунланди!</b>\n\n"
        f"🆔 #{delivery_id}\n"
        f"👤 {order[3]} | 📱 {order[4]}\n"
        f"📍 {order[5]} → {order[6]}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🛵 Масофа: <b>{total_km:.1f} км</b>\n"
        f"💰 Км нархи: {format_amount(km_cost)} сўм\n"
        f"⏱ Кутиш: {wait_minutes:.0f} дақ "
        f"(бепул: {wait_free:.0f} дақ)\n"
        f"💸 Кутиш нархи: {format_amount(wait_cost)} сўм\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💵 Жами: <b>{format_amount(total_price)} сўм</b>\n"
        f"📊 Комиссия ({commission_pct:.0f}%): "
        f"{format_amount(commission)} сўм"
    )

    await query.edit_message_text(result_text, parse_mode='HTML')

    # Админга хабар
    admin_ids = await get_admin_ids()
    for admin_id in admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"✅ <b>Юк ташиш якунланди!</b>\n\n{result_text}",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Админга хабар юборишда хато: {e}")

    # Context тозалаш
    for key in ['active_delivery', 'delivery_started', 'last_lat',
                'last_lon', 'last_time', 'total_km', 'wait_seconds', 'wait_started']:
        context.user_data.pop(key, None)


# ─── КУРЬЕР: Юк тарихи ──────────────────────────────

async def my_deliveries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🚛 Юк ташишларим"""
    courier_id = update.effective_user.id
    deliveries = await get_courier_deliveries(courier_id)

    if not deliveries:
        await update.message.reply_text("📭 Юк ташиш тарихи йўқ.")
        return

    text = "🚛 <b>Юк ташиш тарихингиз:</b>\n\n"
    total_earned = 0

    for d in deliveries[:10]:
        d_id = d[0]
        client = d[3]
        status = d[7]
        km = d[12] or 0
        price = d[14] or 0

        if status == 'completed':
            total_earned += price
            text += f"✅ #{d_id} | {client} | {km:.1f} км | {format_amount(price)} сўм\n"
        elif status == 'active':
            text += f"🔄 #{d_id} | {client} | Жараёнда\n"
        else:
            text += f"❌ #{d_id} | {client} | Бекор\n"

    text += f"\n💰 Жами: <b>{format_amount(total_earned)} сўм</b>"
    await update.message.reply_text(text, parse_mode='HTML')