from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup as PyrogramInlineKeyboardMarkup, InlineKeyboardButton as PyrogramInlineKeyboardButton
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from html import escape

from shivu import (
    user_collection,
    shivuu,
    collection,
    application,
    get_character_media_source,
    send_character_media,
)
from shivu.config import Config

pending_trades = {}


async def reply_character_preview(message, character, caption, reply_markup, parse_mode):
    source, media_type, is_video = await get_character_media_source(character)
    is_python_telegram_bot = message.__class__.__module__.startswith('telegram.')
    return await send_character_media(
        bot=message.get_bot() if is_python_telegram_bot else message._client,
        chat_id=message.chat_id if is_python_telegram_bot else message.chat.id,
        media_url=source,
        caption=caption,
        is_video=is_video,
        media_type=media_type,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        character=character,
    )


@shivuu.on_message(filters.command("trade"))
async def trade(client, message):
    sender_id = message.from_user.id

    if not message.reply_to_message:
        await message.reply_text("You need to reply to a user's message to trade a character!")
        return

    receiver_id = message.reply_to_message.from_user.id

    if sender_id == receiver_id:
        await message.reply_text("You can't trade a character with yourself!")
        return

    if len(message.command) != 3:
        await message.reply_text("You need to provide two character IDs!")
        return

    sender_character_id, receiver_character_id = message.command[1], message.command[2]

    sender = await user_collection.find_one({'id': sender_id})
    receiver = await user_collection.find_one({'id': receiver_id})

    # Check if users exist and have characters field
    if not sender or not sender.get('characters'):
        await message.reply_text("You don't have any characters to trade!")
        return
        
    if not receiver or not receiver.get('characters'):
        await message.reply_text("The other user doesn't have any characters to trade!")
        return

    sender_character = next((character for character in sender['characters'] if character['id'] == sender_character_id), None)
    receiver_character = next((character for character in receiver['characters'] if character['id'] == receiver_character_id), None)

    if not sender_character:
        await message.reply_text("You don't have the character you're trying to trade!")
        return

    if not receiver_character:
        await message.reply_text("The other user doesn't have the character they're trying to trade!")
        return






    if len(message.command) != 3:
        await message.reply_text("/trade [Your Character ID] [Other User Character ID]!")
        return

    sender_character_id, receiver_character_id = message.command[1], message.command[2]

    
    pending_trades[(sender_id, receiver_id)] = (sender_character_id, receiver_character_id)

    
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Confirm Trade", callback_data="confirm_trade")],
            [InlineKeyboardButton("Cancel Trade", callback_data="cancel_trade")]
        ]
    )

    await message.reply_text(f"{message.reply_to_message.from_user.mention}, do you accept this trade?", reply_markup=keyboard)


@shivuu.on_callback_query(filters.create(lambda _, __, query: query.data in ["confirm_trade", "cancel_trade"]))
async def on_trade_callback_query(client, callback_query):
    receiver_id = callback_query.from_user.id

    
    for (sender_id, _receiver_id), (sender_character_id, receiver_character_id) in pending_trades.items():
        if _receiver_id == receiver_id:
            break
    else:
        await callback_query.answer("This is not for you!", show_alert=True)
        return

    if callback_query.data == "confirm_trade":
        
        sender = await user_collection.find_one({'id': sender_id})
        receiver = await user_collection.find_one({'id': receiver_id})

        # Check if users still exist and have characters
        if not sender or not sender.get('characters'):
            await callback_query.answer("Sender no longer has characters!", show_alert=True)
            return
            
        if not receiver or not receiver.get('characters'):
            await callback_query.answer("Receiver no longer has characters!", show_alert=True)
            return

        sender_character = next((character for character in sender['characters'] if character['id'] == sender_character_id), None)
        receiver_character = next((character for character in receiver['characters'] if character['id'] == receiver_character_id), None)

        if not sender_character or not receiver_character:
            await callback_query.answer("One of the characters is no longer available!", show_alert=True)
            return
        
        sender['characters'].remove(sender_character)
        receiver['characters'].remove(receiver_character)

        
        await user_collection.update_one({'id': sender_id}, {'$set': {'characters': sender['characters']}})
        await user_collection.update_one({'id': receiver_id}, {'$set': {'characters': receiver['characters']}})

        
        sender['characters'].append(receiver_character)
        receiver['characters'].append(sender_character)

        
        await user_collection.update_one({'id': sender_id}, {'$set': {'characters': sender['characters']}})
        await user_collection.update_one({'id': receiver_id}, {'$set': {'characters': receiver['characters']}})

        
        del pending_trades[(sender_id, receiver_id)]

        await callback_query.message.edit_text(f"You have successfully traded your character with {callback_query.message.reply_to_message.from_user.mention}!")

    elif callback_query.data == "cancel_trade":
        
        del pending_trades[(sender_id, receiver_id)]

        await callback_query.message.edit_text("❌️ Sad Cancelled....")




