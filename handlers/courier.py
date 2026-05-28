import logging
from telegram import Update
from telegram.ext import ContextTypes
from database.db import (
    get_courier_orders, update_order_status,
    get_order, assign_order_atomic,
    get_broadcast_messages, delete_broadcast_messages,
    get_stats_by_courier, get_courier_balance,
    add_transaction, get_courier_transactions
)
from keyboards.courier_kb import get_courier_order_inline
from utils.helpers import format_date, format_amount, get_status_emoji
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


async def my_active_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    courier_id = update.effective_user.id
    orders = await get_courier_orders(courier_id, 'assigned')

    if not orders:
        await update.message.reply_text("📭 Фаол заказлар йўқ.")
        return

    await update.message.reply_text(
        f"📦 <b>Фаол заказларингиз:</b> {len(orders)} та\n", parse_mode='HTML'
    )

    for order in orders:
        order_id, client_name, client_phone, address, details, amount, *_ = order

        text = (
            f"{get_status_emoji('assigned')} <b>Заказ #{order_id}</b>\n"
            f"👤 {client_name} | 📱 {client_phone}\n"
            f"📍 {address}\n"
            f"📝 {details}\n"
            f"💰 {format_amount(amount)} сўм"
        )

        await update.message.reply_text(
            text,
            reply_markup=get_courier_order_inline(order_id),
            parse_mode='HTML'
        )


async def my_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    courier_id = update.effective_user.id
    orders = await get_courier_orders(courier_id)

    if not orders:
        await update.message.reply_text("📭 Заказлар топилмади.")
        return

    text = "📋 <b>Барча заказларингиз:</b>\n\n"

    for order in orders[:20]:
        order_id, client_name, _, address, _, amount, status, *_, created_at = order
        text += (
            f"{get_status_emoji(status)} #{order_id} | "
            f"{client_name} | "
            f"{format_amount(amount)} сўм | "
            f"{format_date(created_at)}\n"
        )

    await update.message.reply_text(text, parse_mode='HTML')


async def my_completed_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    courier_id = update.effective_user.id
    orders = await get_courier_orders(courier_id, 'completed')

    if not orders:
        await update.message.reply_text("✅ Бажарилган заказлар йўқ.")
        return

    total_amount = sum(order[5] or 0 for order in orders)

    text = (
        f"✅ <b>Бажарилган заказлар:</b> {len(orders)} та\n"
        f"💰 Жами сумма: {format_amount(total_amount)} сўм\n\n"
    )

    for order in orders[:10]:
        order_id, client_name, _, address, _, amount, *_, completed_at = order
        text += f"✅ #{order_id} | {client_name} | {format_amount(amount)} сўм | {format_date(completed_at)}\n"

    await update.message.reply_text(text, parse_mode='HTML')


async def my_rejected_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    courier_id = update.effective_user.id
    orders = await get_courier_orders(courier_id, 'cancelled')

    if not orders:
        await update.message.reply_text("❌ Рад этилган заказлар йўқ.")
        return

    text = f"❌ <b>Рад этилган заказлар:</b> {len(orders)} та\n\n"

    for order in orders[:10]:
        order_id, client_name, _, address, _, amount, *_, created_at = order
        text += f"❌ #{order_id} | {client_name} | {format_amount(amount)} сўм | {format_date(created_at)}\n"

    await update.message.reply_text(text, parse_mode='HTML')


async def my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    courier_id = update.effective_user.id
    stats = await get_stats_by_courier(courier_id)
    balance = await get_courier_balance(courier_id)

    if not stats:
        await update.message.reply_text("📊 Статистика мавжуд эмас.")
        return

    total, total_amount, completed, cancelled = stats

    text = (
        f"📊 <b>Сизнинг статистикангиз</b>\n\n"
        f"📋 Жами заказлар: <b>{total or 0}</b>\n"
        f"✅ Бажарилган: {completed or 0}\n"
        f"❌ Рад этилган: {cancelled or 0}\n"
        f"💰 Жами сумма: <b>{format_amount(total_amount)} сўм</b>\n"
        f"💳 Баланс: <b>{format_amount(balance)} сўм</b>"
    )

    await update.message.reply_text(text, parse_mode='HTML')


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    courier_id = update.effective_user.id
    balance = await get_courier_balance(courier_id)
    transactions = await get_courier_transactions(courier_id)

    text = f"💰 <b>Балансингиз:</b> {format_amount(balance)} сўм\n\n"

    if transactions:
        text += "📋 <b>Охирги транзакциялар:</b>\n"
        for t in transactions[:5]:
            t_id, order_id, c_id, amount, commission, t_type, created_at = t
            text += f"├─ Заказ #{order_id}: {format_amount(amount)} сўм | Комиссия: {format_amount(commission)} сўм\n"

    await update.message.reply_text(text, parse_mode='HTML')


