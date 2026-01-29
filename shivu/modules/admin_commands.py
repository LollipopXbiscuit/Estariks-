from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup as PyrogramInlineKeyboardMarkup, InlineKeyboardButton as PyrogramInlineKeyboardButton
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
import math
import asyncio

from shivu import collection, locked_spawns_collection, shivuu, application, user_collection, group_user_totals_collection, banned_users_collection, OWNER_ID
from shivu.config import Config
from datetime import datetime, timedelta

@shivuu.on_message(filters.command("lockspawn"))
async def lockspawn(client, message):
    """Lock a character from spawning (sudo users only)"""
    sender_id = message.from_user.id
    
    # Check if user is admin
    if str(sender_id) not in [str(u) for u in Config.sudo_users]:
        await message.reply_text("🚫 This command is only available to administrators.")
        return
    
    if len(message.command) != 2:
        await message.reply_text(
            "📝 **Lock Spawn Usage:**\n\n"
            "`/lockspawn [character_id]`\n\n"
            "**Example:** `/lockspawn 123`\n\n"
            "This will prevent the character from appearing in spawns.",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return
    
    character_id = message.command[1]
    
    # Check if character exists
    character = await collection.find_one({'id': character_id})
    if not character:
        await message.reply_text(f"❌ Character with ID `{character_id}` not found!")
        return
    
    # Check if already locked
    existing_lock = await locked_spawns_collection.find_one({'character_id': character_id})
    if existing_lock:
        await message.reply_text(
            f"⚠️ **Already Locked!**\n\n"
            f"🎴 **Character:** {character['name']}\n"
            f"📺 **Anime:** {character['anime']}\n"
            f"🆔 **ID:** `{character_id}`\n\n"
            f"This character is already locked from spawning."
        )
        return
    
    # Lock the character
    await locked_spawns_collection.insert_one({
        'character_id': character_id,
        'character_name': character['name'],
        'anime': character['anime'],
        'rarity': character['rarity'],
        'locked_by': sender_id,
        'locked_by_username': message.from_user.username or message.from_user.first_name
    })
    
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
    
    await message.reply_text(
        f"🔒 **Spawn Locked!**\n\n"
        f"🎴 **Character:** {character['name']}\n"
        f"📺 **Anime:** {character['anime']}\n"
        f"🌟 **Rarity:** {rarity_emoji} {character['rarity']}\n"
        f"🆔 **ID:** `{character_id}`\n\n"
        f"✅ This character will no longer appear in spawns."
    )

@shivuu.on_message(filters.command("unlockspawn"))
async def unlockspawn(client, message):
    """Unlock a character from spawn restrictions (sudo users only)"""
    sender_id = message.from_user.id
    
    # Check if user is admin
    if str(sender_id) not in [str(u) for u in Config.sudo_users]:
        await message.reply_text("🚫 This command is only available to administrators.")
        return
    
    if len(message.command) != 2:
        await message.reply_text(
            "📝 **Unlock Spawn Usage:**\n\n"
            "`/unlockspawn [character_id]`\n\n"
            "**Example:** `/unlockspawn 123`\n\n"
            "This will allow the character to appear in spawns again.",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return
    
    character_id = message.command[1]
    
    # Check if character is locked
    locked_character = await locked_spawns_collection.find_one({'character_id': character_id})
    if not locked_character:
        await message.reply_text(f"❌ Character with ID `{character_id}` is not currently locked!")
        return
    
    # Unlock the character
    await locked_spawns_collection.delete_one({'character_id': character_id})
    
    await message.reply_text(
        f"🔓 **Spawn Unlocked!**\n\n"
        f"🎴 **Character:** {locked_character['character_name']}\n"
        f"📺 **Anime:** {locked_character['anime']}\n"
        f"🆔 **ID:** `{character_id}`\n\n"
        f"✅ This character can now appear in spawns again."
    )

@shivuu.on_message(filters.command("lockedspawns"))
async def lockedspawns(client, message, page=0):
    """View all currently locked spawn characters with pagination"""
    
    locked_characters = await locked_spawns_collection.find().to_list(length=None)
    
    if not locked_characters:
        await message.reply_text(
            "🔓 **No Locked Spawns**\n\n"
            "There are currently no characters locked from spawning.",
            parse_mode='markdown'
        )
        return
    
    # Items per page
    items_per_page = 20
    total_pages = math.ceil(len(locked_characters) / items_per_page)
    
    # Ensure valid page
    if page < 0 or page >= total_pages:
        page = 0
    
    # Get characters for current page
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_page_chars = locked_characters[start_idx:end_idx]
    
    # Group by rarity
    rarity_groups = {}
    for char in current_page_chars:
        rarity = char.get('rarity', 'Common')
        if rarity not in rarity_groups:
            rarity_groups[rarity] = []
        rarity_groups[rarity].append(char)
    
    rarity_emojis = {
        "Common": "⚪️",
        "Rare": "🟠",
        "Legendary": "🟡",
        "Flat": "🔮",
        "Ninja": "⚡️",
        "Knight": "🗡",
        "Catapult": "🪄"
    }
    
    message_text = f"🔒 **Locked Spawn Characters** - Page {page+1}/{total_pages}\n"
    
    for rarity in ["Catapult", "Knight", "Ninja", "Flat", "Legendary", "Rare", "Common"]:
        if rarity in rarity_groups:
            rarity_emoji = rarity_emojis.get(rarity, "✨")
            message_text += f"\n{rarity_emoji} **{rarity}:**\n"
            
            for char in rarity_groups[rarity]:
                message_text += f"• `{char['character_id']}` - {char['character_name']} ({char['anime']})\n"
    
    message_text += f"\n📊 **Total Locked:** {len(locked_characters)} characters"
    
    # Add pagination buttons if needed
    keyboard = None
    if total_pages > 1:
        buttons = []
        if page > 0:
            buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"lockedspawns:{page-1}"))
        if page < total_pages - 1:
            buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"lockedspawns:{page+1}"))
        
        if buttons:
            keyboard = InlineKeyboardMarkup([buttons])
    
    await message.reply_text(message_text, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=keyboard)

