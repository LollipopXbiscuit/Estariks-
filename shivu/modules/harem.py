from telegram import Update
from itertools import groupby
from collections import Counter, defaultdict
import math
from html import escape 
import random

from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardButton as PyroInlineKeyboardButton, InlineKeyboardMarkup as PyroInlineKeyboardMarkup
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, PeerIdInvalid

from shivu import collection, user_collection, application, SUPPORT_CHAT, CHARA_CHANNEL_ID, shivuu, sudo_users
from shivu.config import Config

async def get_character_display_url(character, char_id=None, user_id=None):
    """Get the correct URL to display for a character, respecting owner-specific slots"""
    user_id_str = str(user_id) if user_id else None
    
    # Always fetch fresh data if char_id is provided to check for custom slots
    if char_id:
        fresh_char = await collection.find_one({'id': char_id})
        if fresh_char:
            # Try owner_slots first (for Custom characters)
            if 'owner_slots' in fresh_char and user_id_str and user_id_str in fresh_char['owner_slots']:
                owner_slot_data = fresh_char['owner_slots'][user_id_str]
                if isinstance(owner_slot_data, dict):
                    active_slot = owner_slot_data.get('_active', 1)
                    slot_data = owner_slot_data.get(str(active_slot))
                    if slot_data:
                        # Handle dict format with 'url' key
                        if isinstance(slot_data, dict) and 'url' in slot_data:
                            return slot_data['url']
                        # Handle old string format
                        elif isinstance(slot_data, str):
                            return slot_data
            # Fallback to old 'slots' format if available
            if 'slots' in fresh_char:
                active_slot = fresh_char.get('active_slot', 1)
                slot_data = fresh_char['slots'].get(str(active_slot))
                if slot_data:
                    if isinstance(slot_data, dict) and 'url' in slot_data:
                        return slot_data['url']
                    elif isinstance(slot_data, str):
                        return slot_data
            # Return fresh_char's img_url if custom slots not found
            return fresh_char.get('img_url', '')
    
    # Fallback to character object's data
    if character.get('rarity') == 'Custom':
        # Try owner_slots first
        if 'owner_slots' in character and user_id_str and user_id_str in character['owner_slots']:
            owner_slot_data = character['owner_slots'][user_id_str]
            if isinstance(owner_slot_data, dict):
                active_slot = owner_slot_data.get('_active', 1)
                slot_data = owner_slot_data.get(str(active_slot))
                if slot_data:
                    if isinstance(slot_data, dict) and 'url' in slot_data:
                        return slot_data['url']
                    elif isinstance(slot_data, str):
                        return slot_data
        # Fallback to old 'slots' format if available
        if 'slots' in character:
            active_slot = character.get('active_slot', 1)
            slot_data = character['slots'].get(str(active_slot))
            if slot_data:
                if isinstance(slot_data, dict) and 'url' in slot_data:
                    return slot_data['url']
                elif isinstance(slot_data, str):
                    return slot_data
    
    return character.get('img_url', '')


