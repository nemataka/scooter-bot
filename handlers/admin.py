from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS
from database.db import (
    create_order, get_orders_by_status, get_all_couriers, get_active_couriers,
    get_order, assign_order, update_order_status,
    get_general_stats, get_stats_by_courier, get_all_orders,
    update_user_role, get_pending_couriers, save_broadcast_message,
    get_all_deposits, get_courier_balance, add_deposit, get_user,
    toggle_courier_active
)
from keyboards.admin_kb import (
    get_admin_menu, get_cancel_keyboard,
    get_courier_list_inline, get_order_inline_menu,
    get_courier_manage_inline
)
from keyboards.courier_kb import get_accept_keyboard
from services.reports import generate_excel_report
from utils.helpers import format_date, format_amount, get_status_emoji, get_status_text
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import os

(CLIENT_NAME, CLIENT_PHONE, ADDRESS, DETAILS, AMOUNT) = range(5)
DEPOSIT_AMOUNT = 0


async def start_add_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    await update.message.reply_text(
        "📝 Янги заказ қўшиш\n\n👤 Мижоз исмини киритинг:",
        reply_markup=get_cancel_keyboard()
    )
    return CLIENT_NAME


async def get_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚫 Бекор қилиш":
        await update.message.reply_text("❌ Бекор қилинди.", reply_markup=get_admin_menu())
        return ConversationHandler.END
    context.user_data['order'] = {'client_name': update.message.text}
    await update.message.reply_text("📱 Мижоз телефон рақамини киритинг:")
    return CLIENT_PHONE


async def get_client_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚫 Бекор қилиш":
        await update.message.reply_text("❌ Бекор қилинди.", reply_markup=get_admin_menu())
        return ConversationHandler.END
    context.user_data['order']['client_phone'] = update.message.text
    await update.message.reply_text("📍 Етказиб бериш манзилини киритинг:")
    return ADDRESS


async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚫 Бекор қилиш":
        await update.message.reply_text("❌ Бекор қилинди.", reply_markup=get_admin_menu())
        return ConversationHandler.END
    context.user_data['order']['address'] = update.message.text
    await update.message.reply_text("📝 Буюртма тафсилотларини киритинг:")
    return DETAILS


async def get_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚫 Бекор қилиш":
        await update.message.reply_text("❌ Бекор қилинди.", reply_markup=get_admin_menu())
        return ConversationHandler.END
    context.user_data['order']['details'] = update.message.text
    await update.message.reply_text("💰 Заказ суммасини киритинг (сўмда):")
    return AMOUNT


async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚫 Бекор қилиш":
        await update.message.reply_text("❌ Бекор қилинди.", reply_markup=get_admin_menu())
        return ConversationHandler.END
    try:
        amount = float(update.message.text.replace(",", "").replace(" ", ""))
    except:
        await update.message.reply_text("❌ Фақат рақам киритинг! Қайтадан:")
        return AMOUNT
    order = context.user_data['order']
    order_id = await create_order(
        client_name=order['client_name'],
        client_phone=order['client_phone'],
        delivery_address=order['address'],
        order_details=order['details'],
        amount=amount,
        created_by=update.effective_user.id
    )
    text = (
        f"✅ <b>Заказ яратилди!</b>\n\n"
        f"🆔 ID: <b>#{order_id}</b>\n"
        f"👤 Мижоз: {order['client_name']}\n"
        f"📱 Тел: {order['client_phone']}\n"
        f"📍 Манзил: {order['address']}\n"
        f"📝 Буюртма: {order['details']}\n"
        f"💰 Сумма: {format_amount(amount)} сўм\n\n"
        f"Курьер танлаш учун «Янги заказлар» бўлимига ўтинг."
    )
    context.user_data.clear()
    await update.message.reply_text(text, reply_markup=get_admin_menu(), parse_mode='HTML')
    return ConversationHandler.END


