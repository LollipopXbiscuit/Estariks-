import importlib
import random
import asyncio
import time
import os
from aiohttp import web

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackContext, MessageHandler, filters
from html import escape

from shivu import collection, top_global_groups_collection, group_user_totals_collection, user_collection, user_totals_collection, locked_spawns_collection, shivuu, banned_users_collection, event_settings_collection
from shivu import application, SUPPORT_CHAT, UPDATE_CHAT, db, LOGGER, OWNER_ID, sudo_users
from datetime import datetime
from shivu.modules import ALL_MODULES


locks = {}
last_characters = {}
sent_characters = {}
first_correct_guesses = {}
message_counts = {}
retro_message_counts = {}  # Track messages for Flat spawns (every 4k messages)
star_message_counts = {}  # Track messages for Catapult spawns (every 200 messages)
zenith_event_message_counts = {}  # Track messages for Knight spawns during Christmas event (every 3015 messages)
manually_summoned = {}  # Track manually summoned characters to allow multiple marriages

# Spam detection system
user_message_times = {}  # Track message timestamps per user {user_id: [timestamp1, timestamp2, ...]}
blocked_users = {}  # Track blocked users {user_id: block_end_time}
SPAM_MESSAGE_LIMIT = 7  # Max messages allowed
SPAM_TIME_WINDOW = 10  # Time window in seconds to check for spam
BLOCK_DURATION = 720  # Block duration in seconds (12 minutes)


for module_name in ALL_MODULES:
    imported_module = importlib.import_module("shivu.modules." + module_name)


def is_user_blocked(user_id: int) -> bool:
    """Check if user is currently blocked"""
    current_time = time.time()
    if user_id in blocked_users:
        if current_time < blocked_users[user_id]:
            return True
        else:
            # Block expired, remove from blocked list
            del blocked_users[user_id]
    return False


def detect_spam(user_id: int) -> bool:
    """Detect if user is sending messages too quickly"""
    current_time = time.time()
    
    # Initialize user message times if not exists
    if user_id not in user_message_times:
        user_message_times[user_id] = []
    
    # Add current message time
    user_message_times[user_id].append(current_time)
    
    # Remove old messages outside the time window
    user_message_times[user_id] = [
        msg_time for msg_time in user_message_times[user_id] 
        if current_time - msg_time <= SPAM_TIME_WINDOW
    ]
    
    # Check if user exceeded message limit
    if len(user_message_times[user_id]) > SPAM_MESSAGE_LIMIT:
        # Block the user
        blocked_users[user_id] = current_time + BLOCK_DURATION
        user_message_times[user_id] = []  # Clear message history
        LOGGER.warning(f"User {user_id} blocked for spam (sent {len(user_message_times[user_id])} messages in {SPAM_TIME_WINDOW}s)")
        return True
    
    return False

