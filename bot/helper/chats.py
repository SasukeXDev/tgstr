from asyncio import gather, create_task

from bot.config import Telegram
from bot.helper.database import Database
from bot.telegram import StreamBot


db = Database()


async def get_chats():
    auth_channel = await db.get_variable('auth_channel')
    if auth_channel is None or auth_channel.strip() == '':
        auth_channel = Telegram.AUTH_CHANNEL
    else:
        auth_channel = [channel.strip() for channel in auth_channel.split(',')]

    return [
        {
            'chat-id': chat.id,
            'title': chat.title or chat.first_name,
            'type': chat.type.name,
        }
        for chat in await gather(
            *[create_task(StreamBot.get_chat(int(channel_id))) for channel_id in auth_channel]
        )
    ]


async def posts_chat(channels):
    template = """
    <article class="ott-selector-card">
        <a class="ott-selector-link channel-card-link" href="/channel/{cid}" data-channel-id="{cid}" data-channel-title="{title}">
            <div class="ott-selector-art">
                <img src="/api/thumb/{chat_id}" alt="{title}" loading="lazy">
                <span class="ott-selector-badge">{ctype}</span>
            </div>
            <div class="ott-selector-copy">
                <h3>{title}</h3>
                <p>Launch this Telegram channel in the OTT browser experience.</p>
            </div>
        </a>
    </article>
    """
    return ''.join(
        template.format(
            cid=str(channel['chat-id']).replace('-100', ''),
            chat_id=channel['chat-id'],
            title=channel['title'],
            ctype=channel['type'],
        )
        for channel in channels
    )


async def post_playlist(playlists):
    template = """
    <article class="ott-card-item">
        <div class="ott-card-tools admin-only">
            <button type="button" class="ott-icon-button ott-icon-button--ghost" onclick="openEditPopupForm(event, '{img}', '{ctype}', '{cid}', '{title}')">✎</button>
        </div>
        <a class="ott-card-link" href="/playlist?db={cid}">
            <div class="ott-card-media ott-card-media--circle">
                <img src="{img}" alt="{title}" loading="lazy">
            </div>
            <div class="ott-card-body">
                <h3 class="ott-card-title">{title}</h3>
                <div class="ott-pills">
                    <span class="ott-pill">Folder</span>
                </div>
            </div>
        </a>
    </article>
    """
    return ''.join(
        template.format(
            cid=playlist['_id'],
            img=playlist['thumbnail'],
            title=playlist['name'],
            ctype=playlist['parent_folder'],
        )
        for playlist in playlists
    )


async def posts_db_file(posts):
    template = """
    <article class="ott-card-item">
        <div class="ott-card-tools admin-only">
            <button type="button" class="ott-icon-button ott-icon-button--ghost" onclick="openPostEditPopupForm(event, '{img}', '{type}', '{size}', '{title}', '{cid}', '{ctype}')">✎</button>
        </div>
        <a class="ott-card-link" href="/watch/{chat_id}?id={id}&hash={hash}">
            <div class="ott-card-media">
                <img src="{img}" alt="{title}" loading="lazy">
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
    return ''.join(
        template.format(
            cid=post['_id'],
            chat_id=str(post['chat_id']).replace('-100', ''),
            id=post['file_id'],
            img=post['thumbnail'],
            title=post['title'],
            hash=post['hash'],
            size=post['size'],
            type=post['file_type'],
            ctype=post['parent_folder'],
        )
        for post in posts
    )
