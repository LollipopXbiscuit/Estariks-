import asyncio
import time

from pyrogram import StopPropagation, enums, filters
from pyrogram.errors import ChatAdminRequired, PeerIdInvalid, UserNotParticipant
from pyrogram.types import (
    InlineKeyboardButton as PyroInlineKeyboardButton,
    InlineKeyboardMarkup as PyroInlineKeyboardMarkup,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationHandlerStop,
    CallbackContext,
    CallbackQueryHandler,
    InlineQueryHandler,
    MessageHandler,
    filters as telegram_filters,
)

from shivu import (
    LOGGER,
    SUPPORT_CHAT,
    UPDATE_CHAT,
    application,
    restricted_users_collection,
    shivuu,
)


def _chat_reference(chat_name):
    """Return a Pyrogram-compatible public chat reference."""
    value = str(chat_name or "").strip()
    if value.startswith("@") or value.startswith("-100"):
        return value
    return f"@{value}"


def _join_url(chat_name):
    """Return the public Telegram URL used by the join buttons."""
    value = str(chat_name or "").strip().lstrip("@")
    return f"https://t.me/{value}"


SUPPORT_CHAT_REFERENCE = _chat_reference(SUPPORT_CHAT)
GROUP_CHAT_REFERENCE = _chat_reference(UPDATE_CHAT)
SUPPORT_JOIN_URL = _join_url(SUPPORT_CHAT)
GROUP_JOIN_URL = _join_url(UPDATE_CHAT)

ACTIVE_MEMBER_STATUSES = {
    enums.ChatMemberStatus.MEMBER,
    enums.ChatMemberStatus.ADMINISTRATOR,
    enums.ChatMemberStatus.OWNER,
    enums.ChatMemberStatus.RESTRICTED,
}

# PTB and Pyrogram can both receive the same command in this project. Avoid
# sending duplicate join prompts when both clients handle it at the same time.
_last_prompt_at = {}
_PROMPT_COOLDOWN_SECONDS = 2


def _claim_prompt_slot(user_id):
    now = time.monotonic()
    previous = _last_prompt_at.get(user_id, 0)
    if now - previous < _PROMPT_COOLDOWN_SECONDS:
        return False
    _last_prompt_at[user_id] = now
    return True


def get_force_join_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 Join Support Channel", url=SUPPORT_JOIN_URL)],
            [InlineKeyboardButton("👥 Join Main Group", url=GROUP_JOIN_URL)],
            [InlineKeyboardButton("✅ Check Membership", callback_data="force_join:check")],
        ]
    )


def get_force_join_pyro_keyboard():
    return PyroInlineKeyboardMarkup(
        [
            [PyroInlineKeyboardButton("📢 Join Support Channel", url=SUPPORT_JOIN_URL)],
            [PyroInlineKeyboardButton("👥 Join Main Group", url=GROUP_JOIN_URL)],
            [
                PyroInlineKeyboardButton(
                    "✅ Check Membership",
                    callback_data="force_join:check",
                )
            ],
        ]
    )


async def _is_member(chat_reference, user_id):
    try:
        member = await shivuu.get_chat_member(chat_reference, user_id)
        return member.status in ACTIVE_MEMBER_STATUSES
    except (UserNotParticipant, ChatAdminRequired, PeerIdInvalid):
        return False
    except Exception as error:
        LOGGER.error(
            "Force-join membership check failed for %s in %s: %s",
            user_id,
            chat_reference,
            error,
        )
        return False


async def is_force_joined(user_id):
    """Require membership in both the support channel and the main group."""
    support_member, group_member = await asyncio.gather(
        _is_member(SUPPORT_CHAT_REFERENCE, user_id),
        _is_member(GROUP_CHAT_REFERENCE, user_id),
    )
    return support_member and group_member


async def is_restricted(user_id):
    return await restricted_users_collection.find_one({"user_id": int(user_id)}) is not None


async def _send_restricted_ptb_prompt(update):
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not _claim_prompt_slot(user.id):
        return

    await message.reply_text(
        "🚫 <b>Your access to this bot has been restricted by an administrator.</b>",
        parse_mode="HTML",
    )


async def _send_restricted_pyro_prompt(message):
    user = message.from_user
    if not user or not _claim_prompt_slot(user.id):
        return

    await message.reply_text(
        "🚫 <b>Your access to this bot has been restricted by an administrator.</b>",
        parse_mode="html",
    )


