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
    "Transcendent": "🪞",
    "Cosmic": "🌌",
    "Oblivion": "🩸",
    "Infinity": "🎞",
    "Star": "⭐",
    "Catapult": "🪄",
    "Knight": "🗡"
}

def get_format_text(level):
    if level == 1:
        return """<b>Invalid Format ❌</b>

<b>Example:</b>
/upload (reply to photo/video)
Robin-❄️
Honkai Star Rail
1

<b>Rarities:</b>
1 = ⚪️ Common
2 = 🟠 Rare
3 = 🟡 Legendary

<b>Your uploader level:</b> 1 🪄"""
    elif level == 2:
        return """<b>Invalid Format ❌</b>

<b>Example:</b>
/upload (reply to photo/video)
Robin-❄️
Honkai Star Rail
4

<b>Rarities:</b>
1 = ⚪️ Common
2 = 🟠 Rare
3 = 🟡 Legendary
4 = 🔮 Flat
5 = 🪞 Transcendent
6 = 🌌 Cosmic

<b>Your uploader level:</b> 2 🎏"""
    else:
        return """<b>Invalid Format ❌</b>

<b>Example:</b>
/upload (reply to photo/video)
Robin-❄️
Honkai Star Rail
4

<b>Rarities:</b>
1 = ⚪️ Common
2 = 🟠 Rare
3 = 🟡 Legendary
4 = 🔮 Flat
5 = 🪞 Transcendent
6 = 🌌 Cosmic
7 = 🩸 Oblivion
8 = 🎞 Infinity

<b>Your uploader level:</b> 3 🎐"""


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
        # Check if the message is a reply to media or has media attached
        target_message = update.message.reply_to_message if update.message.reply_to_message else update.message
        
        # Get image URL from media
        img_url = None
        is_video = False
        
        if target_message.photo:
            file = await target_message.photo[-1].get_file()
            img_url = file.file_path
        elif target_message.video:
            file = await target_message.video.get_file()
            img_url = file.file_path
            is_video = True
        elif target_message.animation:
            file = await target_message.animation.get_file()
            img_url = file.file_path
            is_video = True
            
        # Check for multi-line text format
        text_to_parse = update.message.text or update.message.caption
        if not text_to_parse:
            await update.message.reply_text(get_format_text(level), parse_mode='HTML')
            return

        # Split lines and remove the command part
        lines = [line.strip() for line in text_to_parse.split('\n') if line.strip()]
        
        # Remove /upload command from first line
        if lines and lines[0].lower().startswith('/upload'):
            first_line = lines[0][7:].strip()
            if first_line:
                lines[0] = first_line
            else:
                lines.pop(0)

        if len(lines) < 3:
            # Fallback to old format or show error
            args = context.args
            if not args or len(args) < 4:
                await update.message.reply_text(get_format_text(level), parse_mode='HTML')
                return
            
            # Old format: /upload url name anime rarity
            img_url = args[0]
            character_name = args[1].replace('-', ' ').title()
            anime = args[2].replace('-', ' ').title()
            rarity_input = args[3]
        else:
            # New format:
            # Line 1: Name
            # Line 2: Anime
            # Line 3: Rarity
            character_name = lines[0].replace('-', ' ').title()
            anime = lines[1].replace('-', ' ').title()
            rarity_input = lines[2]
            
        if not img_url:
             # Basic URL validation if not using media reply
             is_valid, validation_message = validate_url(character_name) # Fallback check if first arg was meant to be URL
             if is_valid:
                 img_url = character_name
                 # Re-parse if it was old format
                 args = context.args
                 if args and len(args) >= 4:
                     img_url = args[0]
                     character_name = args[1].replace('-', ' ').title()
                     anime = args[2].replace('-', ' ').title()
                     rarity_input = args[3]
             else:
                 await update.message.reply_text("❌ Please reply to a photo/video or provide a URL in the old format.")
                 return

        # Map rarity name to number if needed
        rarity_name_map = {
            "common": 1, "rare": 2, "legendary": 3, "flat": 4, 
            "transcendent": 5, "cosmic": 6, "oblivion": 7, "infinity": 8
        }
        
        try:
            if rarity_input.lower() in rarity_name_map:
                rarity_num = rarity_name_map[rarity_input.lower()]
            else:
                rarity_num = int(rarity_input)
                
            rarity_map = {
                1: "Common", 
                2: "Rare", 
                3: "Legendary", 
                4: "Flat", 
                5: "Transcendent", 
                6: "Cosmic", 
                7: "Oblivion", 
                8: "Infinity",
                9: "Star",
                10: "Catapult",
                11: "Knight"
            }
            
            # Level restrictions
            if level == 1 and rarity_num > 3:
                await update.message.reply_text('❌ Level 1 uploaders can only upload up to Legendary rank (1-3).')
                return
            if level == 2 and rarity_num > 6:
                await update.message.reply_text('❌ Level 2 uploaders can only upload up to Cosmic rank (1-6).')
                return
            
            rarity = rarity_map[rarity_num]
        except (KeyError, ValueError):
            await update.message.reply_text(get_format_text(level), parse_mode='HTML')
            return

        id = str(await get_next_sequence_number('character_id'))
        character = {
            'img_url': img_url,
            'name': character_name,
            'anime': anime,
            'rarity': rarity,
            'id': id
        }
        
        # Add to character channel and database
        rarity_emoji = rarity_styles.get(rarity, "")
        from shivu import process_image_url
        processed_url = await process_image_url(img_url)
        
        caption = (
            f"✨ <b>{character_name}</b> ✨\n"
            f"🎌 <i>{anime}</i>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{rarity_emoji} <b>{rarity}</b>\n"
            f"🆔 <b>ID:</b> #{id}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📤 Added by <a href='tg://user?id={update.effective_user.id}'>{update.effective_user.first_name}</a>"
        )
        
        try:
            from shivu import process_image_url
            if img_url.startswith('http'):
                processed_url = await process_image_url(img_url)
            else:
                processed_url = img_url
            
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
            await update.message.reply_text('✅ CHARACTER ADDED SUCCESSFULLY!')
        except Exception as e:
            await collection.insert_one(character)
            await update.message.reply_text(f"✅ Character Added to DB but failed to send to channel: {str(e)}")
        
    except Exception as e:
        await update.message.reply_text(f'❌ Character Upload Unsuccessful. Error: {str(e)}')

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
            1: "Common", 
            2: "Rare", 
            3: "Legendary", 
            4: "Flat", 
            5: "Transcendent", 
            6: "Cosmic", 
            7: "Oblivion", 
            8: "Infinity",
            9: "Star",
            10: "Catapult",
            11: "Knight"
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
            from shivu import process_image_url
            if img_url.startswith('http'):
                processed_url = await process_image_url(img_url)
            else:
                processed_url = img_url
            
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
            "Common": 60,
            "Rare": 30,
            "Legendary": 5,
            "Flat": 3,
            "Transcendent": 1.5,
            "Cosmic": 0.4,
            "Oblivion": 0.05,
            "Infinity": 0.01
        }
        
        # Get available rarities from database (respecting event filter)
        event_filter = {}
        if active_event and active_event.get('event_type') == 'christmas':
            event_filter['name'] = {'$regex': '🎄'}
            
        # Check if we are in the main group (Infinity and Oblivion only spawn there)
        # Main GC ID: -1002961536913 (from user's previous preference logs)
        MAIN_GC_ID = -1002961536913
        is_main_gc = update.effective_chat.id == MAIN_GC_ID
        
        available_rarities = await collection.distinct('rarity', event_filter)
        
        if not available_rarities:
            await update.message.reply_text('❌ No spawnable characters available!\n\nAll characters in the database appear to be Limited Edition or non-spawnable. Please upload some common characters using /upload.')
            return
        
        # Filter weights to only include available rarities
        available_weights = {}
        for rarity in available_rarities:
            if rarity in ["Infinity", "Oblivion"] and not is_main_gc:
                continue
                
            weight = rarities_weights.get(rarity, 0)
            if weight > 0:
                available_weights[rarity] = weight
        
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
        caption = f"{rarity_emoji} 𝘢 𝘱𝘳𝘦𝘤𝘪𝘰𝘶𝘴 𝘴𝘰𝘶𝘭 𝘩𝘢𝘴 𝘦𝘯𝘵𝘦𝘳𝘦𝘥 𝘵𝘩𝘦 𝘤𝘩𝘢𝘵, 𝘶𝘴𝘦 /invite 𝘵𝘰 𝘵𝘢𝘬𝘦 𝘵𝘩𝘦𝘮 𝘪𝘯𝘵𝘰 𝘺𝘰𝘶𝘳 𝘤𝘩𝘢𝘮𝘣𝘦𝘳 🗼"
        
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
                text=f"{caption}\n\n⚠️ 𝘐𝘮𝘢𝘨𝘦 𝘤𝘰𝘶𝘭𝘥 𝘯𝘰𝘵 𝘣𝘦 𝘭𝘰𝘢𝘥𝘦𝘥",
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
    "Halloween 🎃": "🎃",
    "Valentine 💝": "💝",
    "Wedding 💍": "💍",
    "School 🏫": "🏫",
    "Cosplay 🎭": "🎭",
    "Winter ❄️": "❄️",
    "Christmas 🎄": "🎄",
    "Summer 🏖": "🏖",
    "Gamer 🎮": "🎮",
    "𝗣𝗢𝗟𝗜𝗖𝗘 🚨": "🚨",
    "Doctor 🧬": "🧬",
    "Maid 🧹": "🧹",
    "Idol 🎤": "🎤",
    "Office Lady 💼": "💼",
    "sports ⚽️": "⚽️",
    "warrior 🛡": "🛡"
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
        event_text = f"\n🎭 <b>Event:</b> {event_name}" if event_name else ""
        
        # Create pretty display text
        caption = (
            f"✨ <b>{character['name']}</b> ✨\n"
            f"🎌 <b>Anime:</b> {character['anime']}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{rarity_emoji} <b>Rarity:</b> {character['rarity']}{event_text}\n"
            f"🆔 <b>ID:</b> #{character['id']}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Total Caught:</b> {total_caught}\n\n"
            f"🏆 <b>Top Catchers:</b>\n"
        )
        
        if not top_10:
            caption += "<i>No one has caught this character yet!</i>"
        else:
            for i, catcher in enumerate(top_10, 1):
                caption += f"{i}. <a href='tg://user?id={catcher['user_id']}'>{catcher['name']}</a> — {catcher['count']}x\n"
        
        # Process URL and send
        from shivu import process_image_url
        processed_url = await process_image_url(character['img_url'])
        
        if await is_video_character(character):
            try:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=processed_url,
                    caption=caption,
                    parse_mode='HTML'
                )
            except Exception as video_error:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=processed_url,
                    caption=f"🎬 {caption}",
                    parse_mode='HTML'
                )
        else:
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=processed_url,
                    caption=caption,
                    parse_mode='HTML'
                )
            except Exception as photo_error:
                # Last resort: send text with link
                await update.message.reply_text(
                    f"{caption}\n🖼 <a href='{processed_url}'>Character Image</a>",
                    parse_mode='HTML'
                )
                
    except Exception as e:
        await update.message.reply_text(f'❌ Error finding character: {str(e)}')


application.add_handler(CommandHandler("upload", upload))
application.add_handler(CommandHandler("update", update_card))
application.add_handler(CommandHandler("delete", delete))
application.add_handler(CommandHandler("promote", promote))
application.add_handler(CommandHandler("remove", remove_character_from_user))
application.add_handler(CommandHandler("find", find))
application.add_handler(CommandHandler("summon", summon))