async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    status_map = {
        "📋 Янги заказлар": 'new',
        "🔄 Жараёндагилар": 'assigned',
        "✅ Бажарилган": 'completed',
        "❌ Бекор қилинган": 'cancelled'
    }

    status = status_map.get(update.message.text)
    if not status:
        return

    orders = await get_orders_by_status(status)

    if not orders:
        await update.message.reply_text(f"📭 {get_status_text(status)} заказлар йўқ.")
        return

    await update.message.reply_text(
        f"📋 <b>{get_status_text(status)} заказлар:</b>\n", parse_mode='HTML'
    )

    for order in orders:
        order_id = order[0]
        client_name = order[1]
        client_phone = order[2]
        address = order[3]
        details = order[4]
        amount = order[5]
        order_status = order[6]
        courier_id = order[7]
        created_at = order[9]

        msg = (
            f"{get_status_emoji(order_status)} <b>Заказ #{order_id}</b>\n"
            f"👤 {client_name} | 📱 {client_phone}\n"
            f"📍 {address}\n"
            f"📝 {details}\n"
            f"💰 {format_amount(amount)} сўм\n"
            f"🕐 {format_date(created_at)}"
        )

        if courier_id:
            courier = await get_user(courier_id)
            if courier:
                courier_name = courier[2] or courier[1] or f"ID:{courier_id}"
                msg += f"\n🛵 Курьер: <b>{courier_name}</b>"

        await update.message.reply_text(
            msg,
            reply_markup=get_order_inline_menu(order_id, order_status),
            parse_mode='HTML'
        )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        return

    if data.startswith("approve_"):
        courier_id = int(data.split("_")[1])
        await update_user_role(courier_id, 'courier')
        await query.edit_message_text("✅ Курьер тасдиқланди!")
        try:
            await context.bot.send_message(
                chat_id=courier_id,
                text="✅ Сизнинг курьерлик сўровингиз тасдиқланди!\nҚайта /start босинг."
            )
        except:
            pass
        return

    if data.startswith("reject_user_"):
        courier_id = int(data.split("_")[2])
        await update_user_role(courier_id, 'client')
        await query.edit_message_text("❌ Курьер рад этилди!")
        try:
            await context.bot.send_message(
                chat_id=courier_id,
                text="❌ Сизнинг курьерлик сўровингиз рад этилди."
            )
        except:
            pass
        return

    if data.startswith("block_courier_"):
        courier_id = int(data.split("_")[2])
        await toggle_courier_active(courier_id, False)
        courier = await get_user(courier_id)
        name = courier[2] or courier[1] or f"ID:{courier_id}"
        await query.edit_message_text(
            f"🚫 <b>{name}</b> блокланди!",
            parse_mode='HTML',
            reply_markup=get_courier_manage_inline(courier_id, False)
        )
        try:
            await context.bot.send_message(
                chat_id=courier_id,
                text="🚫 Сизнинг аккаунтингиз вақтинча блокланди.\nАдмин билан боғланинг."
            )
        except:
            pass
        return

    if data.startswith("unblock_courier_"):
        courier_id = int(data.split("_")[2])
        await toggle_courier_active(courier_id, True)
        courier = await get_user(courier_id)
        name = courier[2] or courier[1] or f"ID:{courier_id}"
        await query.edit_message_text(
            f"✅ <b>{name}</b> фаоллаштирилди!",
            parse_mode='HTML',
            reply_markup=get_courier_manage_inline(courier_id, True)
        )
        try:
            await context.bot.send_message(
                chat_id=courier_id,
                text="✅ Сизнинг аккаунтингиз фаоллаштирилди!\nҚайта /start босинг."
            )
        except:
            pass
        return

    if data.startswith("deposit_"):
        courier_id = int(data.split("_")[1])
        context.user_data['deposit_courier_id'] = courier_id
        courier = await get_user(courier_id)
        name = courier[2] or courier[1] or f"ID:{courier_id}"
        await query.edit_message_text(
            f"💳 <b>{name}</b> учун депозит суммасини киритинг (сўмда):",
            parse_mode='HTML'
        )
        context.user_data['awaiting_admin_deposit'] = True
        return

    if data.startswith("select_courier_"):
        order_id = int(data.split("_")[2])
        context.user_data['pending_order'] = order_id
        couriers = await get_active_couriers()
        if not couriers:
            await query.edit_message_text("❌ Фаол курьерлар топилмади!")
            return
        await query.edit_message_text(
            f"🛵 <b>Заказ #{order_id}</b> учун курьер танланг:",
            reply_markup=get_courier_list_inline(couriers),
            parse_mode='HTML'
        )
        return

    if data.startswith("assign_to_"):
        courier_id = int(data.split("_")[2])
        order_id = context.user_data.get('pending_order')
        if order_id:
            await assign_order(order_id, courier_id)
            order = await get_order(order_id)
            try:
                await context.bot.send_message(
                    chat_id=courier_id,
                    text=(
                        f"🆕 <b>Янги заказ!</b>\n\n"
                        f"🆔 #{order_id}\n"
                        f"📍 {order[3]}\n"
                        f"📝 {order[4]}\n"
                        f"💰 {format_amount(order[5])} сўм\n\n"
                        f"📋 «Фаол заказларим» бўлимида кўринг."
                    ),
                    parse_mode='HTML'
                )
            except:
                pass
            await query.edit_message_text(f"✅ Заказ #{order_id} курьерга бириктирилди!")
        return

    if data == "assign_all":
        order_id = context.user_data.get('pending_order')
        if order_id:
            couriers = await get_active_couriers()
            order = await get_order(order_id)
            await update_order_status(order_id, 'broadcast')
            for courier in couriers:
                try:
                    msg = await context.bot.send_message(
                        chat_id=courier[0],
                        text=(
                            f"📢 <b>Янги заказ (барчага)!</b>\n\n"
                            f"🆔 #{order_id}\n"
                            f"📍 {order[3]}\n"
                            f"📝 {order[4]}\n"
                            f"💰 {format_amount(order[5])} сўм\n\n"
                            f"Қабул қилиш учун тугмани босинг!"
                        ),
                        parse_mode='HTML',
                        reply_markup=get_accept_keyboard(order_id)
                    )
                    await save_broadcast_message(order_id, courier[0], msg.message_id)
                except:
                    pass
            await query.edit_message_text(f"📢 Заказ #{order_id} барча курьерларга юборилди!")
        return

    if data == "cancel_order":
        order_id = context.user_data.get('pending_order')
        if order_id:
            await update_order_status(order_id, 'cancelled', reason="Админ томонидан бекор қилинди")
            await query.edit_message_text(f"❌ Заказ #{order_id} бекор қилинди!")
        return

    if data.startswith("cancel_"):
        order_id = int(data.split("_")[1])
        await update_order_status(order_id, 'cancelled', reason="Админ томонидан бекор қилинди")
        await query.edit_message_text(f"❌ Заказ #{order_id} бекор қилинди!")
        return


