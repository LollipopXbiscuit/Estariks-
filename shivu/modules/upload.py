import urllib.request
import urllib.parse
import urllib.error
import re
from pymongo import ReturnDocument

from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from shivu import application, sudo_users, uploading_users, collection, db, CHARA_CHANNEL_ID, SUPPORT_CHAT, user_collection
from shivu.modules.harem import get_character_display_url

# Rarity styles for display purposes
rarity_styles = {
    "Common": "⚪️",
    "Rare": "🟠",
    "Legendary": "🟡",
    "Flat": "🔮",
    "Ninja": "⚡️",
    "Knight": "🗡",
    "Catapult": "🪄",
    "Custom": "👾"
}

def get_format_text(level):
    if level == 1:
        return """Wrong ❌️ format...  eg. /upload Img_url muzan-kibutsuji Demon-slayer 5

img_url character-name anime-name rarity-number

𝘠𝘰𝘶 𝘤𝘢𝘯 𝘶𝘱𝘭𝘰𝘢𝘥 𝘵𝘩𝘦𝘴𝘦 𝘳𝘢𝘳𝘪𝘵𝘪𝘦𝘴 :

1 = ⚪️ Common
2 = 🟠 Rare
3 = 🟡 Legendary

𝘠𝘰𝘶𝘳 𝘶𝘱𝘭𝘰𝘢𝘥𝘦𝘳 𝘭𝘦𝘷𝘦𝘭 𝘪𝘴 1 🪄 !

✅ Supported: Discord CDN links, direct image/video URLs (including MP4), and other standard hosting services"""
    elif level == 2:
        return """Wrong ❌️ format...  eg. /upload Img_url muzan-kibutsuji Demon-slayer 5

img_url character-name anime-name rarity-number

𝘠𝘰𝘶 𝘤𝘢𝘯 𝘶𝘱𝘭𝘰𝘢𝘥 𝘵𝘩𝘦𝘴𝘦 𝘳𝘢𝘳𝘪𝘵𝘪𝘦𝘴 :

1 = ⚪️ Common
2 = 🟠 Rare
3 = 🟡 Legendary
4 = 🔮 Flat
5 = ⚡️ Ninja
6 = 🗡 Knight

𝘠𝘰𝘶𝘳 𝘶𝘱𝘭𝘰𝘢𝘥𝘦𝘳 𝘭𝘦𝘷𝘦𝘭 𝘪𝘴 2 🎏 !

✅ Supported: Discord CDN links, direct image/video URLs (including MP4), and other standard hosting services"""
    else:
        return """Wrong ❌️ format...  eg. /upload Img_url muzan-kibutsuji Demon-slayer 5

img_url character-name anime-name rarity-number

𝘠𝘰𝘶 𝘤𝘢𝘯 𝘶𝘱𝘭𝘰𝘢𝘥 𝘢𝘭𝘭 𝘳𝘢𝘳𝘪𝘵𝘪𝘦𝘴 :

1 = ⚪️ Common
2 = 🟠 Rare
3 = 🟡 Legendary
4 = 🔮 Flat
5 = ⚡️ Ninja
6 = 🗡 Knight
7 = 🪄 Catapult
8 = 🍬 Limited Edition
9 = 👾 Custom 

𝘠𝘰𝘶𝘳 𝘶𝘱𝘭𝘰𝘢𝘥𝘦𝘳 𝘭𝘦𝘷𝘦𝘭 is 3 🎐 !

✅ Supported: Discord CDN links, direct image/video URLs (including MP4), and other standard hosting services"""


async def get_uploader_level(user_id):
    """Get uploader level from database (default 1) or 3 for sudo users"""
    user_id_str = str(user_id)
    if user_id_str in sudo_users:
        return 3
    
    dynamic_uploaders_collection = db['dynamic_uploading_users']
    uploader = await dynamic_uploaders_collection.find_one({'user_id': user_id_str})
    if uploader:
        return uploader.get('level', 1)
    
    if user_id_str in uploading_users:
        return 1
    return 0


async def can_upload(user_id):
    """Check if user has upload permissions (sudo_users, uploading_users env var, or dynamic uploading_users)"""
    return await get_uploader_level(user_id) > 0


async def promote(update: Update, context: CallbackContext) -> None:
    if not update.effective_user or not update.message:
        return
        
    if str(update.effective_user.id) not in sudo_users:
        await update.message.reply_text('Only Owners can use this command.')
        return

    try:
        args = context.args
        if not args or len(args) != 2:
            await update.message.reply_text('Usage: /promote <user_id> <level>')
            return

        user_id = args[0]
        level = int(args[1])

        if level not in [1, 2, 3]:
            await update.message.reply_text('Level must be 1, 2, or 3.')
            return

        dynamic_uploaders_collection = db['dynamic_uploading_users']
        await dynamic_uploaders_collection.update_one(
            {'user_id': user_id},
            {'$set': {'level': level}},
            upsert=True
        )
        
        await update.message.reply_text(f'✅ User {user_id} promoted to level {level}.')
    except Exception as e:
        await update.message.reply_text(f'Error: {str(e)}')


def is_discord_cdn_url(url):
    """Check if the URL is a Discord CDN link or a local/direct file link"""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return False
        
        discord_hosts = [
            'cdn.discordapp.com',
            'media.discordapp.net',
            'attachments.discordapp.net',
            'cdn.discord.com',
            'media.discord.com'
        ]
        
        # Also support 0.0.0.0 or other direct IP links mentioned by user
        if parsed.netloc in discord_hosts or parsed.netloc == '0.0.0.0':
            return True
            
        return False
    except:
        return False


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
        # For non-custom or queries without user_id, use simpler lookup
        url = character.get('img_url', '')
    
    if is_video_url(url):
        return True
    
    return False


def validate_url(url):
    """
    Validate a URL and return whether it's accessible.
    Handles Discord CDN links with special logic.
    """
    # For Discord or direct file links (like 0.0.0.0/dl/...), bypass full validation and just check structure
    if is_discord_cdn_url(url):
        try:
            parsed = urllib.parse.urlparse(url)
            # Basic validation for path structure
            if parsed.path and ('/' in parsed.path[1:]):  # Has meaningful path
                return True, "Media link (validation bypassed)"
            else:
                return False, "Invalid media link structure"
        except:
            return False, "Invalid media URL format"
    
    # For non-Discord URLs, perform full validation
    try:
        # Create request with appropriate headers
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        # Try to open the URL
        with urllib.request.urlopen(req, timeout=10) as response:
            # Check if it's an image or video by checking content type or URL
            content_type = response.headers.get('Content-Type', '')
            if content_type.startswith('image/') or content_type.startswith('video/'):
                return True, f"Valid {'image' if content_type.startswith('image/') else 'video'} URL"
            elif any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.mp4', '.mov', '.avi', '.mkv']):
                return True, "Valid media URL"
            else:
                return False, "URL does not appear to be an image or video"
                
    except urllib.error.HTTPError as e:
        return False, f"HTTP Error: {e.code}"
    except urllib.error.URLError as e:
        return False, f"URL Error: {str(e)}"
    except Exception as e:
        return False, f"Validation Error: {str(e)}"



