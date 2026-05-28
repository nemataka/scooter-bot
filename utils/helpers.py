from datetime import datetime

def format_date(date_str):
    """Санани форматлаш"""
    if not date_str:
        return "—"
    try:
        dt = datetime.strptime(str(date_str), '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%d.%m.%Y %H:%M')
    except:
        return str(date_str) if date_str else "—"

def format_amount(amount):
    """Суммани форматлаш"""
    if amount is None:
        return "0"
    return f"{int(amount):,}".replace(",", " ")

def get_status_emoji(status):
    """Статус эмодзиси"""
    emojis = {
        'new': '🆕',
        'assigned': '🔄',
        'completed': '✅',
        'cancelled': '❌'
    }
    return emojis.get(status, '❓')

def get_status_text(status):
    """Статус матни"""
    texts = {
        'new': 'Янги',
        'assigned': 'Жараёнда',
        'completed': 'Бажарилган',
        'cancelled': 'Бекор қилинган'
    }
    return texts.get(status, status)