@shivuu.on_callback_query(filters.create(lambda _, __, query: query.data.startswith("lockedspawns:")))
async def lockedspawns_callback(client, callback_query):
    """Handle lockedspawns pagination"""
    try:
        page = int(callback_query.data.split(":")[1])
        
        # Get locked characters
        locked_characters = await locked_spawns_collection.find().to_list(length=None)
        
        if not locked_characters:
            await callback_query.answer("No locked spawns available!", show_alert=True)
            return
        
        # Items per page
        items_per_page = 20
        total_pages = math.ceil(len(locked_characters) / items_per_page)
        
        # Ensure valid page
        if page < 0 or page >= total_pages:
            page = 0
        
        # Get characters for current page
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_page_chars = locked_characters[start_idx:end_idx]
        
        # Group by rarity
        rarity_groups = {}
        for char in current_page_chars:
            rarity = char.get('rarity', 'Common')
            if rarity not in rarity_groups:
                rarity_groups[rarity] = []
            rarity_groups[rarity].append(char)
        
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
        
        message_text = f"🔒 **Locked Spawn Characters** - Page {page+1}/{total_pages}\n"
        
        for rarity in ["Catapult", "Knight", "Ninja", "Flat", "Legendary", "Rare", "Common"]:
            if rarity in rarity_groups:
                rarity_emoji = rarity_emojis.get(rarity, "✨")
                message_text += f"\n{rarity_emoji} **{rarity}:**\n"
                
                for char in rarity_groups[rarity]:
                    message_text += f"• `{char['character_id']}` - {char['character_name']} ({char['anime']})\n"
        
        message_text += f"\n📊 **Total Locked:** {len(locked_characters)} characters"
        
        # Add pagination buttons if needed
        keyboard = None
        if total_pages > 1:
            buttons = []
            if page > 0:
                buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"lockedspawns:{page-1}"))
            if page < total_pages - 1:
                buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"lockedspawns:{page+1}"))
            
            if buttons:
                keyboard = InlineKeyboardMarkup([buttons])
        
        await callback_query.edit_message_text(message_text, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=keyboard)
        await callback_query.answer()
        
    except Exception as e:
        await callback_query.answer(f"Error: {str(e)}", show_alert=True)

@shivuu.on_message(filters.command("rarity"))
async def rarity(client, message):
    """Show all rarities and their spawn rates"""
    
    message_text = (
        "🎏 𝘊𝘩𝘢𝘳𝘢𝘤𝘵𝘦𝘳 𝘙𝘢𝘳𝘪𝘵𝘺 𝘚𝘺𝘴𝘵𝘦𝘮 🎏\n\n"
        "🎐 𝘙𝘦𝘨𝘶𝘭𝘢𝘳 𝘚𝘱𝘢𝘸𝘯𝘴 (𝘦𝘷𝘦𝘳𝘺 100 𝘮𝘦𝘴𝘴𝘢𝘨𝘦𝘴)\n\n"
        "⚪️ 𝘊𝘰𝘮𝘮𝘰𝘯 : 60% 𝘤𝘩𝘢𝘯𝘤𝘦\n"
        "🟠 𝘙𝘢𝘳𝘦 : 30% 𝘤𝘩𝘢𝘯𝘤𝘦\n"
        "🔮 𝘍𝘭𝘢𝘵 : 5% 𝘤𝘩𝘢𝘯𝘤𝘦\n"
        "🟡 𝘓𝘦𝘨𝘦𝘯𝘥𝘢𝘳𝘺 : 3% 𝘤𝘩𝘢𝘯𝘤𝘦\n"
        "⚡️ 𝘕𝘪𝘯𝘫𝘢 : 1% 𝘤𝘩𝘢𝘯𝘤𝘦\n"
        "🗡 𝘒𝘯𝘪𝘨𝘩𝘵 : 1% 𝘤𝘩𝘢𝘯𝘤𝘦\n"
        "🪄 𝘊𝘢𝘵𝘢𝘱𝘶𝘭𝘵 : 0% 𝘤𝘩𝘢𝘯𝘤𝘦 (𝘓𝘰𝘤𝘬𝘦𝘥)"
    )
  
    await message.reply_text(message_text, parse_mode=enums.ParseMode.MARKDOWN)