def is_video_url(url):
    """Check if a URL points to a video file"""
    if not url:
        return False
    return any(ext in url.lower() for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv'])

def is_video_character(character):
    """Check if a character is a video by URL extension or name marker"""
    if not character:
        return False
    
    url = character.get('img_url', '')
    if is_video_url(url):
        return True
    
    name = character.get('name', '')
    if '🎬' in name:
        return True
    
    return False

async def message_counter(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else None
    
    # Skip processing if user is None (shouldn't happen, but safety check)
    if user_id is None:
        return
    
    # Skip spam detection for owner and sudo users
    is_privileged = str(user_id) == str(OWNER_ID) or str(user_id) in sudo_users
    
    # Check for spam and block user if necessary (skip for privileged users)
    if not is_privileged and detect_spam(user_id):
        await update.message.reply_text(
            "⚠️ **Spam Detected!** ⚠️\n\n"
            "You've been temporarily blocked for sending too many messages quickly.\n"
            "🚫 **Block Duration:** 12 minutes\n\n"
            "During this time, you cannot:\n"
            "• Claim characters (/invite)\n"
            "• Contribute to character spawns\n\n"
            "Please slow down your messaging!",
            parse_mode='Markdown'
        )
        return
    
    # Skip message counting if user is blocked (skip check for privileged users)
    if not is_privileged and is_user_blocked(user_id):
        return

    if chat_id not in locks:
        locks[chat_id] = asyncio.Lock()
    lock = locks[chat_id]

    async with lock:
        
        chat_frequency = await user_totals_collection.find_one({'chat_id': str(chat_id)})
        if chat_frequency:
            message_frequency = chat_frequency.get('message_frequency', 100)
        else:
            message_frequency = 100

        
        if chat_id in message_counts:
            message_counts[chat_id] += 1
        else:
            message_counts[chat_id] = 1

        
        if message_counts[chat_id] % message_frequency == 0:
            await send_image(update, context)
            
            message_counts[chat_id] = 0
        
        # Check for Star spawn (every 200 messages in specific chat only)
        if chat_id == -1002961536913:
            if chat_id in star_message_counts:
                star_message_counts[chat_id] += 1
            else:
                star_message_counts[chat_id] = 1
                
            if star_message_counts[chat_id] % 200 == 0:
                await send_star_character(update, context)
                star_message_counts[chat_id] = 0
        
        # Check for Zenith spawn during Christmas event (every 3015 messages)
        active_event = await event_settings_collection.find_one({'active': True})
        if active_event and active_event.get('event_type') == 'christmas':
            if chat_id in zenith_event_message_counts:
                zenith_event_message_counts[chat_id] += 1
            else:
                zenith_event_message_counts[chat_id] = 1
            
            if zenith_event_message_counts[chat_id] % 3015 == 0:
                await send_zenith_event_character(update, context)
                zenith_event_message_counts[chat_id] = 0
            
async def send_image(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id

    # Get locked character IDs
    locked_character_ids = [doc['character_id'] for doc in await locked_spawns_collection.find().to_list(length=None)]
    
    # Check for active event
    active_event = await event_settings_collection.find_one({'active': True})
    
    # Get spawnable characters (exclude Catapult as it has its own spawn function, and Custom which never spawns)
    filter_criteria = {
        'rarity': {'$nin': ['Catapult', 'Custom']},
        'id': {'$nin': locked_character_ids}
    }
    
    # If Christmas event is active, only spawn characters with 🎄 in name
    if active_event and active_event.get('event_type') == 'christmas':
        filter_criteria['name'] = {'$regex': '🎄'}
    
    all_characters = list(await collection.find(filter_criteria).to_list(length=None))
    
    # Check if there are any spawnable characters
    if not all_characters:
        LOGGER.warning("No spawnable characters available")
        return
    
    # Define rarity weights for weighted random selection
    # Higher weight = more likely to spawn
    # Check if we're in main GC for boosted Retro/Zenith rates
    if chat_id == -1002961536913:
        # Main GC: Significantly higher Flat and Knight rates
        rarity_weights = {
            "Common": 100,
            "Rare": 50,
            "Legendary": 15,
            "Flat": 20,
            "Ninja": 15,
            "Knight": 10,
            "Catapult": 5,
            "Limited Edition": 0.25,
            "Custom": 0
        }
    else:
        # Other chats: Normal rates
        rarity_weights = {
            "Common": 100,
            "Rare": 50,
            "Legendary": 10,
            "Flat": 5,
            "Ninja": 5,
            "Knight": 5,
            "Catapult": 1,
            "Limited Edition": 0.25,
            "Custom": 0
        }
    
    # Group characters by rarity
    characters_by_rarity = {}
    for char in all_characters:
        rarity = char.get('rarity', 'Common')
        if rarity not in characters_by_rarity:
            characters_by_rarity[rarity] = []
        characters_by_rarity[rarity].append(char)
    
    # Filter out rarities with no characters or zero weight
    available_rarities = []
    available_weights = []
    for rarity, chars in characters_by_rarity.items():
        weight = rarity_weights.get(rarity, 0)
        if chars and weight > 0:
            available_rarities.append(rarity)
            available_weights.append(weight)
    
    if not available_rarities:
        LOGGER.warning("No spawnable rarities available with valid weights")
        return
    
    # Use weighted random selection to choose a rarity first
    selected_rarity = random.choices(available_rarities, weights=available_weights, k=1)[0]
    
    # Get characters of the selected rarity
    rarity_characters = characters_by_rarity[selected_rarity]
    
    # Track sent characters to avoid immediate repeats
    if chat_id not in sent_characters:
        sent_characters[chat_id] = []

    # Filter out recently sent characters from this rarity
    available_characters = [c for c in rarity_characters if c['id'] not in sent_characters[chat_id]]
    
    if not available_characters:
        # If all characters of this rarity have been sent, reset and use all
        available_characters = rarity_characters
    
    # Randomly select a character from the chosen rarity
    character = random.choice(available_characters)
    
    # Keep track of sent characters (limit to last 50 to prevent memory issues)
    sent_characters[chat_id].append(character['id'])
    if len(sent_characters[chat_id]) > 50:
        sent_characters[chat_id] = sent_characters[chat_id][-50:]

    last_characters[chat_id] = character

    if chat_id in first_correct_guesses:
        del first_correct_guesses[chat_id]
    
    # Clear manually summoned flag for automatic spawns
    if chat_id in manually_summoned:
        del manually_summoned[chat_id]

    # Rarity emoji mapping
    rarity_emojis = {
        "Common": "⚪️",
        "Rare": "🟠", 
        "Legendary": "🟡",
        "Flat": "🔮",
        "Ninja": "⚡️",
        "Knight": "🗡",
        "Catapult": "🪄",
        "Limited Edition": "🍬"
    }
    
    rarity_emoji = rarity_emojis.get(character['rarity'], "✨")

    try:
        from shivu import process_image_url
        processed_url = await process_image_url(character['img_url'])
        
        caption_text = f"""{rarity_emoji} A beauty has been summoned! Use /invite to add them to your harem!"""
        
        if is_video_character(character):
            try:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=processed_url,
                    caption=caption_text,
                    parse_mode='Markdown')
            except Exception as video_error:
                LOGGER.warning(f"Failed to send as video, trying as photo: {str(video_error)}")
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=processed_url,
                    caption=f"🎬 {caption_text}",
                    parse_mode='Markdown')
        else:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=processed_url,
                caption=caption_text,
                parse_mode='Markdown')
    except Exception as e:
        LOGGER.error(f"Error sending character image: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{rarity_emoji} A beauty has been summoned! Use /marry to add them to your harem!\n\n⚠️ Image could not be loaded",
            parse_mode='Markdown')


