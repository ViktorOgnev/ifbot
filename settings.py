import os
import json

TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    with open('secrets.json') as fp:
        TOKEN = json.load(fp).get('tg_token', None)
BOTURL = f"https://api.telegram.org/bot{TOKEN}"
