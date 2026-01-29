import random
from html import escape 

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler

from shivu import application, PHOTO_URL, SUPPORT_CHAT, UPDATE_CHAT, BOT_USERNAME, db, GROUP_ID
from shivu import pm_users as collection 


async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    username = update.effective_user.username

    user_data = await collection.find_one({"_id": user_id})

    if user_data is None:
        
        await collection.insert_one({"_id": user_id, "first_name": first_name, "username": username, "characters": []})
        
        # Optional: Send notification to group when new users start (uncomment if you have a group set up)
        # await context.bot.send_message(chat_id=GROUP_ID, 
        #                                text=f"New user Started The Bot..\n User: <a href='tg://user?id={user_id}'>{escape(first_name)})</a>", 
        #                                parse_mode='HTML')
    else:
        
        if user_data['first_name'] != first_name or user_data['username'] != username:
            
            await collection.update_one({"_id": user_id}, {"$set": {"first_name": first_name, "username": username}})

    

    if update.effective_chat.type== "private":
        
        
        caption = f"""🏐 𝘞𝘦𝘭𝘤𝘰𝘮𝘦 𝘵𝘰 𝘌𝘴𝘵𝘢𝘳𝘪𝘬𝘴 𝘣𝘰𝘵 ~

💒 - 𝘈𝘤𝘩𝘪𝘦𝘷𝘦 𝘵𝘩𝘰𝘶𝘴𝘢𝘯𝘥𝘴 𝘰𝘧 𝘗𝘳𝘦𝘤𝘪𝘰𝘶𝘴 𝘊𝘩𝘢𝘳𝘢𝘤𝘵𝘦𝘳𝘴.

🏩 - 𝘛𝘳𝘢𝘥𝘦 𝘢𝘯𝘥 𝘎𝘪𝘧𝘵 𝘺𝘰𝘶𝘳 𝘤𝘩𝘢𝘳𝘢𝘤𝘵𝘦𝘳𝘴 𝘵𝘰 𝘺𝘰𝘶𝘳 𝘧𝘳𝘪𝘦𝘯𝘥𝘴 𝘢𝘯𝘥 𝘰𝘵𝘩𝘦𝘳 𝘱𝘭𝘢𝘺𝘦𝘳𝘴

🗼 - 𝘊𝘰𝘭𝘭𝘦𝘤𝘵 𝘺𝘰𝘶𝘳 𝘥𝘳𝘦𝘢𝘮 𝘤𝘰𝘭𝘭𝘦𝘤𝘵𝘪𝘰𝘯

🎀 𝘚𝘶𝘱𝘱𝘰𝘳𝘵 𝘤𝘩𝘢𝘯𝘯𝘦𝘭 : @EstariksUpdates

🎟 𝘔𝘢𝘪𝘯 𝘨𝘤 : @EstariksUpdates
        """
        
        keyboard = [
            [InlineKeyboardButton("SUPPORT", url=f'http://t.me/{SUPPORT_CHAT}')],
            [InlineKeyboardButton("HELP", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        photo_url = "https://fcdn.koyeb.app/dl/697bd4ac8e4f7a0c0bbb8734/Anime%20gif%20scenery%20%282%29.gif"

        await context.bot.send_animation(chat_id=update.effective_chat.id, animation=photo_url, caption=caption, reply_markup=reply_markup, parse_mode='HTML')

    else:
        photo_url = "https://fcdn.koyeb.app/dl/697bd4ac8e4f7a0c0bbb8734/Anime%20gif%20scenery%20%282%29.gif"
        keyboard = [
            [InlineKeyboardButton("SUPPORT", url=f'http://t.me/{SUPPORT_CHAT}')],
            [InlineKeyboardButton("HELP", callback_data='help')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_animation(chat_id=update.effective_chat.id, animation=photo_url, caption="🎴Alive!?... \n connect to me in PM For more information ",reply_markup=reply_markup )

async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'help':
        help_text = """
    ***Help Section:***
    
***/invite: To catch and invite characters (only works in group)***
***/fav: Add Your fav***
***/trade : To trade Characters***
***/gift: Give any Character from Your Collection to another user.. (only works in groups)***
***/collection: To see Your Collection***
***/topgroups : See Top Groups.. Ppl Guesses Most in that Groups***
***/top: Too See Top Users***
***/ctop : Your ChatTop***
***/changetime: Change Character appear time (only works in Groups)***
   """
        help_keyboard = [[InlineKeyboardButton("⤾ Bᴀᴄᴋ", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(help_keyboard)
        
        await context.bot.edit_message_caption(chat_id=update.effective_chat.id, message_id=query.message.message_id, caption=help_text, reply_markup=reply_markup, parse_mode='markdown')

    elif query.data == 'back':

        caption = f"""🏐 𝘞𝘦𝘭𝘤𝘰𝘮𝘦 𝘵𝘰 𝘌𝘴𝘵𝘢𝘳𝘪𝘬𝘴 𝘣𝘰𝘵 ~

💒 - 𝘈𝘤𝘩𝘪𝘦𝘷𝘦 𝘵𝘩𝘰𝘶𝘴𝘢𝘯𝘥𝘴 𝘰𝘧 𝘗𝘳𝘦𝘤𝘪𝘰𝘶𝘴 𝘊𝘩𝘢𝘳𝘢𝘤𝘵𝘦𝘳𝘴.

🏩 - 𝘛𝘳𝘢𝘥𝘦 𝘢𝘯𝘥 𝘎𝘪𝘧𝘵 𝘺𝘰𝘶𝘳 𝘤𝘩𝘢𝘳𝘢𝘤𝘵𝘦𝘳𝘴 𝘵𝘰 𝘺𝘰𝘶𝘳 𝘧𝘳𝘪𝘦𝘯𝘥𝘴 𝘢𝘯𝘥 𝘰𝘵𝘩𝘦𝘳 𝘱𝘭𝘢𝘺𝘦𝘳𝘴

🗼 - 𝘊𝘰𝘭𝘭𝘦𝘤𝘵 𝘺𝘰𝘶𝘳 𝘥𝘳𝘦𝘢𝘮 𝘤𝘰𝘭𝘭𝘦𝘤𝘵𝘪𝘰𝘯

🎀 𝘚𝘶𝘱𝘱𝘰𝘳𝘵 𝘤𝘩𝘢𝘯𝘯𝘦𝘭 : @EstariksUpdates

🎟 𝘔𝘢𝘪𝘯 𝘨𝘤 : @EstariksUpdates
        """

        
        keyboard = [
            [InlineKeyboardButton("SUPPORT", url=f'http://t.me/{SUPPORT_CHAT}')],
            [InlineKeyboardButton("HELP", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.edit_message_caption(chat_id=update.effective_chat.id, message_id=query.message.message_id, caption=caption, reply_markup=reply_markup, parse_mode='HTML')


application.add_handler(CallbackQueryHandler(button, pattern='^help$|^back$', block=False))
start_handler = CommandHandler('start', start, block=False)
application.add_handler(start_handler)