# python-telegram-bot versions (work with webhooks)
async def lockspawn_ptb(update: Update, context: CallbackContext):
    """Lock a character from spawning (sudo users only) - PTB version"""
    sender_id = update.effective_user.id
    
    if str(sender_id) not in [str(u) for u in Config.sudo_users]:
        await update.message.reply_text("🚫 This command is only available to administrators.")
        return
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "📝 **Lock Spawn Usage:**\n\n"
            "`/lockspawn [character_id]`\n\n"
            "**Example:** `/lockspawn 123`\n\n"
            "This will prevent the character from appearing in spawns.",
            parse_mode='Markdown'
        )
        return
    
    character_id = context.args[0]
    
    character = await collection.find_one({'id': character_id})
    if not character:
        await update.message.reply_text(f"❌ Character with ID `{character_id}` not found!")
        return
    
    existing_lock = await locked_spawns_collection.find_one({'character_id': character_id})
    if existing_lock:
        await update.message.reply_text(
            f"⚠️ **Already Locked!**\n\n"
            f"🎴 **Character:** {character['name']}\n"
            f"📺 **Anime:** {character['anime']}\n"
            f"🆔 **ID:** `{character_id}`\n\n"
            f"This character is already locked from spawning."
        )
        return
    
    await locked_spawns_collection.insert_one({
        'character_id': character_id,
        'character_name': character['name'],
        'anime': character['anime'],
        'rarity': character['rarity'],
        'locked_by': sender_id,
        'locked_by_username': update.effective_user.username or update.effective_user.first_name
    })
    
    rarity_emojis = {
        "Common": "⚪️", "Uncommon": "🟢", "Rare": "🔵", "Epic": "🟣",
        "Legendary": "🟡", "Mythic": "🏵", "Retro": "🍥", "Star": "⭐",
        "Zenith": "🪩", "Limited Edition": "🍬"
    }
    
    rarity_emoji = rarity_emojis.get(character.get('rarity', 'Common'), "✨")
    
    await update.message.reply_text(
        f"🔒 **Spawn Locked!**\n\n"
        f"🎴 **Character:** {character['name']}\n"
        f"📺 **Anime:** {character['anime']}\n"
        f"🌟 **Rarity:** {rarity_emoji} {character['rarity']}\n"
        f"🆔 **ID:** `{character_id}`\n\n"
        f"✅ This character will no longer appear in spawns."
    )


async def unlockspawn_ptb(update: Update, context: CallbackContext):
    """Unlock a character from spawn restrictions - PTB version"""
    sender_id = update.effective_user.id
    
    if str(sender_id) not in [str(u) for u in Config.sudo_users]:
        await update.message.reply_text("🚫 This command is only available to administrators.")
        return
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "📝 **Unlock Spawn Usage:**\n\n"
            "`/unlockspawn [character_id]`\n\n"
            "**Example:** `/unlockspawn 123`\n\n"
            "This will allow the character to appear in spawns again.",
            parse_mode='Markdown'
        )
        return
    
    character_id = context.args[0]
    
    locked_character = await locked_spawns_collection.find_one({'character_id': character_id})
    if not locked_character:
        await update.message.reply_text(f"❌ Character with ID `{character_id}` is not currently locked!")
        return
    
    await locked_spawns_collection.delete_one({'character_id': character_id})
    
    await update.message.reply_text(
        f"🔓 **Spawn Unlocked!**\n\n"
        f"🎴 **Character:** {locked_character['character_name']}\n"
        f"📺 **Anime:** {locked_character['anime']}\n"
        f"🆔 **ID:** `{character_id}`\n\n"
        f"✅ This character can now appear in spawns again."
    )


