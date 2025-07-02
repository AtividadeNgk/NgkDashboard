import modules.manager as manager
import json, re, requests


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters, Updater, CallbackContext, ChatJoinRequestHandler
from telegram.error import BadRequest, Conflict

from modules.utils import process_command, is_admin, cancel, error_callback, error_message

RECUPERACAO_ESCOLHA, RECUPERACAO_MENSAGEM, RECUPERACAO_VALOR, RECUPERACAO_PLANO, RECUPERACAO_DELETAR, RECUPERACAO_TEMPO = range(6)




async def recuperaco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_check = await process_command(update, context)
    if not command_check:
        return ConversationHandler.END
    if not await is_admin(context, update.message.from_user.id):
        
        return ConversationHandler.END
    context.user_data['conv_state'] = "recuperação"

    plano_list = manager.get_bot_plans(context.bot_data['id'])

    has_rec = False
    all_rec = True
    for plan in plano_list:
        if plan.get('recovery', False):
            has_rec = True
        else:
            all_rec = False



    keyboard = []
    key_line = []
    if not all_rec:
        key_line.append(InlineKeyboardButton("➕ ADICIONAR", callback_data="adicionar"))
    if has_rec:
        key_line.append(InlineKeyboardButton("➖ REMOVER", callback_data="remover"))
    keyboard.append(key_line)
    keyboard.append([InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔄 Qual ação deseja fazer com as recuperações:", reply_markup=reply_markup)
    return RECUPERACAO_ESCOLHA




async def recuperacao_escolha(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.user_data['recovery_action'] = query.data
    if query.data == 'cancelar':
        await cancel(update, context)
        return ConversationHandler.END
    elif query.data == 'adicionar':
        context.user_data['plan_context'] = {
            'media':False,
            'text':False,
            'value':False,
            }
        await query.message.edit_text("💎 Envie a mensagem da recuperação ", reply_markup=reply_markup)
        return RECUPERACAO_MENSAGEM
    elif query.data == 'remover':
        planos = manager.get_bot_plans(context.bot_data['id'])
        keyboard_plans = []
        for plan_index in range(len(planos)):
            if planos[plan_index].get('recovery', False):
                keyboard_plans.append([InlineKeyboardButton(planos[plan_index]['name'], callback_data=f"planor_{plan_index}")])
        keyboard_plans.append([InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")])
        markup_plans = InlineKeyboardMarkup(keyboard_plans)
        await query.message.edit_text("🔄 Qual plano você deseja deletar a recuperação:", reply_markup=markup_plans, parse_mode='MarkdownV2')
        return RECUPERACAO_DELETAR




async def recuperacao_receber_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        print(update.message)
        save = {
            'media':False,
            'text':False,
            'link':False
            }
        if update.message.photo:
            photo_file = await update.message.photo[-1].get_file()
            save['media'] = {
                'file':photo_file.file_id,
                'type':'photo'
            }

        elif update.message.video:
            video_file = await update.message.video.get_file()
            save['media'] = {
                'file':video_file.file_id,
                'type':'video'
            }
        elif update.message.text:
            save['text'] = update.message.text
        else: 
            await update.message.reply_text("⛔ Somente texto ou midia:")
            return RECUPERACAO_MENSAGEM

        if update.message.caption:
            save['text'] = update.message.caption

        
        context.user_data['recovery_context'] = save
        keyboard = [[InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🔄 Qual valor deseja para a recuperação", reply_markup=reply_markup)
        return RECUPERACAO_VALOR
    except:
        await update.message.reply_text(text="⛔ Erro ao salvar recuperação", parse_mode='MarkdownV2')
        context.user_data['conv_state'] = False
        return ConversationHandler.END

async def recuperacao_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        await update.message.reply_text(text=f"⛔ Formato de midia invalido, por favor envie apenas textos")
        return RECUPERACAO_VALOR
    try:
        keyboard = [[InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        valor = float(update.message.text.replace(',','.'))
        if valor < 4:
            await update.message.reply_text("⛔ O valor deve ser positivo e maior que 4:", reply_markup=reply_markup)
            return RECUPERACAO_VALOR
        

        context.user_data['recovery_context']['value'] = valor
        recovery = context.user_data['recovery_context']
        keyboard = [[InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")]]
        markup_plans = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🔄 Em quantos minutos você deseja disparar a recuperação", reply_markup=markup_plans)

        return RECUPERACAO_TEMPO
    except Exception as e:
        print(e)
        await update.message.reply_text("⛔ Envie um valor numerico valido:")
        return RECUPERACAO_VALOR
    
async def recuperacao_tempo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        await update.message.reply_text(text=f"⛔ Formato de midia invalido, por favor envie apenas textos")
        return RECUPERACAO_TEMPO
    try:
        keyboard = [[InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        tempo = int(update.message.text)
        if tempo < 0:
            await update.message.reply_text("⛔ O valor deve ser positivo:", reply_markup=reply_markup)
            return RECUPERACAO_TEMPO
        

        context.user_data['recovery_context']['tempo'] = tempo
        recovery = context.user_data['recovery_context']
        planos = manager.get_bot_plans(context.bot_data['id'])
        keyboard_plans = []
        for plan_index in range(len(planos)):
            if not planos[plan_index].get('recovery', False):
                keyboard_plans.append([InlineKeyboardButton(planos[plan_index]['name'], callback_data=f"plano_{plan_index}")])
        keyboard_plans.append([InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")])
        markup_plans = InlineKeyboardMarkup(keyboard_plans)
        await update.message.reply_text(f"🔄 Qual plano deseja aplicar a recuperação", reply_markup=markup_plans)

        return RECUPERACAO_PLANO
    except Exception as e:
        print(e)
        await update.message.reply_text("⛔ Envie um valor numerico valido:")
        return RECUPERACAO_TEMPO
    

async def recuperacao_plano(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if query.data == 'cancelar':
        await cancel(update, context)
        return ConversationHandler.END
    plano_index = query.data.split('_')[-1]
    try:
        plano_index = int(plano_index)
        planos = manager.get_bot_plans(context.bot_data['id'])
        planos[plano_index]['recovery'] = context.user_data['recovery_context']
        manager.update_bot_plans(context.bot_data['id'] ,planos)
        await query.message.edit_text("✅ Recuperação atualizada com sucesso")
    except:
        await query.message.edit_text("⛔ Erro ao identificar ação, Todos os comandos cancelados")
    finally:
        context.user_data['conv_state'] = False
        return ConversationHandler.END
    
async def recuperacao_deletar(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if query.data == 'cancelar':
        await cancel(update, context)
        return ConversationHandler.END
    plano_index = query.data.split('_')[-1]
    try:
        plano_index = int(plano_index)
        planos = manager.get_bot_plans(context.bot_data['id'])
        planos[plano_index]['recovery'] = False
        manager.update_bot_plans(context.bot_data['id'] ,planos)
        await query.message.edit_text("✅ Recuperação atualizada com sucesso")
    except:
        await query.message.edit_text("⛔ Erro ao identificar ação, Todos os comandos cancelados")
    finally:
        context.user_data['conv_state'] = False
        return ConversationHandler.END
    


conv_handler_recuperacao = ConversationHandler(
    entry_points=[CommandHandler("recuperacao", recuperaco)],
    states={
        RECUPERACAO_ESCOLHA: [CallbackQueryHandler(recuperacao_escolha)],
        RECUPERACAO_MENSAGEM:[MessageHandler(~filters.COMMAND, recuperacao_receber_mensagem), CallbackQueryHandler(cancel)],
        RECUPERACAO_VALOR:[MessageHandler(~filters.COMMAND, recuperacao_valor), CallbackQueryHandler(cancel)],
        RECUPERACAO_TEMPO:[MessageHandler(~filters.COMMAND, recuperacao_tempo), CallbackQueryHandler(cancel)],
        RECUPERACAO_PLANO: [CallbackQueryHandler(recuperacao_plano)],
        RECUPERACAO_DELETAR: [CallbackQueryHandler(recuperacao_deletar)]
    },
    fallbacks=[CallbackQueryHandler(error_callback)]
    )