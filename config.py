# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_NAME = os.getenv('DB_NAME', 'scooter.db')

# Овнер (эгаси)
OWNER_ID = 6057285077

# Админлар рўйхати (овнер ҳам админ)
ADMIN_IDS = [6057285077]  # Овнер ID си қўшилган!