async def lockedspawns_ptb(update: Update, context: CallbackContext, page=0):
    """View all locked spawn characters with pagination - PTB version"""
    locked_characters = await locked_spawns_collection.find().to_list(length=None)
    
    if not locked_characters:
        await update.message.reply_text(
            "🔓 **No Locked Spawns**\n\n"
            "There are currently no characters locked from spawning.",
            parse_mode='Markdown'
        )
        return
    
    items_per_page = 20
    total_pages = math.ceil(len(locked_characters) / items_per_page)
    
    if page < 0 or page >= total_pages:
        page = 0
    
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_page_chars = locked_characters[start_idx:end_idx]
    
    rarity_groups = {}
    for char in current_page_chars:
        rarity = char.get('rarity', 'Common')
        if rarity not in rarity_groups:
            rarity_groups[rarity] = []
        rarity_groups[rarity].append(char)
    
    rarity_emojis = {
        "Common": "⚪️", "Uncommon": "🟢", "Rare": "🔵", "Epic": "🟣",
        "Legendary": "🟡", "Mythic": "🏵", "Retro": "🍥", "Star": "⭐",
        "Zenith": "🪩", "Limited Edition": "🍬"
    }
    
    message_text = f"🔒 **Locked Spawn Characters** - Page {page+1}/{total_pages}\n"
    
    for rarity in ["Catapult", "Knight", "Ninja", "Flat", "Legendary", "Rare", "Common"]:
        if rarity in rarity_groups:
            rarity_emoji = rarity_emojis.get(rarity, "✨")
            message_text += f"\n{rarity_emoji} **{rarity}:**\n"
            
            for char in rarity_groups[rarity]:
                message_text += f"• `{char['character_id']}` - {char['character_name']} ({char['anime']})\n"
    
    message_text += f"\n📊 **Total Locked:** {len(locked_characters)} characters"
    
    keyboard = None
    if total_pages > 1:
        buttons = []
        if page > 0:
            buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"lockedspawns:{page-1}"))
        if page < total_pages - 1:
            buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"lockedspawns:{page+1}"))
        
        if buttons:
            keyboard = InlineKeyboardMarkup([buttons])
    
    await update.message.reply_text(message_text, parse_mode='Markdown', reply_markup=keyboard)


async def lockedspawns_callback_ptb(update: Update, context: CallbackContext):
    """Handle lockedspawns pagination - PTB version"""
    query = update.callback_query
    
    try:
        page = int(query.data.split(":")[1])
        
        locked_characters = await locked_spawns_collection.find().to_list(length=None)
        
        if not locked_characters:
            await query.answer("No locked spawns available!", show_alert=True)
            return
        
        items_per_page = 20
        total_pages = math.ceil(len(locked_characters) / items_per_page)
        
        if page < 0 or page >= total_pages:
            page = 0
        
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_page_chars = locked_characters[start_idx:end_idx]
        
        rarity_groups = {}
        for char in current_page_chars:
            rarity = char.get('rarity', 'Common')
            if rarity not in rarity_groups:
                rarity_groups[rarity] = []
            rarity_groups[rarity].append(char)
        
        rarity_emojis = {
            "Common": "⚪️", "Uncommon": "🟢", "Rare": "🔵", "Epic": "🟣",
            "Legendary": "🟡", "Mythic": "🏵", "Retro": "🍥", "Star": "⭐",
            "Zenith": "🪩", "Limited Edition": "🍬"
        }
        
        message_text = f"🔒 **Locked Spawn Characters** - Page {page+1}/{total_pages}\n"
        
        for rarity in ["Catapult", "Knight", "Ninja", "Flat", "Legendary", "Rare", "Common"]:
            if rarity in rarity_groups:
                rarity_emoji = rarity_emojis.get(rarity, "✨")
                message_text += f"\n{rarity_emoji} **{rarity}:**\n"
                
                for char in rarity_groups[rarity]:
                    message_text += f"• `{char['character_id']}` - {char['character_name']} ({char['anime']})\n"
        
        message_text += f"\n📊 **Total Locked:** {len(locked_characters)} characters"
        
        keyboard = None
        if total_pages > 1:
            buttons = []
            if page > 0:
                buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"lockedspawns:{page-1}"))
            if page < total_pages - 1:
                buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"lockedspawns:{page+1}"))
            
            if buttons:
                keyboard = InlineKeyboardMarkup([buttons])
        
        await query.edit_message_text(message_text, parse_mode='Markdown', reply_markup=keyboard)
        await query.answer()
        
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)


async def rarity_ptb(update: Update, context: CallbackContext):
    """Show all rarities and their spawn rates - PTB version"""
    
    message_text = (
        "🎏 𝘊𝘩𝘢𝘳𝘢𝘤𝘵𝘦𝘳 𝘙𝘢𝘳𝘪𝘵𝘺 𝘚𝘺𝘴𝘵𝘦𝘮 🎏\n\n"
        "🎐 𝘙𝘦𝘨𝘶𝘭𝘢𝘳 𝘚𝘱𝘢𝘸𝘯𝘴 (𝘦𝘷𝘦𝘳𝘺 100 𝘮𝘦𝘴𝘴𝘢𝘨𝘦𝘴)\n\n"
        "⚪️ 𝘊𝘰𝘮𝘮𝘰𝘯 : 60% 𝘤𝘩𝘢𝘯𝘤𝘦\n"
        "🟠 𝘙𝘢𝘳𝘦 : 30% 𝘤𝘩𝘢𝘯𝘤𝘦\n"
        "🔮 𝘍𝘭𝘢𝘵 : 5% 𝘤𝘩𝘢𝘯𝘤𝘦\n"
        "🟡 𝘓𝘦𝘨𝘦𝘯𝘥𝘢𝘳𝘺 : 3% 𝘤𝘩𝘢𝘯𝘤𝘦\n"
        "⚡️ 𝘕𝘪𝘯𝘫𝘢 : 1% 𝘤𝘩𝘢𝘯𝘤𝘦\n"
        "🗡 𝘒𝘯𝘪𝘨𝘩𝘵 : 1% 𝘤𝘩𝘢𝘯𝘤𝘦\n"
        "🪄 𝘊𝘢𝘵𝘢𝘱𝘶𝘭𝘵 : 0% 𝘤𝘩𝘢𝘯𝘤𝘦 (𝘓𝘰𝘤𝘬𝘦𝘥)"
    )
  
    await update.message.reply_text(message_text, parse_mode='Markdown')


