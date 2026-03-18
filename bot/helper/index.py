from os.path import splitext
import re
from bot.config import Telegram
from bot.helper.database import Database
from bot.telegram import StreamBot, UserBot
from bot.helper.file_size import get_readable_file_size
from bot.helper.cache import get_cache, save_cache
from bot.helper.tmdb import fetch_poster
from asyncio import gather

db = Database()


async def fetch_message(chat_id, message_id):
    try:
        message = await StreamBot.get_messages(chat_id, message_id)
        return message
    except Exception as e:
        return None


async def get_messages(chat_id, first_message_id, last_message_id, batch_size=50):
    messages = []
    current_message_id = first_message_id
    while current_message_id <= last_message_id:
        batch_message_ids = list(range(current_message_id, min(current_message_id + batch_size, last_message_id + 1)))
        tasks = [fetch_message(chat_id, message_id) for message_id in batch_message_ids]
        batch_messages = await gather(*tasks)
        for message in batch_messages:
            if message:
                if file := message.video or message.document:
                    title = message.caption    #file.file_name or message.caption or file.file_id
                    title, _ = splitext(title)
                    title = re.sub(r'[.,|_\',]', ' ', title)
                    messages.append({"msg_id": message.id, "title": title,
                                     "hash": file.file_unique_id[:6], "size": get_readable_file_size(file.file_size),
                                     "type": file.mime_type, "chat_id": str(chat_id)})
        current_message_id += batch_size
    return messages


async def get_files(chat_id, page=1):
    if Telegram.SESSION_STRING == '':
        return await db.list_tgfiles(id=chat_id, page=page)
    if cache := get_cache(chat_id, int(page)):
        return cache
    posts = []
    async for post in UserBot.get_chat_history(chat_id=int(chat_id), limit=50, offset=(int(page) - 1) * 50):
        file = post.video or post.document
        if not file:
            continue
        title = post.caption
        title, _ = splitext(title)
        title = re.sub(r'[.,|_\',]', ' ', title)
        poster = fetch_poster(title)
        posts.append({"msg_id": post.id, "title": title, "poster_url": poster,
                    "hash": file.file_unique_id[:6], "size": get_readable_file_size(file.file_size), "type": file.mime_type})
    save_cache(chat_id, {"posts": posts}, page)
    return posts

async def posts_file(posts, chat_id):
    phtml = """
    <article class="ott-card-item">
        <input type="checkbox" class="ott-select-box admin-only"
            onchange="checkSendButton()" id="selectCheckbox"
            data-id="{id}|{hash}|{title}|{size}|{type}|{img}">
        <a class="ott-card-link" href="/watch/{chat_id}?id={id}&hash={hash}">
            <div class="ott-card-media">
                <img src="{img}" alt="{title}" loading="lazy"
                    onerror="this.onerror=null;this.src='https://cdn-icons-png.flaticon.com/512/565/565547.png';">
            </div>
            <div class="ott-card-body">
                <h3 class="ott-card-title">{title}</h3>
                <div class="ott-pills">
                    <span class="ott-pill">{type}</span>
                    <span class="ott-pill">{size}</span>
                </div>
            </div>
        </a>
    </article>
    """

    return ''.join(phtml.format(chat_id=str(chat_id).replace("-100", ""), id=post["msg_id"], img=post["poster_url"], title=post["title"], hash=post["hash"], size=post['size'], type=post['type']) for post in posts)
