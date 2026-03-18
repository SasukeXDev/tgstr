import re
from aiofiles import open as aiopen
from os import path as ospath

from bot import LOGGER
from bot.config import Telegram
from bot.helper.database import Database
from bot.helper.exceptions import InvalidHash
from bot.helper.file_size import get_readable_file_size
from bot.server.file_properties import get_file_ids
from bot.telegram import StreamBot


db = Database()


async def _render_base(page_title, page_content, is_admin=False, extra_head="", selected_label="360Hub"):
    tpath = ospath.join("bot", "server", "template")
    async with aiopen(ospath.join(tpath, "base_ott.html"), "r") as f:
        html = await f.read()
    return (
        html.replace("<!-- PageTitle -->", page_title)
        .replace("<!-- BodyClass -->", "is-admin" if is_admin else "is-public")
        .replace("<!-- NavbarActions -->", (
            '<form action="/admin/logout" method="post" class="admin-only">'
            '<button type="submit" class="ott-button ott-button--ghost">Logout</button>'
            '</form>'
        ) if is_admin else "")
        .replace("<!-- PageContent -->", page_content)
        .replace("<!-- ExtraHead -->", extra_head)
        .replace("<!-- SelectedLabel -->", selected_label or "360Hub")
    )


async def _render_template_file(filename, replacements):
    tpath = ospath.join("bot", "server", "template")
    async with aiopen(ospath.join(tpath, filename), "r") as f:
        html = await f.read()
    for key, value in replacements.items():
        html = html.replace(key, value)
    return html


async def render_page(
    id,
    secure_hash,
    is_admin=False,
    html="",
    playlist="",
    database="",
    route="",
    redirect_url="",
    msg="",
    chat_id="",
):
    theme = await db.get_variable("theme")
    if theme is None or theme == "":
        theme = Telegram.THEME

    if route == "enter":
        content = await _render_template_file(
            "login.html",
            {
                "<!-- Error -->": msg or "",
                "<!-- RedirectURL -->": redirect_url or "/",
            },
        )
        return await _render_base("360Hub: Enter", content, is_admin=False)

    if route == "admin_login":
        return await _render_template_file(
            "admin_login.html",
            {
                "<!-- Error -->": msg or "",
                "<!-- Theme -->": theme.lower(),
                "<!-- RedirectURL -->": redirect_url or "/",
            },
        )

    if route == "home":
        content = await _render_template_file(
            "home.html",
            {
                "<!-- Print -->": html,
                "<!-- Playlist -->": playlist,
                "<!-- Theme -->": theme.lower(),
                "<!-- ChannelVisibility -->": "hide-channel" if Telegram.HIDE_CHANNEL else "",
                "<!-- HomeHeading -->": "Choose your channel",
            },
        )
        return await _render_base("360Hub: Home", content, is_admin=is_admin, selected_label="Channel Selector")

    if route == "playlist":
        content = await _render_template_file(
            "playlist.html",
            {
                "<!-- Theme -->": theme.lower(),
                "<!-- Playlist -->": playlist,
                "<!-- Database -->": database,
                "<!-- Title -->": msg,
                "<!-- Parent_id -->": str(id),
            },
        )
        return await _render_base(f"360Hub: {msg}", content, is_admin=is_admin)

    if route == "list":
        content = await _render_template_file("list.html", {"<!-- Theme -->": theme.lower()})
        return await _render_base("360Hub: List", content, is_admin=is_admin)

    if route == "index":
        content = await _render_template_file(
            "index.html",
            {
                "<!-- Print -->": html,
                "<!-- Title -->": msg,
                "<!-- Chat_id -->": chat_id,
                "<!-- Theme -->": theme.lower(),
                "<!-- SelectedLabel -->": msg,
            },
        )
        return await _render_base(f"360Hub: {msg}", content, is_admin=is_admin, selected_label=msg)

    file_data = await get_file_ids(StreamBot, chat_id=int(chat_id), message_id=int(id))
    if file_data.unique_id[:6] != secure_hash:
        LOGGER.info("Link hash: %s - %s", secure_hash, file_data.unique_id[:6])
        LOGGER.info("Invalid hash for message with - ID %s", id)
        raise InvalidHash
    filename, tag, size = (
        file_data.file_name,
        file_data.mime_type.split("/")[0].strip(),
        get_readable_file_size(file_data.file_size),
    )
    if filename is None:
        filename = "Proper Filename is Missing"
    filename = re.sub(r"[,|_\',]", " ", filename)
    if tag == "video":
        message = await StreamBot.get_messages(chat_id, int(id))
        caption = message.caption or message.video.file_name or ""
        duration_sec = getattr(message.video, "duration", None)
        if duration_sec:
            duration_sec = int(duration_sec)
            hours = duration_sec // 3600
            minutes = (duration_sec % 3600) // 60
            seconds = duration_sec % 60
            duration = f"{hours:02}:{minutes:02}:{seconds:02}" if hours > 0 else f"{minutes:02}:{seconds:02}"
        else:
            duration = "Unknown"
        content = await _render_template_file(
            "video.html",
            {
                "<!-- Title -->": caption,
                "<!-- Duration -->": duration,
                "<!-- Filename -->": filename,
                "<!-- Theme -->": theme.lower(),
                "<!-- Poster -->": f"/api/thumb/{chat_id}?id={id}",
                "<!-- Size -->": size,
                "<!-- Tag -->": tag,
                "<!-- Username -->": StreamBot.me.username,
            },
        )
        extra_head = '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/weebzone/weebzone/data/Surf-TG/css/plyr.css">'
        return await _render_base(f"360Hub: {caption}", content, is_admin=is_admin, extra_head=extra_head, selected_label=caption)

    content = await _render_template_file(
        "dl.html",
        {
            "<!-- Filename -->": filename,
            "<!-- Theme -->": theme.lower(),
            "<!-- Size -->": size,
            "<!-- Username -->": StreamBot.me.username,
        },
    )
    return await _render_base(f"360Hub: {filename}", content, is_admin=is_admin, selected_label=filename)
