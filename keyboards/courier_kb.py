from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_courier_menu():
    """Курьер асосий менюси"""
    keyboard = [
        [KeyboardButton("📦 Фаол заказларим")],
        [KeyboardButton("📋 Барча заказларим"), KeyboardButton("📊 Статистикам")],
        [KeyboardButton("✅ Бажарилганлар"), KeyboardButton("❌ Рад этилганлар")],
        [KeyboardButton("💰 Баланс")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_courier_order_inline(order_id):
    """Курьер учун заказ тугмалари"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Бажарилди", callback_data=f"done_{order_id}"),
            InlineKeyboardButton("❌ Рад этиш", callback_data=f"reject_{order_id}")
        ],
        [
            InlineKeyboardButton("📞 Клиент", callback_data=f"call_{order_id}"),
            InlineKeyboardButton("📍 Манзил", callback_data=f"map_{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_accept_keyboard(order_id):
    """Заказни қабул қилиш тугмаси"""
    keyboard = [
        [InlineKeyboardButton("✅ Қабул қилиш", callback_data=f"accept_{order_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)