def is_video_url(url):
    """Check if a URL points to a video file"""
    if not url:
        return False
    return any(ext in url.lower() for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv'])

async def is_video_character(character, char_id=None, user_id=None):
    """Check if a character is a video by URL extension, metadata type, or name marker"""
    if not character:
        return False
    
    # For custom characters, also check the 'type' field in slot metadata
    user_id_str = str(user_id) if user_id else None
    if char_id and character.get('rarity') == 'Custom':
        fresh_char = await collection.find_one({'id': char_id})
        if fresh_char:
            # Check owner_slots metadata
            if 'owner_slots' in fresh_char and user_id_str and user_id_str in fresh_char['owner_slots']:
                owner_slot_data = fresh_char['owner_slots'][user_id_str]
                if isinstance(owner_slot_data, dict):
                    active_slot = owner_slot_data.get('_active', 1)
                    slot_data = owner_slot_data.get(str(active_slot))
                    if isinstance(slot_data, dict) and slot_data.get('type') == 'video':
                        return True
    
    # Get the correct display URL (respecting active_slot for custom characters)
    url = await get_character_display_url(character, char_id, user_id)
    if is_video_url(url):
        return True
    
    # Check for 🎬 emoji marker in name
    name = character.get('name', '')
    if '🎬' in name:
        return True
    
    return False

# Main group for membership checking
MAIN_GROUP = "@EstariksUpdates"

async def check_group_membership(user_id: int) -> bool:
    """Check if user is a member of the main group"""
    try:
        member = await shivuu.get_chat_member(MAIN_GROUP, user_id)
        # Check if user is member, admin, or creator
        return member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except (UserNotParticipant, ChatAdminRequired, PeerIdInvalid):
        return False
    except Exception as e:
        # Fail-closed: deny access on any unexpected error
        from shivu import LOGGER
        LOGGER.error(f"Error checking group membership for user {user_id}: {e}")
        return False

async def sorts(update: Update, context: CallbackContext) -> None:
    """Set harem filtering and sorting preferences"""
    if not update.effective_user or not update.message:
        return
        
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "🔧 <b>Harem Filtering & Sorting</b>\n\n"
            "Set how you want your harem displayed:\n\n"
            "📝 <b>Available options:</b>\n"
            "• <code>/sorts rarity [rarity_name]</code> - Filter by specific rarity\n"
            "• <code>/sorts character [character_name]</code> - Filter by character name\n"
            "• <code>/sorts name</code> - Sort by character name\n"
            "• <code>/sorts limited_time</code> - Show limited time cards first\n"
            "• <code>/sorts reset</code> - Reset filters and show all\n\n"
            "<b>Examples:</b>\n"
            "• <code>/sorts rarity Legendary</code>\n"
            "• <code>/sorts character Naruto</code>\n\n"
            "💡 Your preferences will be remembered for future /harem displays!",
            parse_mode='HTML'
        )
        return
    
    sort_type = args[0].lower()
    
    # Handle reset option
    if sort_type == 'reset':
        await user_collection.update_one(
            {'id': user_id}, 
            {'$unset': {'sort_preference': '', 'filter_type': '', 'filter_value': ''}}, 
            upsert=True
        )
        await update.message.reply_text(
            "✅ Harem filters and sorting have been reset!\n\n"
            "Your /harem will now show all characters sorted by anime. 📋",
            parse_mode='HTML'
        )
        return
    
    # Handle filtering options
    if sort_type == 'rarity':
        if len(args) < 2:
            valid_rarities = ["Common", "Rare", "Legendary", "Flat", "Ninja", "Knight", "Catapult", "Limited Edition"]
            await update.message.reply_text(
                "❌ Please specify a rarity!\n\n"
                "<b>Valid rarities:</b>\n" + 
                "\n".join([f"• <code>{r}</code>" for r in valid_rarities]),
                parse_mode='HTML'
            )
            return
        
        rarity_filter = ' '.join(args[1:]).title()
        valid_rarities = ["Common", "Rare", "Legendary", "Flat", "Ninja", "Knight", "Catapult", "Limited Edition"]
        
        if rarity_filter not in valid_rarities:
            await update.message.reply_text(
                f"❌ Invalid rarity '{rarity_filter}'!\n\n"
                "<b>Valid rarities:</b>\n" + 
                "\n".join([f"• <code>{r}</code>" for r in valid_rarities]),
                parse_mode='HTML'
            )
            return
        
        # Update user's filter preference
        await user_collection.update_one(
            {'id': user_id}, 
            {'$set': {'filter_type': 'rarity', 'filter_value': rarity_filter, 'sort_preference': 'rarity'}}, 
            upsert=True
        )
        
        await update.message.reply_text(
            f"✅ Harem filter set to <b>{rarity_filter}</b> rarity only!\n\n"
            f"Your /harem will now show only {rarity_filter} characters. 📋",
            parse_mode='HTML'
        )
        
    elif sort_type == 'character':
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Please specify a character name!\n\n"
                "<b>Example:</b> <code>/sorts character Naruto</code>",
                parse_mode='HTML'
            )
            return
        
        character_filter = ' '.join(args[1:]).title()
        
        # Check if user has this character
        user = await user_collection.find_one({'id': user_id})
        if not user or not user.get('characters'):
            await update.message.reply_text("❌ You don't have any characters yet!")
            return
        
        # Check if character exists in user's collection (partial match)
        character_exists = any(character_filter.lower() in char['name'].lower() for char in user['characters'])
        if not character_exists:
            await update.message.reply_text(
                f"❌ You don't have any characters named '{character_filter}' in your collection!",
                parse_mode='HTML'
            )
            return
        
        # Update user's filter preference
        await user_collection.update_one(
            {'id': user_id}, 
            {'$set': {'filter_type': 'character', 'filter_value': character_filter, 'sort_preference': 'name'}}, 
            upsert=True
        )
        
        await update.message.reply_text(
            f"✅ Harem filter set to <b>{character_filter}</b> character only!\n\n"
            f"Your /harem will now show only {character_filter} cards (all rarities). 📋",
            parse_mode='HTML'
        )
        
    elif sort_type in ['name', 'limited_time']:
        # Update user's sort preference and clear any filters
        await user_collection.update_one(
            {'id': user_id}, 
            {'$set': {'sort_preference': sort_type}, '$unset': {'filter_type': '', 'filter_value': ''}}, 
            upsert=True
        )
        
        await update.message.reply_text(
            f"✅ Harem sorting set to <b>{sort_type}</b>!\n\n"
            f"Your /harem will now be sorted by {sort_type}. 📋",
            parse_mode='HTML'
        )
        
    else:
        await update.message.reply_text(
            "❌ Invalid command!\n\n"
            "Available options:\n"
            "• <code>/sorts rarity [rarity_name]</code>\n"
            "• <code>/sorts character [character_name]</code>\n"
            "• <code>/sorts name</code>\n"
            "• <code>/sorts limited_time</code>\n"
            "• <code>/sorts reset</code>",
            parse_mode='HTML'
        )
        return


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