pending_gifts = {}


@shivuu.on_message(filters.command("gift"))
async def gift(client, message):
    sender_id = message.from_user.id

    if not message.reply_to_message:
        await message.reply_text("You need to reply to a user's message to gift a character!")
        return

    receiver_id = message.reply_to_message.from_user.id
    receiver_username = message.reply_to_message.from_user.username
    receiver_first_name = message.reply_to_message.from_user.first_name

    if sender_id == receiver_id:
        await message.reply_text("You can't gift a character to yourself!")
        return

    if len(message.command) != 2:
        await message.reply_text("You need to provide a character ID!")
        return

    character_id = message.command[1]

    sender = await user_collection.find_one({'id': sender_id})

    # Check if user exists and has characters field
    if not sender or not sender.get('characters'):
        await message.reply_text("You don't have any characters to gift!")
        return

    character = next((character for character in sender['characters'] if character['id'] == character_id), None)

    if not character:
        await message.reply_text("You don't have this character in your collection!")
        return

    
    pending_gifts[(sender_id, receiver_id)] = {
        'character': character,
        'receiver_username': receiver_username,
        'receiver_first_name': receiver_first_name
    }

    
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Confirm Gift", callback_data="confirm_gift")],
            [InlineKeyboardButton("❌ Cancel Gift", callback_data="cancel_gift")]
        ]
    )

    # Rarity emoji mapping
    rarity_emojis = {
        "Worn": "🟤",
        "Gear": "⚙️",
        "Blaze": "🔥",
        "Nebula": "🌌",
        "Apex": "👑"
    }
    
    rarity_emoji = rarity_emojis.get(character.get('rarity', 'Worn'), "✨")
    
    caption = (f"🎁 <b>Do you want to gift this character?</b>\n\n"
               f"🎴 <b>Name:</b> {escape(character['name'])}\n"
               f"📺 <b>Anime:</b> {escape(character['anime'])}\n"
               f"🌟 <b>Rarity:</b> {rarity_emoji} "
               f"{escape(str(character.get('rarity', 'Unknown')))}\n"
               f"🆔 <b>ID:</b> <code>{escape(str(character['id']))}</code>\n\n"
               f"👤 <b>To:</b> {escape(message.reply_to_message.from_user.first_name)}")

    try:
        if 'img_url' in character:
            await reply_character_preview(
                message, character, caption, keyboard, enums.ParseMode.HTML
            )
        else:
            await message.reply_text(caption, parse_mode=enums.ParseMode.HTML, reply_markup=keyboard)
    except Exception as e:
        await message.reply_text(caption, parse_mode=enums.ParseMode.HTML, reply_markup=keyboard)