async def can_upload(user_id):
    """Check if user has upload permissions (sudo_users, uploading_users env var, or dynamic uploading_users)"""
    user_id_str = str(user_id)
    
    # Check if user is in sudo_users or env uploading_users
    if user_id_str in sudo_users or user_id_str in uploading_users:
        return True
    
    # Check if user is in dynamic uploading_users collection
    dynamic_uploaders_collection = db['dynamic_uploading_users']
    uploader = await dynamic_uploaders_collection.find_one({'user_id': user_id_str})
    return uploader is not None

async def get_next_sequence_number(sequence_name):
    sequence_collection = db.sequences
    sequence_document = await sequence_collection.find_one_and_update(
        {'_id': sequence_name}, 
        {'$inc': {'sequence_value': 1}}, 
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return sequence_document['sequence_value']

async def upload(update: Update, context: CallbackContext) -> None:
    if not update.effective_user or not update.message:
        return
        
    level = await get_uploader_level(update.effective_user.id)
    if level == 0:
        await update.message.reply_text('Ask My Owner or authorized uploader...')
        return

    try:
        args = context.args
        if not args or len(args) != 4:
            await update.message.reply_text(get_format_text(level), parse_mode='HTML')
            return

        # Clean character name: remove special Unicode chars, replace separators with spaces
        import unicodedata
        character_name = args[1]
        # Replace common Arabic diacritics and special characters with spaces
        character_name = character_name.replace('ـ', ' ')  # Arabic Tatweel
        character_name = character_name.replace('-', ' ')
        character_name = character_name.replace('_', ' ')
        # Remove combining marks and normalize Unicode
        character_name = ''.join(c for c in unicodedata.normalize('NFKD', character_name) 
                                 if not unicodedata.combining(c))
        # Clean up multiple spaces
        character_name = ' '.join(character_name.split())
        character_name = character_name.title()
        
        # Clean anime name similarly
        anime = args[2]
        anime = anime.replace('ـ', ' ')
        anime = anime.replace('-', ' ')
        anime = anime.replace('_', ' ')
        anime = ''.join(c for c in unicodedata.normalize('NFKD', anime) 
                       if not unicodedata.combining(c))
        anime = ' '.join(anime.split())
        anime = anime.title()

        # Validate URL with enhanced Discord CDN support
        is_valid, validation_message = validate_url(args[0])
        # If the error is "URL does not appear to be an image or video", we check for local links
        if not is_valid and "does not appear to be an image or video" in validation_message:
             if is_discord_cdn_url(args[0]):
                 is_valid = True
                 validation_message = "Media link (validation bypassed)"

        if not is_valid:
            await update.message.reply_text(f'Invalid URL: {validation_message}')
            return
        
        # Check if it's a video based on validation message or URL extension
        is_video = 'video' in validation_message.lower() or any(ext in args[0].lower() for ext in ['.mp4', '.mov', '.avi', '.mkv'])
        
        # If it's a Discord CDN link, inform the user
        if is_discord_cdn_url(args[0]):
            await update.message.reply_text('✅ Discord CDN link detected - processing...', reply_to_message_id=update.message.message_id)

        rarity_map = {
            1: "Common", 
            2: "Rare", 
            3: "Legendary", 
            4: "Flat", 
            5: "Ninja", 
            6: "Knight", 
            7: "Catapult", 
            8: "Custom"
        }
        try:
            rarity_num = int(args[3])
            # Level restrictions
            if level == 1 and rarity_num > 3:
                await update.message.reply_text('❌ Level 1 uploaders can only upload up to Legendary rank (1-3).')
                return
            if level == 2 and rarity_num > 6:
                await update.message.reply_text('❌ Level 2 uploaders can only upload up to Knight rank (1-6).')
                return
            
            rarity = rarity_map[rarity_num]
        except (KeyError, ValueError):
            await update.message.reply_text(get_format_text(level), parse_mode='HTML')
            return

        id = str(await get_next_sequence_number('character_id'))

        character = {
            'img_url': args[0],
            'name': character_name,
            'anime': anime,
            'rarity': rarity,
            'id': id
        }

        try:
            rarity_emoji = rarity_styles.get(rarity, "")
            from shivu import process_image_url
            processed_url = await process_image_url(args[0])
            # Create neat and pretty caption format
            caption = (
                f"✨ <b>{character_name}</b> ✨\n"
                f"🎌 <i>{anime}</i>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"{rarity_emoji} <b>{rarity}</b>\n"
                f"🆔 <b>ID:</b> #{id}\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📤 Added by <a href='tg://user?id={update.effective_user.id}'>{update.effective_user.first_name}</a>"
            )
            
            if is_video:
                message = await context.bot.send_video(
                    chat_id=CHARA_CHANNEL_ID,
                    video=processed_url,
                    caption=caption,
                    parse_mode='HTML'
                )
            else:
                message = await context.bot.send_photo(
                    chat_id=CHARA_CHANNEL_ID,
                    photo=processed_url,
                    caption=caption,
                    parse_mode='HTML'
                )
            character['message_id'] = message.message_id
            await collection.insert_one(character)
            await update.message.reply_text('CHARACTER ADDED....')
        except:
            await collection.insert_one(character)
            await update.effective_message.reply_text("Character Added but no Database Channel Found, Consider adding one.")
        
    except Exception as e:
        await update.message.reply_text(f'Character Upload Unsuccessful. Error: {str(e)}\nIf you think this is a source error, forward to: {SUPPORT_CHAT}')


async def update_card(update: Update, context: CallbackContext) -> None:
    if not update.effective_user or not update.message:
        return
        
    if not await can_upload(update.effective_user.id):
        await update.message.reply_text('Ask My Owner or authorized uploader...')
        return

    try:
        args = context.args
        if not args or len(args) < 5:
            await update.message.reply_text(
                "Usage: /update ID img_url character-name anime-name rarity-number\n\n"
                "Example: /update 1 https://example.com/img.jpg Muzan-Kibutsuji Demon-Slayer 5"
            )
            return

        character_id = args[0]
        new_img_url = args[1]
        character_name = args[2].replace('-', ' ').title()
        anime = args[3].replace('-', ' ').title()

        # Find the character
        character = await collection.find_one({'id': character_id})
        if not character:
            await update.message.reply_text(f'❌ Character with ID #{character_id} not found!')
            return

        # Validate URL
        is_valid, validation_message = validate_url(new_img_url)
        if not is_valid:
            await update.message.reply_text(f'Invalid URL: {validation_message}')
            return
        
        is_video = 'video' in validation_message.lower() or any(ext in new_img_url.lower() for ext in ['.mp4', '.mov', '.avi', '.mkv'])

        rarity_map = {
            1: "Common", 2: "Rare", 3: "Legendary", 4: "Flat", 5: "Ninja", 
            6: "Knight", 7: "Catapult"
        }
        try:
            rarity = rarity_map[int(args[4])]
        except (KeyError, ValueError):
            await update.message.reply_text('Invalid rarity (1-8).')
            return

        rarity_emoji = rarity_styles.get(rarity, "")
        from shivu import process_image_url
        processed_url = await process_image_url(new_img_url)
        
        caption = (
            f"✨ <b>{character_name}</b> (UPDATED) ✨\n"
            f"🎌 <i>{anime}</i>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{rarity_emoji} <b>{rarity}</b>\n"
            f"🆔 <b>ID:</b> #{character_id}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📤 Updated by <a href='tg://user?id={update.effective_user.id}'>{update.effective_user.first_name}</a>"
        )
        
        try:
            if is_video:
                message = await context.bot.send_video(
                    chat_id=CHARA_CHANNEL_ID,
                    video=processed_url,
                    caption=caption,
                    parse_mode='HTML'
                )
            else:
                message = await context.bot.send_photo(
                    chat_id=CHARA_CHANNEL_ID,
                    photo=processed_url,
                    caption=caption,
                    parse_mode='HTML'
                )
            
            # Update database
            update_data = {
                'img_url': new_img_url,
                'name': character_name,
                'anime': anime,
                'rarity': rarity,
                'message_id': message.message_id
            }
            
            await collection.update_one({'id': character_id}, {'$set': update_data})
            
            # Try to delete old message if exists
            if 'message_id' in character:
                try:
                    await context.bot.delete_message(chat_id=CHARA_CHANNEL_ID, message_id=character['message_id'])
                except:
                    pass
            
            await update.message.reply_text(f'✅ Character #{character_id} updated successfully!')
            
        except Exception as e:
            # Fallback update if channel sending fails
            await collection.update_one({'id': character_id}, {'$set': {
                'img_url': new_img_url,
                'name': character_name,
                'anime': anime,
                'rarity': rarity
            }})
            await update.message.reply_text(f'Character updated in DB but failed to update in channel: {str(e)}')

    except Exception as e:
        await update.message.reply_text(f'Update failed: {str(e)}')


async def delete(update: Update, context: CallbackContext) -> None:
    if not update.effective_user or not update.message:
        return
        
    if str(update.effective_user.id) not in sudo_users:
        await update.message.reply_text('Ask my Owner to use this Command...')
        return

    try:
        args = context.args
        if not args or len(args) != 1:
            await update.message.reply_text('Incorrect format... Please use: /delete ID')
            return

        
        character = await collection.find_one_and_delete({'id': args[0]})

        if character:
            # Also remove from all user collections
            from shivu import user_collection
            user_result = await user_collection.update_many(
                {'characters.id': args[0]},
                {'$pull': {'characters': {'id': args[0]}}}
            )
            
            await context.bot.delete_message(chat_id=CHARA_CHANNEL_ID, message_id=character['message_id'])
            await update.message.reply_text(f'✅ Character deleted from database and removed from {user_result.modified_count} user collections.')
        else:
            await update.message.reply_text('Deleted Successfully from db, but character not found In Channel')
    except Exception as e:
        await update.message.reply_text(f'{str(e)}')

async def summon(update: Update, context: CallbackContext) -> None:
    """Summon a random character for testing (sudo users only)"""
    if not update.effective_user or not update.message:
        return
        
    if str(update.effective_user.id) not in sudo_users:
        await update.message.reply_text('Ask My Owner...')
        return
        
    try:
        from shivu import event_settings_collection
        
        # Check for active event
        active_event = await event_settings_collection.find_one({'active': True})
        
        # Build filter criteria based on event
        filter_criteria = {}
        if active_event and active_event.get('event_type') == 'christmas':
            filter_criteria['name'] = {'$regex': '🎄'}
        
        # Get total character count
        total_characters = await collection.count_documents(filter_criteria)
        
        if total_characters == 0:
            await update.message.reply_text('📭 No characters in database to summon!\n\nUpload some characters first using /upload')
            return
        
        # Get characters grouped by rarity for weighted selection
        # Higher weight = more likely to spawn
        rarities_weights = {
            "Common": 100,
            "Rare": 50,
            "Legendary": 2,
            "Flat": 5,
            "Ninja": 1,
            "Knight": 0.5,
            "Catapult": 0,
            "Custom": 0
        }
        
        # Get available rarities from database (excluding Custom which never spawn, respecting event filter)
        event_filter = {'rarity': {'$ne': 'Custom'}}
        if active_event and active_event.get('event_type') == 'christmas':
            event_filter['name'] = {'$regex': '🎄'}
        available_rarities = await collection.distinct('rarity', event_filter)
        
        if not available_rarities:
            await update.message.reply_text('❌ No spawnable characters available!\n\nAll characters in the database appear to be Limited Edition or non-spawnable. Please upload some common characters using /upload.')
            return
        
        # Filter weights to only include available rarities
        available_weights = {rarity: rarities_weights.get(rarity, 0) for rarity in available_rarities if rarities_weights.get(rarity, 0) > 0}
        
        if not available_weights:
            await update.message.reply_text('❌ No spawnable characters available!\n\nAll available character rarities have 0 spawn weight. Please upload some common characters using /upload.')
            return
        
        # Use weighted random selection for rarity
        import random
        selected_rarity = random.choices(
            population=list(available_weights.keys()),
            weights=list(available_weights.values()),
            k=1
        )[0]
        
        # Get a random character from the selected rarity (respecting event filter)
        match_criteria = {'rarity': selected_rarity}
        if active_event and active_event.get('event_type') == 'christmas':
            match_criteria['name'] = {'$regex': '🎄'}
        
        random_character = await collection.aggregate([
            {'$match': match_criteria},
            {'$sample': {'size': 1}}
        ]).to_list(length=1)
        
        if not random_character:
            await update.message.reply_text('❌ No spawnable characters available!')
            return
            
        character = random_character[0]
        chat_id = update.effective_chat.id
        
        # Store character for marry command to find it
        from shivu.__main__ import last_characters, first_correct_guesses, manually_summoned
        last_characters[chat_id] = character
        
        # Mark as manually summoned to allow multiple marriages
        manually_summoned[chat_id] = True
        
        # Clear any existing guesses for this chat
        if chat_id in first_correct_guesses:
            del first_correct_guesses[chat_id]
        
        # Get rarity emoji
        rarity_emoji = rarity_styles.get(character.get('rarity', ''), "")
        
        # Create beautiful summon display with hidden character details
        caption = f"{rarity_emoji} A beauty has been summoned! Use /invite to add them to your harem!"
        
        # Process the image URL for compatibility and handle errors gracefully
        try:
            from shivu import process_image_url
            processed_url = await process_image_url(character['img_url'])
            
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=processed_url,
                caption=caption,
                parse_mode='HTML'
            )
        except Exception as img_error:
            # If image fails to load, send text message instead
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"{caption}\n\n⚠️ Image could not be loaded - {character['name']} from {character['anime']}",
                parse_mode='HTML'
            )
        
    except Exception as e:
        await update.message.reply_text(f'❌ Error summoning character: {str(e)}')


