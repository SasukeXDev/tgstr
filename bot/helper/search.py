import re
from os.path import splitext

from bot.config import Telegram
from bot.helper.database import Database
from bot.helper.file_size import get_readable_file_size
from bot.helper.tmdb import fetch_artwork
from bot.telegram import UserBot


db = Database()


async def search(chat_id, query, page):
    if Telegram.SESSION_STRING == '':
        posts = await db.search_tgfiles(id=chat_id, query=query, page=page)
        for post in posts:
            artwork = fetch_artwork(post.get('title', ''))
            post.setdefault('poster_url', artwork['poster'])
            post.setdefault('backdrop_url', artwork['backdrop'])
            post.setdefault('size_bytes', 0)
        return posts

    posts = []
    async for post in UserBot.search_messages(chat_id=int(chat_id), limit=50, query=str(query), offset=(int(page) - 1) * 50):
        file = post.video or post.document
        if not file:
            continue
        title = post.caption
        title, _ = splitext(title)
        title = re.sub(r"[.,|_\',]", ' ', title)
        artwork = fetch_artwork(title)
        posts.append({
            'msg_id': post.id,
            'title': title,
            'poster_url': artwork['poster'],
            'backdrop_url': artwork['backdrop'],
            'hash': file.file_unique_id[:6],
            'size': get_readable_file_size(file.file_size),
            'size_bytes': file.file_size,
            'type': file.mime_type,
        })
    return posts