async def harem(update: Update, context: CallbackContext, page=0) -> None:
    if not update.effective_user:
        return
        
    requester_id = update.effective_user.id
    user_id = requester_id
    is_sudo_viewing_other = False
    
    # Check if sudo user is viewing another user's harem
    if context.args and len(context.args) >= 1:
        if str(requester_id) in [str(u) for u in Config.sudo_users]:
            try:
                target_id = int(context.args[0])
                user_id = target_id
                is_sudo_viewing_other = True
            except ValueError:
                if update.message:
                    await update.message.reply_text("❌ Invalid user ID!")
                return
        else:
            if update.message:
                await update.message.reply_text("🚫 Only admins can view other people's harems!")
            return

    # Check if user is a member of the main group (only for non-sudo viewing others)
    if not is_sudo_viewing_other:
        if not await check_group_membership(requester_id):
            message_text = (
                "🚫 <b>Access Restricted</b>\n\n"
                f"To use the /harem command, you must join our main group:\n"
                f"👥 {MAIN_GROUP}\n\n"
                f"Once you've joined, you'll be able to access your harem!"
            )
            if update.message:
                await update.message.reply_text(message_text, parse_mode='HTML')
            elif update.callback_query:
                await update.callback_query.edit_message_text(message_text, parse_mode='HTML')
            return

    user = await user_collection.find_one({'id': user_id})
    if not user:
        if update.message:
            await update.message.reply_text('You Have Not Guessed any Characters Yet..')
        elif update.callback_query:
            await update.callback_query.edit_message_text('You Have Not Guessed any Characters Yet..')
        return

    # Get user's filter and sort preferences
    filter_type = user.get('filter_type')
    filter_value = user.get('filter_value')
    sort_preference = user.get('sort_preference', 'anime')  # Default to anime (current behavior)
    
    # Apply filters first
    characters = user['characters']
    if filter_type == 'rarity' and filter_value:
        characters = [char for char in characters if char.get('rarity') == filter_value]
    elif filter_type == 'character' and filter_value:
        characters = [char for char in characters if filter_value.lower() in char['name'].lower()]
    
    # Then apply sorting
    if sort_preference == 'rarity':
        # Sort by rarity (rarest first) then by name
        rarity_order = ["Catapult", "Knight", "Ninja", "Flat", "Legendary", "Rare", "Common"]
        characters = sorted(characters, key=lambda x: (rarity_order.index(x.get('rarity', 'Common')), x['name']))
    elif sort_preference == 'name':
        # Sort by character name alphabetically
        characters = sorted(characters, key=lambda x: x['name'])
    elif sort_preference == 'limited_time':
        # Sort by rarity (rarest first), then by name
        rarity_order = ["Catapult", "Knight", "Ninja", "Flat", "Legendary", "Rare", "Common"]
        characters = sorted(characters, key=lambda x: (
            rarity_order.index(x.get('rarity', 'Common')),
            x['name']
        ))
    else:
        # Default: sort by anime then ID (existing behavior)
        characters = sorted(characters, key=lambda x: (x['anime'], x['id']))

    # Use Counter to properly count character occurrences regardless of sort order
    character_counts = Counter(character['id'] for character in user['characters'])

    
    unique_characters = list({character['id']: character for character in characters}.values())

    
    total_pages = math.ceil(len(unique_characters) / 15)  

    if page < 0 or page >= total_pages:
        page = 0  

    user_name = update.effective_user.first_name or "User"
    
    # Build harem title with filter info
    title = f"{escape(user_name)}'s Harem"
    if filter_type == 'rarity' and filter_value:
        title += f" [{filter_value} Only]"
    elif filter_type == 'character' and filter_value:
        title += f" [{filter_value} Only]"
    title += f" - Page {page+1}/{total_pages}"
    
    harem_message = f"<b>{title}</b>\n"

    
    current_characters = unique_characters[page*15:(page+1)*15]

    # Group characters by anime properly regardless of sort order
    current_grouped_characters = defaultdict(list)
    for character in current_characters:
        current_grouped_characters[character['anime']].append(character)

    for anime, characters in current_grouped_characters.items():
        # Get total count of anime characters in database
        anime_total = await collection.count_documents({"anime": anime})
        
        # Stylish anime header with count
        harem_message += f'\n✢ {anime} 「 {len(characters)}/{anime_total} 」\n'
        harem_message += '⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋\n'

        for character in characters:
            # Add rarity emoji to make it more beautiful
            rarity_emojis = {
                "Common": "⚪️",
                "Rare": "🟠",
                "Legendary": "🟡",
                "Flat": "🔮",
                "Ninja": "⚡️",
                "Knight": "🗡",
                "Catapult": "🪄"
            }
            rarity_emoji = rarity_emojis.get(character.get('rarity', 'Common'), "✨")
            count = character_counts[character['id']]
            
            # Detect event
            event_name = get_event_name(character.get('name', ''))
            event_line = f"\n🌟 Event: {event_name}" if event_name else ""
            
            # Stylish character entry format
            harem_message += f'➥ {character["id"]}〔{rarity_emoji} 〕{character["name"]} x{count}{event_line}\n'

        # Add separator after each anime section
        harem_message += '⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋\n'


    total_count = len(user['characters'])
    
    keyboard = [
        [InlineKeyboardButton(f"See Collection ({total_count})", switch_inline_query_current_chat=f"collection.{user_id}")],
        [InlineKeyboardButton(f"📊 Database", url=f"https://t.me/c/{str(CHARA_CHANNEL_ID).replace('-100', '')}")]
    ]


    if total_pages > 1:
        
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"harem:{page-1}:{user_id}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"harem:{page+1}:{user_id}"))
        keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if 'favorites' in user and user['favorites']:
        
        fav_character_id = user['favorites'][0]
        fav_character = next((c for c in user['characters'] if c['id'] == fav_character_id), None)

        if fav_character and 'img_url' in fav_character:
            if update.message:
                try:
                    from shivu import process_image_url, LOGGER
                    user_id = update.effective_user.id if update.effective_user else None
                    processed_url = await process_image_url(await get_character_display_url(fav_character, fav_character_id, user_id))
                    
                    # Check if it's a video and use appropriate send method
                    if await is_video_character(fav_character, fav_character_id, user_id):
                        try:
                            await update.message.reply_video(video=processed_url, parse_mode='HTML', caption=harem_message, reply_markup=reply_markup)
                        except Exception as video_error:
                            # Fallback: try as photo if video fails
                            LOGGER.warning(f"Harem: Favorite video send failed, URL: {processed_url[:100]}, Error: {str(video_error)}. Trying as photo.")
                            try:
                                await update.message.reply_photo(photo=processed_url, parse_mode='HTML', caption=f"🎬 [Video] {harem_message}", reply_markup=reply_markup)
                            except Exception as photo_error:
                                # If media fails, send text instead
                                LOGGER.error(f"Harem: Both favorite video and photo failed, URL: {processed_url[:100]}")
                                await update.message.reply_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
                    else:
                        await update.message.reply_photo(photo=processed_url, parse_mode='HTML', caption=harem_message, reply_markup=reply_markup)
                except Exception as e:
                    # If media fails, send text instead
                    await update.message.reply_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
            else:
                # For callback queries, update image and caption using media edit
                try:
                    from shivu import process_image_url, LOGGER
                    from telegram import InputMediaPhoto, InputMediaVideo
                    user_id = update.effective_user.id if update.effective_user else None
                    processed_url = await process_image_url(await get_character_display_url(fav_character, fav_character_id, user_id))
                    
                    # Check if it's a video and use appropriate media type
                    if await is_video_character(fav_character, fav_character_id, user_id):
                        try:
                            media = InputMediaVideo(media=processed_url, caption=harem_message, parse_mode='HTML')
                            await update.callback_query.edit_message_media(media=media, reply_markup=reply_markup)
                            await update.callback_query.answer()
                        except Exception as video_error:
                            # Fallback: try as photo if video fails
                            LOGGER.warning(f"Harem callback: Favorite video edit failed, URL: {processed_url[:100]}, Error: {str(video_error)}. Trying as photo.")
                            try:
                                media = InputMediaPhoto(media=processed_url, caption=f"🎬 [Video] {harem_message}", parse_mode='HTML')
                                await update.callback_query.edit_message_media(media=media, reply_markup=reply_markup)
                                await update.callback_query.answer()
                            except Exception as photo_error:
                                # Fallback to just editing caption if media edit fails
                                LOGGER.error(f"Harem callback: Both favorite video and photo edit failed, URL: {processed_url[:100]}")
                                try:
                                    if update.callback_query and update.callback_query.message and update.callback_query.message.caption != harem_message:
                                        await update.callback_query.edit_message_caption(caption=harem_message, reply_markup=reply_markup, parse_mode='HTML')
                                    if update.callback_query:
                                        await update.callback_query.answer()
                                except Exception:
                                    if update.callback_query:
                                        await update.callback_query.answer("Failed to update media")
                    else:
                        media = InputMediaPhoto(media=processed_url, caption=harem_message, parse_mode='HTML')
                        await update.callback_query.edit_message_media(media=media, reply_markup=reply_markup)
                        await update.callback_query.answer()
                except Exception:
                    # Fallback to just editing caption if media edit fails
                    try:
                        if update.callback_query and update.callback_query.message and update.callback_query.message.caption != harem_message:
                            await update.callback_query.edit_message_caption(caption=harem_message, reply_markup=reply_markup, parse_mode='HTML')
                        if update.callback_query:
                            await update.callback_query.answer()
                    except Exception:
                        if update.callback_query:
                            await update.callback_query.answer("Failed to update media")
        else:
            # Favorite not found or has no img_url - fall back to random character
            if user['characters']:
                random_character = random.choice(user['characters'])
                if 'img_url' in random_character:
                    if update.message:
                        try:
                            from shivu import process_image_url, LOGGER
                            user_id = update.effective_user.id if update.effective_user else None
                            processed_url = await process_image_url(await get_character_display_url(random_character, random_character.get("id"), user_id))
                            
                            if await is_video_character(random_character, random_character.get("id"), user_id):
                                try:
                                    await update.message.reply_video(video=processed_url, parse_mode='HTML', caption=harem_message, reply_markup=reply_markup)
                                except Exception:
                                    try:
                                        await update.message.reply_photo(photo=processed_url, parse_mode='HTML', caption=harem_message, reply_markup=reply_markup)
                                    except Exception:
                                        await update.message.reply_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
                            else:
                                await update.message.reply_photo(photo=processed_url, parse_mode='HTML', caption=harem_message, reply_markup=reply_markup)
                        except Exception:
                            await update.message.reply_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
                    else:
                        try:
                            from shivu import process_image_url, LOGGER
                            from telegram import InputMediaPhoto, InputMediaVideo
                            user_id = update.effective_user.id if update.effective_user else None
                            processed_url = await process_image_url(await get_character_display_url(random_character, random_character.get("id"), user_id))
                            
                            if await is_video_character(random_character, random_character.get("id"), user_id):
                                try:
                                    media = InputMediaVideo(media=processed_url, caption=harem_message, parse_mode='HTML')
                                    await update.callback_query.edit_message_media(media=media, reply_markup=reply_markup)
                                    await update.callback_query.answer()
                                except Exception:
                                    try:
                                        media = InputMediaPhoto(media=processed_url, caption=harem_message, parse_mode='HTML')
                                        await update.callback_query.edit_message_media(media=media, reply_markup=reply_markup)
                                        await update.callback_query.answer()
                                    except Exception:
                                        if update.callback_query and update.callback_query.message:
                                            await update.callback_query.edit_message_caption(caption=harem_message, reply_markup=reply_markup, parse_mode='HTML')
                                        await update.callback_query.answer()
                            else:
                                media = InputMediaPhoto(media=processed_url, caption=harem_message, parse_mode='HTML')
                                await update.callback_query.edit_message_media(media=media, reply_markup=reply_markup)
                                await update.callback_query.answer()
                        except Exception:
                            if update.callback_query and update.callback_query.message:
                                await update.callback_query.edit_message_caption(caption=harem_message, reply_markup=reply_markup, parse_mode='HTML')
                            if update.callback_query:
                                await update.callback_query.answer()
                else:
                    if update.message:
                        await update.message.reply_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
                    else:
                        if update.callback_query and update.callback_query.message and update.callback_query.message.text != harem_message:
                            await update.callback_query.edit_message_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
            else:
                if update.message:
                    await update.message.reply_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
                else:
                    if update.callback_query and update.callback_query.message and update.callback_query.message.text != harem_message:
                        await update.callback_query.edit_message_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
    else:
        
        if user['characters']:
        
            random_character = random.choice(user['characters'])

            if 'img_url' in random_character:
                if update.message:
                    try:
                        from shivu import process_image_url, LOGGER
                        user_id_no_fav = update.effective_user.id if update.effective_user else None
                        processed_url = await process_image_url(await get_character_display_url(random_character, random_character.get("id"), user_id_no_fav))
                        
                        # Check if it's a video and use appropriate send method
                        if await is_video_character(random_character, random_character.get("id"), user_id_no_fav):
                            try:
                                await update.message.reply_video(video=processed_url, parse_mode='HTML', caption=harem_message, reply_markup=reply_markup)
                            except Exception as video_error:
                                # Fallback: try as photo if video fails
                                LOGGER.warning(f"Harem: Random video send failed, URL: {processed_url[:100]}, Error: {str(video_error)}. Trying as photo.")
                                try:
                                    await update.message.reply_photo(photo=processed_url, parse_mode='HTML', caption=f"🎬 [Video] {harem_message}", reply_markup=reply_markup)
                                except Exception as photo_error:
                                    # If media fails, send text instead
                                    LOGGER.error(f"Harem: Both random video and photo failed, URL: {processed_url[:100]}")
                                    await update.message.reply_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
                        else:
                            await update.message.reply_photo(photo=processed_url, parse_mode='HTML', caption=harem_message, reply_markup=reply_markup)
                    except Exception as e:
                        # If media fails, send text instead
                        await update.message.reply_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
                else:
                    # For callback queries, update image and caption using media edit
                    try:
                        from shivu import process_image_url, LOGGER
                        from telegram import InputMediaPhoto, InputMediaVideo
                        user_id_no_fav = update.effective_user.id if update.effective_user else None
                        processed_url = await process_image_url(await get_character_display_url(random_character, random_character.get("id"), user_id_no_fav))
                        
                        # Check if it's a video and use appropriate media type
                        if await is_video_character(random_character, random_character.get("id"), user_id_no_fav):
                            try:
                                media = InputMediaVideo(media=processed_url, caption=harem_message, parse_mode='HTML')
                                await update.callback_query.edit_message_media(media=media, reply_markup=reply_markup)
                                await update.callback_query.answer()
                            except Exception as video_error:
                                # Fallback: try as photo if video fails
                                LOGGER.warning(f"Harem callback: Random video edit failed, URL: {processed_url[:100]}, Error: {str(video_error)}. Trying as photo.")
                                try:
                                    media = InputMediaPhoto(media=processed_url, caption=f"🎬 [Video] {harem_message}", parse_mode='HTML')
                                    await update.callback_query.edit_message_media(media=media, reply_markup=reply_markup)
                                    await update.callback_query.answer()
                                except Exception as photo_error:
                                    # Fallback to just editing caption if media edit fails
                                    LOGGER.error(f"Harem callback: Both random video and photo edit failed, URL: {processed_url[:100]}")
                                    try:
                                        if update.callback_query and update.callback_query.message and update.callback_query.message.caption != harem_message:
                                            await update.callback_query.edit_message_caption(caption=harem_message, reply_markup=reply_markup, parse_mode='HTML')
                                        if update.callback_query:
                                            await update.callback_query.answer()
                                    except Exception:
                                        if update.callback_query:
                                            await update.callback_query.answer("Failed to update media")
                        else:
                            media = InputMediaPhoto(media=processed_url, caption=harem_message, parse_mode='HTML')
                            await update.callback_query.edit_message_media(media=media, reply_markup=reply_markup)
                            await update.callback_query.answer()
                    except Exception:
                        # Fallback to just editing caption if media edit fails
                        try:
                            if update.callback_query and update.callback_query.message and update.callback_query.message.caption != harem_message:
                                await update.callback_query.edit_message_caption(caption=harem_message, reply_markup=reply_markup, parse_mode='HTML')
                            if update.callback_query:
                                await update.callback_query.answer()
                        except Exception:
                            if update.callback_query:
                                await update.callback_query.answer("Failed to update media")
            else:
                if update.message:
                    await update.message.reply_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
                else:
                
                    if update.callback_query and update.callback_query.message and update.callback_query.message.text != harem_message:
                        await update.callback_query.edit_message_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
                    if update.callback_query:
                        await update.callback_query.answer()
        else:
            if update.message:
                await update.message.reply_text("Your List is Empty :)")


