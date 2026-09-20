import random
from html import escape 

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler

from shivu import application, PHOTO_URL, SUPPORT_CHAT, UPDATE_CHAT, BOT_USERNAME, db, GROUP_ID
from shivu import pm_users as collection 

START_MEDIA_URL = "https://mymeowbot-production.up.railway.app/dl/AgADFA/BAACAgQAAxkDAAIQr2qq0iSwmG4TeyBMKmYShO5VmjAIAALLCwACluJdUUFVZ1p5HLfuPQQ.mp4"
START_CAPTION = """𝘞𝘦𝘭𝘤𝘰𝘮𝘦 𝘵𝘰 𝘊𝘪𝘯𝘦𝘓𝘦𝘨𝘢𝘤𝘺 𝘣𝘰𝘵.

<tg-emoji emoji-id="5215248920606698936">😈</tg-emoji> - 𝘈𝘤𝘩𝘪𝘦𝘷𝘦 𝘵𝘩𝘰𝘶𝘴𝘢𝘯𝘥𝘴 𝘰𝘧 𝘗𝘳𝘦𝘤𝘪𝘰𝘶𝘴 𝘊𝘩𝘢𝘳𝘢𝘤𝘵𝘦𝘳𝘴.

<tg-emoji emoji-id="5363822289030755872">👆</tg-emoji> - 𝘛𝘳𝘢𝘥𝘦 𝘢𝘯𝘥 𝘎𝘪𝘧𝘵 𝘺𝘰𝘶𝘳 𝘤𝘩𝘢𝘳𝘢𝘤𝘵𝘦𝘳𝘴 𝘵𝘰 𝘺𝘰𝘶𝘳 𝘧𝘳𝘪𝘦𝘯𝘥𝘴 𝘢𝘯𝘥 𝘰𝘵𝘩𝘦𝘳 𝘱𝘭𝘢𝘺𝘦𝘳𝘴

<tg-emoji emoji-id="5364024367242033401">😀</tg-emoji> - 𝘊𝘰𝘭𝘭𝘦𝘤𝘵 𝘺𝘰𝘶𝘳 𝘥𝘳𝘦𝘢𝘮 𝘤𝘰𝘭𝘭𝘦𝘤𝘵𝘪𝘰𝘯

<tg-emoji emoji-id="5366198501162105680">💔</tg-emoji> 𝘚𝘶𝘱𝘱𝘰𝘳𝘵 𝘤𝘩𝘢𝘯𝘯𝘦𝘭 : @cinelegacyupdates

<tg-emoji emoji-id="5418010521309815154">🎫</tg-emoji> 𝘔𝘢𝘪𝘯 𝘨𝘤 : @cinelegacygroup"""


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
        
        
        caption = START_CAPTION
        
        keyboard = [
            [InlineKeyboardButton("SUPPORT", url=f'http://t.me/{SUPPORT_CHAT}')],
            [InlineKeyboardButton("HELP", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        photo_url = START_MEDIA_URL

        await context.bot.send_animation(chat_id=update.effective_chat.id, animation=photo_url, caption=caption, reply_markup=reply_markup, parse_mode='HTML')

    else:
        photo_url = START_MEDIA_URL
        keyboard = [
            [InlineKeyboardButton("SUPPORT", url=f'http://t.me/{SUPPORT_CHAT}')],
            [InlineKeyboardButton("HELP", callback_data='help')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_animation(chat_id=update.effective_chat.id, animation=photo_url, caption="🎴Alive!?... \n connect to me in PM For more information ",reply_markup=reply_markup, parse_mode='HTML')

async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'help':
        help_text = """
<b>Help Section:</b>

<b>/invite:</b> To catch and invite characters (only works in group)
<b>/fav:</b> Add Your fav
<b>/trade:</b> To trade Characters
<b>/gift:</b> Give any Character from Your Collection to another user.. (only works in groups)
<b>/inventory:</b> To see Your Collection
<b>/topgroups:</b> See Top Groups.. Ppl Guesses Most in that Groups
<b>/top:</b> To See Top Users
<b>/ctop:</b> Your ChatTop
<b>/changetime:</b> Change Character appear time (only works in Groups)
   """
        help_keyboard = [[InlineKeyboardButton("⤾ Bᴀᴄᴋ", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(help_keyboard)
        
        await context.bot.edit_message_caption(chat_id=update.effective_chat.id, message_id=query.message.message_id, caption=help_text, reply_markup=reply_markup, parse_mode='HTML')

    elif query.data == 'back':

        caption = START_CAPTION

        
        keyboard = [
            [InlineKeyboardButton("SUPPORT", url=f'http://t.me/{SUPPORT_CHAT}')],
            [InlineKeyboardButton("HELP", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.edit_message_caption(chat_id=update.effective_chat.id, message_id=query.message.message_id, caption=caption, reply_markup=reply_markup, parse_mode='HTML')


application.add_handler(CallbackQueryHandler(button, pattern='^help$|^back$', block=False))
start_handler = CommandHandler('start', start, block=False)
application.add_handler(start_handler)
