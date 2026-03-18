from asyncio import gather
from html import escape
from os.path import splitext
import re

from bot.config import Telegram
from bot.helper.cache import get_cache, save_cache
from bot.helper.database import Database
from bot.helper.file_size import get_readable_file_size
from bot.helper.tmdb import fetch_artwork, fetch_poster
from bot.telegram import StreamBot, UserBot


db = Database()


async def fetch_message(chat_id, message_id):
    try:
        return await StreamBot.get_messages(chat_id, message_id)
    except Exception:
        return None


async def get_messages(chat_id, first_message_id, last_message_id, batch_size=50):
    messages = []
    current_message_id = first_message_id
    while current_message_id <= last_message_id:
        batch_message_ids = list(range(current_message_id, min(current_message_id + batch_size, last_message_id + 1)))
        batch_messages = await gather(*[fetch_message(chat_id, message_id) for message_id in batch_message_ids])
        for message in batch_messages:
            if message and (file := message.video or message.document):
                title = message.caption
                title, _ = splitext(title)
                title = re.sub(r"[.,|_\',]", ' ', title)
                artwork = fetch_artwork(title)
                messages.append({
                    'msg_id': message.id,
                    'title': title,
                    'hash': file.file_unique_id[:6],
                    'size': get_readable_file_size(file.file_size),
                    'size_bytes': file.file_size,
                    'type': file.mime_type,
                    'chat_id': str(chat_id),
                    'poster_url': artwork['poster'],
                    'backdrop_url': artwork['backdrop'],
                })
        current_message_id += batch_size
    return messages


async def get_files(chat_id, page=1):
    if Telegram.SESSION_STRING == '':
        posts = await db.list_tgfiles(id=chat_id, page=page)
        for post in posts:
            artwork = fetch_artwork(post.get('title', ''))
            post.setdefault('poster_url', artwork['poster'])
            post.setdefault('backdrop_url', artwork['backdrop'])
            post.setdefault('size_bytes', 0)
        return posts
    if cache := get_cache(chat_id, int(page)):
        return cache

    posts = []
    async for post in UserBot.get_chat_history(chat_id=int(chat_id), limit=50, offset=(int(page) - 1) * 50):
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
    save_cache(chat_id, {'posts': posts}, page)
    return posts


def _rail_card(post, chat_id):
    title = escape(post.get('title', 'Untitled'))
    image = escape(post.get('poster_url') or fetch_poster(post.get('title', '')))
    item_type = escape(post.get('type', 'Media'))
    size = escape(post.get('size', 'Unknown'))
    msg_id = post.get('msg_id')
    hash_value = escape(post.get('hash', ''))
    checkbox = (
        f'<input type="checkbox" class="ott-select-box admin-only" '
        f'onchange="checkSendButton()" id="selectCheckbox" '
        f'data-id="{msg_id}|{hash_value}|{title}|{size}|{item_type}|{image}">'
    )
    return f"""
    <article class="ott-rail-card">
        {checkbox}
        <a class="ott-card-link" href="/watch/{str(chat_id).replace('-100', '')}?id={msg_id}&hash={hash_value}">
            <div class="ott-rail-card__poster">
                <img src="{image}" alt="{title}" loading="lazy" onerror="this.onerror=null;this.src='https://cdn-icons-png.flaticon.com/512/565/565547.png';">
            </div>
            <div class="ott-rail-card__body">
                <h3 class="ott-card-title">{title}</h3>
                <div class="ott-pills">
                    <span class="ott-pill">{item_type}</span>
                    <span class="ott-pill">{size}</span>
                </div>
            </div>
        </a>
    </article>
    """


def _render_rail(title, subtitle, posts, chat_id):
    if not posts:
        return ''
    cards = ''.join(_rail_card(post, chat_id) for post in posts)
    return f"""
    <section class="ott-section">
        <div class="ott-section-header">
            <div>
                <h2>{escape(title)}</h2>
                <p class="ott-copy">{escape(subtitle)}</p>
            </div>
        </div>
        <div class="ott-rail">{cards}</div>
    </section>
    """