async def harem_callback(update: Update, context: CallbackContext) -> None:
    if not update.callback_query or not update.callback_query.data:
        return
        
    query = update.callback_query
    data = query.data

    data_parts = data.split(':')
    if len(data_parts) != 3:
        return
        
    _, page_str, user_id_str = data_parts

    try:
        page = int(page_str)
        user_id = int(user_id_str)
    except ValueError:
        return

    # Check if the user is allowed to navigate this harem
    if query.from_user:
        viewer_id = query.from_user.id
        is_owner = viewer_id == user_id
        is_sudo = str(viewer_id) in [str(u) for u in Config.sudo_users]
        
        if not is_owner and not is_sudo:
            await query.answer("This is not your harem!", show_alert=True)
            return

    await harem(update, context, page)




# Pending favorites for confirmation
pending_favorites = {}

@shivuu.on_message(filters.command("fav"))
async def fav(client, message):
    """Set a favorite character with confirmation"""
    user_id = message.from_user.id
    
    if len(message.command) != 2:
        await message.reply_text(
            "💕 <b>Set Favorite Character</b>\n\n"
            "Usage: <code>/fav [character_id]</code>\n\n"
            "Example: <code>/fav 123</code>",
            parse_mode=enums.ParseMode.HTML
        )
        return
    
    character_id = message.command[1]
    
    # Get user's collection
    user = await user_collection.find_one({'id': user_id})
    if not user or not user.get('characters'):
        await message.reply_text("❌ You don't have any characters yet!")
        return
    
    # Find the character
    character = next((c for c in user['characters'] if c['id'] == character_id), None)
    if not character:
        await message.reply_text(f"❌ You don't have character ID `{character_id}` in your collection!", parse_mode=enums.ParseMode.MARKDOWN)
        return
    
    # Store pending favorite
    pending_favorites[user_id] = character
    
    # Create confirmation keyboard
    keyboard = PyroInlineKeyboardMarkup([
        [PyroInlineKeyboardButton("✅ Confirm", callback_data="confirm_fav")],
        [PyroInlineKeyboardButton("❌ Cancel", callback_data="cancel_fav")]
    ])
    
    # Send character image with confirmation
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
        "Limited Edition": "🍬"
    }
    
    rarity_emoji = rarity_emojis.get(character.get('rarity', 'Common'), "✨")
    
    caption = (f"💕 <b>Do you want to favorite this character?</b>\n\n"
               f"🎴 <b>Name:</b> {escape(character['name'])}\n"
               f"📺 <b>Anime:</b> {escape(character['anime'])}\n"
               f"🌟 <b>Rarity:</b> {rarity_emoji} {character['rarity']}\n"
               f"🆔 <b>ID:</b> <code>{character['id']}</code>")
    
    try:
        if 'img_url' in character:
            from shivu import process_image_url, LOGGER
            user_id_pyrogram = message.from_user.id if message.from_user else None
            display_url = await get_character_display_url(character, character.get('id'), user_id_pyrogram)
            processed_url = await process_image_url(display_url)
            
            # Check if it's a video and use appropriate send method
            if await is_video_character(character, character.get('id')):
                try:
                    await message.reply_video(
                        video=processed_url,
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=keyboard
                    )
                except Exception as video_error:
                    # Fallback: try sending as photo if video fails
                    LOGGER.warning(f"/fav: Video send failed for character {character['id']}, URL: {processed_url[:100]}, Error: {str(video_error)}. Trying as photo.")
                    try:
                        await message.reply_photo(
                            photo=processed_url,
                            caption=f"🎬 [Video] {caption}",
                            parse_mode=enums.ParseMode.HTML,
                            reply_markup=keyboard
                        )
                    except Exception as photo_error:
                        # Last resort: send text
                        LOGGER.error(f"/fav: Both video and photo failed for character {character['id']}, URL: {processed_url[:100]}")
                        await message.reply_text(f"{caption}\n\n⚠️ Media display failed.", parse_mode=enums.ParseMode.HTML, reply_markup=keyboard)
            else:
                await message.reply_photo(
                    photo=processed_url,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=keyboard
                )
        else:
            await message.reply_text(caption, parse_mode=enums.ParseMode.HTML, reply_markup=keyboard)
    except Exception as e:
        await message.reply_text(caption, parse_mode=enums.ParseMode.HTML, reply_markup=keyboard)

