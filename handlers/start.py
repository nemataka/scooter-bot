from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from database.db import add_user, update_user_role, get_user
from keyboards.admin_kb import get_admin_menu, get_pending_keyboard
from keyboards.courier_kb import get_courier_menu

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт командаси"""
    user = update.effective_user
    
    print(f"DEBUG: User {user.id} ({user.first_name}) started bot")
    
    # Фойдаланувчини базага қўшиш
    await add_user(user.id, user.username, user.first_name, user.last_name)
    
    # Фойдаланувчини базадан олиш
    db_user = await get_user(user.id)
    print(f"DEBUG: DB user role = {db_user[4] if db_user else 'None'}")
    
    # Админ текшириш
    if user.id in ADMIN_IDS:
        print("DEBUG: Admin detected")
        await update_user_role(user.id, 'admin')
        await update.message.reply_text(
            f"👑 Ассалому алейкум, {user.first_name}!\n\n"
            f"Сиз админ сифатида кирдингиз.\nКеракли бўлимни танланг:",
            reply_markup=get_admin_menu()
        )
    elif db_user and db_user[4] == 'courier':
        # Блокланганликни текшириш
        if db_user[6] == 0:  # is_active = 0
            print("DEBUG: Blocked courier")
            await update.message.reply_text(
                "🚫 Сизнинг аккаунтингиз блокланган.\n"
                "Админ билан боғланинг."
            )
        else:
            print("DEBUG: Existing courier")
            await update.message.reply_text(
                f"🛵 Ассалому алейкум, {user.first_name}!\n\n"
                f"Сиз курьер сифатида кирдингиз.\nКеракли бўлимни танланг:",
                reply_markup=get_courier_menu()
            )
    elif db_user and db_user[4] == 'pending':
        print("DEBUG: Pending user - NOTIFYING ADMIN")
        
        # Админга хабар
        for admin_id in ADMIN_IDS:
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
                print("DEBUG: Admin notified!")
            except Exception as e:
                print(f"DEBUG ERROR: {e}")
        
        await update.message.reply_text(
            "⏳ Сизнинг сўровингиз кўриб чиқилмоқда.\n"
            "Админ тасдиқлаганидан кейин қайта /start босинг."
        )
    else:
        print("DEBUG: New user, sending to admin")
        await update_user_role(user.id, 'pending')
        
        # Админга хабар
        for admin_id in ADMIN_IDS:
            print(f"DEBUG: Sending message to admin {admin_id}")
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
                print("DEBUG: Message sent successfully")
            except Exception as e:
                print(f"DEBUG ERROR: {e}")
        
        await update.message.reply_text(
            "📝 Сизнинг курьерлик сўровингиз админга юборилди.\n"
            "Илтимос, тасдиқланишини кутинг."
        )