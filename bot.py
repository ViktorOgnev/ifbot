# TODO: escape sql
import datetime
import json
import logging
import re
import requests
import sys
import time
import threading
import urllib

import db
import settings

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
LOG = logging.getLogger(__name__)

NOTIFY_DICT = {
    time.time() + 30: ['user', 'id', 'list']
}


DAYS = 21
BIAS = 10 * 60
mutex = threading.Lock()

INIT_MSG = """
Привет, {}.
Этот бот  поможет Вам пройти переходный период на интервальном голодании.
В течение выбранного периода времени он будет слать Вам сообщение
на выбранное количество минут позже, чтобы постепенно сменить
режим питания.
Просто введите время, во сколько Вы обычно завтракаете.
Остальное бот посчитает сам и раз в день будет присылать сообщения,
когда можно начинать питаться.
Пока-что бот понимает время в формате "чч:мм"
Если Вы выбрали неверно введите /cancel
"""


def get_url(url):
    return requests.get(url).content.decode('utf8')


def get_json_from_url(url):
    return json.loads(get_url(url))


def get_lastchatid_n_text(updates):
    n_upd = len(updates['result'])
    last_upd = n_upd - 1
    text = updates['result'][last_upd]['message']['text']
    chat_id = updates['result'][last_upd]['message']['chat']['id']
    return text, chat_id


def send(text, chat_id, reply_markup=None):
    text = f"text={urllib.parse.quote_plus(text)}"
    chat_id = f"chat_id={chat_id}"
    parse_mode = f"parse_mode=Markdown"
    reply_markup = f"reply_markup={reply_markup}" if reply_markup else ""
    get_url(f"{settings.BOTURL}/sendMessage?{text}&{chat_id}&{parse_mode}&{reply_markup}")


def get_updates(offset=None, url=settings.BOTURL, timeout=100):
    timeout = f"?timeout={timeout}"
    offset = f"&offset={offset}" if offset else ""
    return get_json_from_url(f"{url}/getUpdates{timeout}{offset}")


def make_seconds(timestr):

    hour, minute = map(int, timestr.split(':'))
    now = datetime.datetime.now()
    start = datetime.datetime(now.year, now.month, now.day, hour, minute)
    if start > now:
        # if a time specified by user is yet to come today
        # then we will notify today for the first time
        seconds = int(start.strftime('%s'))
    else:
        # else we will start tomorrow
        seconds = int(start.strftime('%s')) + 60 * 60 * 24

    return seconds


def do_update(mapping, chat_id, starttime):
    t = starttime
    mapping.setdefault(t, []).append(chat_id)
    for day in range(DAYS):
        t += 60 * 60 * 24 + BIAS
        mapping.setdefault(t, []).append(chat_id)


def handle_one(update, db):
    try:
        text = update['message']['text']
        chat_id = update['message']['chat']['id']
        username = update['message']['chat']['first_name']
    except KeyError as e:
        print(f'There was an exception {e}')
        return
    with mutex:
        start = db.get(chat_id)
    print(start)
    keyboard = build_keyboard()
    if start:
        if text.startswith(('/отмен', '/cancel')):
            db.delete(chat_id)
            send('Уведомления отменены. Теперь можно установить таймер заново!', chat_id)
        else:
            send('Вы уже получаете уведомления! '
                 'Мы верим в Вас, всё обязательно получится!', chat_id)
        return
    if text.startswith(('/отмен', '/cancel')):
        send('У вас ещё нет уведомлений.'
             ' Просто введите время в виде чч:мм чтобы начать их получать.'
             'Введите /начать или /start чтобы понять, как работает бот.', chat_id)
    if text.startswith(('/начать', '/start')):
        send(INIT_MSG.format(username), chat_id, keyboard)
        return
    match = re.match(r"\d\d?:\d\d", text)
    if match:
        timestr = match.group()
        starttime = make_seconds(timestr)
        db.add(starttime, chat_id)
        with mutex:
            do_update(NOTIFY_DICT, chat_id, starttime)
        send(f"время старта {timestr} успешно установлено.", chat_id)
        return
    else:
        send('Вот такие команды у этого бота: \n'
             '/start или /начать\n'
             '/cancel или /отмена \n'
             '/commands или команды \n ', chat_id, keyboard)


def get_last_update_id(updates):
    update_ids = []
    for update in updates["result"]:
        update_ids.append(int(update["update_id"]))
    return max(update_ids)


def notify(uids):
    LOG.info(f'notifying {uids}')
    for uid in uids:
        send('Время начинать питаться \n Следующее уведомление через 24 часа 10 минут', uid)


def notify_users():
    LOG.info('notify thread started')

    while True:
        t = int(time.time())
        LOG.info(f'in notify loop t is {t}')
        ids = NOTIFY_DICT.get(t)
        if ids:
            threading.Thread(target=notify, args=(ids,)).start()
            with mutex:
                NOTIFY_DICT.pop(int(t))
        time.sleep(0.5)


def build_keyboard():
    keyboard = {
        'keyboard': [['/отмена'], ['/команды'], ['/начать']],
        'one_time_keyboard': True
    }
    return json.dumps(keyboard)


def initiate():
    LOG.info('Initialization started')
    db = db.db()
    db.setup()

    items = db.all()
    for item in items:
        starttime, chat_id = item
        do_update(NOTIFY_DICT, chat_id, starttime)
    LOG.info(f'Initialization done {len(items)} processed')
    return db


def handle(updates, db):
    for update in updates["result"]:
        handle_one(update, db)


def main():
    LOG.info('Main thread running')
    db = initiate()

    last_update_id = None
    while True:
        print(f"waiting {time.time()}")
        updates = get_updates(last_update_id)
        if len(updates['result']) > 0:
            last_update_id = get_last_update_id(updates) + 1

            handle(updates, db)
        time.sleep(0.5)


if __name__ == '__main__':

    t1 = threading.Thread(target=main)
    t2 = threading.Thread(target=notify_users)
    t1.start()
    t2.start()


# message schema
# 'result': [{'message': {'chat': {'first_name': 'Viktor',
#      'id': 293863478,
#      'type': 'private',
#      'username': 'viktorognev'},
#     'date': 1512579927,
#     'entities': [{'length': 6, 'offset': 0, 'type': 'bot_command'}],
#     'from': {'first_name': 'Viktor',
#      'id': 293863478,
#      'is_bot': False,
#      'language_code': 'en',
#      'username': 'viktorognev'},
#     'message_id': 1,
#     'text': '/start'},
