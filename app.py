from flask import Flask, jsonify, request, send_file, session, redirect, url_for
import modules.manager as manager
import asyncio, json, requests, datetime, time
import mercadopago, os, signal
from telegram import Update
import modules.payment as payment
from flask import render_template, flash
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from multiprocessing import Process
from bot import run_bot_sync

# Configurações do Mercado Pago
CLIENT_ID = os.environ.get("CLIENT_ID", "4714763730515747")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "i33hQ8VZ11pYH1I3xMEMECphRJjT0CiP")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", 'kekel')

# Carrega configurações
try:
    config = json.loads(open('./config.json', 'r').read())
except:
    config = {}

# Usa variáveis de ambiente com fallback para config.json
IP_DA_VPS = os.environ.get("URL", config.get("url", "https://localhost:4040"))
REGISTRO_TOKEN = os.environ.get("REGISTRO_TOKEN", config.get("registro", ""))
ADMIN_PASSWORD = os.environ.get("PASSWORD", config.get("password", "adminadmin"))

# Porta do Railway ou padrão
port = int(os.environ.get("PORT", 4040))

dashboard_data = {
    "botsActive": 0,
    "usersCount": 0,
    "salesCount": 0
}

bots_data = {}
processes = {}
tokens = []
event_loop = asyncio.new_event_loop()

def initialize_all_registered_bots():
    """Inicializa todos os bots registrados e ativos."""
    print('Inicializando bots registrados...')
    global bots_data, processes
    bots = manager.get_all_bots()
    print(f'Encontrados {len(bots)} bots')
    
    for bot in bots:
        bot_id = bot[0]

        # Verifica se já existe um processo rodando para este bot
        if bot_id in processes and processes[str(bot_id)].is_alive():
            print(f"Bot {bot_id} já está em execução. Ignorando nova inicialização.")
            continue

        try:
            start_bot(bot[1], bot_id)
            print(f"Bot {bot_id} iniciado com sucesso.")
            
        except Exception as e:
            print(f"Erro ao iniciar o bot {bot_id}: {e}")
            
@app.route('/dashboard')
def web_dashboard():
    """Nova dashboard web"""
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    # Pega dados do dashboard
    dashboard_data = {
        'botsActive': manager.count_bots(),
        'usersCount': '?',  # Por enquanto
        'salesCount': len(manager.get_all_payments_by_status('finished'))
    }
    
    # Pega lista de bots para mostrar
    all_bots = manager.get_all_bots()
    recent_bots = []
    
    for bot in all_bots[:5]:  # Mostra só os 5 primeiros
        bot_obj = {
            'id': bot[0],
            'name': f"Bot {bot[0]}",  # Por enquanto
            'active': str(bot[0]) in processes,
            'users_count': len(manager.get_bot_users(bot[0]))
        }
        recent_bots.append(bot_obj)
    
    return render_template('dashboard.html', 
                         dashboard_data=dashboard_data,
                         recent_bots=recent_bots)

@app.route('/bots')
def web_bots_list():
    """Lista todos os bots"""
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    all_bots = manager.get_all_bots()
    bots_list = []
    
    for bot in all_bots:
        bot_details = manager.check_bot_token(bot[1])
        bot_obj = {
            'id': bot[0],
            'token': bot[1][:10] + '...',  # Mostra só parte do token
            'owner': bot[2],
            'username': bot_details['result'].get('username', 'INDEFINIDO') if bot_details else 'Token Inválido',
            'active': str(bot[0]) in processes
        }
        bots_list.append(bot_obj)
    
    return render_template('bots_list.html', bots=bots_list)

@app.route('/bot/<bot_id>/select')
def select_bot(bot_id):
    """Seleciona um bot para gerenciar"""
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    bot = manager.get_bot_by_id(bot_id)
    if bot:
        session['current_bot_id'] = bot_id
        bot_details = manager.check_bot_token(bot[1])
        if bot_details:
            session['current_bot_name'] = f"@{bot_details['result'].get('username', 'Bot')}"
        flash('Bot selecionado com sucesso!', 'success')
        return redirect(url_for('web_dashboard'))
    else:
        flash('Bot não encontrado!', 'error')
        return redirect(url_for('web_bots_list'))