# ============== BROADCAST COMMAND ==============

@shivuu.on_message(filters.command("broadcast"))
async def broadcast(client, message):
    """Broadcast a message to all players and/or groups (owner only)"""
    sender_id = message.from_user.id
    
    if str(sender_id) not in [str(u) for u in Config.sudo_users]:
        await message.reply_text("🚫 This command is only available to administrators.")
        return
    
    if not message.reply_to_message and len(message.command) < 2:
        await message.reply_text(
            "📢 **Broadcast Command**\n\n"
            "**Usage:**\n"
            "`/broadcast [message]` - Send to all users & groups\n"
            "`/broadcast -users [message]` - Send to users only\n"
            "`/broadcast -groups [message]` - Send to groups only\n\n"
            "**Or:** Reply to any message with `/broadcast`\n\n"
            "**Example:**\n"
            "`/broadcast Hello everyone! New update is here!`",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return
    
    args = message.command[1:] if len(message.command) > 1 else []
    
    send_to_users = True
    send_to_groups = True
    
    if args and args[0] == "-users":
        send_to_groups = False
        args = args[1:]
    elif args and args[0] == "-groups":
        send_to_users = False
        args = args[1:]
    
    if message.reply_to_message:
        broadcast_message = message.reply_to_message
        is_reply = True
    else:
        broadcast_text = " ".join(args)
        if not broadcast_text:
            await message.reply_text("❌ Please provide a message to broadcast!")
            return
        is_reply = False
    
    status_msg = await message.reply_text("📡 Starting broadcast...")
    
    success_users = 0
    failed_users = 0
    success_groups = 0
    failed_groups = 0
    
    if send_to_users:
        all_users = await user_collection.find({}).to_list(length=None)
        total_users = len(all_users)
        
        for i, user in enumerate(all_users):
            try:
                user_id = user.get('id')
                if not user_id:
                    continue
                    
                if is_reply:
                    await broadcast_message.copy(chat_id=user_id)
                else:
                    await client.send_message(chat_id=user_id, text=broadcast_text)
                    
                success_users += 1
                
                if (i + 1) % 25 == 0:
                    await status_msg.edit_text(
                        f"📡 **Broadcasting...**\n\n"
                        f"👥 Users: {success_users}/{total_users} sent\n"
                        f"❌ Failed: {failed_users}"
                    )
                    
                await asyncio.sleep(0.05)
                
            except Exception as e:
                failed_users += 1
    
    if send_to_groups:
        all_groups = await group_user_totals_collection.distinct('group_id')
        total_groups = len(all_groups)
        
        for i, group_id in enumerate(all_groups):
            try:
                if not group_id:
                    continue
                    
                chat_id = int(group_id) if isinstance(group_id, str) else group_id
                    
                if is_reply:
                    await broadcast_message.copy(chat_id=chat_id)
                else:
                    await client.send_message(chat_id=chat_id, text=broadcast_text)
                    
                success_groups += 1
                
                if (i + 1) % 10 == 0:
                    await status_msg.edit_text(
                        f"📡 **Broadcasting...**\n\n"
                        f"👥 Users: {success_users} sent, {failed_users} failed\n"
                        f"💬 Groups: {success_groups}/{total_groups} sent\n"
                        f"❌ Failed: {failed_groups}"
                    )
                    
                await asyncio.sleep(0.1)
                
            except Exception as e:
                failed_groups += 1
    
    target_text = ""
    if send_to_users and send_to_groups:
        target_text = "users & groups"
    elif send_to_users:
        target_text = "users only"
    else:
        target_text = "groups only"
    
    await status_msg.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"📢 Target: {target_text}\n\n"
        f"👥 **Users:**\n"
        f"   ✓ Sent: {success_users}\n"
        f"   ✗ Failed: {failed_users}\n\n"
        f"💬 **Groups:**\n"
        f"   ✓ Sent: {success_groups}\n"
        f"   ✗ Failed: {failed_groups}\n\n"
        f"📊 **Total:** {success_users + success_groups} messages sent"
    )