@shivuu.on_callback_query(filters.create(lambda _, __, query: query.data in ["confirm_fav", "cancel_fav"]))
async def fav_callback(client, callback_query):
    """Handle favorite confirmation callbacks"""
    user_id = callback_query.from_user.id
    
    if user_id not in pending_favorites:
        await callback_query.answer("❌ No pending favorite found!", show_alert=True)
        return
    
    if callback_query.data == "confirm_fav":
        character = pending_favorites[user_id]
        
        # Update user's favorite
        await user_collection.update_one(
            {'id': user_id},
            {'$set': {'favorites': [character['id']]}},
            upsert=True
        )
        
        await callback_query.edit_message_caption(
            caption=f"💕 <b>Favorite Set!</b>\n\n🎴 <b>{escape(character['name'])}\n</b>📺 <b>{escape(character['anime'])}\n</b>✨ This character is now your favorite!",
            parse_mode=enums.ParseMode.HTML
        )
        
    elif callback_query.data == "cancel_fav":
        await callback_query.edit_message_caption(
            caption="❌ <b>Favorite cancelled.</b>",
            parse_mode=enums.ParseMode.HTML
        )
    
    # Clean up pending favorite
    if user_id in pending_favorites:
        del pending_favorites[user_id]
    
    await callback_query.answer()