@shivuu.on_callback_query(filters.create(lambda _, __, query: query.data in ["confirm_gift", "cancel_gift"]))
async def on_gift_callback_query(client, callback_query):
    sender_id = callback_query.from_user.id

    
    for (_sender_id, receiver_id), gift in pending_gifts.items():
        if _sender_id == sender_id:
            break
    else:
        await callback_query.answer("This is not for you!", show_alert=True)
        return

    if callback_query.data == "confirm_gift":
        
        sender = await user_collection.find_one({'id': sender_id})
        receiver = await user_collection.find_one({'id': receiver_id})

        # Check if sender still exists and has characters
        if not sender or not sender.get('characters'):
            await callback_query.answer("You no longer have characters to gift!", show_alert=True)
            return
        
        sender['characters'].remove(gift['character'])
        await user_collection.update_one({'id': sender_id}, {'$set': {'characters': sender['characters']}})

        
        if receiver:
            await user_collection.update_one({'id': receiver_id}, {'$push': {'characters': gift['character']}})
        else:
            
            await user_collection.insert_one({
                'id': receiver_id,
                'username': gift['receiver_username'],
                'first_name': gift['receiver_first_name'],
                'characters': [gift['character']],
            })

        
        del pending_gifts[(sender_id, receiver_id)]

        success_message = f"✅ <b>Gift successful!</b>\n\nYou have successfully gifted your character to <a href=\"tg://user?id={receiver_id}\">{escape(gift['receiver_first_name'])}</a>!"
        
        # Check if message has media (photo) or is text
        if callback_query.message.photo:
            await callback_query.message.edit_caption(caption=success_message, parse_mode=enums.ParseMode.HTML)
        else:
            await callback_query.message.edit_text(success_message, parse_mode=enums.ParseMode.HTML)

    elif callback_query.data == "cancel_gift":
        
        del pending_gifts[(sender_id, receiver_id)]

        cancel_message = "❌ <b>Gift cancelled.</b>"
        
        # Check if message has media (photo) or is text
        if callback_query.message.photo:
            await callback_query.message.edit_caption(caption=cancel_message, parse_mode=enums.ParseMode.HTML)
        else:
            await callback_query.message.edit_text(cancel_message, parse_mode=enums.ParseMode.HTML)


@shivuu.on_message(filters.command("give"))
async def give(client, message):
    """Admin-only command to give characters to users"""
    sender_id = message.from_user.id
    
    # Check if user is admin
    if str(sender_id) not in Config.sudo_users:
        await message.reply_text("🚫 This command is only available to administrators.")
        return
    
    # Command format: /give <character_id> <user_id>
    # Or: /give <character_id> (when replying to a user)
    
    if message.reply_to_message:
        # Giving to the user being replied to
        if len(message.command) != 2:
            await message.reply_text("📝 **Give Character**\n\nUsage when replying: `/give <character_id>`\nExample: `/give 1`")
            return
            
        character_id = message.command[1]
        receiver_id = message.reply_to_message.from_user.id
        receiver_username = message.reply_to_message.from_user.username
        receiver_first_name = message.reply_to_message.from_user.first_name
        
    else:
        # Giving to a specific user ID
        if len(message.command) != 3:
            await message.reply_text("📝 **Give Character**\n\nUsage: `/give <character_id> <user_id>`\nExample: `/give 1 123456789`\n\nOr reply to a user: `/give <character_id>`")
            return
            
        character_id = message.command[1]
        try:
            receiver_id = int(message.command[2])
        except ValueError:
            await message.reply_text("❌ Invalid user ID. Please provide a valid number.")
            return
            
        receiver_username = None
        receiver_first_name = "User"
    
    # Find the character in the database
    character = await collection.find_one({'id': character_id})
    if not character:
        await message.reply_text(f"❌ Character with ID `{character_id}` not found in the database.")
        return
    
    # Check if receiver exists in database, if not create entry
    receiver = await user_collection.find_one({'id': receiver_id})
    if receiver:
        # Add character to existing user
        await user_collection.update_one(
            {'id': receiver_id}, 
            {'$push': {'characters': character}}
        )
    else:
        # Create new user entry
        await user_collection.insert_one({
            'id': receiver_id,
            'username': receiver_username,
            'first_name': receiver_first_name,
            'characters': [character],
        })
    
    # Success message
    if message.reply_to_message:
        await message.reply_text(
            f"✅ **Character Given!**\n\n"
            f"🎴 **{character['name']}** ({character['rarity']})\n"
            f"📺 From: **{character['anime']}**\n"
            f"👤 Given to: {message.reply_to_message.from_user.mention}\n"
            f"🆔 Character ID: `{character['id']}`"
        )
    else:
        await message.reply_text(
            f"✅ **Character Given!**\n\n"
            f"🎴 **{character['name']}** ({character['rarity']})\n"
            f"📺 From: **{character['anime']}**\n"
            f"👤 Given to: User ID `{receiver_id}`\n"
            f"🆔 Character ID: `{character['id']}`"
        )


