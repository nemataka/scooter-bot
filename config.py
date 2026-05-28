import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [6057285077]
DB_NAME = os.getenv('DB_NAME', 'scooter.db')