async def transfer_harem(update: Update, context: CallbackContext) -> None:
    """Transfer a user's harem from old user_id to new user_id (admin only)"""
    if not update.effective_user or not update.message:
        return
        
    user_id = update.effective_user.id
    
    # Check if user is admin
    from shivu.config import Config
    if str(user_id) not in [str(u) for u in Config.sudo_users]:
        await update.message.reply_text('🚫 This command is only available to bot administrators.')
        return
    
    args = context.args or []
    if len(args) != 2:
        await update.message.reply_text(
            "📝 <b>Transfer Harem Usage:</b>\n\n"
            "<code>/transfer [old_user_id] [new_user_id]</code>\n\n"
            "<b>Example:</b> <code>/transfer 123456789 987654321</code>\n\n"
            "This will transfer all characters from the old user to the new user.",
            parse_mode='HTML'
        )
        return
    
    try:
        old_user_id = int(args[0])
        new_user_id = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid user IDs! Please provide valid numeric user IDs.")
        return
    
    if old_user_id == new_user_id:
        await update.message.reply_text("❌ Old and new user IDs cannot be the same!")
        return
    
    # Find the old user's collection
    old_user = await user_collection.find_one({'id': old_user_id})
    if not old_user or not old_user.get('characters'):
        await update.message.reply_text(f"❌ User {old_user_id} has no characters to transfer!")
        return
    
    # Get character count for confirmation message
    character_count = len(old_user['characters'])
    old_username = old_user.get('username', 'Unknown')
    old_first_name = old_user.get('first_name', 'Unknown')
    
    # Check if new user exists, if not create their document
    new_user = await user_collection.find_one({'id': new_user_id})
    characters_to_transfer = old_user['characters']  # All characters will be transferred
    
    if not new_user:
        # Create new user document
        await user_collection.insert_one({
            'id': new_user_id,
            'first_name': 'Unknown',
            'username': 'Unknown',
            'characters': characters_to_transfer
        })
    else:
        # Add all characters to existing user, preserving duplicates
        existing_characters = new_user.get('characters', [])
        all_characters = existing_characters + characters_to_transfer
        await user_collection.update_one(
            {'id': new_user_id},
            {'$set': {'characters': all_characters}}
        )
    
    # Clear the old user's characters and favorites to maintain consistency
    await user_collection.update_one(
        {'id': old_user_id},
        {'$set': {'characters': []}, '$unset': {'favorites': 1}}
    )
    
    # Success message
    new_user_info = await user_collection.find_one({'id': new_user_id})
    new_username = new_user_info.get('username', 'Unknown') if new_user_info else 'Unknown'
    new_first_name = new_user_info.get('first_name', 'Unknown') if new_user_info else 'Unknown'
    
    await update.message.reply_text(
        f"✅ <b>Transfer Completed!</b>\n\n"
        f"📤 <b>From:</b> {escape(old_first_name)} (@{old_username}) - <code>{old_user_id}</code>\n"
        f"📥 <b>To:</b> {escape(new_first_name)} (@{new_username}) - <code>{new_user_id}</code>\n\n"
        f"🎴 <b>Characters Transferred:</b> {character_count}\n\n"
        f"All characters (including duplicates) have been successfully transferred!",
        parse_mode='HTML'
    )


