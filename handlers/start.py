from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from config import OWNER_ID
from database.db import add_user, update_user_role, get_user, get_admin_ids, get_setting, set_setting
from keyboards.admin_kb import get_admin_menu, get_pending_keyboard
from keyboards.courier_kb import get_courier_menu

# Conversation states
CHOOSE_ROLE, ENTER_PASSWORD = range(20, 22)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт командаси"""
    user = update.effective_user
    await add_user(user.id, user.username, user.first_name, user.last_name)
    db_user = await get_user(user.id)

    # ⚠️ ОВНЕРНИ БИРИНЧИ ТЕКШИРИШ КЕРАК!
    if user.id == OWNER_ID:
        # Овнер ҳар доим овнер сифатида киради
        await update_user_role(user.id, 'admin')  # Ролни админ қилиб қўямиз
        await update.message.reply_text(
            f"👑 Ассалому алейкум, {user.first_name}!\n\n"
            f"Сиз овнер сифатида кирдингиз.\n"
            f"Барча ҳуқуқларга эгасиз.",
            reply_markup=get_admin_menu(is_owner=True)  # is_owner=True!
        )
        return ConversationHandler.END

    # Мавжуд админ (овнердан бошқа)
    if db_user and db_user[4] == 'admin':
        await update.message.reply_text(
            f"👑 Ассалому алейкум, {user.first_name}!\n\n"
            f"Керакли бўлимни танланг:",
            reply_markup=get_admin_menu(is_owner=False)  # is_owner=False
        )
        return ConversationHandler.END

    # Мавжуд курьер
    if db_user and db_user[4] == 'courier':
        if db_user[6] == 0:  # blocked field
            await update.message.reply_text(
                "🚫 Сизнинг аккаунтингиз блокланган.\n"
                "Админ билан боғланинг."
            )
        else:
            await update.message.reply_text(
                f"🛵 Ассалому алейкум, {user.first_name}!\n\n"
                f"Керакли бўлимни танланг:",
                reply_markup=get_courier_menu()
            )
        return ConversationHandler.END

    # Кутилаётган курьер
    if db_user and db_user[4] == 'pending':
        await update.message.reply_text(
            "⏳ Сизнинг сўровингиз кўриб чиқилмоқда.\n"
            "Админ тасдиқлаганидан кейин қайта /start босинг."
        )
        return ConversationHandler.END

    # Янги фойдаланувчи — рол танлаш
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🛵 Курьер"), KeyboardButton("👑 Админ")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await update.message.reply_text(
        f"👋 Ассалому алейкум, {user.first_name}!\n\n"
        f"Сиз кимсиз?",
        reply_markup=keyboard
    )
    return CHOOSE_ROLE


async def choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рол танлаш"""
    text = update.message.text
    user = update.effective_user

    if text == "🛵 Курьер":
        await update_user_role(user.id, 'pending')

        # Админларга хабар (овнер ҳам админлар қаторида)
        admin_ids = await get_admin_ids()
        for admin_id in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🆕 <b>Янги курьер сўрови!</b>\n\n"
                         f"🆔 ID: <code>{user.id}</code>\n"
                         f"👤 Исм: {user.first_name}\n"
                         f"📝 Username: @{user.username if user.username else 'йўқ'}\n\n"
                         f"Тасдиқлаш ёки рад этиш учун тугмалардан фойдаланинг.",
                    parse_mode='HTML',
                    reply_markup=get_pending_keyboard(user.id)
                )
            except Exception as e:
                print(f"Админга хабар юборишда хато: {e}")

        await update.message.reply_text(
            "📝 Сизнинг курьерлик сўровингиз админга юборилди.\n"
            "Илтимос, тасдиқланишини кутинг.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    elif text == "👑 Админ":
        await update.message.reply_text(
            "🔐 Админ паролини киритинг:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ENTER_PASSWORD

    else:
        await update.message.reply_text("Илтимос, тугмалардан бирини танланг.")
        return CHOOSE_ROLE


async def enter_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Парол текшириш"""
    user = update.effective_user
    entered = update.message.text

    # Паролни базадан олиш
    admin_password = await get_setting('admin_password')
    if not admin_password:
        admin_password = '1qadam2024'  # Default парол

    if entered == admin_password:
        await update_user_role(user.id, 'admin')
        await update.message.reply_text(
            f"✅ Хуш келибсиз, {user.first_name}!\n\n"
            f"Керакли бўлимни танланг:",
            reply_markup=get_admin_menu(is_owner=False)  # is_owner=False
        )

        # Овнерга хабар
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"👑 <b>Янги админ кирди!</b>\n\n"
                     f"👤 {user.first_name}\n"
                     f"📝 @{user.username if user.username else 'йўқ'}\n"
                     f"🆔 <code>{user.id}</code>",
                parse_mode='HTML'
            )
        except:
            pass

        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ Парол нотўғри!\n\n"
            "Қайтадан киритинг ёки /start босинг."
        )
        return ENTER_PASSWORD