async def remove_character_from_user(update: Update, context: CallbackContext) -> None:
    """Remove a specific character from a user's harem - Admin only"""
    if not update.effective_user or not update.message:
        return
        
    if str(update.effective_user.id) not in sudo_users:
        await update.message.reply_text('Ask My Owner to use this Command...')
        return

    try:
        args = context.args
        if not args or len(args) != 2:
            await update.message.reply_text('❌ Incorrect format!\n\nUsage: /remove <character_id> <user_id>\nExample: /remove 123 987654321')
            return

        character_id = args[0]
        user_id_str = args[1]
        
        try:
            user_id = int(user_id_str)
        except ValueError:
            await update.message.reply_text('❌ Invalid user ID format!')
            return

        # Find the character first to show details
        character = await collection.find_one({'id': character_id})
        if not character:
            await update.message.reply_text(f'❌ Character with ID #{character_id} not found in database!')
            return

        # Find the user
        from shivu import user_collection
        user = await user_collection.find_one({'id': user_id})
        if not user:
            await update.message.reply_text(f'❌ User with ID {user_id} not found!')
            return

        # Check if user has this character
        user_character_count = sum(1 for c in user.get('characters', []) if c.get('id') == character_id)
        if user_character_count == 0:
            await update.message.reply_text(f'❌ User does not have character #{character_id} ({character["name"]}) in their harem!')
            return

        # Remove one instance of the character
        # Remove only one instance of the character (two-step process)
        # First, unset the first matching character to null
        await user_collection.update_one(
            {'id': user_id, 'characters.id': character_id},
            {'$unset': {'characters.$': 1}}
        )
        # Then pull the null values
        result = await user_collection.update_one(
            {'id': user_id},
            {'$pull': {'characters': None}}
        )

        if result.modified_count > 0:
            remaining_count = user_character_count - 1
            user_name = user.get('first_name', 'User')
            await update.message.reply_text(
                f'✅ <b>Character Removed!</b>\n\n'
                f'🗑️ Removed: {character["name"]} (#{character_id})\n'
                f'👤 From: <a href="tg://user?id={user_id}">{user_name}</a>\n'
                f'📊 Remaining: {remaining_count} copies',
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text('❌ Failed to remove character from user harem!')
            
    except Exception as e:
        await update.message.reply_text(f'❌ Error removing character: {str(e)}')


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

async def find(update: Update, context: CallbackContext) -> None:
    """Find a character by ID number"""
    if not update.effective_chat or not update.message:
        return
        
    try:
        args = context.args
        if not args:
            await update.message.reply_text('🔍 <b>Find Character</b>\n\nUsage: /find <id>\nExample: /find 1', parse_mode='HTML')
            return
        
        character_id = args[0]
        
        # Search for character by ID
        character = await collection.find_one({'id': character_id})
        
        if not character:
            await update.message.reply_text(f'❌ No character found with ID #{character_id}')
            return
        
        # Get rarity emoji
        rarity_emoji = rarity_styles.get(character.get('rarity', ''), "✨")
        
        # Find global catchers - users who have this character
        global_catchers = []
        total_caught = 0
        
        users_with_character = user_collection.find({"characters.id": character_id})
        async for user in users_with_character:
            user_id = user['id']
            character_count = sum(1 for c in user.get('characters', []) if c.get('id') == character_id)
            if character_count > 0:
                user_name = user.get('first_name', f'User{user_id}')
                global_catchers.append({
                    'user_id': user_id,
                    'name': user_name,
                    'count': character_count
                })
                total_caught += character_count
        
        # Sort by count and get top 10
        global_catchers.sort(key=lambda x: x['count'], reverse=True)
        top_10 = global_catchers[:10]
        
        # Detect event
        event_name = get_event_name(character.get('name', ''))
        event_line = f"\n🌟 Event: {event_name}" if event_name else ""

        # Create new format caption
        caption = f"OwO! Check out this Character!\n\n"
        caption += f"{character['anime']}\n"
        caption += f"{character['id']} {character['name']}\n"
        caption += f"(𝙍𝘼𝙍𝙄𝙏𝙔: {rarity_emoji} {character.get('rarity', 'Unknown')}){event_line}\n\n"
        caption += f"⦿ ɢʟᴏʙᴀʟʟʏ ᴄᴀᴜɢʜᴛ : {total_caught} ᴛɪᴍᴇs\n\n"
        caption += "🏆 ᴛᴏᴘ 10 ɢʟᴏʙᴀʟ ᴄᴀᴛᴄʜᴇʀs\n"
        
        for i in range(10):
            if i < len(top_10):
                catcher = top_10[i]
                caption += f"{i+1}. {catcher['name']} → {catcher['count']}\n"
            elif i == 4:  # Add the special invisible line at position 5
                caption += "5. ⁭⁯⁯⁭⁯⁭⁯⁯⁭⁯⁭⁯⁯⁭⁯⁭⁯⁯⁭⁯⁭⁯⁯⁭⁯⁭⁯⁯⁭⁯⁭⁯⁯⁭⁯⁭⁯⁯⁭⁯⁭⁯⁯⁭⁯⁭⁯⁯⁭⁯⁭⁯⁯⁭⁯⁭⁯⁯⁭⁯⁭⁯⁯⁭\n"
            else:
                caption += f"{i+1}. \n"
        
        # Process the image URL for compatibility
        from shivu import process_image_url, LOGGER
        from shivu.modules.harem import get_character_display_url
        user_id = update.effective_user.id if update.effective_user else None
        display_url = await get_character_display_url(character, character_id, user_id)
        
        # Handle custom characters without URLs
        if not display_url or display_url == '':
            caption += "\n⚠️ No image available yet."
            if character.get('rarity') == 'Custom':
                caption += "\nPlease upload slots using /customupload"
            await update.message.reply_text(caption, parse_mode='HTML')
            return
        
        processed_url = await process_image_url(display_url)
        
        # Check if it's a video and use appropriate send method
        if await is_video_character(character, character_id, user_id):
            try:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=processed_url,
                    caption=caption,
                    parse_mode='HTML'
                )
            except Exception as video_error:
                # Fallback: try sending as photo if video fails
                LOGGER.warning(f"/find: Video send failed for character {character_id}, URL: {processed_url[:100]}, Error: {str(video_error)}. Trying as photo.")
                try:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=processed_url,
                        caption=f"🎬 [Video] {caption}",
                        parse_mode='HTML'
                    )
                except Exception as photo_error:
                    # Last resort: send text with link
                    LOGGER.error(f"/find: Both video and photo failed for character {character_id}, URL: {processed_url[:100]}")
                    await update.message.reply_text(
                        f"{caption}\n\n⚠️ Media display failed. View directly: {processed_url}",
                        parse_mode='HTML'
                    )
        else:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=processed_url,
                caption=caption,
                parse_mode='HTML'
            )
        
    except Exception as e:
        await update.message.reply_text(f'❌ Error finding character: {str(e)}')