async def send_star_character(update: Update, context: CallbackContext) -> None:
    """Send a Catapult character every 200 messages in the main GC"""
    chat_id = update.effective_chat.id
    
    # Check for active event
    active_event = await event_settings_collection.find_one({'active': True})
    
    # Build filter criteria for Catapult characters
    star_filter = {'rarity': 'Catapult'}
    
    # If Christmas event is active, only spawn Catapult characters with 🎄 in name
    if active_event and active_event.get('event_type') == 'christmas':
        star_filter['name'] = {'$regex': '🎄'}
    
    # Get Catapult characters (respecting event filter)
    star_characters = list(await collection.find(star_filter).to_list(length=None))
    
    if not star_characters:
        LOGGER.warning("No Catapult characters available to spawn (event filter may be active)")
        return
    
    # Filter out locked characters
    locked_character_ids = await locked_spawns_collection.distinct('character_id')
    star_characters = [char for char in star_characters if char['id'] not in locked_character_ids]
    
    if not star_characters:
        LOGGER.info("No unlocked Catapult characters available to spawn")
        return
    
    # Track sent Catapult characters separately to avoid repeats
    star_sent_key = f"{chat_id}_star"
    
    if star_sent_key not in sent_characters:
        sent_characters[star_sent_key] = []

    if len(sent_characters[star_sent_key]) == len(star_characters):
        sent_characters[star_sent_key] = []

    available_star = [c for c in star_characters if c['id'] not in sent_characters[star_sent_key]]
    if not available_star:
        available_star = star_characters
        sent_characters[star_sent_key] = []
    
    character = random.choice(available_star)
    sent_characters[star_sent_key].append(character['id'])
    last_characters[chat_id] = character

    if chat_id in first_correct_guesses:
        del first_correct_guesses[chat_id]
    
    # Clear manually summoned flag for automatic spawns
    if chat_id in manually_summoned:
        del manually_summoned[chat_id]

    try:
        from shivu import process_image_url
        processed_url = await process_image_url(character['img_url'])
        
        caption_text = f"🪄 A magical CATAPULT beauty has appeared! Use /marry to add them to your harem!"
        
        if is_video_character(character):
            try:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=processed_url,
                    caption=caption_text,
                    parse_mode='Markdown')
            except Exception as video_error:
                LOGGER.warning(f"Failed to send star video, trying as photo: {str(video_error)}")
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=processed_url,
                    caption=f"🎬 {caption_text}",
                    parse_mode='Markdown')
        else:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=processed_url,
                caption=caption_text,
                parse_mode='Markdown')
    except Exception as e:
        LOGGER.error(f"Error sending star character image: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🪄 A magical CATAPULT beauty has appeared! Use /marry to add them to your harem!\n\n⚠️ Image could not be loaded",
            parse_mode='Markdown')