# python-telegram-bot version of /fav command (works with webhooks)
async def fav_ptb(update: Update, context: CallbackContext):
    """Set a favorite character with confirmation - PTB version"""
    user_id = update.effective_user.id
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "💕 <b>Set Favorite Character</b>\n\n"
            "Usage: <code>/fav [character_id]</code>\n\n"
            "Example: <code>/fav 123</code>",
            parse_mode='HTML'
        )
        return
    
    character_id = context.args[0]
    
    # Get user's collection
    user = await user_collection.find_one({'id': user_id})
    if not user or not user.get('characters'):
        await update.message.reply_text("❌ You don't have any characters yet!")
        return
    
    # Find the character
    character = next((c for c in user['characters'] if c['id'] == character_id), None)
    if not character:
        await update.message.reply_text(f"❌ You don't have character ID `{character_id}` in your collection!", parse_mode='Markdown')
        return
    
    # Store pending favorite
    pending_favorites[user_id] = character
    
    # Create confirmation keyboard
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_fav")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_fav")]
    ])
    
    # Send character image with confirmation
    rarity_emojis = {
        "Common": "⚪️", "Uncommon": "🟢", "Rare": "🔵", "Epic": "🟣",
        "Legendary": "🟡", "Mythic": "🏵", "Retro": "🍥", "Star": "⭐",
        "Zenith": "🪩", "Limited Edition": "🍬"
    }
    
    rarity_emoji = rarity_emojis.get(character.get('rarity', 'Common'), "✨")
    
    caption = (f"💕 <b>Do you want to favorite this character?</b>\n\n"
               f"🎴 <b>Name:</b> {escape(character['name'])}\n"
               f"📺 <b>Anime:</b> {escape(character['anime'])}\n"
               f"🌟 <b>Rarity:</b> {rarity_emoji} {character['rarity']}\n"
               f"🆔 <b>ID:</b> <code>{character['id']}</code>")
    
    try:
        if 'img_url' in character:
            from shivu import process_image_url, LOGGER
            user_id_ptb = update.effective_user.id if update.effective_user else None
            display_url = await get_character_display_url(character, character.get('id'), user_id_ptb)
            processed_url = await process_image_url(display_url)
            
            # Check if it's a video
            if await is_video_character(character, character.get('id')):
                try:
                    await update.message.reply_video(
                        video=processed_url,
                        caption=caption,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                except Exception as video_error:
                    LOGGER.warning(f"/fav PTB: Video failed, trying photo")
                    try:
                        await update.message.reply_photo(
                            photo=processed_url,
                            caption=f"🎬 [Video] {caption}",
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                    except:
                        await update.message.reply_text(f"{caption}\n\n⚠️ Media display failed.", parse_mode='HTML', reply_markup=keyboard)
            else:
                await update.message.reply_photo(
                    photo=processed_url,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
        else:
            await update.message.reply_text(caption, parse_mode='HTML', reply_markup=keyboard)
    except Exception as e:
        await update.message.reply_text(caption, parse_mode='HTML', reply_markup=keyboard)


async def fav_callback_ptb(update: Update, context: CallbackContext):
    """Handle favorite confirmation callbacks - PTB version"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in pending_favorites:
        await query.answer("❌ No pending favorite found!", show_alert=True)
        return
    
    if query.data == "confirm_fav":
        character = pending_favorites[user_id]
        
        # Update user's favorite
        await user_collection.update_one(
            {'id': user_id},
            {'$set': {'favorites': [character['id']]}},
            upsert=True
        )
        
        try:
            await query.edit_message_caption(
                caption=f"💕 <b>Favorite Set!</b>\n\n🎴 <b>{escape(character['name'])}\n</b>📺 <b>{escape(character['anime'])}\n</b>✨ This character is now your favorite!",
                parse_mode='HTML'
            )
        except:
            await query.message.edit_text(
                text=f"💕 <b>Favorite Set!</b>\n\n🎴 <b>{escape(character['name'])}\n</b>📺 <b>{escape(character['anime'])}\n</b>✨ This character is now your favorite!",
                parse_mode='HTML'
            )
        
    elif query.data == "cancel_fav":
        try:
            await query.edit_message_caption(
                caption="❌ <b>Favorite cancelled.</b>",
                parse_mode='HTML'
            )
        except:
            await query.message.edit_text("❌ <b>Favorite cancelled.</b>", parse_mode='HTML')
    
    # Clean up pending favorite
    if user_id in pending_favorites:
        del pending_favorites[user_id]
    
    await query.answer()


async def all_rarities(update: Update, context: CallbackContext) -> None:
    """Show collection progress for all rarities"""
    if not update.effective_user or not update.message:
        return
    
    user_id = update.effective_user.id
    
    user = await user_collection.find_one({'id': user_id})
    if not user:
        await update.message.reply_text(
            "❌ You haven't started collecting yet!\n\n"
            "Characters appear every 100 messages. Use /invite to collect them!",
            parse_mode='HTML'
        )
        return
    
    user_characters = user.get('characters', [])
    if not user_characters:
        await update.message.reply_text(
            "❌ You don't have any characters yet!\n\n"
            "Characters appear every 100 messages. Use /invite to collect them!",
            parse_mode='HTML'
        )
        return
    
    # Get unique characters only (no duplicates)
    unique_user_characters = list({char['id']: char for char in user_characters}.values())
    
    # Count unique user's characters by rarity
    user_rarity_counts = Counter(char.get('rarity', 'Common') for char in unique_user_characters)
    
    # Get total counts for each rarity from the collection
    all_characters = await collection.find().to_list(length=None)
    total_rarity_counts = Counter(char.get('rarity', 'Common') for char in all_characters)
    
    # Define rarity order and emojis (Star above Zenith as requested)
    rarity_order = ["Limited Edition", "Star", "Zenith", "Retro", "Mythic", "Legendary", "Epic", "Rare", "Uncommon", "Common"]
    rarity_emojis = {
        "Common": "⚪️",
        "Uncommon": "🟢",
        "Rare": "🟠",
        "Epic": "🟣",
        "Legendary": "🟡",
        "Mythic": "🏵",
        "Retro": "🍥",
        "Star": "⭐",
        "Zenith": "🪩",
        "Limited Edition": "🍬"
    }
    
    # Build message
    message_text = f"📊 <b>{escape(update.effective_user.first_name)}'s Collection Progress</b>\n\n"
    
    for rarity in rarity_order:
        owned = user_rarity_counts.get(rarity, 0)
        total = total_rarity_counts.get(rarity, 0)
        
        if total == 0:
            continue
        
        percentage = int((owned / total) * 100) if total > 0 else 0
        
        # Create progress bar (10 blocks)
        filled_blocks = int((owned / total) * 10) if total > 0 else 0
        progress_bar = "▰" * filled_blocks + "▱" * (10 - filled_blocks)
        
        emoji = rarity_emojis.get(rarity, "✨")
        
        message_text += f"{emoji} <b>{rarity}:</b> {owned}/{total}\n"
        message_text += f"{progress_bar} {percentage}%\n"
    
    message_text += f"\n✨ <b>Total Unique Characters:</b> {len(unique_user_characters)}/{len(all_characters)}"
    
    await update.message.reply_text(message_text, parse_mode='HTML')


application.add_handler(CommandHandler(["harem", "collection"], harem,block=False))
application.add_handler(CommandHandler("sorts", sorts, block=False))
application.add_handler(CommandHandler("transfer", transfer_harem, block=False))
application.add_handler(CommandHandler("fav", fav_ptb, block=False))
application.add_handler(CommandHandler("all", all_rarities, block=False))
harem_handler = CallbackQueryHandler(harem_callback, pattern='^harem', block=False)
application.add_handler(harem_handler)
fav_callback_handler = CallbackQueryHandler(fav_callback_ptb, pattern="^(confirm_fav|cancel_fav)$", block=False)
application.add_handler(fav_callback_handler)
    
