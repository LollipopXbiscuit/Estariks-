from telegram import Update
from telegram.ext import CallbackContext, CommandHandler 

from shivu import application, top_global_groups_collection, pm_users, OWNER_ID 

async def broadcast(update: Update, context: CallbackContext) -> None:
    
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    message_to_broadcast = update.message.reply_to_message

    if message_to_broadcast is None:
        await update.message.reply_text("Please reply to a message to broadcast.\n\nSupported: Text, Images, GIFs, Videos, and more!")
        return

    all_chats = await top_global_groups_collection.distinct("group_id")
    all_users = await pm_users.distinct("_id")

    shuyaa = list(set(all_chats + all_users))

    failed_sends = 0
    success_sends = 0

    for chat_id in shuyaa:
        try:
            # Check message type and send accordingly
            if message_to_broadcast.animation:  # GIF/Animation
                await context.bot.send_animation(
                    chat_id=chat_id,
                    animation=message_to_broadcast.animation.file_id,
                    caption=message_to_broadcast.caption,
                    parse_mode='HTML'
                )
            elif message_to_broadcast.photo:  # Photo
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=message_to_broadcast.photo[-1].file_id,
                    caption=message_to_broadcast.caption,
                    parse_mode='HTML'
                )
            elif message_to_broadcast.video:  # Video
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=message_to_broadcast.video.file_id,
                    caption=message_to_broadcast.caption,
                    parse_mode='HTML'
                )
            elif message_to_broadcast.document:  # Document
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=message_to_broadcast.document.file_id,
                    caption=message_to_broadcast.caption,
                    parse_mode='HTML'
                )
            else:  # Text or other
                await context.bot.forward_message(
                    chat_id=chat_id,
                    from_chat_id=message_to_broadcast.chat_id,
                    message_id=message_to_broadcast.message_id
                )
            success_sends += 1
        except Exception as e:
            print(f"Failed to send message to {chat_id}: {e}")
            failed_sends += 1

    await update.message.reply_text(f"✅ Broadcast complete!\n\n📤 Sent to: {success_sends} chats/users\n❌ Failed: {failed_sends}")

application.add_handler(CommandHandler("broadcast", broadcast, block=False))