async def send_zenith_event_character(update: Update, context: CallbackContext) -> None:
    """Send a Knight character with 🎄 every 3015 messages during Christmas event"""
    chat_id = update.effective_chat.id
    
    # Get Knight characters with 🎄 in name for Christmas event
    zenith_filter = {
        'rarity': 'Knight',
        'name': {'$regex': '🎄'}
    }
    
    zenith_characters = list(await collection.find(zenith_filter).to_list(length=None))
    
    if not zenith_characters:
        LOGGER.warning("No Knight Christmas characters available to spawn")
        return
    
    # Filter out locked characters
    locked_character_ids = await locked_spawns_collection.distinct('character_id')
    zenith_characters = [char for char in zenith_characters if char['id'] not in locked_character_ids]
    
    if not zenith_characters:
        LOGGER.info("No unlocked Knight Christmas characters available to spawn")
        return
    
    # Track sent Knight event characters separately to avoid repeats
    zenith_sent_key = f"{chat_id}_zenith_event"
    
    if zenith_sent_key not in sent_characters:
        sent_characters[zenith_sent_key] = []

    if len(sent_characters[zenith_sent_key]) == len(zenith_characters):
        sent_characters[zenith_sent_key] = []

    available_zenith = [c for c in zenith_characters if c['id'] not in sent_characters[zenith_sent_key]]
    if not available_zenith:
        available_zenith = zenith_characters
        sent_characters[zenith_sent_key] = []
    
    character = random.choice(available_zenith)
    sent_characters[zenith_sent_key].append(character['id'])
    last_characters[chat_id] = character

    if chat_id in first_correct_guesses:
        del first_correct_guesses[chat_id]
    
    # Clear manually summoned flag for automatic spawns
    if chat_id in manually_summoned:
        del manually_summoned[chat_id]

    try:
        from shivu import process_image_url
        processed_url = await process_image_url(character['img_url'])
        
        caption_text = f"🗡🎄 A valiant KNIGHT Christmas beauty has appeared! Use /marry to add them to your harem!"
        
        if is_video_character(character):
            try:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=processed_url,
                    caption=caption_text,
                    parse_mode='Markdown')
            except Exception as video_error:
                LOGGER.warning(f"Failed to send zenith video, trying as photo: {str(video_error)}")
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=processed_url,
                    caption=f"🎬 {caption_text}",
                    parse_mode='Markdown')
        else:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=processed_url,
                caption=caption_text,
                parse_mode='Markdown')
    except Exception as e:
        LOGGER.error(f"Error sending zenith event character image: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🗡🎄 A valiant KNIGHT Christmas beauty has appeared! Use /marry to add them to your harem!\n\n⚠️ Image could not be loaded",
            parse_mode='Markdown')