async def broadcast_ptb(update: Update, context: CallbackContext) -> None:
    """PTB wrapper for broadcast command"""
    sender_id = update.effective_user.id
    
    if str(sender_id) not in [str(u) for u in Config.sudo_users]:
        await update.message.reply_text("🚫 This command is only available to administrators.")
        return
    
    args = context.args if context.args else []
    
    if not update.message.reply_to_message and len(args) < 1:
        await update.message.reply_text(
            "📢 **Broadcast Command**\n\n"
            "**Usage:**\n"
            "`/broadcast [message]` - Send to all users & groups\n"
            "`/broadcast -users [message]` - Send to users only\n"
            "`/broadcast -groups [message]` - Send to groups only\n\n"
            "**Or:** Reply to any message with `/broadcast`\n\n"
            "**Example:**\n"
            "`/broadcast Hello everyone! New update is here!`",
            parse_mode='Markdown'
        )
        return
    
    send_to_users = True
    send_to_groups = True
    
    if args and args[0] == "-users":
        send_to_groups = False
        args = args[1:]
    elif args and args[0] == "-groups":
        send_to_users = False
        args = args[1:]
    
    if update.message.reply_to_message:
        is_reply = True
        reply_msg = update.message.reply_to_message
    else:
        broadcast_text = " ".join(args)
        if not broadcast_text:
            await update.message.reply_text("❌ Please provide a message to broadcast!")
            return
        is_reply = False
    
    status_msg = await update.message.reply_text("📡 Starting broadcast...")
    
    success_users = 0
    failed_users = 0
    success_groups = 0
    failed_groups = 0
    
    if send_to_users:
        all_users = await user_collection.find({}).to_list(length=None)
        total_users = len(all_users)
        
        for i, user in enumerate(all_users):
            try:
                user_id = user.get('id')
                if not user_id:
                    continue
                    
                if is_reply:
                    await reply_msg.copy(chat_id=user_id)
                else:
                    await context.bot.send_message(chat_id=user_id, text=broadcast_text)
                    
                success_users += 1
                
                if (i + 1) % 25 == 0:
                    await status_msg.edit_text(
                        f"📡 **Broadcasting...**\n\n"
                        f"👥 Users: {success_users}/{total_users} sent\n"
                        f"❌ Failed: {failed_users}",
                        parse_mode='Markdown'
                    )
                    
                await asyncio.sleep(0.05)
                
            except Exception as e:
                failed_users += 1
    
    if send_to_groups:
        all_groups = await group_user_totals_collection.distinct('group_id')
        total_groups = len(all_groups)
        
        for i, group_id in enumerate(all_groups):
            try:
                if not group_id:
                    continue
                    
                chat_id = int(group_id) if isinstance(group_id, str) else group_id
                    
                if is_reply:
                    await reply_msg.copy(chat_id=chat_id)
                else:
                    await context.bot.send_message(chat_id=chat_id, text=broadcast_text)
                    
                success_groups += 1
                
                if (i + 1) % 10 == 0:
                    await status_msg.edit_text(
                        f"📡 **Broadcasting...**\n\n"
                        f"👥 Users: {success_users} sent, {failed_users} failed\n"
                        f"💬 Groups: {success_groups}/{total_groups} sent\n"
                        f"❌ Failed: {failed_groups}",
                        parse_mode='Markdown'
                    )
                    
                await asyncio.sleep(0.1)
                
            except Exception as e:
                failed_groups += 1
    
    target_text = ""
    if send_to_users and send_to_groups:
        target_text = "users & groups"
    elif send_to_users:
        target_text = "users only"
    else:
        target_text = "groups only"
    
    await status_msg.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"📢 Target: {target_text}\n\n"
        f"👥 **Users:**\n"
        f"   ✓ Sent: {success_users}\n"
        f"   ✗ Failed: {failed_users}\n\n"
        f"💬 **Groups:**\n"
        f"   ✓ Sent: {success_groups}\n"
        f"   ✗ Failed: {failed_groups}\n\n"
        f"📊 **Total:** {success_users + success_groups} messages sent",
        parse_mode='Markdown'
    )


# ============== BONK/UNBONK COMMANDS ==============