def related_items_html(posts, chat_id, exclude_id=None, limit=12):
    filtered = [post for post in posts if str(post.get('msg_id')) != str(exclude_id)]
    filtered = filtered[:limit]
    if not filtered:
        return '<div class="ott-empty">No related content available yet.</div>'
    cards = ''.join(_rail_card(post, chat_id) for post in filtered)
    return f"""
    <section class="ott-section">
        <div class="ott-section-header">
            <div>
                <h2>Related Content</h2>
                <p class="ott-copy">More from the same channel context.</p>
            </div>
        </div>
        <div class="ott-rail">{cards}</div>
    </section>
    """


async def posts_file(posts, chat_id):
    posts = list(posts)
    if not posts:
        return '<div class="ott-empty">No media available yet in this channel.</div>'

    enriched = []
    for post in posts:
        title = post.get('title', '')
        artwork = fetch_artwork(title)
        item = dict(post)
        item['poster_url'] = item.get('poster_url') or artwork['poster']
        item['backdrop_url'] = item.get('backdrop_url') or artwork['backdrop']
        item['size_bytes'] = item.get('size_bytes', 0) or 0
        enriched.append(item)

    latest = sorted(enriched, key=lambda item: item.get('msg_id', 0), reverse=True)
    popular = sorted(enriched, key=lambda item: (item.get('size_bytes', 0), item.get('msg_id', 0)), reverse=True)
    midpoint = max(1, len(enriched) // 3)
    featured = popular[0] if popular else latest[0]

    hero_title = escape(featured.get('title', 'Featured Release'))
    hero_bg = escape(featured.get('backdrop_url') or featured.get('poster_url'))
    hero_poster = escape(featured.get('poster_url'))
    hero_size = escape(featured.get('size', 'Unknown'))
    hero_type = escape(featured.get('type', 'Media'))
    hero_msg_id = featured.get('msg_id')
    hero_hash = escape(featured.get('hash', ''))

    hero = f"""
    <section class="ott-channel-hero">
        <div class="ott-channel-hero__backdrop"><img src="{hero_bg}" alt="{hero_title}" loading="lazy"></div>
        <div class="ott-channel-hero__overlay"></div>
        <div class="ott-channel-hero__content">
            <div class="ott-channel-hero__poster"><img src="{hero_poster}" alt="{hero_title}" loading="lazy"></div>
            <div class="ott-channel-hero__copy">
                <span class="ott-hero__eyebrow">Featured from this channel</span>
                <h2>{hero_title}</h2>
                <p class="ott-copy">This hero spotlight is derived deterministically from the current channel feed using newest and larger files.</p>
                <div class="ott-pills">
                    <span class="ott-pill">{hero_type}</span>
                    <span class="ott-pill">{hero_size}</span>
                </div>
                <div class="ott-action-row">
                    <a class="ott-button" href="/watch/{str(chat_id).replace('-100', '')}?id={hero_msg_id}&hash={hero_hash}">Play featured</a>
                </div>
            </div>
        </div>
    </section>
    """

    trending = latest[:12]
    latest_uploads = latest[12:24] if len(latest) > 12 else latest[:12]
    popular_slice = popular[:12]
    curated = enriched[midpoint:midpoint + 12] if len(enriched) > midpoint else enriched[:12]

    return ''.join([
        hero,
        _render_rail('Trending Now', 'Newest arrivals from this channel.', trending, chat_id),
        _render_rail('Latest Uploads', 'A deterministic slice of recent uploads.', latest_uploads, chat_id),
        _render_rail('Popular', 'Bigger files promoted as a simple popularity signal.', popular_slice, chat_id),
        _render_rail('Because You Opened This Channel', 'A curated slice from the current page for extra discovery.', curated, chat_id),
    ])
