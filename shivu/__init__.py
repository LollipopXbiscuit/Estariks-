import logging  
import os
from pyrogram.client import Client 
from telegram.ext import Application
from telegram.request import HTTPXRequest
from motor.motor_asyncio import AsyncIOMotorClient
import requests
import tempfile
import io
import aiohttp
from urllib.parse import urlparse

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()],
    level=logging.INFO,
)

logging.getLogger("apscheduler").setLevel(logging.ERROR)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger("pyrate_limiter").setLevel(logging.ERROR)
LOGGER = logging.getLogger(__name__)

from shivu.config import Development as Config


api_id = Config.api_id
api_hash = Config.api_hash
TOKEN = Config.TOKEN
GROUP_ID = Config.GROUP_ID
CHARA_CHANNEL_ID = Config.CHARA_CHANNEL_ID 
mongo_url = Config.mongo_url 
PHOTO_URL = Config.PHOTO_URL 
SUPPORT_CHAT = Config.SUPPORT_CHAT 
UPDATE_CHAT = Config.UPDATE_CHAT
BOT_USERNAME = Config.BOT_USERNAME 
sudo_users = Config.sudo_users
uploading_users = Config.uploading_users
head_users = Config.head_users
OWNER_ID = Config.OWNER_ID 

# Validate required environment variables
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is required but not provided")
if not api_hash:
    raise ValueError("TELEGRAM_API_HASH is required but not provided")
if not mongo_url:
    raise ValueError("MONGODB_URL is required but not provided")
if api_id == 0:
    raise ValueError("TELEGRAM_API_ID is required but not provided")

# Clean and validate MongoDB URL
mongo_url = mongo_url.strip()
if mongo_url.endswith(','):
    mongo_url = mongo_url.rstrip(',')
if not mongo_url or mongo_url == ',':
    raise ValueError("MONGODB_URL is empty or contains only commas")

telegram_request = HTTPXRequest(
    connection_pool_size=8,
    read_timeout=30,
    write_timeout=30,
    connect_timeout=30,
    pool_timeout=30,
)
telegram_updates_request = HTTPXRequest(
    connection_pool_size=8,
    read_timeout=30,
    write_timeout=30,
    connect_timeout=30,
    pool_timeout=30,
)
application = (
    Application.builder()
    .token(TOKEN)
    .request(telegram_request)
    .get_updates_request(telegram_updates_request)
    .build()
)
shivuu = Client("Shivu", api_id, api_hash, bot_token=TOKEN)
lol = AsyncIOMotorClient(mongo_url)
db = lol['Character_catcher']
collection = db['anime_characters_lol']
user_totals_collection = db['user_totals_lmaoooo']
user_collection = db["user_collection_lmaoooo"]
group_user_totals_collection = db['group_user_totalsssssss']
top_global_groups_collection = db['top_global_groups']
pm_users = db['total_pm_users']
locked_spawns_collection = db['locked_spawns']
banned_users_collection = db['banned_users']
restricted_users_collection = db['restricted_users']
event_settings_collection = db['event_settings']

# Helper function to handle JFIF and other image formats
async def process_image_url(url):
    """
    Process image URLs to ensure compatibility with Telegram.
    Handles JFIF files by converting them when needed.
    """
    if not url:
        return url
    
    # If it's a JFIF file, we need special handling
    if url.lower().endswith('.jfif'):
        try:
            # Try to modify the URL to work better with Telegram
            # Some services like Catbox work better with different extensions
            if 'catbox.moe' in url.lower():
                # Try converting .jfif to .jpg for Catbox URLs
                new_url = url.replace('.jfif', '.jpg')
                LOGGER.info(f"Converting JFIF URL: {url} -> {new_url}")
                return new_url
            else:
                # For other services, return as-is but log the JFIF detection
                LOGGER.info(f"JFIF file detected: {url}")
                return url
        except Exception as e:
            LOGGER.error(f"Error processing JFIF image {url}: {str(e)}")
            return url
    
    return url


def telegram_message_media(message, default_media_type=None, default_is_video=False):
    """Return the Telegram file id and media kind from a sent message."""
    for media_type in ('video', 'animation', 'document'):
        media = getattr(message, media_type, None)
        if media:
            return media.file_id, media_type, (
                media_type in ('video', 'animation')
                or (media_type == 'document' and str(getattr(media, 'mime_type', '')).startswith('video/'))
            )

    photos = getattr(message, 'photo', None)
    if photos:
        photo = photos[-1] if isinstance(photos, (list, tuple)) else photos
        return photo.file_id, 'photo', False

    return None, default_media_type, default_is_video