async def show_couriers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    couriers = await get_all_couriers()
    pending = await get_pending_couriers()

    if not couriers and not pending:
        await update.message.reply_text("👥 Курьерлар йўқ.")
        return

    if pending:
        text = "⏳ <b>Тасдиқланиши кутилмоқда:</b>\n\n"
        for p in pending:
            user_id, username, first_name, *_ = p
            name = first_name or "Исм йўқ"
            uname = f"@{username}" if username else "Username йўқ"
            text += f"🆕 <b>{name}</b>\n├─ 📝 {uname}\n└─ 🆔 <code>{user_id}</code>\n\n"
        await update.message.reply_text(text, parse_mode='HTML')

    for courier in couriers:
        user_id, username, first_name, last_name, role, phone, is_active, created_at = courier
        stats = await get_stats_by_courier(user_id)
        balance = await get_courier_balance(user_id)
        total, total_amount, completed, cancelled = stats if stats else (0, 0, 0, 0)
        name = first_name or "Исм йўқ"
        uname = f"@{username}" if username else "Username йўқ"
        status_icon = "✅" if is_active else "🚫"

        text = (
            f"{status_icon} <b>{name}</b>\n"
            f"├─ 📝 {uname}\n"
            f"├─ 🆔 <code>{user_id}</code>\n"
            f"├─ 📋 Жами: {total} | ✅ {completed} | ❌ {cancelled}\n"
            f"├─ 💰 Сумма: {format_amount(total_amount)} сўм\n"
            f"└─ 💳 Баланс: {format_amount(balance)} сўм"
        )

        await update.message.reply_text(
            text,
            reply_markup=get_courier_manage_inline(user_id, is_active),
            parse_mode='HTML'
        )