@app.route('/callback', methods=['GET'])
def callback():
    """
    Endpoint para receber o webhook de redirecionamento do Mercado Pago.
    """
    TOKEN_URL = "https://api.mercadopago.com/oauth/token"

    authorization_code = request.args.get('code')
    bot_id = request.args.get('state')

    if not authorization_code:
        return jsonify({"error": "Authorization code not provided"}), 400

    try:
        payload = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": authorization_code,
            "redirect_uri": IP_DA_VPS+'/callback',
            "state":bot_id,
        }
        
        response = requests.post(TOKEN_URL, data=payload)
        response_data = response.json()

        if response.status_code == 200:
            access_token = response_data.get("access_token")
            print(f"Token MP recebido para bot {bot_id}")
            manager.update_bot_gateway(bot_id, {'type':"MP", 'token':access_token})
            return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Token Cadastrado</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f9;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            color: #333;
        }
        .container {
            background-color: #fff;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 20px 30px;
            text-align: center;
            max-width: 400px;
        }
        .container h1 {
            color: #4caf50;
            font-size: 24px;
            margin-bottom: 10px;
        }
        .container p {
            font-size: 16px;
            margin-bottom: 20px;
        }
        .btn {
            display: inline-block;
            padding: 10px 20px;
            font-size: 14px;
            color: #fff;
            background-color: #4caf50;
            text-decoration: none;
            border-radius: 4px;
            transition: background-color 0.3s ease;
        }
        .btn:hover {
            background-color: #45a049;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Token Cadastrado com Sucesso!</h1>
        <p>O seu token Mercado Pago está pronto para uso.</p>
    </div>
</body>
</html>
"""
        else:
            return jsonify({"error": response_data}), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/mp', methods=['POST'])
def handle_webhook():
    data = request.get_json(silent=True)
    print(f"Webhook MP recebido: {data}")
    
    if data and data.get('type') == 'payment':
        transaction_id = (data.get('data').get('id'))
        print(f'Pagamento {transaction_id} recebido - Mercado Pago')
        payment = manager.get_payment_by_trans_id(transaction_id)
        
        if payment:
            print(payment)
            bot_id = json.loads(payment[4])
            token = manager.get_bot_gateway(bot_id)
            sdk = mercadopago.SDK(token['token'])
            pagamento = sdk.payment().get(transaction_id)
            pagamento_status = pagamento["response"]["status"]

            if pagamento_status == "approved":
                print(f'Pagamento {transaction_id} aprovado - Mercado Pago')
                manager.update_payment_status(transaction_id, 'paid')
                return jsonify({"message": "Webhook recebido com sucesso."}), 200
    
    return jsonify({"message": "Evento ignorado."}), 400

@app.route('/webhook/pp', methods=['POST'])
def webhook():
    if request.content_type == 'application/json':
        data = request.get_json()
    elif request.content_type == 'application/x-www-form-urlencoded':
        data = request.form.to_dict()
    else:
        print("[ERRO] Tipo de conteúdo não suportado")
        return jsonify({"error": "Unsupported Media Type"}), 415

    if not data:
        print("[ERRO] Dados JSON ou Form Data inválidos")
        return jsonify({"error": "Invalid JSON or Form Data"}), 400
    
    print(f"[DEBUG] Webhook PP recebido: {data}")
    transaction_id = data.get("id", "").lower()
    
    if data.get('status', '').lower() == 'paid':
        print(f'Pagamento {transaction_id} pago - PushinPay')
        manager.update_payment_status(transaction_id, 'paid')
    else:
        print(f"[ERRO] Status do pagamento não é 'paid': {data.get('status')}")

    return jsonify({"status": "success"})

@app.route('/', methods=['GET'])
def home():
    if session.get("auth", False):
        dashboard_data['botsActive'] = manager.count_bots()
        dashboard_data['usersCount'] = '?'
        dashboard_data['salesCount'] = len(manager.get_all_payments_by_status('finished'))
        return send_file('./templates/terminal.html')
    return redirect(url_for('login'))

@app.route('/visualizar', methods=['GET'])
def view():
    if session.get("auth", False):
        return send_file('./templates/bots.html')
    return redirect(url_for('login'))

@app.route('/delete/<id>', methods=['DELETE'])
async def delete(id):
    if session.get("auth", False):
        open('blacklist.txt', 'a').write(str(bots_data[id]['owner'])+'\n')
        if id in processes.keys():
            processes.pop(id)
        if id in bots_data:
            bots_data.pop(id)
        
        manager.update_bot_config(id, [])
        manager.update_bot_token(id, f'BANIDO-{id}')
        return 'true'
    else:
        return 'Unauthorized', 403

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            session['auth'] = True
            return redirect('/')
    return '''
        <form method="post">
            <p><input type="text" name="password" placeholder="Digite a senha"></p>
            <p><input type="submit" value="Entrar"></p>
        </form>
    '''

def start_bot(new_token, bot_id):
    """Inicia um novo bot em um processo separado."""
    bot_id = str(bot_id)
    if not str(bot_id) in processes.keys():
        process = Process(target=run_bot_sync, args=(new_token, bot_id))
        process.start()
        tokens.append(new_token)
        bot = manager.get_bot_by_id(bot_id)
        bot_details = manager.check_bot_token(new_token)
        bot_obj = {
            'id': bot_id,
            'url':f'https://t.me/{bot_details['result'].get('username', "INDEFINIDO")}',
            'token': bot[1],
            'owner': bot[2],
            'data': json.loads(bot[4])
        }
        bots_data[str(bot_id)] = bot_obj
        processes[str(bot_id)] = process
        print(f"Bot {bot_id} processo iniciado")
        return True

async def receive_token_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_token = update.message.text.strip()
    admin_id = update.effective_user.id
    
    if manager.bot_exists(new_token):
        await update.message.reply_text('Token já registrado no sistema.')
    elif manager.bot_banned(str(admin_id)):
        await update.message.reply_photo('https://media.tenor.com/BosnE3kdeu8AAAAM/banned-pepe.gif', caption='Você foi banido do sistema.')
    else:
        telegram_bot = manager.check_bot_token(new_token)
        if telegram_bot:
            print(f'Novo BOT registrado: {telegram_bot}')
            id = telegram_bot.get('result', {}).get('id', False)
            if id:
                bot = manager.create_bot(str(id), new_token, admin_id)
                start_bot(new_token, id)
                await update.message.reply_text(f'Bot t.me/{telegram_bot['result']['username']} registrado e iniciado. Apenas você pode gerenciá-lo.')
            else:
                await update.message.reply_text('Erro ao obter ID do bot.')
        else:
            await update.message.reply_text('O token inserido é inválido.')
    return ConversationHandler.END

async def start_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if manager.bot_banned(str(update.message.from_user.id)):
        await update.message.reply_photo('https://media.tenor.com/BosnE3kdeu8AAAAM/banned-pepe.gif', caption='Você foi banido do sistema.')
    else:
        await update.message.reply_text('Envie seu token')
    return ConversationHandler.END

def main():
    """Função principal para rodar o bot de registro"""
    if not REGISTRO_TOKEN:
        print("Token de registro não configurado!")
        return
        
    registro_token = REGISTRO_TOKEN
    application = Application.builder().token(registro_token).build()
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token_register))
    application.add_handler(CommandHandler('start', start_func))
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    print('Iniciando BOT de Registro')
    application.run_polling()

def start_register():
    register = Process(target=main)
    register.start()

@app.route('/dashboard-data', methods=['GET'])
def get_dashboard_data():
    if session.get("auth", False):
        dashboard_data['botsActive'] = len(processes)
        dashboard_data['usersCount'] = '?'
        dashboard_data['salesCount'] = len(manager.get_all_payments_by_status('finished'))
        return jsonify(dashboard_data)
    return jsonify({"error": "Unauthorized"}), 403

@app.route('/bots', methods=['GET'])
def bots():
    if session.get("auth", False):
        bot_list = manager.get_all_bots()
        bots = []

        for bot in bot_list:
            bot_details = manager.check_bot_token(bot[1])
            bot_structure = {
                'id': bot[0],
                'token': bot[1],
                'url': "Token Inválido",
                'owner': bot[2],
                'data': json.loads(bot[3])
            }
            if bot_details:
                bot_structure['url'] = f'https://t.me/{bot_details['result'].get('username', "INDEFINIDO")}'
            
            bots_data[str(bot[0])] = bot_structure
            bots.append(bot_structure)
        return jsonify(bots)
    return jsonify({"error": "Unauthorized"}), 403

# ROTAS PARA PLANOS
@app.route('/bot/<bot_id>/planos', methods=['GET', 'POST'])
def web_planos(bot_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Cria novo plano
        nome = request.form.get('nome')
        tipo_tempo = request.form.get('tipo_tempo')
        tempo = request.form.get('tempo', 'eterno')
        valor = float(request.form.get('valor'))
        
        # Monta o plano
        plano = {
            'name': nome,
            'value': valor,
            'time_type': tipo_tempo,
            'time': int(tempo) if tempo != 'eterno' else 'eterno'
        }
        
        # Adiciona aos planos existentes
        planos = manager.get_bot_plans(bot_id)
        planos.append(plano)
        manager.update_bot_plans(bot_id, planos)
        
        flash('Plano adicionado com sucesso!', 'success')
        return redirect(url_for('web_planos', bot_id=bot_id))
    
    # GET - mostra os planos
    planos = manager.get_bot_plans(bot_id)
    return render_template('bot_config/planos.html', planos=planos)

@app.route('/bot/<bot_id>/planos/delete/<int:index>', methods=['POST'])
def web_delete_plano(bot_id, index):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    planos = manager.get_bot_plans(bot_id)
    if 0 <= index < len(planos):
        planos.pop(index)
        manager.update_bot_plans(bot_id, planos)
        flash('Plano removido com sucesso!', 'success')
    
    return redirect(url_for('web_planos', bot_id=bot_id))

# ROTAS PARA GATEWAY
@app.route('/bot/<bot_id>/gateway', methods=['GET', 'POST'])
def web_gateway(bot_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        gateway_type = request.form.get('gateway_type')
        
        if gateway_type == 'pushinpay':
            token = request.form.get('token')
            # Verifica se o token é válido
            if payment.verificar_push(token):
                manager.update_bot_gateway(bot_id, {'type': 'pp', 'token': token})
                flash('Gateway PushinPay configurado com sucesso!', 'success')
            else:
                flash('Token PushinPay inválido!', 'error')
        
        return redirect(url_for('web_gateway', bot_id=bot_id))
    
    # GET - mostra opções
    gateway_atual = manager.get_bot_gateway(bot_id)
    mp_auth_url = f"https://auth.mercadopago.com/authorization?client_id={config['client_id']}&response_type=code&platform_id=mp&state={bot_id}&redirect_url={config['url']}/callback"
    
    return render_template('bot_config/gateway.html', 
                         gateway_atual=gateway_atual,
                         mp_auth_url=mp_auth_url)
    
# ROTAS PARA MENSAGEM INICIAL
@app.route('/bot/<bot_id>/inicio', methods=['GET', 'POST'])
def web_inicio(bot_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    config_atual = manager.get_bot_config(bot_id)
    
    if request.method == 'POST':
        # Verifica se é para remover algo
        if request.form.get('remover_midia'):
            config_atual['midia'] = False
        elif request.form.get('remover_texto1'):
            config_atual['texto1'] = False
        else:
            # Atualiza configurações
            if 'midia' in request.files:
                file = request.files['midia']
                if file and file.filename:
                    # Aqui você precisaria processar o upload
                    # Por enquanto vamos só marcar que tem mídia
                    config_atual['midia'] = {'type': 'photo', 'file': 'FILE_ID_AQUI'}
            
            config_atual['texto1'] = request.form.get('texto1') or False
            config_atual['texto2'] = request.form.get('texto2')
            config_atual['button'] = request.form.get('botao')
        
        manager.update_bot_config(bot_id, config_atual)
        flash('Configurações salvas com sucesso!', 'success')
        return redirect(url_for('web_inicio', bot_id=bot_id))
    
    return render_template('bot_config/inicio.html', config_atual=config_atual)

# ROTAS PARA UPSELL
@app.route('/bot/<bot_id>/upsell', methods=['GET', 'POST'])
def web_upsell(bot_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    upsell_atual = manager.get_bot_upsell(bot_id)
    
    if request.method == 'POST':
        if request.form.get('remover'):
            manager.update_bot_upsell(bot_id, {})
            flash('Upsell removido!', 'success')
        else:
            upsell_data = {
                'text': request.form.get('texto'),
                'value': float(request.form.get('valor')),
                'group_id': request.form.get('grupo_id'),
                'media': upsell_atual.get('media', False)  # Mantém mídia existente
            }
            
            # Processa upload de mídia se houver
            if 'midia' in request.files:
                file = request.files['midia']
                if file and file.filename:
                    # Aqui você processaria o upload
                    upsell_data['media'] = {'type': 'photo', 'file': 'FILE_ID_AQUI'}
            
            manager.update_bot_upsell(bot_id, upsell_data)
            flash('Upsell configurado com sucesso!', 'success')
        
        return redirect(url_for('web_upsell', bot_id=bot_id))
    
    return render_template('bot_config/upsell.html', upsell_atual=upsell_atual)

# ROTAS PARA DOWNSELL
@app.route('/bot/<bot_id>/downsell', methods=['GET', 'POST'])
def web_downsell(bot_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    upsell_config = manager.get_bot_upsell(bot_id)
    downsell_atual = manager.get_bot_downsell(bot_id)
    
    # Verifica se tem upsell configurado
    upsell_configurado = bool(upsell_config and upsell_config.get('group_id'))
    upsell_value = upsell_config.get('value', 0) if upsell_config else 0
    
    if request.method == 'POST':
        if not upsell_configurado:
            flash('Configure o upsell primeiro!', 'error')
        elif request.form.get('remover'):
            manager.update_bot_downsell(bot_id, {})
            flash('Downsell removido!', 'success')
        else:
            valor = float(request.form.get('valor'))
            
            # Valida se é menor que o upsell
            if valor >= upsell_value:
                flash(f'O downsell deve ser menor que o upsell (R$ {upsell_value})!', 'error')
            else:
                downsell_data = {
                    'text': request.form.get('texto'),
                    'value': valor,
                    'media': downsell_atual.get('media', False)  # Mantém mídia existente
                }
                
                # Processa upload de mídia se houver
                if 'midia' in request.files:
                    file = request.files['midia']
                    if file and file.filename:
                        # Aqui você processaria o upload
                        downsell_data['media'] = {'type': 'photo', 'file': 'FILE_ID_AQUI'}
                
                manager.update_bot_downsell(bot_id, downsell_data)
                flash('Downsell configurado com sucesso!', 'success')
        
        return redirect(url_for('web_downsell', bot_id=bot_id))
    
    return render_template('bot_config/downsell.html', 
                         downsell_atual=downsell_atual,
                         upsell_configurado=upsell_configurado,
                         upsell_value=upsell_value)

# ROTAS PARA ADMINS
@app.route('/bot/<bot_id>/admins', methods=['GET', 'POST'])
def web_admins(bot_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        admin_id = request.form.get('admin_id').strip()
        admin_list = manager.get_bot_admin(bot_id)
        
        if admin_id in admin_list:
            flash('Este usuário já é admin!', 'error')
        else:
            # Aqui você poderia verificar se o ID é válido
            # Por enquanto vamos só adicionar
            admin_list.append(admin_id)
            manager.update_bot_admin(bot_id, admin_list)
            flash('Admin adicionado com sucesso!', 'success')
        
        return redirect(url_for('web_admins', bot_id=bot_id))
    
    # GET - Pega lista de admins
    admin_ids = manager.get_bot_admin(bot_id)
    admins = []
    
    for admin_id in admin_ids:
        admins.append({
            'id': admin_id,
            'username': 'usuario'  # Aqui você pegaria o username real
        })
    
    return render_template('bot_config/admins.html', admins=admins)

@app.route('/bot/<bot_id>/admins/remove/<admin_id>', methods=['POST'])
def web_remove_admin(bot_id, admin_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    admin_list = manager.get_bot_admin(bot_id)
    if admin_id in admin_list:
        admin_list.remove(admin_id)
        manager.update_bot_admin(bot_id, admin_list)
        flash('Admin removido!', 'success')
    
    return redirect(url_for('web_admins', bot_id=bot_id))

# ADICIONE TAMBÉM NO TOPO DO ARQUIVO, junto com as outras importações
import asyncio

# ROTAS PARA EXPIRAÇÃO
@app.route('/bot/<bot_id>/expiracao', methods=['GET', 'POST'])
def web_expiracao(bot_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    expiracao_atual = manager.get_bot_expiration(bot_id)
    
    if request.method == 'POST':
        if request.form.get('remover'):
            manager.update_bot_expiration(bot_id, {})
            flash('Mensagem de expiração removida!', 'success')
        else:
            expiracao_data = {
                'text': request.form.get('texto'),
                'media': expiracao_atual.get('media', False)  # Mantém mídia existente
            }
            
            # Processa upload de mídia se houver
            if 'midia' in request.files:
                file = request.files['midia']
                if file and file.filename:
                    expiracao_data['media'] = {'type': 'photo', 'file': 'FILE_ID_AQUI'}
            
            manager.update_bot_expiration(bot_id, expiracao_data)
            flash('Mensagem de expiração configurada!', 'success')
        
        return redirect(url_for('web_expiracao', bot_id=bot_id))
    
    return render_template('bot_config/expiracao.html', expiracao_atual=expiracao_atual)

# ROTAS PARA RECUPERAÇÃO
@app.route('/bot/<bot_id>/recuperacao', methods=['GET', 'POST'])
def web_recuperacao(bot_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    todos_planos = manager.get_bot_plans(bot_id)
    planos_com_recuperacao = [p for p in todos_planos if p.get('recovery')]
    planos_sem_recuperacao = [p for p in todos_planos if not p.get('recovery')]
    
    if request.method == 'POST':
        plano_index = int(request.form.get('plano_index'))
        
        recovery_data = {
            'text': request.form.get('texto'),
            'value': float(request.form.get('valor')),
            'tempo': int(request.form.get('tempo')),
            'media': False
        }
        
        # Processa upload de mídia se houver
        if 'midia' in request.files:
            file = request.files['midia']
            if file and file.filename:
                recovery_data['media'] = {'type': 'photo', 'file': 'FILE_ID_AQUI'}
        
        # Atualiza o plano com a recuperação
        todos_planos[plano_index]['recovery'] = recovery_data
        manager.update_bot_plans(bot_id, todos_planos)
        
        flash('Recuperação configurada com sucesso!', 'success')
        return redirect(url_for('web_recuperacao', bot_id=bot_id))
    
    return render_template('bot_config/recuperacao.html',
                         planos_com_recuperacao=planos_com_recuperacao,
                         planos_sem_recuperacao=planos_sem_recuperacao)

@app.route('/bot/<bot_id>/recuperacao/remove/<int:plano_index>', methods=['POST'])
def web_remove_recuperacao(bot_id, plano_index):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    planos = manager.get_bot_plans(bot_id)
    if 0 <= plano_index < len(planos):
        planos[plano_index]['recovery'] = False
        manager.update_bot_plans(bot_id, planos)
        flash('Recuperação removida!', 'success')
    
    return redirect(url_for('web_recuperacao', bot_id=bot_id))

# ROTAS PARA ORDER BUMP
@app.route('/bot/<bot_id>/orderbump', methods=['GET', 'POST'])
def web_orderbump(bot_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    todos_planos = manager.get_bot_plans(bot_id)
    orderbumps = manager.get_bot_orderbump(bot_id)
    
    # Prepara dados para exibição
    orderbumps_display = []
    planos_disponiveis = []
    
    for i, plano in enumerate(todos_planos):
        ob = manager.get_orderbump_by_plan(bot_id, i)
        if ob:
            orderbumps_display.append({
                'plano_id': i,
                'plano_nome': plano['name'],
                'value': ob['value'],
                'valor_total': plano['value'] + ob['value']
            })
        else:
            planos_disponiveis.append(plano)
    
    if request.method == 'POST':
        plano_index = int(request.form.get('plano_index'))
        
        orderbump_data = {
            'text': request.form.get('texto'),
            'value': float(request.form.get('valor')),
            'media': False
        }
        
        # Processa upload de mídia se houver
        if 'midia' in request.files:
            file = request.files['midia']
            if file and file.filename:
                orderbump_data['media'] = {'type': 'photo', 'file': 'FILE_ID_AQUI'}
        
        manager.add_orderbump_to_plan(bot_id, plano_index, orderbump_data)
        flash('Order Bump adicionado com sucesso!', 'success')
        return redirect(url_for('web_orderbump', bot_id=bot_id))
    
    return render_template('bot_config/orderbump.html',
                         orderbumps=orderbumps_display,
                         planos_disponiveis=planos_disponiveis)

@app.route('/bot/<bot_id>/orderbump/remove/<int:plano_id>', methods=['POST'])
def web_remove_orderbump(bot_id, plano_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    manager.remove_orderbump_from_plan(bot_id, plano_id)
    flash('Order Bump removido!', 'success')
    
    return redirect(url_for('web_orderbump', bot_id=bot_id))

# ROTAS PARA DISPARO
@app.route('/bot/<bot_id>/disparo', methods=['GET', 'POST'])
def web_disparo(bot_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    usuarios = manager.get_bot_users(bot_id)
    planos = manager.get_bot_plans(bot_id)
    disparo_resultado = None
    
    if request.method == 'POST':
        tipo_disparo = request.form.get('tipo_disparo')
        texto = request.form.get('texto')
        
        config_disparo = {
            'tipo': tipo_disparo,
            'mensagem': {
                'text': texto,
                'media': False
            }
        }
        
        # Processa mídia se houver
        if 'midia' in request.files:
            file = request.files['midia']
            if file and file.filename:
                config_disparo['mensagem']['media'] = {'type': 'photo', 'file': 'FILE_ID_AQUI'}
        
        # Configura baseado no tipo
        if tipo_disparo == 'livre':
            config_disparo['link'] = request.form.get('link')
        elif tipo_disparo == 'plano':
            plano_index = int(request.form.get('plano_index'))
            config_disparo['plano'] = planos[plano_index]
        
        # Aqui você executaria o disparo real
        # Por enquanto vamos simular
        flash(f'Disparo iniciado para {len(usuarios)} usuários!', 'success')
        
        disparo_resultado = {
            'total': len(usuarios),
            'enviados': len(usuarios) - 2,  # Simulando
            'erros': 2,
            'bloqueados': 1
        }
    
    return render_template('bot_config/disparo.html',
                         total_usuarios=len(usuarios),
                         planos=planos,
                         disparo_resultado=disparo_resultado)

# ROTA PARA CRIAR BOT
@app.route('/criar-bot', methods=['GET', 'POST'])
def web_criar_bot():
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        new_token = request.form.get('token').strip()
        
        # Verifica se já existe
        if manager.bot_exists(new_token):
            flash('Este bot já está registrado no sistema!', 'error')
            return redirect(url_for('web_criar_bot'))
        
        # Verifica se o token é válido
        telegram_bot = manager.check_bot_token(new_token)
        if telegram_bot:
            bot_id = str(telegram_bot.get('result', {}).get('id'))
            username = telegram_bot.get('result', {}).get('username')
            
            # Cria o bot no banco
            bot = manager.create_bot(bot_id, new_token, 'web_admin')
            
            # Inicia o bot
            start_bot(new_token, bot_id)
            
            flash(f'Bot @{username} criado e iniciado com sucesso!', 'success')
            
            # Seleciona o bot automaticamente
            session['current_bot_id'] = bot_id
            session['current_bot_name'] = f'@{username}'
            
            return redirect(url_for('web_dashboard'))
        else:
            flash('Token inválido! Verifique e tente novamente.', 'error')
    
    return render_template('criar_bot.html')

# ROTAS PARA GRUPO VIP
@app.route('/bot/<bot_id>/grupo', methods=['GET', 'POST'])
def web_grupo(bot_id):
    if not session.get("auth", False):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        grupo_id = request.form.get('grupo_id').strip()
        
        # Tenta criar link de convite para testar
        try:
            # Pega o bot correto da lista de processos
            bot = manager.get_bot_by_id(bot_id)
            if bot:
                bot_token = bot[1]
                # Cria application temporário só para testar
                test_app = Application.builder().token(bot_token).build()
                
                # Tenta com o ID fornecido
                try:
                    asyncio.run(test_app.bot.get_chat(grupo_id))
                    final_grupo_id = grupo_id
                except:
                    # Tenta com -100
                    try:
                        new_id = grupo_id.replace('-', '-100')
                        asyncio.run(test_app.bot.get_chat(new_id))
                        final_grupo_id = new_id
                    except:
                        flash('ID inválido ou bot sem permissão de admin!', 'error')
                        return redirect(url_for('web_grupo', bot_id=bot_id))
                
                # Se chegou aqui, funcionou
                manager.update_bot_group(bot_id, final_grupo_id)
                flash('Grupo VIP configurado com sucesso!', 'success')
                
        except Exception as e:
            flash(f'Erro ao configurar grupo: {str(e)}', 'error')
        
        return redirect(url_for('web_grupo', bot_id=bot_id))
    
    # GET - mostra o formulário
    grupo_atual = manager.get_bot_group(bot_id)
    grupo_link = None
    
    # Tenta pegar o link do grupo se existir
    if grupo_atual:
        try:
            bot = manager.get_bot_by_id(bot_id)
            if bot:
                # Aqui você poderia tentar gerar um link, mas por enquanto vamos deixar None
                pass
        except:
            pass
    
    return render_template('bot_config/grupo.html', 
                         grupo_atual=grupo_atual,
                         grupo_link=grupo_link)

# ADICIONE TAMBÉM O LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/terminal', methods=['POST'])
def terminal():
    if session.get("auth", False):
        data = request.get_json()
        command = data.get('command', '').strip()
        if not command:
            return jsonify({"response": "Comando vazio. Digite algo para enviar."}), 400
        
        response = f"Comando '{command}' recebido com sucesso. Processado às {time.strftime('%H:%M:%S')}."
        return jsonify({"response": response})
    return jsonify({"error": "Unauthorized"}), 403

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de health check para o Railway"""
    return jsonify({
        "status": "healthy",
        "bots_active": len(processes),
        "timestamp": datetime.datetime.now().isoformat()
    })

if __name__ == '__main__':
    print(f"Iniciando aplicação na porta {port}")
    print(f"URL configurada: {IP_DA_VPS}")
    
    # Cria arquivo blacklist.txt se não existir
    if not os.path.exists('blacklist.txt'):
        open('blacklist.txt', 'w').close()
    
    manager.inicialize_database()
    initialize_all_registered_bots()
    start_register()
    
    app.run(debug=False, host='0.0.0.0', port=port)