async def update(update: Update, context: CallbackContext) -> None:
    if not update.effective_user or not update.message:
        return
        
    if str(update.effective_user.id) not in sudo_users:
        await update.message.reply_text('You do not have permission to use this command.')
        return

    try:
        args = context.args
        if not args or len(args) != 3:
            await update.message.reply_text('Incorrect format. Please use: /update id field new_value')
            return

        # Get character by ID
        character = await collection.find_one({'id': args[0]})
        if not character:
            await update.message.reply_text('Character not found.')
            return

        # Check if field is valid
        valid_fields = ['img_url', 'name', 'anime', 'rarity']
        if args[1] not in valid_fields:
            await update.message.reply_text(f'Invalid field. Please use one of the following: {", ".join(valid_fields)}')
            return

        # Update field
        if args[1] in ['name', 'anime']:
            new_value = args[2].replace('-', ' ').title()
        elif args[1] == 'rarity':
            rarity_map = {
                1: "Common", 
                2: "Uncommon", 
                3: "Rare", 
                4: "Epic", 
                5: "Legendary", 
                6: "Mythic", 
                7: "Retro", 
                8: "Star", 
                9: "Zenith", 
                10: "Limited Edition"
            }
            try:
                new_value = rarity_map[int(args[2])]
            except KeyError:
                await update.message.reply_text('Invalid rarity. Please use 1-10:\n1=Common, 2=Uncommon, 3=Rare, 4=Epic, 5=Legendary, 6=Mythic, 7=Retro, 8=Star, 9=Zenith, 10=Limited Edition')
                return
        else:
            new_value = args[2]

        await collection.find_one_and_update({'id': args[0]}, {'$set': {args[1]: new_value}})

        # Update user collections when character properties change (including img_url)
        from shivu import user_collection
        user_update_result = await user_collection.update_many(
            {'characters.id': args[0]},
            {'$set': {f'characters.$[elem].{args[1]}': new_value}},
            array_filters=[{'elem.id': args[0]}]
        )
        users_updated = user_update_result.modified_count

        if args[1] == 'img_url':
            await context.bot.delete_message(chat_id=CHARA_CHANNEL_ID, message_id=character['message_id'])
            rarity_emoji = rarity_styles.get(character["rarity"], "")
            message = await context.bot.send_photo(
                chat_id=CHARA_CHANNEL_ID,
                photo=new_value,
                caption=(
                    f"✨ <b>{character['name']}</b> ✨\n"
                    f"🎌 <i>{character['anime']}</i>\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"{rarity_emoji} <b>{character['rarity']}</b>\n"
                    f"🆔 <b>ID:</b> #{character['id']}\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"📝 Updated by <a href='tg://user?id={update.effective_user.id}'>{update.effective_user.first_name}</a>"
                ),
                parse_mode='HTML'
            )
            character['message_id'] = message.message_id
            await collection.find_one_and_update({'id': args[0]}, {'$set': {'message_id': message.message_id}})
        else:
            # Update character dict with new value for accurate caption
            character[args[1]] = new_value
            
            rarity_emoji = rarity_styles.get(character["rarity"], "")
            
            # Create updated beautiful caption with fresh values
            updated_caption = (
                f"✨ <b>{character['name']}</b> ✨\n"
                f"🎌 <i>{character['anime']}</i>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"{rarity_emoji} <b>{character['rarity']}</b>\n"
                f"🆔 <b>ID:</b> #{character['id']}\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📝 Updated by <a href='tg://user?id={update.effective_user.id}'>{update.effective_user.first_name}</a>"
            )
            
            await context.bot.edit_message_caption(
                chat_id=CHARA_CHANNEL_ID,
                message_id=character['message_id'],
                caption=updated_caption,
                parse_mode='HTML'
            )

        await update.message.reply_text(f'✅ Updated Done in Database!\n\n📊 {users_updated} user collection(s) synced.\n\nNote: Channel caption may take a moment to update.')
    except Exception as e:
        await update.message.reply_text(f'I guess did not added bot in channel.. or character uploaded Long time ago.. Or character not exits.. orr Wrong id')


