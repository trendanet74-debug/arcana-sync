import asyncio
import logging
import os
import sqlite3
import tempfile
from pathlib import Path

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
PAGE_TOKEN = os.environ['FACEBOOK_PAGE_TOKEN']
PAGE_ID = os.environ['FACEBOOK_PAGE_ID']
CHANNEL = os.getenv('TELEGRAM_CHANNEL', '@ArcanaLab_AI').lower()
BOT_LINK = os.getenv('ARCANA_BOT_URL', '').strip()
GRAPH_VERSION = os.getenv('GRAPH_VERSION', 'v26.0')
DB_PATH = os.getenv('DB_PATH', 'arcana_sync.sqlite3')
GRAPH = f'https://graph.facebook.com/{GRAPH_VERSION}/{PAGE_ID}'
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('arcana_sync')

conn = sqlite3.connect(DB_PATH)
conn.execute('CREATE TABLE IF NOT EXISTS sent (chat_id INTEGER, message_id INTEGER, PRIMARY KEY(chat_id,message_id))')
conn.commit()

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

async def graph_post(endpoint, data=None, files=None):
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(f'{GRAPH}/{endpoint}', data={**(data or {}), 'access_token': PAGE_TOKEN}, files=files)
        response.raise_for_status()
        result = response.json()
        if 'error' in result:
            raise RuntimeError(result['error'])
        return result

def caption(text):
    text = text or ''
    if BOT_LINK and BOT_LINK not in text:
        text = f'{text}\n\n🔮 Расклады Таро: {BOT_LINK}'.strip()
    return text

async def download_photo(file_id):
    file = await bot.get_file(file_id)
    stream = await bot.download_file(file.file_path)
    return stream.read()

async def publish_photo(photo_id, text):
    image = await download_photo(photo_id)
    return await graph_post('photos', {'message': caption(text)}, {'source': ('arcana.jpg', image, 'image/jpeg')})

async def publish_album(messages):
    photos = [m for m in messages if m.photo]
    if not photos:
        return
    attached = []
    for m in photos:
        image = await download_photo(m.photo[-1].file_id)
        result = await graph_post('photos', {'published': 'false'}, {'source': ('arcana.jpg', image, 'image/jpeg')})
        attached.append(result['id'])
    text = next((m.caption for m in messages if m.caption), '')
    payload = {'message': caption(text)}
    for i, photo_id in enumerate(attached):
        payload[f'attached_media[{i}]'] = '{"media_fbid":"' + str(photo_id) + '"}'
    return await graph_post('feed', payload)

pending = {}

async def flush_album(key):
    await asyncio.sleep(3)
    messages = pending.pop(key, [])
    if not messages:
        return
    unsent = [m for m in messages if not conn.execute('SELECT 1 FROM sent WHERE chat_id=? AND message_id=?', (m.chat.id, m.message_id)).fetchone()]
    if not unsent:
        return
    try:
        await publish_album(unsent)
        conn.executemany('INSERT OR IGNORE INTO sent VALUES (?,?)', [(m.chat.id, m.message_id) for m in unsent])
        conn.commit()
    except Exception:
        log.exception('Album failed; retry by reposting or use future retry queue')

@dp.channel_post()
async def channel_post(message: Message):
    if (message.chat.username or '').lower() != CHANNEL.lstrip('@'):
        return
    if conn.execute('SELECT 1 FROM sent WHERE chat_id=? AND message_id=?', (message.chat.id, message.message_id)).fetchone():
        return
    if message.media_group_id:
        key = (message.chat.id, message.media_group_id)
        if key not in pending:
            pending[key] = []
            asyncio.create_task(flush_album(key))
        pending[key].append(message)
        return
    try:
        if message.photo:
            await publish_photo(message.photo[-1].file_id, message.caption)
        elif message.text:
            await graph_post('feed', {'message': caption(message.text)})
        else:
            log.info('Unsupported content message_id=%s; skipped', message.message_id)
            return
        conn.execute('INSERT OR IGNORE INTO sent VALUES (?,?)', (message.chat.id, message.message_id))
        conn.commit()
        log.info('Published Telegram message %s', message.message_id)
    except Exception:
        log.exception('Publishing failed for message %s', message.message_id)

async def main():
    await dp.start_polling(bot, allowed_updates=['channel_post'])

if __name__ == '__main__':
    asyncio.run(main())
