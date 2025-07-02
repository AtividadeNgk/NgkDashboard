import modules.manager as manager
import json, re, requests


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters, Updater, CallbackContext, ChatJoinRequestHandler
from telegram.error import BadRequest, Conflict

from modules.utils import process_command, is_admin, cancel, error_callback, error_message, escape_markdown_v2


def add_user_to_list(user, bot_id):

    print(user)
    print(bot_id)
    users = manager.get_bot_users(bot_id)
    print(users)
    if not user in users:
        users.append(user)
        manager.update_bot_users(bot_id, users)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = manager.get_bot_config(context.bot_data['id'])
    add_user_to_list(str(update.message.from_user.id), context.bot_data['id'])
    print(config)


    keyboard = [
        [InlineKeyboardButton(config['button'], callback_data='acessar_ofertas')]
    ]
    user_id = update.message.from_user.id
    reply_markup = InlineKeyboardMarkup(keyboard)
    if config.get('midia', False):
        if config['midia'].get('type') == 'photo':
            await context.bot.send_photo(chat_id=user_id, photo=config['midia']['file'])
        else:
            await context.bot.send_video(chat_id=user_id, video=config['midia']['file'])


    if config.get('texto1', False):
        await context.bot.send_message(chat_id=update.message.from_user.id, text=config['texto1'])


    await context.bot.send_message(chat_id=update.message.from_user.id, text=config['texto2'], reply_markup=reply_markup)
    return ConversationHandler.END