# python-telegram-bot version (works with webhooks)
async def gift_ptb(update: Update, context: CallbackContext):
    """Gift a character to another user - python-telegram-bot version"""
    sender_id = update.effective_user.id
    
    if not update.message.reply_to_message:
        await update.message.reply_text("You need to reply to a user's message to gift a character!")
        return
    
    receiver_id = update.message.reply_to_message.from_user.id
    receiver_username = update.message.reply_to_message.from_user.username
    receiver_first_name = update.message.reply_to_message.from_user.first_name
    
    if sender_id == receiver_id:
        await update.message.reply_text("You can't gift a character to yourself!")
        return
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("You need to provide a character ID!\nUsage: /gift <character_id>")
        return
    
    character_id = context.args[0]
    
    sender = await user_collection.find_one({'id': sender_id})
    
    # Check if user exists and has characters field
    if not sender or not sender.get('characters'):
        await update.message.reply_text("You don't have any characters to gift!")
        return
    
    character = next((character for character in sender['characters'] if character['id'] == character_id), None)
    
    if not character:
        await update.message.reply_text("You don't have this character in your collection!")
        return
    
    # Store pending gift
    pending_gifts[(sender_id, receiver_id)] = {
        'character': character,
        'receiver_username': receiver_username,
        'receiver_first_name': receiver_first_name
    }
    
    # Create keyboard
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm Gift", callback_data="confirm_gift")],
        [InlineKeyboardButton("❌ Cancel Gift", callback_data="cancel_gift")]
    ])
    
    # Rarity emoji mapping
    rarity_emojis = {
        "Worn": "🟤",
        "Gear": "⚙️",
        "Blaze": "🔥",
        "Nebula": "🌌",
        "Apex": "👑"
    }
    
    rarity_emoji = rarity_emojis.get(character.get('rarity', 'Worn'), "✨")
    
    caption = (f"🎁 <b>Do you want to gift this character?</b>\n\n"
               f"🎴 <b>Name:</b> {escape(character['name'])}\n"
               f"📺 <b>Anime:</b> {escape(character['anime'])}\n"
               f"🌟 <b>Rarity:</b> {rarity_emoji} "
               f"{escape(str(character.get('rarity', 'Unknown')))}\n"
               f"🆔 <b>ID:</b> <code>{escape(str(character['id']))}</code>\n\n"
               f"👤 <b>To:</b> {escape(update.message.reply_to_message.from_user.first_name)}")
    
    try:
        if 'img_url' in character:
            await reply_character_preview(
                update.message, character, caption, keyboard, 'HTML'
            )
        else:
            await update.message.reply_text(caption, parse_mode='HTML', reply_markup=keyboard)
    except Exception as e:
        await update.message.reply_text(caption, parse_mode='HTML', reply_markup=keyboard)


async def gift_callback_handler(update: Update, context: CallbackContext):
    """Handle gift confirmation/cancellation callbacks"""
    query = update.callback_query
    sender_id = query.from_user.id
    
    # Find the pending gift for this sender
    gift_key = None
    gift = None
    for (sid, rid), g in pending_gifts.items():
        if sid == sender_id:
            gift_key = (sid, rid)
            gift = g
            receiver_id = rid
            break
    
    if not gift_key:
        await query.answer("This is not for you!", show_alert=True)
        return
    
    if query.data == "confirm_gift":
        # Get sender from database
        sender = await user_collection.find_one({'id': sender_id})
        receiver = await user_collection.find_one({'id': receiver_id})
        
        # Check if sender still exists and has characters
        if not sender or not sender.get('characters'):
            await query.answer("You no longer have characters to gift!", show_alert=True)
            return
        
        # Remove character from sender
        sender['characters'].remove(gift['character'])
        await user_collection.update_one({'id': sender_id}, {'$set': {'characters': sender['characters']}})
        
        # Add to receiver
        if receiver:
            await user_collection.update_one({'id': receiver_id}, {'$push': {'characters': gift['character']}})
        else:
            await user_collection.insert_one({
                'id': receiver_id,
                'username': gift['receiver_username'],
                'first_name': gift['receiver_first_name'],
                'characters': [gift['character']],
            })
        
        # Remove from pending
        del pending_gifts[gift_key]
        
        success_message = f"✅ <b>Gift successful!</b>\n\nYou have successfully gifted your character to <a href=\"tg://user?id={receiver_id}\">{escape(gift['receiver_first_name'])}</a>!"
        
        # Edit the message
        try:
            if query.message.photo:
                await query.message.edit_caption(caption=success_message, parse_mode='HTML')
            else:
                await query.message.edit_text(success_message, parse_mode='HTML')
        except:
            await query.message.edit_text(success_message, parse_mode='HTML')
        
        await query.answer("Gift sent successfully!")
        
    elif query.data == "cancel_gift":
        # Remove from pending
        del pending_gifts[gift_key]
        
        cancel_message = "❌ <b>Gift cancelled.</b>"
        
        # Edit the message
        try:
            if query.message.photo:
                await query.message.edit_caption(caption=cancel_message, parse_mode='HTML')
            else:
                await query.message.edit_text(cancel_message, parse_mode='HTML')
        except:
            await query.message.edit_text(cancel_message, parse_mode='HTML')
        
        await query.answer("Gift cancelled")