async def guess(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if user is bonked (banned)
    ban = await banned_users_collection.find_one({'user_id': user_id})
    if ban:
        unban_date = ban.get('unban_date')
        if datetime.now() >= unban_date:
            await banned_users_collection.delete_one({'user_id': user_id})
        else:
            remaining = unban_date - datetime.now()
            days = remaining.days
            hours = remaining.seconds // 3600
            time_str = f"{days} days" if days > 0 else f"{hours} hours"
            await update.message.reply_text(
                f"🔨 You've been bonked for spamming too much.. please wait for {time_str}"
            )
            return
    
    # Check if user is blocked from spam
    if is_user_blocked(user_id):
        remaining_time = int(blocked_users[user_id] - time.time())
        minutes = remaining_time // 60
        seconds = remaining_time % 60
        await update.message.reply_text(
            f"🚫 **You are temporarily blocked!**\n\n"
            f"⏰ **Time remaining:** {minutes}m {seconds}s\n\n"
            f"You cannot claim characters while blocked for spam.\n"
            f"Please wait for your block to expire.",
            parse_mode='Markdown'
        )
        return

    # Check daily marriage limit (30 per day)
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    user_data = await user_collection.find_one({'id': user_id})
    if user_data:
        daily_marriages = user_data.get('daily_marriages', {})
        today_count = daily_marriages.get(today, 0)
        
        if today_count >= 30:
            await update.message.reply_text(
                f"💒 **Daily Marriage Limit Reached!**\n\n"
                f"❌ You've already married **{today_count}/30** characters today.\n\n"
                f"⏰ **Reset time:** Tomorrow at 00:00 UTC\n\n"
                f"Come back tomorrow to continue building your harem!",
                parse_mode='Markdown'
            )
            return

    if chat_id not in last_characters:
        await update.message.reply_text('🚫 No character has been summoned yet!\n\nCharacters appear automatically every 100 messages, or admins can use /summon to spawn one manually.')
        return

    # Only prevent multiple guesses for automatically spawned characters
    # Allow multiple marriages for manually summoned characters
    if chat_id in first_correct_guesses and chat_id not in manually_summoned:
        await update.message.reply_text(f'❌️ Already Guessed By Someone.. Try Next Time Bruhh ')
        return

    guess = ' '.join(context.args).lower() if context.args else ''
    
    if "()" in guess or "&" in guess.lower():
        await update.message.reply_text("Nahh You Can't use This Types of words in your guess..❌️")
        return


    name_parts = last_characters[chat_id]['name'].lower().split()

    # Smart matching: exact parts, partial matches, or fuzzy matches
    def smart_name_match(guess, name_parts):
        guess = guess.strip()
        if not guess:
            return False
            
        # 1. Exact full name match (any word order)
        if sorted(name_parts) == sorted(guess.split()):
            return True
            
        # 2. Exact single part match 
        if any(part == guess for part in name_parts):
            return True
            
        # 3. Partial match - guess is start of any name part (min 3 chars)
        if len(guess) >= 3:
            if any(part.startswith(guess) for part in name_parts):
                return True
                
        # 4. Stricter fuzzy match - only allow if guess is contained in part AND is at least half the length
        if len(guess) >= 4:
            for part in name_parts:
                if guess in part and len(guess) >= len(part) * 0.7:
                    return True
                
        return False

    if smart_name_match(guess, name_parts):
        # For manually summoned characters, don't prevent multiple marriages
        if chat_id not in manually_summoned:
            first_correct_guesses[chat_id] = user_id
        
        # Update daily marriage counter
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        user = await user_collection.find_one({'id': user_id})
        if user:
            update_fields = {}
            if hasattr(update.effective_user, 'username') and update.effective_user.username != user.get('username'):
                update_fields['username'] = update.effective_user.username
            if update.effective_user.first_name != user.get('first_name'):
                update_fields['first_name'] = update.effective_user.first_name
            
            # Ensure characters field exists as a list
            if 'characters' not in user or user['characters'] is None:
                update_fields['characters'] = []
                
            # Update daily marriage counter
            daily_marriages = user.get('daily_marriages', {})
            daily_marriages[today] = daily_marriages.get(today, 0) + 1
            update_fields[f'daily_marriages.{today}'] = daily_marriages[today]
                
            if update_fields:
                await user_collection.update_one({'id': user_id}, {'$set': update_fields})
            
            await user_collection.update_one({'id': user_id}, {'$push': {'characters': last_characters[chat_id]}})
      
        elif hasattr(update.effective_user, 'username'):
            # For new users, also initialize daily marriage counter
            daily_marriages = {today: 1}
            await user_collection.insert_one({
                'id': user_id,
                'username': update.effective_user.username,
                'first_name': update.effective_user.first_name,
                'characters': [last_characters[chat_id]],
                'daily_marriages': daily_marriages
            })

        
        group_user_total = await group_user_totals_collection.find_one({'user_id': user_id, 'group_id': chat_id})
        if group_user_total:
            update_fields = {}
            if hasattr(update.effective_user, 'username') and update.effective_user.username != group_user_total.get('username'):
                update_fields['username'] = update.effective_user.username
            if update.effective_user.first_name != group_user_total.get('first_name'):
                update_fields['first_name'] = update.effective_user.first_name
            if update_fields:
                await group_user_totals_collection.update_one({'user_id': user_id, 'group_id': chat_id}, {'$set': update_fields})
            
            await group_user_totals_collection.update_one({'user_id': user_id, 'group_id': chat_id}, {'$inc': {'count': 1}})
      
        else:
            await group_user_totals_collection.insert_one({
                'user_id': user_id,
                'group_id': chat_id,
                'username': update.effective_user.username,
                'first_name': update.effective_user.first_name,
                'count': 1,
            })


    
        group_info = await top_global_groups_collection.find_one({'group_id': chat_id})
        if group_info:
            update_fields = {}
            if update.effective_chat.title != group_info.get('group_name'):
                update_fields['group_name'] = update.effective_chat.title
            if update_fields:
                await top_global_groups_collection.update_one({'group_id': chat_id}, {'$set': update_fields})
            
            await top_global_groups_collection.update_one({'group_id': chat_id}, {'$inc': {'count': 1}})
      
        else:
            await top_global_groups_collection.insert_one({
                'group_id': chat_id,
                'group_name': update.effective_chat.title,
                'count': 1,
            })


        
        keyboard = [[InlineKeyboardButton(f"See Harem", switch_inline_query_current_chat=f"collection.{user_id}")]]


        await update.message.reply_text(f'<b><a href="tg://user?id={user_id}">{escape(update.effective_user.first_name)}</a></b> You Guessed a New Character ✅️ \n\n𝗡𝗔𝗠𝗘: <b>{last_characters[chat_id]["name"]}</b> \n𝗔𝗡𝗜𝗠𝗘: <b>{last_characters[chat_id]["anime"]}</b> \n𝗥𝗔𝗥𝗜𝗧𝗬: <b>{last_characters[chat_id]["rarity"]}</b>\n\nThis Character added in Your harem.. use /harem To see your harem', parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    else:
        await update.message.reply_text('Please Write Correct Character Name... ❌️')
   



async def post_init(application):
    """Set bot commands after application starts"""
    from telegram import BotCommand
    
    commands = [
        BotCommand("start", "Start the bot and get help"),
        BotCommand("harem", "View your character collection"),
        BotCommand("fav", "Set favorite character by ID"),
        BotCommand("find", "Find character by ID number"),  
        BotCommand("sorts", "Set harem sorting preference"),
        BotCommand("invite", "Guess and collect a character"),
        BotCommand("upload", "Upload new character (admin only)"),
        BotCommand("summon", "Test character summon (admin only)"),
        BotCommand("changetime", "Change spawn frequency (admin only)"),
        BotCommand("ping", "Check bot status"),
        BotCommand("topgroups", "View top groups leaderboard"),
    ]
    
    await application.bot.set_my_commands(commands)
    LOGGER.info("Bot commands set successfully")


async def health_check(request):
    """Health check endpoint for Render"""
    return web.Response(text="Bot is running!")

async def webhook_handler(request):
    """Handle incoming webhook updates from Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.update_queue.put(update)
        return web.Response(text="OK")
    except Exception as e:
        LOGGER.error(f"Webhook error: {e}")
        return web.Response(text="ERROR", status=500)

async def run_web_server():
    """Run web server for webhooks and health checks"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    app.router.add_post('/webhook', webhook_handler)
    
    port = int(os.environ.get('PORT', 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    LOGGER.info(f"Web server started on 0.0.0.0:{port}")

async def run_bot():
    """Run the Telegram bot with webhooks or polling"""
    application.add_handler(CommandHandler(["invite"], guess, block=False))
    application.add_handler(MessageHandler(filters.ALL, message_counter, block=False))
    application.post_init = post_init
    
    await application.initialize()
    await application.start()
    
    webhook_url = os.environ.get('WEBHOOK_URL')
    if webhook_url:
        await application.bot.set_webhook(url=f"{webhook_url}/webhook")
        LOGGER.info(f"Webhook set to {webhook_url}/webhook")
        await asyncio.Event().wait()
    else:
        LOGGER.info("Using polling mode (no WEBHOOK_URL set)")
        await application.bot.delete_webhook()
        await application.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()

async def main_async():
    """Run both web server and bot"""
    await shivuu.start()
    LOGGER.info("Pyrogram client started")
    
    await asyncio.gather(
        run_web_server(),
        run_bot()
    )

def main() -> None:
    """Run bot."""
    asyncio.run(main_async())
    
if __name__ == "__main__":
    main()