async def show_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    deposits = await get_all_deposits()

    if not deposits:
        await update.message.reply_text("💳 Депозитлар топилмади.")
        return

    text = "💳 <b>Депозитлар тарихи:</b>\n\n"
    for d in deposits[:20]:
        d_id, courier_id, amount, created_at, first_name, username = d
        name = first_name or username or f"ID:{courier_id}"
        text += f"├─ {name}: {format_amount(amount)} сўм | {format_date(created_at)}\n"

    await update.message.reply_text(text, parse_mode='HTML')


async def add_deposit_for_courier_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END

    couriers = await get_all_couriers()
    if not couriers:
        await update.message.reply_text("❌ Курьерлар топилмади.")
        return ConversationHandler.END

    keyboard = []
    for courier in couriers:
        user_id, username, first_name, *_ = courier
        name = first_name or username or f"ID:{user_id}"
        keyboard.append([InlineKeyboardButton(name, callback_data=f"deposit_{user_id}")])

    await update.message.reply_text(
        "🛵 Депозит қўшиш учун курьерни танланг:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DEPOSIT_AMOUNT


async def handle_admin_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    courier_id = context.user_data.get('deposit_courier_id')

    if not courier_id:
        await update.message.reply_text("⚠️ Аввал курьерни танланг.", reply_markup=get_admin_menu())
        return ConversationHandler.END

    try:
        amount = float(update.message.text.replace(",", "").replace(" ", ""))
    except:
        await update.message.reply_text("❌ Фақат рақам киритинг!")
        return DEPOSIT_AMOUNT

    await add_deposit(courier_id, amount)
    balance = await get_courier_balance(courier_id)

    courier = await get_user(courier_id)
    name = courier[2] or courier[1] or f"ID:{courier_id}"

    context.user_data.pop('deposit_courier_id', None)
    context.user_data.pop('awaiting_admin_deposit', None)

    await update.message.reply_text(
        f"✅ Депозит қўшилди!\n"
        f"🛵 Курьер: {name}\n"
        f"💰 Сумма: {format_amount(amount)} сўм\n"
        f"💳 Баланс: {format_amount(balance)} сўм",
        reply_markup=get_admin_menu()
    )

    try:
        await context.bot.send_message(
            chat_id=courier_id,
            text=(
                f"💳 <b>Балансингиз тўлдирилди!</b>\n\n"
                f"💰 Қўшилди: {format_amount(amount)} сўм\n"
                f"💳 Жорий баланс: {format_amount(balance)} сўм"
            ),
            parse_mode='HTML'
        )
    except:
        pass

    return ConversationHandler.END


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    stats = await get_general_stats()

    if not stats:
        await update.message.reply_text("📊 Статистика мавжуд эмас.")
        return

    total, total_amount, completed, in_progress, new_orders, cancelled = stats

    text = (
        f"📊 <b>Умумий статистика</b>\n\n"
        f"📋 Жами заказлар: <b>{total or 0}</b>\n"
        f"├─ 🆕 Янги: {new_orders or 0}\n"
        f"├─ 🔄 Жараёнда: {in_progress or 0}\n"
        f"├─ ✅ Бажарилган: {completed or 0}\n"
        f"└─ ❌ Бекор қил.: {cancelled or 0}\n\n"
        f"💰 Жами сумма: <b>{format_amount(total_amount)} сўм</b>"
    )

    await update.message.reply_text(text, parse_mode='HTML')


async def send_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    await update.message.reply_text("⏳ Excel отчёт тайёрланмоқда...")

    try:
        filepath = await generate_excel_report()
        with open(filepath, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(filepath),
                caption="📊 Заказлар бўйича тўлиқ отчёт"
            )
        os.remove(filepath)
    except Exception as e:
        await update.message.reply_text(f"❌ Хатолик: {e}")