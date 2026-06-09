import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_NAME = os.getenv('DB_NAME', 'scooter.db')

# Овнер (эгаси)
OWNER_ID = 6057285077

# Бошқа админлар (овнердан ташқари)
ADMIN_IDS = []  # Бошқа админлар ID'си, масалан: [123456789, 987654321]