async def courier_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    courier_id = update.effective_user.id
    courier_name = update.effective_user.first_name

    # ─── Broadcast заказни қабул қилиш ───
    if data.startswith("accept_"):
        order_id = int(data.split("_")[1])

        # RACE CONDITION ТУЗАТИЛДИ:
        # assign_order_atomic фақат status='broadcast' бўлса UPDATE қилади.
        # Биринчи курьер ютади, қолганлар "аллақачон қабул қилинган" кўради.
        success = await assign_order_atomic(order_id, courier_id)

        if success:
            order = await get_order(order_id)

            await query.edit_message_text(
                f"✅ Заказ #{order_id} сизга бириктирилди!\n"
                f"📍 {order[3]}\n"
                f"💰 {format_amount(order[5])} сўм"
            )

            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"📢 <b>Заказ қабул қилинди!</b>\n\n"
                            f"🆔 #{order_id}\n"
                            f"👤 Мижоз: {order[1]}\n"
                            f"📍 {order[3]}\n"
                            f"💰 {format_amount(order[5])} сўм\n"
                            f"🛵 Курьер: {courier_name}"
                        ),
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Админга хабар юборишда хато: {e}")

            # Бошқа курьерлардаги broadcast хабарларни ўчириш
            broadcast_msgs = await get_broadcast_messages(order_id)
            for b_courier_id, msg_id in broadcast_msgs:
                if b_courier_id != courier_id:
                    try:
                        await context.bot.edit_message_text(
                            chat_id=b_courier_id,
                            message_id=msg_id,
                            text=f"❌ Заказ #{order_id} бошқа курьер томонидан қабул қилинди."
                        )
                    except Exception as e:
                        logger.warning(f"Broadcast хабарни ўзгартиришда хато: {e}")

            await delete_broadcast_messages(order_id)
        else:
            # Бошқа курьер илгариlab олган
            await query.edit_message_text("❌ Заказ аллақачон бошқа курьер томонидан қабул қилинди!")
        return

    # ─── Заказни бажарилди деб белгилаш ───
    if data.startswith("done_"):
        order_id = int(data.split("_")[1])
        await update_order_status(order_id, 'completed')

        order = await get_order(order_id)
        order_amount = order[5] or 0
        commission = order_amount * 0.15
        await add_transaction(order_id, courier_id, order_amount, commission)

        balance = await get_courier_balance(courier_id)

        await query.edit_message_text(
            f"✅ Заказ #{order_id} бажарилди!\n"
            f"💰 Сумма: {format_amount(order[5])} сўм\n"
            f"💸 Комиссия (15%): {format_amount(commission)} сўм\n"
            f"💳 Баланс: {format_amount(balance)} сўм"
        )

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"✅ <b>Заказ бажарилди!</b>\n\n"
                        f"🆔 #{order_id}\n"
                        f"👤 Мижоз: {order[1]}\n"
                        f"💰 Сумма: {format_amount(order[5])} сўм\n"
                        f"💸 Комиссия: {format_amount(commission)} сўм\n"
                        f"🛵 Курьер: {courier_name}"
                    ),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Админга хабар юборишда хато: {e}")

        if balance <= 0:
            try:
                await context.bot.send_message(
                    chat_id=courier_id,
                    text="⚠️ <b>Диққат!</b> Депозитингиз тугади!\nАдмин билан боғланинг.",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Курьерга огоҳлантириш юборишда хато: {e}")
        return

    # ─── Заказни рад этиш ───
    if data.startswith("reject_"):
        order_id = int(data.split("_")[1])
        await update_order_status(order_id, 'cancelled', reason="Курьер рад этди")
        await query.edit_message_text(f"❌ Заказ #{order_id} рад этилди!")

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"❌ <b>Заказ рад этилди!</b>\n\n"
                        f"🆔 #{order_id}\n"
                        f"🛵 Курьер: {courier_name}"
                    ),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Админга хабар юборишда хато: {e}")
        return

    # ─── Телефон рақамини кўрсатиш ───
    if data.startswith("call_"):
        order_id = int(data.split("_")[1])
        order = await get_order(order_id)
        await query.edit_message_text(
            f"📱 <b>Заказ #{order_id}</b>\n"
            f"Клиент телефони: <code>{order[2]}</code>",
            parse_mode='HTML'
        )
        return

    # ─── Манзилни кўрсатиш ───
    if data.startswith("map_"):
        order_id = int(data.split("_")[1])
        order = await get_order(order_id)
        await query.edit_message_text(
            f"📍 <b>Заказ #{order_id}</b>\n"
            f"Манзил: {order[3]}",
            parse_mode='HTML'
        )
        return