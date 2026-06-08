import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from config import OWNER_ID
from database.db import get_user, update_user_role, get_admin_ids, get_setting, set_setting
from keyboards.admin_kb import get_admin_menu
from utils.helpers import format_amount

logger = logging.getLogger(__name__)

# Conversation states
WAIT_ADMIN_ID = 30
REMOVE_ADMIN_ID = 31   # Фақат бир марта


async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """👑 Админ қўшиш тугмаси"""
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text(
        "👑 <b>Янги админ қўшиш</b>\n\n"
        "Админнинг Telegram ID сини киритинг:\n\n"
        "<i>ID олиш учун @userinfobot га /start юборинг</i>",
        parse_mode='HTML'
    )
    return WAIT_ADMIN_ID


async def add_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ ID киритилганда"""
    if update.effective_user.id != OWNER_ID:
        return ConversationHandler.END

    try:
        new_admin_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Фақат рақам киритинг!")
        return WAIT_ADMIN_ID

    if new_admin_id == OWNER_ID:
        await update.message.reply_text("❌ Сиз аллақачон овнерсиз!")
        return ConversationHandler.END

    user = await get_user(new_admin_id)
    if not user:
        await update.message.reply_text(
            f"❌ ID {new_admin_id} базада топилмади.\n"
            "Фойдаланувчи аввал ботга /start босиши керак."
        )
        return WAIT_ADMIN_ID

    await update_user_role(new_admin_id, 'admin')
    name = user[2] or user[1] or f"ID:{new_admin_id}"

    await update.message.reply_text(
        f"✅ <b>{name}</b> админ қилинди!\n"
        f"🆔 <code>{new_admin_id}</code>",
        parse_mode='HTML',
        reply_markup=get_admin_menu(is_owner=True)
    )

    try:
        await context.bot.send_message(
            chat_id=new_admin_id,
            text="👑 Сиз админ қилиндингиз!\nҚайта /start босинг."
        )
    except Exception as e:
        logger.error(f"Янги админга хабар юборишда хато: {e}")

    return ConversationHandler.END


async def remove_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🗑 Админни ўчириш тугмаси"""
    if update.effective_user.id != OWNER_ID:
        return

    admin_ids = await get_admin_ids()
    if not admin_ids:
        await update.message.reply_text("👥 Админлар йўқ.")
        return ConversationHandler.END  # END qaytarish kerak

    text = "🗑 <b>Қайси админни ўчириш?</b>\n\n"
    for admin_id in admin_ids:
        user = await get_user(admin_id)
        if user:
            name = user[2] or user[1] or f"ID:{admin_id}"
            text += f"👤 {name} — <code>{admin_id}</code>\n"

    text += "\n🆔 Ўчириладиган админнинг ID сини киритинг:"

    await update.message.reply_text(text, parse_mode='HTML')
    return REMOVE_ADMIN_ID


async def remove_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ ID киритилганда ўчириш"""
    if update.effective_user.id != OWNER_ID:
        return ConversationHandler.END

    try:
        admin_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Фақат рақам киритинг!")
        return REMOVE_ADMIN_ID

    if admin_id == OWNER_ID:
        await update.message.reply_text("❌ Овнерни ўчириб бўлмайди!")
        return ConversationHandler.END

    user = await get_user(admin_id)
    if not user or user[4] != 'admin':
        await update.message.reply_text(f"❌ ID {admin_id} админ эмас!")
        return REMOVE_ADMIN_ID

    await update_user_role(admin_id, 'client')
    name = user[2] or user[1] or f"ID:{admin_id}"

    await update.message.reply_text(
        f"✅ <b>{name}</b> админликдан олинди!",
        parse_mode='HTML',
        reply_markup=get_admin_menu(is_owner=True)
    )

    try:
        await context.bot.send_message(
            chat_id=admin_id,
            text="ℹ️ Сизнинг админлик ҳуқуқингиз олинди."
        )
    except:
        pass

    return ConversationHandler.END


# cmd_removeadmin ЎЧИРИЛСИН (бу қисмни олиб ташланг)


async def cmd_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admins — барча админлар"""
    if update.effective_user.id != OWNER_ID:
        return
    admin_ids = await get_admin_ids()
    if not admin_ids:
        await update.message.reply_text("👥 Админлар йўқ.")
        return
    text = "👑 <b>Админлар рўйхати:</b>\n\n"
    for admin_id in admin_ids:
        user = await get_user(admin_id)
        if user:
            name = user[2] or user[1] or f"ID:{admin_id}"
            uname = f"@{user[1]}" if user[1] else "username йўқ"
            text += f"👤 <b>{name}</b> | {uname} | <code>{admin_id}</code>\n"
    await update.message.reply_text(text, parse_mode='HTML')


async def cmd_setpassword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setpassword yangi_parol"""
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text("❗ /setpassword <янги_парол>")
        return
    new_password = context.args[0]
    await set_setting('admin_password', new_password)
    await update.message.reply_text(f"✅ Парол ўзгартирилди: <code>{new_password}</code>", parse_mode='HTML')


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/settings — жорий созламалар"""
    if update.effective_user.id != OWNER_ID:
        return
    from database.db import get_all_settings
    s = await get_all_settings()
    text = (
        f"⚙️ <b>Жорий созламалар:</b>\n\n"
        f"🔐 Админ пароли: <code>{s.get('admin_password', '1qadam2024')}</code>\n"
        f"🛵 1 км нархи: <b>{format_amount(float(s.get('km_price', 2000)))} сўм</b>\n"
        f"⏱ Бепул кутиш: <b>{s.get('wait_free_minutes', 5)} дақиқа</b>\n"
        f"💸 Кутиш нархи: <b>{format_amount(float(s.get('wait_price_per_minute', 500)))} сўм/дақ</b>\n"
        f"📊 Комиссия: <b>{s.get('commission_percent', 15)}%</b>\n\n"
        f"/setpassword — парол ўзгартириш\n"
        f"/setprice — км нархи\n"
        f"/setfree — бепул кутиш\n"
        f"/setwait — кутиш нархи\n"
        f"/setcommission — комиссия %"
    )
    await update.message.reply_text(text, parse_mode='HTML')