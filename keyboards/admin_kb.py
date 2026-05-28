from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_menu():
    """Админ асосий менюси"""
    keyboard = [
        [KeyboardButton("🆕 Янги заказ қўшиш")],
        [KeyboardButton("📋 Янги заказлар"), KeyboardButton("🔄 Жараёндагилар")],
        [KeyboardButton("✅ Бажарилган"), KeyboardButton("❌ Бекор қилинган")],
        [KeyboardButton("👥 Курьерлар"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("📥 Excel отчёт"), KeyboardButton("💳 Депозитлар")],
        [KeyboardButton("💰 Депозит қўшиш")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_cancel_keyboard():
    """Бекор қилиш клавиатураси"""
    keyboard = [[KeyboardButton("🚫 Бекор қилиш")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def get_courier_list_inline(couriers):
    """Курьерлар рўйхати (инлайн)"""
    keyboard = []
    for courier in couriers:
        user_id, username, first_name, *_ = courier
        name = first_name or username or f"ID:{user_id}"
        keyboard.append([
            InlineKeyboardButton(f"🛵 {name}", callback_data=f"assign_to_{user_id}")
        ])
    keyboard.append([
        InlineKeyboardButton("📢 Барчага юбориш", callback_data="assign_all")
    ])
    keyboard.append([
        InlineKeyboardButton("❌ Заказни бекор қилиш", callback_data="cancel_order")
    ])
    return InlineKeyboardMarkup(keyboard)

def get_order_inline_menu(order_id, status):
    """Заказ бошқарув тугмалари"""
    keyboard = []
    
    if status == 'new':
        keyboard.append([
            InlineKeyboardButton("👤 Курьер танлаш", callback_data=f"select_courier_{order_id}"),
        ])
        keyboard.append([
            InlineKeyboardButton("❌ Бекор қилиш", callback_data=f"cancel_{order_id}")
        ])
    elif status == 'assigned':
        keyboard.append([
            InlineKeyboardButton("🔄 Бошқа курьер", callback_data=f"select_courier_{order_id}"),
            InlineKeyboardButton("❌ Бекор қилиш", callback_data=f"cancel_{order_id}")
        ])
    
    return InlineKeyboardMarkup(keyboard)

def get_pending_keyboard(user_id):
    """Курьер тасдиқлаш тугмалари"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Тасдиқлаш", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ Рад этиш", callback_data=f"reject_user_{user_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_courier_manage_inline(courier_id, is_active):
    """Курьер бошқарув тугмалари"""
    keyboard = []
    if is_active:
        keyboard.append([
            InlineKeyboardButton("🚫 Блоклаш", callback_data=f"block_courier_{courier_id}")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("✅ Фаоллаштириш", callback_data=f"unblock_courier_{courier_id}")
        ])
    keyboard.append([
        InlineKeyboardButton("💰 Депозит қўшиш", callback_data=f"deposit_{courier_id}")
    ])
    return InlineKeyboardMarkup(keyboard)