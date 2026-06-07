from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_delivery_order_inline(delivery_id):
    """Юк ташиш закази тугмалари (курьер учун)"""
    keyboard = [
        [InlineKeyboardButton("▶️ Старт", callback_data=f"delivery_start_{delivery_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_delivery_finish_inline(delivery_id):
    """Тугатиш тугмаси"""
    keyboard = [
        [InlineKeyboardButton("🏁 Тугатиш", callback_data=f"delivery_finish_{delivery_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_delivery_admin_inline(delivery_id):
    """Админ юк заказ бошқаруви"""
    keyboard = [
        [InlineKeyboardButton("🚛 Курьер белгилаш", callback_data=f"delivery_assign_{delivery_id}")],
        [InlineKeyboardButton("❌ Бекор қилиш", callback_data=f"delivery_cancel_{delivery_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_delivery_courier_list_inline(couriers, delivery_id):
    """Юк ташиш учун курьер рўйхати"""
    keyboard = []
    for courier in couriers:
        user_id, username, first_name, *_ = courier
        name = first_name or username or f"ID:{user_id}"
        keyboard.append([
            InlineKeyboardButton(
                f"🚛 {name}",
                callback_data=f"delivery_to_{user_id}_{delivery_id}"
            )
        ])
    keyboard.append([
        InlineKeyboardButton("❌ Бекор қилиш", callback_data=f"delivery_cancel_{delivery_id}")
    ])
    return InlineKeyboardMarkup(keyboard)