# python-telegram-bot version of /trade command (works with webhooks)
async def trade_ptb(update: Update, context: CallbackContext):
    """Trade characters between users - PTB version"""
    sender_id = update.effective_user.id

    if not update.message.reply_to_message:
        await update.message.reply_text("You need to reply to a user's message to trade a character!")
        return

    receiver_id = update.message.reply_to_message.from_user.id

    if sender_id == receiver_id:
        await update.message.reply_text("You can't trade a character with yourself!")
        return

    if not context.args or len(context.args) != 2:
        await update.message.reply_text("You need to provide two character IDs!\nUsage: /trade [your_character_id] [their_character_id]")
        return

    sender_character_id, receiver_character_id = context.args[0], context.args[1]

    sender = await user_collection.find_one({'id': sender_id})
    receiver = await user_collection.find_one({'id': receiver_id})

    if not sender or not sender.get('characters'):
        await update.message.reply_text("You don't have any characters to trade!")
        return
        
    if not receiver or not receiver.get('characters'):
        await update.message.reply_text("The other user doesn't have any characters to trade!")
        return

    sender_character = next((character for character in sender['characters'] if character['id'] == sender_character_id), None)
    receiver_character = next((character for character in receiver['characters'] if character['id'] == receiver_character_id), None)

    if not sender_character:
        await update.message.reply_text("You don't have the character you're trying to trade!")
        return

    if not receiver_character:
        await update.message.reply_text("The other user doesn't have the character they're trying to trade!")
        return

    pending_trades[(sender_id, receiver_id)] = (sender_character_id, receiver_character_id)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Confirm Trade", callback_data="confirm_trade")],
        [InlineKeyboardButton("Cancel Trade", callback_data="cancel_trade")]
    ])

    await update.message.reply_text(
        f"{update.message.reply_to_message.from_user.mention_html()}, do you accept this trade?",
        parse_mode='HTML',
        reply_markup=keyboard
    )


async def trade_callback_ptb(update: Update, context: CallbackContext):
    """Handle trade confirmation/cancellation - PTB version"""
    query = update.callback_query
    receiver_id = query.from_user.id

    # Find the pending trade for this receiver
    trade_key = None
    for (sender_id, _receiver_id), (sender_character_id, receiver_character_id) in pending_trades.items():
        if _receiver_id == receiver_id:
            trade_key = (sender_id, _receiver_id)
            break
    else:
        await query.answer("This is not for you!", show_alert=True)
        return

    if query.data == "confirm_trade":
        sender = await user_collection.find_one({'id': sender_id})
        receiver = await user_collection.find_one({'id': receiver_id})

        if not sender or not sender.get('characters'):
            await query.answer("Sender no longer has characters!", show_alert=True)
            return
            
        if not receiver or not receiver.get('characters'):
            await query.answer("Receiver no longer has characters!", show_alert=True)
            return

        sender_character = next((character for character in sender['characters'] if character['id'] == sender_character_id), None)
        receiver_character = next((character for character in receiver['characters'] if character['id'] == receiver_character_id), None)

        if not sender_character or not receiver_character:
            await query.answer("One of the characters is no longer available!", show_alert=True)
            return
        
        sender['characters'].remove(sender_character)
        receiver['characters'].remove(receiver_character)

        await user_collection.update_one({'id': sender_id}, {'$set': {'characters': sender['characters']}})
        await user_collection.update_one({'id': receiver_id}, {'$set': {'characters': receiver['characters']}})

        sender['characters'].append(receiver_character)
        receiver['characters'].append(sender_character)

        await user_collection.update_one({'id': sender_id}, {'$set': {'characters': sender['characters']}})
        await user_collection.update_one({'id': receiver_id}, {'$set': {'characters': receiver['characters']}})

        del pending_trades[trade_key]

        await query.message.edit_text(f"✅ Trade successful! You have exchanged characters.")
        await query.answer("Trade completed!")

    elif query.data == "cancel_trade":
        del pending_trades[trade_key]
        await query.message.edit_text("❌ Trade cancelled.")
        await query.answer("Trade cancelled")