async def _send_ptb_prompt(update):
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not _claim_prompt_slot(user.id):
        return

    await message.reply_text(
        "🔒 <b>Join both required chats to use this bot.</b>\n\n"
        "Join the support channel and the main group, then press "
        "<b>Check Membership</b>.",
        parse_mode="HTML",
        reply_markup=get_force_join_keyboard(),
    )


async def _send_pyro_prompt(message):
    user = message.from_user
    if not user or not _claim_prompt_slot(user.id):
        return

    await message.reply_text(
        "🔒 <b>Join both required chats to use this bot.</b>\n\n"
        "Join the support channel and the main group, then press "
        "<b>Check Membership</b>.",
        parse_mode="html",
        reply_markup=get_force_join_pyro_keyboard(),
    )


async def force_join_ptb_message(update, context: CallbackContext):
    user = update.effective_user
    if not user:
        return

    if await is_restricted(user.id):
        await _send_restricted_ptb_prompt(update)
        raise ApplicationHandlerStop

    if await is_force_joined(user.id):
        return

    await _send_ptb_prompt(update)
    raise ApplicationHandlerStop


async def force_join_ptb_callback(update, context: CallbackContext):
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return

    if await is_restricted(user.id):
        await query.answer(
            "Your access to this bot has been restricted.",
            show_alert=True,
        )
        raise ApplicationHandlerStop

    if query.data == "force_join:check":
        if await is_force_joined(user.id):
            await query.answer("Membership verified. You can use the bot now.")
            if query.message:
                await query.message.edit_text(
                    "✅ <b>Membership verified.</b>\n\n"
                    "You can use the bot now.",
                    parse_mode="HTML",
                    reply_markup=None,
                )
        else:
            await query.answer(
                "Please join both chats first, then try again.",
                show_alert=True,
            )
        raise ApplicationHandlerStop

    if await is_force_joined(user.id):
        return

    await query.answer(
        "Join both required chats before using the bot.",
        show_alert=True,
    )
    await _send_ptb_prompt(update)
    raise ApplicationHandlerStop


async def force_join_ptb_inline(update, context: CallbackContext):
    inline_query = update.inline_query
    user = update.effective_user
    if not inline_query or not user:
        return

    if await is_restricted(user.id):
        await inline_query.answer([], cache_time=0, is_personal=True)
        raise ApplicationHandlerStop

    if await is_force_joined(user.id):
        return

    await inline_query.answer(
        [],
        cache_time=0,
        is_personal=True,
        switch_pm_text="Join the required chats",
        switch_pm_parameter="force_join",
    )
    raise ApplicationHandlerStop


@shivuu.on_message(
    filters.regex(r"^/[A-Za-z_][A-Za-z0-9_]*(?:@[A-Za-z0-9_]+)?(?:\s|$)"),
    group=-1,
)
async def force_join_pyro_message(client, message):
    user = message.from_user
    if not user:
        return

    if await is_restricted(user.id):
        await _send_restricted_pyro_prompt(message)
        raise StopPropagation

    if await is_force_joined(user.id):
        return

    await _send_pyro_prompt(message)
    raise StopPropagation


@shivuu.on_callback_query(group=-1)
async def force_join_pyro_callback(client, callback_query):
    user = callback_query.from_user
    if not user:
        return

    if await is_restricted(user.id):
        await callback_query.answer(
            "Your access to this bot has been restricted.",
            show_alert=True,
        )
        raise StopPropagation

    if callback_query.data == "force_join:check":
        if await is_force_joined(user.id):
            await callback_query.answer(
                "Membership verified. You can use the bot now."
            )
            if callback_query.message:
                await callback_query.message.edit_reply_markup(None)
        else:
            await callback_query.answer(
                "Please join both chats first, then try again.",
                show_alert=True,
            )
        raise StopPropagation

    if await is_force_joined(user.id):
        return

    await callback_query.answer(
        "Join both required chats before using the bot.",
        show_alert=True,
    )
    if callback_query.message:
        await _send_pyro_prompt(callback_query.message)
    raise StopPropagation


application.add_handler(
    MessageHandler(telegram_filters.ALL, force_join_ptb_message, block=True),
    group=-1,
)
application.add_handler(
    CallbackQueryHandler(force_join_ptb_callback, block=True),
    group=-1,
)
application.add_handler(
    InlineQueryHandler(force_join_ptb_inline, block=True),
    group=-1,
)