import re
import time
from html import escape
from cachetools import TTLCache
from pymongo import MongoClient, ASCENDING

from telegram import Update, InlineQueryResultPhoto, InlineQueryResultVideo
from telegram.ext import InlineQueryHandler, CallbackContext, CommandHandler 
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from shivu import user_collection, collection, application, db, LOGGER, process_image_url
from shivu.modules.harem import get_character_display_url

def is_video_url(url):
    """Check if a URL points to a video file"""
    if not url:
        return False
    return any(ext in url.lower() for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv'])

async def is_video_character(character, char_id=None, user_id=None):
    """Check if a character is a video by URL extension or name marker"""
    if not character:
        return False
    
    # Check for 🎬 emoji marker first (fastest check)
    name = character.get('name', '')
    if '🎬' in name:
        return True
    
    # Get the correct display URL (respecting active_slot for custom characters)
    # Only fetch fresh data for custom characters with user_id to avoid expensive lookups
    if user_id and character.get('rarity') == 'Custom':
        url = await get_character_display_url(character, char_id, user_id)
    else:
        # For non-custom or inline queries without user_id, use simpler lookup
        url = character.get('img_url', '')
    
    if is_video_url(url):
        return True
    
    return False

# Rarity emojis configuration (updated to match latest rarities)
rarity_emojis = {
    "Common": "⚪️",
    "Uncommon": "🟢",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟡",
    "Mythic": "🏵",
    "Retro": "🍥",
    "Star": "⭐",
    "Zenith": "🪩",
    "Limited Edition": "🍬",
    "Flat": "🔮"
}

# Event configuration
events = {
    "Football ⚽️": "⚽️",
    "Basketball 🏀": "🏀",
    "Tenis 🎾": "🎾",
    "𝗣𝗢𝗟𝗜𝗖𝗘 🚨": "🚨",
    "𝗕𝗔𝗥𝗧𝗘𝗡𝗗𝗘𝗥 🍾": "🍾",
    "Gamer 🎮": "🎮",
    "Christmas🎄": "🎄",
    "Halloween 🎃": "🎃",
    "Valentine 💝": "💝"
}

def get_event_name(character_name):
    """Detect which event a character belongs to based on the emoji in their name"""
    if not character_name:
        return None
    for event_name, emoji in events.items():
        if emoji in character_name:
            return event_name
    return None

async def inlinequery(update: Update, context: CallbackContext) -> None:
    if not update.inline_query:
        return
        
    query = update.inline_query.query.strip()
    offset = int(update.inline_query.offset) if update.inline_query.offset else 0
    
    # Debug logging to help troubleshoot
    LOGGER.info(f"Inline query received: '{query}', offset: {offset}")

    # Initialize user variable to avoid unbound errors
    user = None
    all_characters = []

    if query.startswith('collection.'):
        # Handle user collection queries
        try:
            # Parse the query: "collection.user_id optional_search_terms"
            parts = query.split(' ', 1)  # Split into max 2 parts
            collection_part = parts[0]  # "collection.user_id"
            search_terms = parts[1] if len(parts) > 1 else ""  # Optional search terms
            
            # Extract user_id from "collection.user_id"
            if '.' in collection_part:
                user_id = collection_part.split('.')[1]
                
                if user_id.isdigit():
                    user_id_int = int(user_id)
                    
                    # Get user from cache or database
                    if user_id in user_collection_cache:
                        user = user_collection_cache[user_id]
                    else:
                        user = await user_collection.find_one({'id': user_id_int})
                        if user:
                            user_collection_cache[user_id] = user

                    if user and 'characters' in user:
                        # Get unique characters by ID
                        all_characters = list({v['id']:v for v in user['characters']}.values())
                        
                        # Apply search filter if provided
                        if search_terms.strip():
                            try:
                                escaped_search = re.escape(search_terms.strip())
                                regex = re.compile(escaped_search, re.IGNORECASE)
                                all_characters = [character for character in all_characters 
                                               if regex.search(character.get('name', '')) or 
                                                  regex.search(character.get('anime', ''))]
                            except re.error as e:
                                LOGGER.error(f"Regex error for search terms '{search_terms}': {str(e)}")
                        
                        LOGGER.info(f"Found {len(all_characters)} characters for user {user_id}")
                    else:
                        all_characters = []
                        LOGGER.info(f"No user found or no characters for user {user_id}")
                else:
                    all_characters = []
                    LOGGER.info(f"Invalid user ID format: {user_id}")
            else:
                all_characters = []
                LOGGER.info(f"Invalid collection query format: {query}")
        except Exception as e:
            LOGGER.error(f"Error processing collection query '{query}': {str(e)}")
            all_characters = []
    else:
        # Handle general character search
        if query:
            # Search for specific characters by name or anime
            # Escape special regex characters to prevent errors with user input
            try:
                escaped_query = re.escape(query)
                regex = re.compile(escaped_query, re.IGNORECASE)
                all_characters = list(await collection.find({"$or": [{"name": regex}, {"anime": regex}]}).to_list(length=None))
            except re.error as e:
                LOGGER.error(f"Regex error for query '{query}': {str(e)}")
                all_characters = []
        else:
            # Empty query - show popular/random characters like Yandex image search
            if 'all_characters' in all_characters_cache:
                all_characters = all_characters_cache['all_characters']
            else:
                # Get a diverse selection of characters (limit to prevent too much load)
                all_characters = list(await collection.find({}).limit(200).to_list(length=None))
                all_characters_cache['all_characters'] = all_characters

    # Limit characters per page for better performance
    characters = all_characters[offset:offset+50]
    if len(all_characters) > offset + 50:
        next_offset = str(offset + 50)
    else:
        next_offset = ""

    results = []
    for character in characters:
        try:
            # Get rarity emoji for consistent display
            rarity_emoji = rarity_emojis.get(character.get('rarity', 'Common'), "✨")
            
            # Detect event
            event_name = get_event_name(character.get('name', ''))
            event_line = f"\n🌟 Event: {event_name}" if event_name else ""
            
            # Simple caption without slow database queries
            caption = (
                f"OwO! Check out this Character!\n\n"
                f"{character['anime']}\n"
                f"{character['id']} {character['name']}\n"
                f"(𝙍𝘼𝙍𝙄𝙏𝙔: {rarity_emoji} {character.get('rarity', 'Unknown')}){event_line}"
            )
            
            # Get the correct display URL (respecting active_slot for custom characters)
            # Don't pass user_id for inline queries to skip custom slot lookups
            display_url = await get_character_display_url(character, character.get('id'), None)
            processed_url = await process_image_url(display_url)
            
            # Check if it's a video and use appropriate result type
            # Don't pass user_id for inline queries to avoid expensive database lookups
            if await is_video_character(character, character.get('id'), None):
                # Determine mime type based on file extension
                if '.webm' in processed_url.lower():
                    mime_type = 'video/webm'
                elif '.mov' in processed_url.lower():
                    mime_type = 'video/quicktime'
                elif '.avi' in processed_url.lower():
                    mime_type = 'video/x-msvideo'
                elif '.mkv' in processed_url.lower():
                    mime_type = 'video/x-matroska'
                elif '.flv' in processed_url.lower():
                    mime_type = 'video/x-flv'
                else:
                    mime_type = 'video/mp4'
                
                try:
                    # Use a placeholder thumbnail (must be JPEG for Telegram API)
                    placeholder_thumbnail = 'https://via.placeholder.com/320x180.jpg'
                    
                    results.append(
                        InlineQueryResultVideo(
                            id=f"{character['id']}_{time.time()}",
                            video_url=processed_url,
                            mime_type=mime_type,
                            thumbnail_url=placeholder_thumbnail,
                            title=f"{character['name']} - {character['anime']}",
                            caption=caption
                        )
                    )
                except Exception as video_error:
                    # Fallback: treat as photo if video format is rejected
                    LOGGER.warning(f"Video inline result failed for character {character['id']} ({character['name']}), URL: {processed_url[:100]}, Error: {str(video_error)}. Falling back to photo.")
                    results.append(
                        InlineQueryResultPhoto(
                            thumbnail_url=processed_url,
                            id=f"{character['id']}_{time.time()}",
                            photo_url=processed_url,
                            caption=f"🎬 [Video] {caption}"
                        )
                    )
            else:
                results.append(
                    InlineQueryResultPhoto(
                        thumbnail_url=processed_url,
                        id=f"{character['id']}_{time.time()}",
                        photo_url=processed_url,
                        caption=caption
                    )
                )
        except Exception as e:
            # Log error and skip problematic characters to prevent the entire query from failing
            LOGGER.error(f"Failed to create inline result for character {character.get('id', 'unknown')} ({character.get('name', 'unknown')}): {str(e)}")
            continue

    await update.inline_query.answer(results, next_offset=next_offset, cache_time=5)

application.add_handler(InlineQueryHandler(inlinequery, block=False))