# python-telegram-bot version of /give command (works with webhooks)
async def give_ptb(update: Update, context: CallbackContext):
    """Admin command to give characters to users - PTB version"""
    sender_id = update.effective_user.id
    
    if str(sender_id) not in Config.sudo_users:
        await update.message.reply_text("🚫 This command is only available to administrators.")
        return
    
    if update.message.reply_to_message:
        if not context.args or len(context.args) != 1:
            await update.message.reply_text(
                "📝 **Give Character**\n\n"
                "Usage when replying: `/give <character_id>`\n"
                "Example: `/give 1`",
                parse_mode='HTML'
            )
            return
            
        character_id = context.args[0]
        receiver_id = update.message.reply_to_message.from_user.id
        receiver_username = update.message.reply_to_message.from_user.username
        receiver_first_name = update.message.reply_to_message.from_user.first_name
        
    else:
        if not context.args or len(context.args) != 2:
            await update.message.reply_text(
                "📝 **Give Character**\n\n"
                "Usage: `/give <character_id> <user_id>`\n"
                "Example: `/give 1 123456789`\n\n"
                "Or reply to a user: `/give <character_id>`",
                parse_mode='HTML'
            )
            return
            
        character_id = context.args[0]
        try:
            receiver_id = int(context.args[1])
            receiver_username = None
            receiver_first_name = "Unknown"
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID! Please provide a valid numeric user ID.")
            return
    
    character = await collection.find_one({'id': character_id})
    if not character:
        await update.message.reply_text(f"❌ Character with ID `{character_id}` not found in the database.")
        return
    
    receiver = await user_collection.find_one({'id': receiver_id})
    if receiver:
        await user_collection.update_one(
            {'id': receiver_id}, 
            {'$push': {'characters': character}}
        )
    else:
        await user_collection.insert_one({
            'id': receiver_id,
            'username': receiver_username,
            'first_name': receiver_first_name,
            'characters': [character],
        })
    
    if update.message.reply_to_message:
        await update.message.reply_text(
            f"✅ **Character Given!**\n\n"
            f"🎴 **{character['name']}** ({character['rarity']})\n"
            f"📺 From: **{character['anime']}**\n"
            f"👤 Given to: {update.message.reply_to_message.from_user.mention_html()}\n"
            f"🆔 Character ID: `{character['id']}`",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            f"✅ **Character Given!**\n\n"
            f"🎴 **{character['name']}** ({character['rarity']})\n"
            f"📺 From: **{character['anime']}**\n"
            f"👤 Given to: User ID `{receiver_id}`\n"
            f"🆔 Character ID: `{character['id']}`",
            parse_mode='HTML'
        )


# Register handlers
application.add_handler(CommandHandler("gift", gift_ptb, block=False))
application.add_handler(CallbackQueryHandler(gift_callback_handler, pattern="^(confirm_gift|cancel_gift)$", block=False))
application.add_handler(CommandHandler("trade", trade_ptb, block=False))
application.add_handler(CallbackQueryHandler(trade_callback_ptb, pattern="^(confirm_trade|cancel_trade)$", block=False))
application.add_handler(CommandHandler("give", give_ptb, block=False))