async def get_character_media_source(character):
    """Resolve a character's reusable Telegram file id or a remote media URL."""
    media_type = character.get('media_type')
    is_video = bool(
        character.get('is_video')
        or media_type in ('video', 'animation')
        or (media_type == 'document' and 'video' in str(character.get('img_url', '')).lower())
        or '🎬' in str(character.get('name', ''))
    )
    media_file_id = character.get('media_file_id')
    if media_file_id:
        return media_file_id, media_type, is_video

    media_url = str(character.get('img_url') or '')
    parsed_url = urlparse(media_url)
    is_telegram_download_url = (
        parsed_url.netloc.lower() == 'api.telegram.org'
        and parsed_url.path.startswith('/file/bot')
    )
    is_non_url_path = not parsed_url.scheme

    # Telegram file download paths are temporary and must not be reused as
    # media URLs. Recover the stable file_id from the bot's channel copy.
    if is_telegram_download_url or is_non_url_path:
        message_id = character.get('message_id')
        if message_id:
            try:
                channel_message = await shivuu.get_messages(
                    CHARA_CHANNEL_ID,
                    int(message_id),
                )
                media_file_id, media_type, is_video = telegram_message_media(
                    channel_message,
                    media_type,
                    is_video,
                )
                if media_file_id:
                    character.update({
                        'media_file_id': media_file_id,
                        'media_type': media_type,
                        'is_video': is_video,
                    })
                    if character.get('id') is not None:
                        await collection.update_one(
                            {'id': str(character['id'])},
                            {'$set': {
                                'media_file_id': media_file_id,
                                'media_type': media_type,
                                'is_video': is_video,
                            }},
                        )
                    return media_file_id, media_type, is_video
            except Exception as error:
                LOGGER.warning(
                    "Could not recover Telegram media for character %s: %s",
                    character.get('id', 'unknown'),
                    error,
                )
        raise ValueError(
            "This character has an expired Telegram file path and no reusable channel copy."
        )

    return await process_image_url(media_url), media_type, is_video


async def send_character_media(
    bot,
    chat_id,
    media_url,
    caption,
    is_video,
    media_type=None,
    reply_markup=None,
):
    """Send a character image or video without silently changing its media type."""
    def send_media(source):
        options = {
            'chat_id': chat_id,
            'caption': caption,
            'parse_mode': 'HTML',
            'reply_markup': reply_markup,
        }
        if media_type == 'animation':
            return bot.send_animation(animation=source, **options)
        if media_type == 'document':
            return bot.send_document(document=source, **options)
        if is_video:
            return bot.send_video(video=source, **options)
        return bot.send_photo(photo=source, **options)

    try:
        return await send_media(media_url)
    except Exception as direct_error:
        # Telegram's servers cannot fetch some valid remote media URLs (CDN
        # headers, redirects, or an incorrect content type). Upload the bytes
        # from this process instead of changing a video into a still image.
        if (
            not isinstance(media_url, str)
            or not media_url.startswith(('http://', 'https://'))
            or 'api.telegram.org/file/bot' in media_url
        ):
            raise

        LOGGER.warning(
            "Direct %s send failed; downloading before retry: %s",
            "video" if is_video else "photo",
            direct_error,
        )

        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers={'User-Agent': 'CineLegacyBot/1.0'},
        ) as session:
            async with session.get(media_url, allow_redirects=True) as response:
                response.raise_for_status()
                media_bytes = io.BytesIO()
                async for chunk in response.content.iter_chunked(1024 * 1024):
                    media_bytes.write(chunk)

        media_bytes.seek(0)
        if media_type == 'animation':
            suffix = 'gif'
        elif media_type == 'document':
            suffix = 'mp4' if is_video else 'bin'
        else:
            suffix = 'mp4' if is_video else (
                urlparse(media_url).path.rsplit('.', 1)[-1]
                if '.' in urlparse(media_url).path else 'jpg'
            )
        media_bytes.name = f'character.{suffix.lstrip(".")}'
        try:
            return await send_media(media_bytes)
        except Exception as upload_error:
            raise RuntimeError(
                f"Telegram rejected the direct {'video' if is_video else 'photo'} URL "
                f"({direct_error}) and the downloaded media upload ({upload_error})"
            ) from upload_error