@shivuu.on_message(filters.command("bonk"))
async def bonk(client, message):
    """Ban a user from using the bot for 2 weeks (owner only)"""
    sender_id = message.from_user.id
    
    if sender_id != int(OWNER_ID):
        await message.reply_text("🚫 This command is only available to the bot owner.")
        return
    
    target_user = None
    target_id = None
    
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
    elif len(message.command) >= 2:
        try:
            target_id = int(message.command[1])
        except ValueError:
            await message.reply_text("❌ Invalid user ID!")
            return
    else:
        await message.reply_text(
            "🔨 **Bonk Command**\n\n"
            "**Usage:**\n"
            "• Reply to a user's message with `/bonk`\n"
            "• Or use `/bonk [user_id]`\n\n"
            "This will ban the user from using the bot for 2 weeks.",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return
    
    if target_id == int(OWNER_ID):
        await message.reply_text("❌ You can't bonk yourself!")
        return
    
    existing_ban = await banned_users_collection.find_one({'user_id': target_id})
    if existing_ban:
        unban_date = existing_ban.get('unban_date')
        remaining = unban_date - datetime.now()
        days = remaining.days
        await message.reply_text(
            f"⚠️ User is already bonked!\n"
            f"🕐 Remaining: {days} days"
        )
        return
    
    ban_date = datetime.now()
    unban_date = ban_date + timedelta(weeks=2)
    
    await banned_users_collection.insert_one({
        'user_id': target_id,
        'banned_by': sender_id,
        'ban_date': ban_date,
        'unban_date': unban_date,
        'reason': 'Spamming'
    })
    
    target_name = target_user.first_name if target_user else str(target_id)
    
    await message.reply_text(
        f"🔨 **BONK!**\n\n"
        f"👤 **User:** {target_name} (`{target_id}`)\n"
        f"⏰ **Duration:** 2 weeks\n"
        f"📅 **Unbanned on:** {unban_date.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"They won't be able to use the bot until then!",
        parse_mode=enums.ParseMode.MARKDOWN
    )


@shivuu.on_message(filters.command("unbonk"))
async def unbonk(client, message):
    """Unban a user from using the bot (owner only)"""
    sender_id = message.from_user.id
    
    if sender_id != int(OWNER_ID):
        await message.reply_text("🚫 This command is only available to the bot owner.")
        return
    
    target_user = None
    target_id = None
    
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
    elif len(message.command) >= 2:
        try:
            target_id = int(message.command[1])
        except ValueError:
            await message.reply_text("❌ Invalid user ID!")
            return
    else:
        await message.reply_text(
            "✨ **Unbonk Command**\n\n"
            "**Usage:**\n"
            "• Reply to a user's message with `/unbonk`\n"
            "• Or use `/unbonk [user_id]`\n\n"
            "This will remove the ban and allow them to use the bot again.",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return
    
    existing_ban = await banned_users_collection.find_one({'user_id': target_id})
    if not existing_ban:
        await message.reply_text("❌ This user is not bonked!")
        return
    
    await banned_users_collection.delete_one({'user_id': target_id})
    
    target_name = target_user.first_name if target_user else str(target_id)
    
    await message.reply_text(
        f"✨ **UNBONKED!**\n\n"
        f"👤 **User:** {target_name} (`{target_id}`)\n\n"
        f"They can now use the bot again!",
        parse_mode=enums.ParseMode.MARKDOWN
    )


async def bonk_ptb(update: Update, context: CallbackContext) -> None:
    """PTB wrapper for bonk command"""
    sender_id = update.effective_user.id
    
    if sender_id != int(OWNER_ID):
        await update.message.reply_text("🚫 This command is only available to the bot owner.")
        return
    
    target_user = None
    target_id = None
    
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_id = target_user.id
    elif context.args and len(context.args) >= 1:
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
            return
    else:
        await update.message.reply_text(
            "🔨 **Bonk Command**\n\n"
            "**Usage:**\n"
            "• Reply to a user's message with `/bonk`\n"
            "• Or use `/bonk [user_id]`\n\n"
            "This will ban the user from using the bot for 2 weeks.",
            parse_mode='Markdown'
        )
        return
    
    if target_id == int(OWNER_ID):
        await update.message.reply_text("❌ You can't bonk yourself!")
        return
    
    existing_ban = await banned_users_collection.find_one({'user_id': target_id})
    if existing_ban:
        unban_date = existing_ban.get('unban_date')
        remaining = unban_date - datetime.now()
        days = remaining.days
        await update.message.reply_text(
            f"⚠️ User is already bonked!\n"
            f"🕐 Remaining: {days} days"
        )
        return
    
    ban_date = datetime.now()
    unban_date = ban_date + timedelta(weeks=2)
    
    await banned_users_collection.insert_one({
        'user_id': target_id,
        'banned_by': sender_id,
        'ban_date': ban_date,
        'unban_date': unban_date,
        'reason': 'Spamming'
    })
    
    target_name = target_user.first_name if target_user else str(target_id)
    
    await update.message.reply_text(
        f"🔨 **BONK!**\n\n"
        f"👤 **User:** {target_name} (`{target_id}`)\n"
        f"⏰ **Duration:** 2 weeks\n"
        f"📅 **Unbanned on:** {unban_date.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"They won't be able to use the bot until then!",
        parse_mode='Markdown'
    )


async def unbonk_ptb(update: Update, context: CallbackContext) -> None:
    """PTB wrapper for unbonk command"""
    sender_id = update.effective_user.id
    
    if sender_id != int(OWNER_ID):
        await update.message.reply_text("🚫 This command is only available to the bot owner.")
        return
    
    target_user = None
    target_id = None
    
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_id = target_user.id
    elif context.args and len(context.args) >= 1:
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
            return
    else:
        await update.message.reply_text(
            "✨ **Unbonk Command**\n\n"
            "**Usage:**\n"
            "• Reply to a user's message with `/unbonk`\n"
            "• Or use `/unbonk [user_id]`\n\n"
            "This will remove the ban and allow them to use the bot again.",
            parse_mode='Markdown'
        )
        return
    
    existing_ban = await banned_users_collection.find_one({'user_id': target_id})
    if not existing_ban:
        await update.message.reply_text("❌ This user is not bonked!")
        return
    
    await banned_users_collection.delete_one({'user_id': target_id})
    
    target_name = target_user.first_name if target_user else str(target_id)
    
    await update.message.reply_text(
        f"✨ **UNBONKED!**\n\n"
        f"👤 **User:** {target_name} (`{target_id}`)\n\n"
        f"They can now use the bot again!",
        parse_mode='Markdown'
    )


# Helper function to check if user is banned
async def check_ban(user_id: int):
    """Check if a user is banned and return ban info if so"""
    ban = await banned_users_collection.find_one({'user_id': user_id})
    if ban:
        unban_date = ban.get('unban_date')
        if datetime.now() >= unban_date:
            await banned_users_collection.delete_one({'user_id': user_id})
            return None
        remaining = unban_date - datetime.now()
        days = remaining.days
        hours = remaining.seconds // 3600
        return {'banned': True, 'days': days, 'hours': hours}
    return None


# ============== RESETM COMMAND ==============

@shivuu.on_message(filters.command("resetm"))
async def resetm(client, message):
    """Reset a user's daily marriage limit (sudo users only)"""
    sender_id = message.from_user.id
    
    if str(sender_id) not in [str(u) for u in Config.sudo_users]:
        await message.reply_text("🚫 This command is only available to administrators.")
        return
    
    target_user = None
    target_id = None
    
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
    elif len(message.command) >= 2:
        try:
            target_id = int(message.command[1])
        except ValueError:
            await message.reply_text("❌ Invalid user ID!")
            return
    else:
        await message.reply_text(
            "💒 **Reset Marriage Limit Command**\n\n"
            "**Usage:**\n"
            "• Reply to a user's message with `/resetm`\n"
            "• Or use `/resetm [user_id]`\n\n"
            "This will reset their daily marriage limit to 0/30.",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return
    
    user = await user_collection.find_one({'id': target_id})
    if not user:
        await message.reply_text(f"❌ User ID `{target_id}` not found in database!")
        return
    
    await user_collection.update_one(
        {'id': target_id},
        {'$set': {'daily_marriages': {}}}
    )
    
    target_name = target_user.first_name if target_user else str(target_id)
    
    await message.reply_text(
        f"💒 **Marriage Limit Reset!**\n\n"
        f"👤 **User:** {target_name} (`{target_id}`)\n"
        f"📊 **Status:** Set to 0/30\n\n"
        f"They can now marry up to 30 characters again!",
        parse_mode=enums.ParseMode.MARKDOWN
    )


async def resetm_ptb(update: Update, context: CallbackContext) -> None:
    """PTB wrapper for resetm command"""
    sender_id = update.effective_user.id
    
    if str(sender_id) not in [str(u) for u in Config.sudo_users]:
        await update.message.reply_text("🚫 This command is only available to administrators.")
        return
    
    target_user = None
    target_id = None
    
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_id = target_user.id
    elif context.args and len(context.args) >= 1:
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
            return
    else:
        await update.message.reply_text(
            "💒 **Reset Marriage Limit Command**\n\n"
            "**Usage:**\n"
            "• Reply to a user's message with `/resetm`\n"
            "• Or use `/resetm [user_id]`\n\n"
            "This will reset their daily marriage limit to 0/30.",
            parse_mode='Markdown'
        )
        return
    
    user = await user_collection.find_one({'id': target_id})
    if not user:
        await update.message.reply_text(f"❌ User ID `{target_id}` not found in database!")
        return
    
    await user_collection.update_one(
        {'id': target_id},
        {'$set': {'daily_marriages': {}}}
    )
    
    target_name = target_user.first_name if target_user else str(target_id)
    
    await update.message.reply_text(
        f"💒 **Marriage Limit Reset!**\n\n"
        f"👤 **User:** {target_name} (`{target_id}`)\n"
        f"📊 **Status:** Set to 0/30\n\n"
        f"They can now marry up to 30 characters again!",
        parse_mode='Markdown'
    )


# Register handlers
application.add_handler(CommandHandler("lockspawn", lockspawn_ptb, block=False))
application.add_handler(CommandHandler("unlockspawn", unlockspawn_ptb, block=False))
application.add_handler(CommandHandler("lockedspawns", lockedspawns_ptb, block=False))
application.add_handler(CommandHandler("rarity", rarity_ptb, block=False))
application.add_handler(CommandHandler("broadcast", broadcast_ptb, block=False))
application.add_handler(CommandHandler("bonk", bonk_ptb, block=False))
application.add_handler(CommandHandler("unbonk", unbonk_ptb, block=False))
application.add_handler(CommandHandler("resetm", resetm_ptb, block=False))
application.add_handler(CallbackQueryHandler(lockedspawns_callback_ptb, pattern="^lockedspawns:", block=False))