async def migrate_rarities(update: Update, context: CallbackContext) -> None:
    """Migrate old rarity names to new ones in the database - Admin only"""
    if not update.effective_user or not update.message:
        return
        
    if str(update.effective_user.id) not in sudo_users:
        await update.message.reply_text('You do not have permission to use this command.')
        return

    try:
        await update.message.reply_text('🔄 Starting rarity migration...\n\nUpdating database to change:\n• Celestial → Retro\n• Arcane → Zenith')
        
        # Update main character collection
        result_celestial = await collection.update_many(
            {'rarity': 'Celestial'},
            {'$set': {'rarity': 'Retro'}}
        )
        
        result_arcane = await collection.update_many(
            {'rarity': 'Arcane'}, 
            {'$set': {'rarity': 'Zenith'}}
        )
        
        # Update user collections
        from shivu import user_collection
        
        user_result_celestial = await user_collection.update_many(
            {'characters.rarity': 'Celestial'},
            {'$set': {'characters.$[elem].rarity': 'Retro'}},
            array_filters=[{'elem.rarity': 'Celestial'}]
        )
        
        user_result_arcane = await user_collection.update_many(
            {'characters.rarity': 'Arcane'},
            {'$set': {'characters.$[elem].rarity': 'Zenith'}},
            array_filters=[{'elem.rarity': 'Arcane'}]
        )
        
        # Verify changes
        celestial_count = await collection.count_documents({'rarity': 'Celestial'})
        arcane_count = await collection.count_documents({'rarity': 'Arcane'})
        retro_count = await collection.count_documents({'rarity': 'Retro'})
        zenith_count = await collection.count_documents({'rarity': 'Zenith'})
        
        success_message = (
            f'✅ <b>Migration Completed!</b>\n\n'
            f'📊 <b>Characters updated:</b>\n'
            f'• Celestial → Retro: {result_celestial.modified_count}\n'
            f'• Arcane → Zenith: {result_arcane.modified_count}\n\n'
            f'👥 <b>User collections updated:</b>\n'
            f'• Celestial → Retro: {user_result_celestial.modified_count} users\n'
            f'• Arcane → Zenith: {user_result_arcane.modified_count} users\n\n'
            f'🔍 <b>Current counts:</b>\n'
            f'• Retro: {retro_count}\n'
            f'• Zenith: {zenith_count}\n'
            f'• Old Celestial remaining: {celestial_count}\n'
            f'• Old Arcane remaining: {arcane_count}'
        )
        
        await update.message.reply_text(success_message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f'❌ Error during migration: {str(e)}')


async def adduploader(update: Update, context: CallbackContext) -> None:
    """Add a user to the uploading users list (owners only)"""
    if not update.effective_user or not update.message:
        return
    
    # Check if user is an owner
    OWNERS = ["8376223999", "6702213812"]
    if str(update.effective_user.id) not in OWNERS:
        await update.message.reply_text('🚫 Only owners can use this command.')
        return
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            '📝 **Add Uploader Usage:**\n\n'
            '`/adduploader [user_id]`\n\n'
            '**Example:** `/adduploader 123456789`\n\n'
            'This will give the user upload permissions.',
            parse_mode='Markdown'
        )
        return
    
    try:
        user_id_to_add = context.args[0]
        
        # Validate user_id is numeric
        if not user_id_to_add.isdigit():
            await update.message.reply_text('❌ Invalid user ID! Please provide a numeric user ID.')
            return
        
        # Check if already an uploader
        dynamic_uploaders_collection = db['dynamic_uploading_users']
        existing = await dynamic_uploaders_collection.find_one({'user_id': user_id_to_add})
        
        if existing:
            await update.message.reply_text(f'⚠️ User `{user_id_to_add}` is already an uploader!')
            return
        
        # Check if already sudo user
        if user_id_to_add in sudo_users:
            await update.message.reply_text(f'⚠️ User `{user_id_to_add}` is already a sudo user (has all permissions)!')
            return
        
        # Add to uploaders collection
        await dynamic_uploaders_collection.insert_one({
            'user_id': user_id_to_add,
            'level': 1,
            'added_by': update.effective_user.id,
            'added_by_username': update.effective_user.username or update.effective_user.first_name,
            'added_at': update.message.date
        })
        
        await update.message.reply_text(
            f'✅ **Uploader Added!**\n\n'
            f'👤 **User ID:** `{user_id_to_add}`\n'
            f'🔑 **Permissions:** Upload characters only\n'
            f'👨‍💼 **Added by:** {update.effective_user.first_name}\n\n'
            f'The user can now use the `/upload` command.',
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text(f'❌ Error adding uploader: {str(e)}')


async def removeuploader(update: Update, context: CallbackContext) -> None:
    """Remove a user from the uploading users list (owners only)"""
    if not update.effective_user or not update.message:
        return
    
    # Check if user is an owner
    OWNERS = ["8376223999", "6702213812"]
    if str(update.effective_user.id) not in OWNERS:
        await update.message.reply_text('🚫 Only owners can use this command.')
        return
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            '📝 **Remove Uploader Usage:**\n\n'
            '`/removeuploader [user_id]`\n\n'
            '**Example:** `/removeuploader 123456789`\n\n'
            'This will remove the user\'s upload permissions.',
            parse_mode='Markdown'
        )
        return
    
    try:
        user_id_to_remove = context.args[0]
        
        # Validate user_id is numeric
        if not user_id_to_remove.isdigit():
            await update.message.reply_text('❌ Invalid user ID! Please provide a numeric user ID.')
            return
        
        # Check if user is in uploaders collection
        dynamic_uploaders_collection = db['dynamic_uploading_users']
        uploader = await dynamic_uploaders_collection.find_one({'user_id': user_id_to_remove})
        
        if not uploader:
            await update.message.reply_text(f'❌ User `{user_id_to_remove}` is not currently an uploader!')
            return
        
        # Remove from uploaders collection
        await dynamic_uploaders_collection.delete_one({'user_id': user_id_to_remove})
        
        await update.message.reply_text(
            f'✅ **Uploader Removed!**\n\n'
            f'👤 **User ID:** `{user_id_to_remove}`\n'
            f'❌ **Permissions:** Upload access revoked\n'
            f'👨‍💼 **Removed by:** {update.effective_user.first_name}\n\n'
            f'The user can no longer use the `/upload` command.',
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text(f'❌ Error removing uploader: {str(e)}')


async def customupload(update: Update, context: CallbackContext) -> None:
    """Upload custom character URLs for level 3 artists only - /customupload img_url id slot-number owner_id"""
    if not update.effective_user or not update.message:
        return
    
    level = await get_uploader_level(update.effective_user.id)
    if level != 3:
        await update.message.reply_text('❌ Only level 3 artists (🎐) can use /customupload command.')
        return
    
    try:
        args = context.args
        if not args or len(args) != 4:
            await update.message.reply_text(
                '❌ Wrong format!\n\n'
                'Usage: /customupload img_url id slot-number owner_id\n\n'
                'Example: /customupload https://example.com/image.jpg 1617 1 123456789\n\n'
                '📌 Slots:\n'
                '• Slot 1: Image URL (Mystical)\n'
                '• Slot 2: Video URL (Edit)\n'
                '• Slot 3: Image URL (Custom Nude)\n\n'
                '✅ Supported: Direct image/video URLs (MP4), Discord CDN links, etc.\n\n'
                '👤 owner_id: The Telegram user ID of the character owner'
            )
            return
        
        url = args[0]
        char_id = args[1]
        slot_num = args[2]
        owner_id = args[3]
        
        # Validate slot number
        try:
            slot = int(slot_num)
            if slot not in [1, 2, 3]:
                await update.message.reply_text('❌ Slot must be 1, 2, or 3.')
                return
        except ValueError:
            await update.message.reply_text('❌ Slot must be a number (1, 2, or 3).')
            return
        
        # Validate URL
        is_valid, validation_message = validate_url(url)
        if not is_valid:
            await update.message.reply_text(f'❌ Invalid URL: {validation_message}')
            return
        
        # Determine URL type (image or video)
        is_video = 'video' in validation_message.lower() or any(ext in url.lower() for ext in ['.mp4', '.mov', '.avi', '.mkv'])
        
        # Check if slot 2 must be video, slots 1 and 3 must be images
        if slot == 2 and not is_video:
            await update.message.reply_text('❌ Slot 2 must be a video URL (MP4, MOV, AVI, MKV).')
            return
        if slot in [1, 3] and is_video:
            await update.message.reply_text('❌ Slots 1 and 3 must be image URLs, not videos.')
            return
        
        # Find custom character by ID
        custom_char = await collection.find_one({'id': char_id, 'rarity': 'Custom'})
        
        if not custom_char:
            await update.message.reply_text(f'❌ Custom character with ID {char_id} not found.')
            return
        
        # Initialize owner_slots if not present
        if 'owner_slots' not in custom_char:
            custom_char['owner_slots'] = {}
        
        # Initialize this owner's slots if not present
        owner_id_str = str(owner_id)
        if owner_id_str not in custom_char['owner_slots']:
            custom_char['owner_slots'][owner_id_str] = {'1': None, '2': None, '3': None}
        
        # Update the specific slot for this owner
        custom_char['owner_slots'][owner_id_str][str(slot)] = {'url': url, 'type': 'video' if is_video else 'image'}
        
        # Update database
        await collection.update_one(
            {'_id': custom_char['_id']},
            {'$set': {'owner_slots': custom_char['owner_slots']}}
        )
        
        slot_type = '🎬 Video' if is_video else '🖼️ Image'
        slot_label = ['Mystical', 'Edit', 'Custom Nude'][slot - 1]
        await update.message.reply_text(
            f'✅ **Custom Slot Updated!**\n\n'
            f'👾 Character: {custom_char["name"]}\n'
            f'🎌 Anime: {custom_char["anime"]}\n'
            f'📍 Slot {slot} ({slot_label}): {slot_type}\n'
            f'👤 Owner ID: {owner_id}\n'
            f'🔗 URL added successfully!'
        )
        
    except Exception as e:
        await update.message.reply_text(f'❌ Error uploading custom slot: {str(e)}')


async def customchange(update: Update, context: CallbackContext) -> None:
    """Change active custom character slot - /customchange character_id [slot_number]"""
    if not update.effective_user or not update.message:
        return
    
    user_id = str(update.effective_user.id)
    
    try:
        args = context.args
        if not args or len(args) == 0:
            await update.message.reply_text(
                '❌ Wrong format!\n\n'
                'Usage: /customchange character_id [slot_number]\n\n'
                'Example: /customchange 123 1\n\n'
                'If no slot is specified, shows all available slots.'
            )
            return
        
        char_id = args[0]
        
        # Find the character
        custom_char = await collection.find_one({'id': char_id})
        
        if not custom_char:
            await update.message.reply_text(f'❌ Character with ID {char_id} not found.')
            return
        
        if custom_char.get('rarity') != 'Custom':
            await update.message.reply_text(f'❌ This character is not a Custom character.')
            return
        
        # Initialize owner_slots if not present
        if 'owner_slots' not in custom_char:
            custom_char['owner_slots'] = {}
        
        # Initialize this owner's slots if not present
        if user_id not in custom_char['owner_slots']:
            # Check if old 'slots' format still exists - if so, use it for this owner
            if 'slots' in custom_char:
                custom_char['owner_slots'][user_id] = {
                    '1': custom_char['slots'].get('1'),
                    '2': custom_char['slots'].get('2'),
                    '3': custom_char['slots'].get('3'),
                    '_active': 1
                }
            else:
                custom_char['owner_slots'][user_id] = {'1': None, '2': None, '3': None}
        
        owner_slots = custom_char['owner_slots'][user_id]
        
        # If slot number is provided, change active slot for this owner
        if len(args) > 1:
            try:
                new_slot = int(args[1])
                if new_slot not in [1, 2, 3]:
                    await update.message.reply_text('❌ Slot must be 1, 2, or 3.')
                    return
                
                # Check if slot is populated for this owner
                slot_data = owner_slots.get(str(new_slot))
                if not slot_data or (isinstance(slot_data, dict) and not slot_data.get('url')):
                    slot_names = {1: 'Mystical', 2: 'Edit', 3: 'Custom Nude'}
                    await update.message.reply_text(
                        f'❌ Slot {new_slot} ({slot_names.get(new_slot, "Unknown")}) is empty.\n\n'
                        f'Use /customupload to add a URL to this slot first.'
                    )
                    return
                
                # Update owner's active slot preference
                await collection.update_one(
                    {'_id': custom_char['_id']},
                    {'$set': {f'owner_slots.{user_id}._active': new_slot}}
                )
                
                await update.message.reply_text(f'✅ Your active slot changed to slot {new_slot} for {custom_char["name"]}!')
                
            except ValueError:
                await update.message.reply_text('❌ Slot must be a number (1, 2, or 3).')
                return
        
        # Show all slots for this owner
        char_name = custom_char.get('name', 'Unknown')
        anime = custom_char.get('anime', 'Unknown')
        active = owner_slots.get('_active', 1)
        
        slots_display = f"🎐 𝘠𝘰𝘶𝘳 𝘤𝘶𝘴𝘵𝘰𝘮 𝘈𝘳𝘵𝘴 ({char_name}): \n\n"
        
        # Helper function to check if slot has data
        def has_url(slot_data):
            if not slot_data:
                return False
            if isinstance(slot_data, dict):
                return bool(slot_data.get('url'))
            # Handle string URLs (old format)
            return bool(slot_data) if isinstance(slot_data, str) else False
        
        # Slot 1
        slots_display += "𝘚𝘭𝘰𝘵 1 (Mystical 💎):\n"
        slot1_data = owner_slots.get('1')
        if has_url(slot1_data):
            slot_type = slot1_data.get('type', 'Image').upper() if isinstance(slot1_data, dict) else 'IMAGE'
            slots_display += f"✅ {slot_type}"
            if active == 1:
                slots_display += " (ACTIVE)"
        else:
            slots_display += "❌ empty"
        
        slots_display += "\n\n-------------------\n"
        
        # Slot 2
        slots_display += "𝘚𝘭𝘰𝘵 2 (Edit 🎬):\n"
        slot2_data = owner_slots.get('2')
        if has_url(slot2_data):
            slot_type = slot2_data.get('type', 'Video').upper() if isinstance(slot2_data, dict) else 'VIDEO'
            slots_display += f"✅ {slot_type}"
            if active == 2:
                slots_display += " (ACTIVE)"
        else:
            slots_display += "❌ empty"
        
        slots_display += "\n\n-------------------\n"
        
        # Slot 3
        slots_display += "𝘚𝘭𝘰𝘵 3 (Custom Nude 💎):\n"
        slot3_data = owner_slots.get('3')
        if has_url(slot3_data):
            slot_type = slot3_data.get('type', 'Image').upper() if isinstance(slot3_data, dict) else 'IMAGE'
            slots_display += f"✅ {slot_type}"
            if active == 3:
                slots_display += " (ACTIVE)"
        else:
            slots_display += "❌ empty"
        
        slots_display += f"\n\n💡 Commands:\n"
        slots_display += f"/customupload <url> {char_id} <1/2/3> <your_id>\n"
        slots_display += f"/customchange {char_id} <1/2/3>"
        
        await update.message.reply_text(slots_display)
        
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')


async def debug_card(update: Update, context: CallbackContext) -> None:
    """Debug card owners and slots - /debugcard card_id"""
    if not update.effective_user or not update.message:
        return
    
    try:
        args = context.args
        if not args or len(args) < 1:
            await update.message.reply_text('Usage: /debugcard card_id')
            return
        
        card_id = args[0]
        
        # Find the character
        char = await collection.find_one({'id': card_id})
        if not char:
            char = await collection.find_one({'id': int(card_id)})
        
        if not char:
            await update.message.reply_text(f'❌ Card {card_id} not found.')
            return
        
        msg = f"📊 Card Debug Info:\n\n"
        msg += f"ID: {char.get('id')}\n"
        msg += f"Name: {char.get('name')}\n"
        msg += f"Has 'slots': {'Yes' if 'slots' in char else 'No'}\n"
        msg += f"Has 'owner_slots': {'Yes' if 'owner_slots' in char else 'No'}\n\n"
        
        # Find owners
        char_id_str = str(card_id)
        char_id_int = int(card_id) if isinstance(card_id, str) and card_id.isdigit() else card_id
        
        users_with_char = await user_collection.find({'characters.id': char_id_str}).to_list(None)
        if not users_with_char:
            users_with_char = await user_collection.find({'characters.id': char_id_int}).to_list(None)
        
        msg += f"👥 Found {len(users_with_char)} owner(s):\n"
        for user in users_with_char:
            msg += f"  • User ID: {user.get('id')} ({user.get('first_name', 'Unknown')})\n"
        
        if 'slots' in char:
            msg += f"\n🎰 Old slots data exists:"
            for slot_num in ['1', '2', '3']:
                slot_data = char.get('slots', {}).get(slot_num)
                if slot_data:
                    msg += f"\n  Slot {slot_num}: ✓ Filled"
                else:
                    msg += f"\n  Slot {slot_num}: Empty"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        await update.message.reply_text(f'❌ Debug error: {str(e)}')


async def migrate_slots(update: Update, context: CallbackContext) -> None:
    """Auto-migrate old slots format to owner-specific slots by detecting owners from user harem"""
    if not update.effective_user or not update.message:
        return
    
    # Check if user is admin/sudo
    if update.effective_user.id not in sudo_users:
        await update.message.reply_text('❌ Admin only command.')
        return
    
    try:
        # Find all custom characters with old 'slots' format
        old_format_chars = await collection.find({'rarity': 'Custom', 'slots': {'$exists': True}}).to_list(None)
        
        if not old_format_chars:
            await update.message.reply_text('✅ No custom characters need migration.')
            return
        
        migrated_count = 0
        failed_chars = []
        
        for char in old_format_chars:
            char_id = char.get('id')
            char_id_str = str(char_id)
            char_id_int = int(char_id) if isinstance(char_id, str) and char_id.isdigit() else char_id
            
            old_slots = char.get('slots', {})
            
            # Find owners of this character - try both string and int formats
            owners = []
            users_with_char_str = await user_collection.find({'characters.id': char_id_str}).to_list(None)
            users_with_char_int = await user_collection.find({'characters.id': char_id_int}).to_list(None)
            users_with_char = users_with_char_str if users_with_char_str else users_with_char_int
            
            for user in users_with_char:
                owner_id = str(user.get('id'))
                if owner_id not in owners:
                    owners.append(owner_id)
            
            # If owners found, migrate their slots
            if len(owners) > 0:
                # Create owner_slots from old slots
                owner_slots = {}
                
                # Give each owner the full set of slots
                for owner_id in owners[:2]:  # Limit to 2 owners
                    owner_slots[owner_id] = {
                        '1': old_slots.get('1'),
                        '2': old_slots.get('2'),
                        '3': old_slots.get('3'),
                        '_active': 1
                    }
                
                # Update character to new format
                await collection.update_one(
                    {'_id': char['_id']},
                    {
                        '$set': {'owner_slots': owner_slots},
                        '$unset': {'slots': '', 'active_slot': ''}
                    }
                )
                
                migrated_count += 1
            else:
                failed_chars.append(char_id_str)
        
        msg = f'✅ Migration Complete!\n\n'
        msg += f'Migrated: {migrated_count} custom character(s)\n'
        if failed_chars:
            msg += f'Failed (no owners): {", ".join(failed_chars)}\n'
            msg += f'\n💡 Cards with no owners need to be in user harems first.'
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        await update.message.reply_text(f'❌ Migration error: {str(e)}')


UPLOAD_HANDLER = CommandHandler('upload', upload, block=False)
application.add_handler(UPLOAD_HANDLER)
DELETE_HANDLER = CommandHandler('delete', delete, block=False)
application.add_handler(DELETE_HANDLER)
SUMMON_HANDLER = CommandHandler('summon', summon, block=False)
application.add_handler(SUMMON_HANDLER)
FIND_HANDLER = CommandHandler('find', find, block=False)
application.add_handler(FIND_HANDLER)
UPDATE_HANDLER = CommandHandler('update', update_card, block=False)
application.add_handler(UPDATE_HANDLER)
EDIT_HANDLER = CommandHandler('edit', update_card, block=False)
application.add_handler(EDIT_HANDLER)
REMOVE_HANDLER = CommandHandler('remove', remove_character_from_user, block=False)
application.add_handler(REMOVE_HANDLER)
MIGRATE_HANDLER = CommandHandler('migrate_rarities', migrate_rarities, block=False)
application.add_handler(MIGRATE_HANDLER)
ADDUPLOADER_HANDLER = CommandHandler('adduploader', adduploader, block=False)
application.add_handler(ADDUPLOADER_HANDLER)
REMOVEUPLOADER_HANDLER = CommandHandler('removeuploader', removeuploader, block=False)
application.add_handler(REMOVEUPLOADER_HANDLER)
PROMOTE_HANDLER = CommandHandler('promote', promote, block=False)
application.add_handler(PROMOTE_HANDLER)
CUSTOMUPLOAD_HANDLER = CommandHandler('customupload', customupload, block=False)
application.add_handler(CUSTOMUPLOAD_HANDLER)
CUSTOMCHANGE_HANDLER = CommandHandler('customchange', customchange, block=False)
application.add_handler(CUSTOMCHANGE_HANDLER)
DEBUG_CARD_HANDLER = CommandHandler('debugcard', debug_card, block=False)
application.add_handler(DEBUG_CARD_HANDLER)
MIGRATE_SLOTS_HANDLER = CommandHandler('migrateslots', migrate_slots, block=False)
application.add_handler(MIGRATE_SLOTS_HANDLER)
