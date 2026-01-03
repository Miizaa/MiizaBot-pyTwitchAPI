import sys
import os
import json
import datetime
import asyncio
import time
import random
import winshell
import http.client
from win32com.client import Dispatch

# --- IMPORTAÇÕES DA INTERFACE GRÁFICA (PySide6) ---
# Usamos PySide6 para criar janelas, botões e a interface visual moderna.
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLineEdit, QPushButton, QTextEdit,
                               QTextBrowser, QLabel, QDialog, QTabWidget, QFormLayout,
                               QCheckBox, QSpinBox, QListWidget, QMessageBox,
                               QFrame, QSplitter, QComboBox, QInputDialog)
from PySide6.QtCore import Qt, Signal, QObject, Slot, QSize, QUrl
from PySide6.QtGui import QIcon, QFont, QColor, QPalette, QDesktopServices

# --- IMPORTAÇÕES DA TWITCH API ---
# Biblioteca para conectar e interagir com a Twitch.
from twitchAPI import helper
# Helper para corrigir problemas de async generator em versões específicas do Python/Lib
async def fixed_first(generator):
    items = [i async for i in generator]
    return items[0] if items else None
helper.first = fixed_first

from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.chat import Chat, ChatMessage, ChatEvent
from twitchAPI.type import AuthScope
import qasync # Integra o loop do asyncio (Python) com o loop de eventos do Qt (Interface)

# --- CONFIGURAÇÃO DE CAMINHOS E ARQUIVOS ---
# Verifica se está rodando como executável (congelado) ou script Python normal
if getattr(sys, 'frozen', False):
    # Se for .exe, a pasta base é onde o executável está
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Se for script, a pasta base é onde o arquivo .py está
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
PASTA_LOGS = os.path.join(BASE_DIR, 'logs')
SUB_LOG_FILE = os.path.join(PASTA_LOGS, 'subscription_history.txt')

# --- PERMISSÕES (SCOPES) ---
# Define o que o bot pode fazer na conta do usuário (ler chat, moderar, banir, etc).
SCOPES = [
    AuthScope.CHANNEL_MODERATE,
    AuthScope.CHAT_EDIT,
    AuthScope.CHAT_READ,
    AuthScope.MODERATION_READ,
    AuthScope.MODERATOR_MANAGE_BANNED_USERS,
    AuthScope.MODERATOR_MANAGE_CHAT_MESSAGES
]

# Função para encontrar recursos (ícones, etc) tanto no script quanto no .exe
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- GERENCIAMENTO DE CONFIGURAÇÃO ---
# Carrega o arquivo JSON ou cria um padrão se não existir.
def carregar_config():
    default_config = {
        "APP_ID": "",
        "APP_SECRET": "",
        "ACCESS_TOKEN": "",
        "REFRESH_TOKEN": "",
        "NOME_DO_BOT": "",
        "CANAIS": "",
        "PALAVRAS_ALERTA": [""],
        "COMANDOS_CUSTOM": {},
        "COOLDOWN_PADRAO": 10,
        "ATRASO_RESPOSTA_MIN": 2,
        "ATRASO_RESPOSTA_MAX": 5,
        "SAUDACOES": {
            "bom dia": {
                "respostas": ["Bom dia!"],
                "cooldown": 60,
                "gatilhos": ["bom dia"]}},
        "INICIAR_COM_WINDOWS": False
    }
    
    # Cria a pasta de logs se não existir
    if not os.path.exists(PASTA_LOGS):
        os.makedirs(PASTA_LOGS)

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            # Mescla com padrão para garantir que chaves novas existam
            for k, v in default_config.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except Exception:
        return default_config

def salvar_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

# --- LOGGING DE ARQUIVOS ---
# Salva histórico de Subs em arquivo de texto.
def registrar_inscricao(canal, usuario, tier, meses, mensagem=""):
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        info = f"[{timestamp}] CANAL: {canal} SUB: {usuario} | TIER: {tier} | MESES: {meses} | MSG: {mensagem}\n"
        
        if not os.path.exists(PASTA_LOGS):
            os.makedirs(PASTA_LOGS)
            
        with open(SUB_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(info)
    except Exception as e:
        print(f"Erro ao salvar sub: {e}")

# Cria atalho no Windows para iniciar com o sistema
def configurar_inicializacao_windows(ativar):
    startup_path = winshell.startup()
    shortcut_path = os.path.join(startup_path, "MiizaBot.lnk")
    
    if ativar:
        if not os.path.exists(shortcut_path):
            shortcutpath(shortcut_path)
    elif os.path.exists(shortcut_path):
        os.remove(shortcut_path)

def shortcutpath(shortcut_path):
    exe_path = sys.executable
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = exe_path
    shortcut.WorkingDirectory = os.path.dirname(exe_path)
    shortcut.IconLocation = exe_path
    shortcut.save()

# --- COMPONENTE DE LOG CUSTOMIZADO ---
# Subclasse de QTextBrowser para impedir que cliques em links naveguem para outra página.
# Isso evita que o log seja limpo ao clicar nos botões de moderação.
class LogBrowser(QTextBrowser):
    def setSource(self, name: QUrl):
        pass # Não faz nada, bloqueando a navegação padrão

# --- SINAIS DO BOT (COMUNICAÇÃO THREAD -> GUI) ---
# O Bot roda em uma thread separada da interface. Usamos sinais para atualizar a tela.
class BotSignals(QObject):
    log = Signal(str, str, str) # Mensagem, Tipo, Canal
    chat_message = Signal(dict) # Dados estruturados da mensagem de chat
    status = Signal(str)        # Status da conexão (ONLINE, OFFLINE)
    counter = Signal(int)       # Contador de mensagens
    stats_update = Signal(str, int) # Atualiza contadores de Subs
    pop_alert = Signal(str, str)    # Mostra popups de alerta

# --- LÓGICA PRINCIPAL DO BOT ---
class TwitchBotLogic:
    def __init__(self, signals: BotSignals):
        self.signals = signals
        self.twitch = None
        self.chat = None
        self.bot_user_id = None
        self.is_connected = False
        self.should_be_connected = False
        self.total_mensagens = 0
        self.last_command_usage = {}
        self.canais_conectados = set()
        self.stats = {"bans": 0, "timeouts": 0, "subs": 0}
        self.user_id_cache = {} # Cache para evitar buscar IDs na API repetidamente

    # Busca o ID numérico de um usuário/canal (necessário para banir/deletar)
    async def get_user_id(self, username):
        username = username.strip().lower()
        if username in self.user_id_cache:
            return self.user_id_cache[username]
        
        try:
            users_gen = self.twitch.get_users(logins=[username])
            user = await helper.first(users_gen)
            if user:
                self.user_id_cache[username] = user.id
                return user.id
        except Exception as e:
            print(f"Erro ao buscar ID de {username}: {e}")
        return None

    # Conecta à Twitch, autentica e entra nos canais
    async def connect(self, channels_list):
        self.should_be_connected = True
        cfg = carregar_config()
        try:
            self.signals.log.emit("Inicializando API Twitch...", "sistema", "")
            self.twitch = await Twitch(cfg["APP_ID"], cfg["APP_SECRET"])

            # Autenticação OAuth
            token = cfg.get("ACCESS_TOKEN")
            refresh = cfg.get("REFRESH_TOKEN")
            target_scopes = SCOPES
            
            auth = UserAuthenticator(self.twitch, target_scopes, force_verify=False)
            if not token or not refresh:
                token, refresh = await auth.authenticate()
            else:
                try:
                    await self.twitch.set_user_authentication(token, target_scopes, refresh)
                except Exception:
                    self.signals.log.emit("Token expirado, renovando...", "erro", "")
                    token, refresh = await auth.authenticate()

            await self.twitch.set_user_authentication(token, target_scopes, refresh)
            cfg["ACCESS_TOKEN"] = token
            cfg["REFRESH_TOKEN"] = refresh
            salvar_config(cfg)

            # Pega informações do próprio bot
            if users_list := [u async for u in self.twitch.get_users()]:
                user_info = users_list[0]
                self.bot_user_id = user_info.id
                self.user_id_cache[user_info.login.lower()] = user_info.id
                self.signals.log.emit(f"🔑 Logado como: {user_info.login.upper()}", "sistema", "")

            # Inicializa o Chat
            self.chat = await Chat(self.twitch)
            
            # Registra eventos (Mensagens, Subs, Conexão Pronta)
            self.chat.register_event(ChatEvent.MESSAGE, self.on_message)
            self.chat.register_event(ChatEvent.SUB, self.on_sub)
            self.chat.register_event(ChatEvent.READY, self.on_ready)
            
            self.chat.start()
            
            await asyncio.sleep(1)

            # Entra nos canais listados
            self.canais_conectados = set()
            for canal in channels_list:
                c_nome = canal.strip().lower()
                if not c_nome: continue
                try:
                    await self.chat.join_room(c_nome)
                    self.canais_conectados.add(c_nome)
                    self.signals.log.emit(f"💬 Entrou no canal #{c_nome}", "sistema", "")
                    asyncio.create_task(self.get_user_id(c_nome))
                except Exception as e:
                    self.signals.log.emit(f"Erro ao entrar em #{c_nome}: {e}", "erro", "")
            
            # Inicia tarefas de fundo
            asyncio.create_task(self.monitorar_conexao())
            asyncio.create_task(self.agendar_virada_ano())
            self.is_connected = True

        except Exception as e:
            self.signals.log.emit(f"ERRO CRÍTICO NA CONEXÃO: {str(e)}", "erro", "")
            self.signals.status.emit("ERRO")
            self.is_connected = False
            
    async def on_ready(self, event):
        self.is_connected = True 
        self.signals.status.emit("ONLINE")
        self.signals.log.emit("🟢 Conexão com o Chat estabelecida!", "sistema", "")
    
    # Tarefa que espera o Ano Novo para mandar mensagem
    async def agendar_virada_ano(self):
        try:
            while self.should_be_connected:
                agora = datetime.datetime.now()
                ano_que_vem = agora.year + 1
                data_alvo = datetime.datetime(ano_que_vem, 1, 1, 0, 0, 0)
                self.signals.log.emit(f"📅 Alvo do Ano Novo: {data_alvo}", "sistema", "")
                
                # Loop de espera fracionada para evitar overflow do timer
                while True:
                    if not self.should_be_connected: return
                    agora = datetime.datetime.now()
                    delta = (data_alvo - agora).total_seconds()
                    if delta <= 0:
                        break # Chegou a hora!
                    
                    # Dorme no máximo 1 hora por vez
                    tempo_sono = min(delta, 3600)
                    await asyncio.sleep(tempo_sono)
                
                # Envia mensagem festiva
                if self.is_connected and self.chat:
                    mensagem_festiva = f"🎆 FELIZ ANO NOVO DE {ano_que_vem}! 🎆 Que seja um ano incrível para todos nós! 🥂✨"
                    for canal in self.canais_conectados:
                        try:
                            await self.chat.send_message(canal, mensagem_festiva)
                            await asyncio.sleep(0.5) # Delay anti-spam
                        except Exception as e:
                            print(f"Erro envio ano novo {canal}: {e}")
                    self.signals.log.emit("🎉 Mensagens de Ano Novo enviadas!", "evento", "")
                await asyncio.sleep(60) 
        except Exception as e:
            print(f"Erro no agendamento de Ano Novo: {e}")
        
    # Monitora se a internet ou a conexão com a Twitch caiu e tenta reconectar
    async def monitorar_conexao(self):
        print(">>> MONITOR: Iniciado com sucesso.")
        while self.should_be_connected:
            try:
                lib_conectada = self.chat is not None and self.chat.is_connected()
                try:
                    # Verifica internet real pingando o Google
                    internet_ok = await asyncio.wait_for(
                        asyncio.to_thread(self.checar_internet_real), 
                        timeout=3.0
                    )
                except asyncio.TimeoutError:
                    print(">>> MONITOR: Timeout! Internet lenta ou caída.")
                    internet_ok = False
                except Exception:
                    internet_ok = False
                
                if lib_conectada and internet_ok:
                    if not self.is_connected:
                        self.is_connected = True
                        self.signals.status.emit("ONLINE")
                        self.signals.log.emit("🟢 Conexão restabelecida.", "sistema", "")
                elif self.is_connected:
                    self.is_connected = False
                    msg = "⚠️ Queda na Twitch" if internet_ok else "⚠️ Internet caiu!"
                    self.signals.status.emit("RECONECTANDO...")
                    self.signals.log.emit(msg, "erro", "")

            except Exception as e:
                print(f">>> MONITOR ERRO: {e}")
            await asyncio.sleep(3)

    def checar_internet_real(self):
        try:
            conn = http.client.HTTPConnection("www.google.com", timeout=3)
            conn.request("HEAD", "/")
            conn.close()
            return True
        except Exception:
            return False

    # Permite adicionar/remover canais sem reiniciar o bot
    async def atualizar_canais_dinamico(self, nova_lista_str):
        if not self.is_connected or self.chat is None: return
        novos_canais = {c.strip().lower() for c in nova_lista_str.split(',') if c.strip()}
        
        para_entrar = novos_canais - self.canais_conectados
        for c in para_entrar:
            try:
                await self.chat.join_room(c)
                self.canais_conectados.add(c)
                self.signals.log.emit(f"➡️ Entrou em #{c}", "sistema", "")
                asyncio.create_task(self.get_user_id(c))
            except Exception as e:
                self.signals.log.emit(f"Erro ao entrar em #{c}: {e}", "erro", "")
        
        para_sair = self.canais_conectados - novos_canais
        for c in para_sair:
            try:
                await self.chat.leave_room(c)
                self.canais_conectados.remove(c)
                self.signals.log.emit(f"⬅️ Saiu de #{c}", "sistema", "")
            except Exception as e:
                self.signals.log.emit(f"Erro ao sair de #{c}: {e}", "erro", "")
                
        cfg = carregar_config()
        cfg["CANAIS"] = nova_lista_str
        salvar_config(cfg)
        self.signals.log.emit("Lista de canais atualizada.", "sistema", "")

    async def close(self):
        self.should_be_connected = False 
        if not self.chat: return
        self.signals.status.emit("Desconectando...")
        self.chat.stop()
        if self.twitch: await self.twitch.close()
        self.is_connected = False
        self.signals.status.emit("OFFLINE")
        self.signals.log.emit("Bot desconectado manualmente.", "sistema", "")
        
    # --- MÉTODO DE INSCRIÇÕES HÍBRIDO ---
    # Detecta Subs e Presentes analisando a mensagem do sistema,
    # garantindo que o nome de quem pagou apareça corretamente.
    async def on_sub(self, sub):
        try:
            canal = sub.room.name
            
            # 1. Pega a mensagem do sistema crua
            system_msg = getattr(sub, 'system_message', '')
            if system_msg:
                system_msg = system_msg.replace(r'\s', ' ')
            
            # 2. Identifica o "Ator" (Quem pagou)
            usuario = "Anônimo"
            if system_msg:
                usuario = system_msg.split(' ')[0]
            elif hasattr(sub, 'chat_user') and sub.chat_user:
                usuario = sub.chat_user.display_name
            
            # 3. Detecta se é Gift e tenta achar o Receptor na string
            msg_lower = system_msg.lower()
            is_gift = "gift" in msg_lower or "presente" in msg_lower
            
            receptor = None
            if is_gift:
                if " to " in system_msg:
                    try:
                        parts = system_msg.split(" to ")
                        possible_name = parts[-1].strip()
                        if possible_name.endswith('.'): possible_name = possible_name[:-1]
                        receptor = possible_name
                    except Exception:
                        pass
                
                if not receptor and hasattr(sub, 'recipient') and sub.recipient:
                    receptor = sub.recipient.display_name

            tier = getattr(sub, 'sub_plan', 'Tier 1')
            msg_usuario = getattr(sub, 'sub_message', '') 
            
            self.stats['subs'] += 1
            self.signals.stats_update.emit('subs', self.stats['subs'])
            
            if is_gift:
                quem_recebeu = receptor or "Alguém"
                log_text = f"PRESENTE: De {usuario} -> Para {quem_recebeu}"
                self.signals.log.emit(f"🎁 {usuario} presenteou {quem_recebeu} ({tier})", "evento", canal)
                registrar_inscricao(canal, log_text, tier, 1, "Gift Sub")
            else:
                self.signals.log.emit(f"{canal}✨ Novo Sub: {usuario} ({tier})", "evento", canal)
                registrar_inscricao(canal, usuario, tier, 1, msg_usuario)
                
        except Exception as e:
            print(f"Erro ao processar sub: {e}")
            self.signals.log.emit(f"{canal}✨ Novo Sub (Erro parser): {str(e)}", "evento", canal)

    # --- MODERAÇÃO (BAN/TIMEOUT/DELETE) ---
    async def timeout_user(self, channel_name, target_user, duration):
        if not self.is_connected: return
        try:
            broadcaster_id = await self.get_user_id(channel_name)
            target_id = await self.get_user_id(target_user)
            
            if not broadcaster_id or not target_id:
                self.signals.log.emit(f"Erro ID: {channel_name}/{target_user}", "erro", channel_name)
                return

            await self.twitch.ban_user(
                broadcaster_id,
                self.bot_user_id,
                target_id,
                f"Timeout via MiizaBot ({duration}s)",
                duration=duration
            )
            self.signals.log.emit(f"⏳ Timeout aplicado em {target_user} ({duration}s)", "moderacao", channel_name)
        except Exception as e:
            self.signals.log.emit(f"Falha ao dar Timeout: {e}", "erro", channel_name)

    async def ban_user(self, channel_name, target_user):
        if not self.is_connected: return
        try:
            broadcaster_id = await self.get_user_id(channel_name)
            target_id = await self.get_user_id(target_user)
            if not broadcaster_id or not target_id:
                self.signals.log.emit(f"Erro ID: {channel_name}/{target_user}", "erro", channel_name)
                return

            await self.twitch.ban_user(broadcaster_id, self.bot_user_id, target_id, "Banido via MiizaBot")
            self.signals.log.emit(f"🚫 Ban aplicado em {target_user}", "moderacao", channel_name)
        except Exception as e:
            self.signals.log.emit(f"Falha ao Banir: {e}", "erro", channel_name)

    async def delete_message(self, channel_name, msg_id):
        if not self.is_connected: return
        try:
            broadcaster_id = await self.get_user_id(channel_name)
            if not broadcaster_id: return

            await self.twitch.delete_chat_message(
                broadcaster_id,
                self.bot_user_id,
                message_id=msg_id
            )
            self.signals.log.emit("🗑️ Mensagem deletada", "moderacao", channel_name)
        except Exception as e:
            self.signals.log.emit("Falha ao Deletar: {e}", "erro", channel_name)

    # Processa comandos customizados, de moderação e saudações
    async def processar_texto_comando(self, texto_original, canal, usuario, user_id, is_mod, responder_func, ignorar_saudacoes=True):
        # Sub-função para adicionar comandos (!addcmd)
        async def _handle_addcmd(cfg, texto_low, texto_original, canal_key):
            if not (is_mod and texto_low.startswith("!addcmd")):
                return False

            partes = texto_original.split(" ", 4)
            if len(partes) < 5:
                await responder_func("Sintaxe: !addcmd <nome> <segundos> <global/user> <resposta>")
                return True

            cmd_nome = partes[1].lower()
            if not cmd_nome.startswith('!'):
                cmd_nome = f"!{cmd_nome}"

            try:
                cd_tempo = int(partes[2])
                cd_tipo = partes[3].lower()
                resposta_cmd = partes[4]

                if cd_tipo not in ['global', 'user']:
                    await responder_func("Cooldown deve ser 'global' ou 'user'.")
                    return True

                if "COMANDOS_CUSTOM" not in cfg:
                    cfg["COMANDOS_CUSTOM"] = {}
                if canal_key not in cfg["COMANDOS_CUSTOM"]:
                    cfg["COMANDOS_CUSTOM"][canal_key] = {}

                cfg["COMANDOS_CUSTOM"][canal_key][cmd_nome] = {
                    "resposta": resposta_cmd,
                    "cooldown": cd_tempo,
                    "tipo": cd_tipo
                }
                salvar_config(cfg)
                self.signals.log.emit(
                    f"Comando {cmd_nome} salvo em #{canal} por {usuario}",
                    "sistema",
                    canal
                )
                await responder_func(f"Comando {cmd_nome} salvo para #{canal}!")
            except ValueError:
                await responder_func("Tempo deve ser número inteiro.")
            except Exception as e:
                self.signals.log.emit(f"Erro ao salvar comando: {e}", "erro", canal)
            return True

        # Sub-função para remover comandos (!delcmd)
        async def _handle_delcmd(cfg, texto_low, texto_original, canal_key):
            if not (is_mod and texto_low.startswith("!delcmd")):
                return False

            partes = texto_original.split(" ")
            if len(partes) < 2:
                await responder_func("Sintaxe: !delcmd <nome>")
                return True

            cmd_nome = partes[1].lower()
            if not cmd_nome.startswith('!'):
                cmd_nome = f"!{cmd_nome}"

            if "COMANDOS_CUSTOM" in cfg and canal_key in cfg["COMANDOS_CUSTOM"]:
                if cmd_nome in cfg["COMANDOS_CUSTOM"][canal_key]:
                    del cfg["COMANDOS_CUSTOM"][canal_key][cmd_nome]
                    salvar_config(cfg)
                    self.signals.log.emit(
                        f"Comando {cmd_nome} deletado de #{canal}",
                        "sistema",
                        canal
                    )
                    await responder_func(f"Comando {cmd_nome} removido deste canal.")
                else:
                    await responder_func(f"Comando {cmd_nome} não existe neste canal.")
            else:
                await responder_func("Não há comandos customizados neste canal.")
            return True

        # Sub-função para executar comandos customizados
        async def _handle_custom_command(cfg, texto_original, canal_key):
            if not texto_original.startswith('!'):
                return False

            partes_msg = texto_original.split(' ')
            comando_acionado = partes_msg[0].lower()

            custom_cmds_canal = cfg.get("COMANDOS_CUSTOM", {}).get(canal_key, {})

            if comando_acionado not in custom_cmds_canal:
                return False

            dados = custom_cmds_canal[comando_acionado]

            if isinstance(dados, str):
                resposta = dados
                cooldown = 10
                tipo_cd = "global"
            else:
                resposta = dados.get("resposta", "")
                cooldown = int(dados.get("cooldown", 10))
                tipo_cd = dados.get("tipo", "global")

            chave_cd = (
                f"{canal}_{comando_acionado}_{user_id}"
                if tipo_cd == "user"
                else f"{canal}_{comando_acionado}"
            )

            if time.time() - self.last_command_usage.get(chave_cd, 0) >= cooldown:
                await responder_func(resposta)
                self.last_command_usage[chave_cd] = time.time()
            return True

        # Sub-função para saudações automáticas (Bom dia, etc)
        async def _handle_saudacoes(cfg, texto_low):
            if ignorar_saudacoes:
                return True 

            saudacoes = cfg.get("SAUDACOES", {})
            for grp_id, dados in saudacoes.items():
                gatilhos = dados.get("gatilhos", [])
                if not any(texto_low.startswith(g.lower()) for g in gatilhos):
                    continue

                chave_cd = f"{canal}_{usuario}_{grp_id}"
                if time.time() - self.last_command_usage.get(chave_cd, 0) > dados.get("cooldown", 30):
                    resp = random.choice(dados.get("respostas", ["Olá!"]))
                    atraso = random.uniform(
                        cfg.get("ATRASO_RESPOSTA_MIN", 2),
                        cfg.get("ATRASO_RESPOSTA_MAX", 5)
                    )
                    await asyncio.sleep(atraso)
                    await responder_func(resp.format(user=usuario))
                    self.last_command_usage[chave_cd] = time.time()
                    return True
            return False

        try:
            cfg = carregar_config()
            texto_low = texto_original.lower()
            canal_key = canal.lower()

            # Processa na ordem: Add, Del, Custom, Saudações
            if await _handle_addcmd(cfg, texto_low, texto_original, canal_key):
                return

            if await _handle_delcmd(cfg, texto_low, texto_original, canal_key):
                return

            if await _handle_custom_command(cfg, texto_original, canal_key):
                return

            await _handle_saudacoes(cfg, texto_low)

        except Exception as e:
            print(f"Erro crítico no processamento de mensagem: {e}")
            self.signals.log.emit(f"Erro interno no bot: {e}", "erro", canal)

    async def send_message(self, message, channel):
        if self.is_connected and self.chat:
            await self.chat.send_message(channel, message)
            self.signals.log.emit(f"[BOT -> #{channel}]: {message}", "proprio", channel)
            async def reply_handler(resp_text):
                await self.chat.send_message(channel, resp_text)
                self.signals.log.emit(f"[BOT RESPOSTA]: {resp_text}", "proprio", channel)
            await self.processar_texto_comando(message, channel, "MIIZA", "BOT_ID", True, reply_handler, ignorar_saudacoes=True)

    async def on_message(self, msg: ChatMessage):
        # Ignora mensagens do próprio bot se necessário (descomente se quiser)
        if self.bot_user_id and msg.user.id == self.bot_user_id:
            return
        
        self.total_mensagens += 1
        self.signals.counter.emit(self.total_mensagens)
        
        cfg = carregar_config()
        texto = msg.text.strip()
        user = msg.user.display_name
        canal = msg.room.name
        is_mod = msg.user.mod or msg.user.name.lower() == canal
        
        # Verifica se é highlight (palavra de alerta)
        is_highlight = any(p.lower() in texto.lower() for p in cfg.get("PALAVRAS_ALERTA", []))
        
        # Prepara pacote de dados para enviar à interface
        chat_data = {
            "text": texto,
            "user": user,
            "channel": canal,
            "msg_id": msg.id,
            "highlight": is_highlight
        }
        self.signals.chat_message.emit(chat_data)
        
        async def reply_handler(resp_text):
            await msg.reply(resp_text)

        # Processa comandos
        await self.processar_texto_comando(texto, canal, user, msg.user.id, is_mod, reply_handler, ignorar_saudacoes=False)

# --- JANELA DE CONFIGURAÇÕES (UI) ---
class ModernConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações - MiizaBot")
        self.resize(800, 600)
        self.config = carregar_config()
        if "SAUDACOES" not in self.config: self.config["SAUDACOES"] = {}
        if "COMANDOS_CUSTOM" not in self.config: self.config["COMANDOS_CUSTOM"] = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.setup_general_tab()
        self.setup_commands_tab()
        self.setup_greetings_tab()
        
        # Botões de Salvar/Cancelar
        btn_box = QHBoxLayout()
        btn_save = QPushButton("Salvar Tudo e Fechar")
        btn_save.clicked.connect(self.salvar_tudo)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        # Estilos dos botões
        btn_save.setStyleSheet("""QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; border-radius: 4px; } QPushButton:hover { background-color: #45a049; } QPushButton:pressed { background-color: #3e8e41; }""")
        btn_cancel.setStyleSheet("""QPushButton { background-color: #f44336; color: white; padding: 10px; border-radius: 4px; } QPushButton:hover { background-color: #d32f2f; } QPushButton:pressed { background-color: #b71c1c; }""")
        
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    # Auxiliar para criar SpinBox com botões + e -
    def criar_spinbox_customizado(self, min_val, max_val, suffix=""):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSuffix(suffix)
        spin.setAlignment(Qt.AlignCenter)
        btn_minus = QPushButton("-")
        btn_minus.setObjectName("BtnSmall") 
        btn_minus.setFixedSize(30, 30)
        btn_minus.setCursor(Qt.PointingHandCursor)
        btn_minus.clicked.connect(lambda: spin.stepBy(-1))
        btn_plus = QPushButton("+")
        btn_plus.setObjectName("BtnSmall")
        btn_plus.setFixedSize(30, 30)
        btn_plus.setCursor(Qt.PointingHandCursor)
        btn_plus.clicked.connect(lambda: spin.stepBy(1))
        layout.addWidget(btn_minus)
        layout.addWidget(spin)
        layout.addWidget(btn_plus)
        return container, spin

    # Aba Geral (Credenciais e Delays)
    def setup_general_tab(self):
        tab_geral = QWidget()
        form_layout = QFormLayout(tab_geral)
        form_layout.setLabelAlignment(Qt.AlignRight)
        self.input_bot_name = QLineEdit(self.config.get("NOME_DO_BOT", ""))
        self.input_app_id = QLineEdit(self.config.get("APP_ID", ""))
        self.input_app_secret = QLineEdit(self.config.get("APP_SECRET", ""))
        self.input_app_secret.setEchoMode(QLineEdit.Password)
        self.input_alertas = QLineEdit(", ".join(self.config.get("PALAVRAS_ALERTA", [])))
        self.check_startup = QCheckBox("Iniciar com Windows")
        self.check_startup.setChecked(self.config.get("INICIAR_COM_WINDOWS", False))
        self.container_min, self.spin_min_delay = self.criar_spinbox_customizado(0, 60)
        self.spin_min_delay.setValue(int(self.config.get("ATRASO_RESPOSTA_MIN", 2)))
        self.container_max, self.spin_max_delay = self.criar_spinbox_customizado(1, 120)
        self.spin_max_delay.setValue(int(self.config.get("ATRASO_RESPOSTA_MAX", 5)))
        form_layout.addRow("Nome do Bot:", self.input_bot_name)
        form_layout.addRow("Client ID:", self.input_app_id)
        form_layout.addRow("Client Secret:", self.input_app_secret)
        form_layout.addRow("Palavras Alerta:", self.input_alertas)
        form_layout.addRow("Delay Mínimo (s):", self.container_min)
        form_layout.addRow("Delay Máximo (s):", self.container_max)
        form_layout.addRow(self.check_startup)
        self.tabs.addTab(tab_geral, "Geral")

    # Aba Comandos Customizados
    def setup_commands_tab(self):
        tab_cmds = QWidget()
        main_layout = QHBoxLayout(tab_cmds)
        
        # Painel Esquerdo: Lista
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        lbl_list = QLabel("Lista de Comandos")
        lbl_list.setStyleSheet("font-weight: bold; color: #50fa7b;")
        self.list_cmds = QListWidget()
        self.list_cmds.itemClicked.connect(self.carregar_comando_selecionado)
        
        btn_box = QHBoxLayout()
        btn_add = QPushButton("+")
        btn_add.clicked.connect(self.adicionar_comando)
        btn_del = QPushButton("-")
        btn_del.clicked.connect(self.remover_comando)
        
        # Estilos Add/Del
        style_add = """QPushButton { background-color: #4CAF50; font-weight: bold; color: white; border-radius: 4px; } QPushButton:hover { background-color: #45a049; } QPushButton:pressed { background-color: #3e8e41; }"""
        style_del = """QPushButton { background-color: #f44336; font-weight: bold; color: white; border-radius: 4px; } QPushButton:hover { background-color: #d32f2f; } QPushButton:pressed { background-color: #b71c1c; }"""
        btn_add.setStyleSheet(style_add)
        btn_del.setStyleSheet(style_del)
        
        btn_box.addWidget(btn_add)
        btn_box.addWidget(btn_del)
        left_layout.addWidget(lbl_list)
        left_layout.addWidget(self.list_cmds)
        left_layout.addLayout(btn_box)
        
        # Painel Direito: Edição
        right_frame = QFrame()
        right_frame.setStyleSheet("background-color: #252526; border-radius: 5px;")
        right_layout = QVBoxLayout(right_frame)
        self.lbl_cmd_editing = QLabel("Selecione um comando")
        self.lbl_cmd_editing.setStyleSheet("font-weight: bold; color: #8be9fd;")
        self.edit_cmd_response = QTextEdit()
        self.edit_cmd_response.setPlaceholderText("Resposta do comando...")
        self.edit_cmd_response.textChanged.connect(self.reset_cmd_save_button)
        row_cd = QHBoxLayout()
        self.container_cmd_cd, self.spin_cmd_cd = self.criar_spinbox_customizado(0, 99999, " seg")
        self.spin_cmd_cd.valueChanged.connect(self.reset_cmd_save_button)
        self.combo_cmd_type = QComboBox()
        self.combo_cmd_type.addItems(["global", "user"])
        self.combo_cmd_type.currentIndexChanged.connect(self.reset_cmd_save_button)
        row_cd.addWidget(QLabel("Cooldown:"))
        row_cd.addWidget(self.container_cmd_cd)
        row_cd.addWidget(QLabel("Tipo:"))
        row_cd.addWidget(self.combo_cmd_type)
        self.btn_update_cmd = QPushButton("Gravar Alterações do Comando")
        self.btn_update_cmd.setStyleSheet("""QPushButton { background-color: #6272a4; color: white; font-weight: bold; border-radius: 4px; } QPushButton:hover { background-color: #7080b5; } QPushButton:pressed { background-color: #536396; }""")
        self.btn_update_cmd.clicked.connect(self.atualizar_comando_memoria)
        right_layout.addWidget(self.lbl_cmd_editing)
        right_layout.addWidget(QLabel("Resposta:"))
        right_layout.addWidget(self.edit_cmd_response)
        right_layout.addLayout(row_cd)
        right_layout.addWidget(self.btn_update_cmd)
        main_layout.addWidget(left_frame, 1)
        main_layout.addWidget(right_frame, 2)
        self.tabs.addTab(tab_cmds, "Comandos Custom")
        self.refresh_command_list()

    # Aba Saudações
    def setup_greetings_tab(self):
        tab_saudacoes = QWidget()
        main_layout = QHBoxLayout(tab_saudacoes)
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        lbl_list = QLabel("Grupos de Saudações")
        lbl_list.setStyleSheet("font-weight: bold; color: #bd93f9;")
        self.list_groups = QListWidget()
        self.list_groups.itemClicked.connect(self.carregar_grupo_selecionado)
        btn_group_box = QHBoxLayout()
        btn_add = QPushButton("+")
        btn_add.clicked.connect(self.adicionar_grupo)
        btn_del = QPushButton("-")
        btn_del.clicked.connect(self.remover_grupo)
        btn_add.setStyleSheet("""QPushButton { background-color: #4CAF50; font-weight: bold; color: white; border-radius: 4px; } QPushButton:hover { background-color: #45a049; } QPushButton:pressed { background-color: #3e8e41; }""")
        btn_del.setStyleSheet("""QPushButton { background-color: #f44336; font-weight: bold; color: white; border-radius: 4px; } QPushButton:hover { background-color: #d32f2f; } QPushButton:pressed { background-color: #b71c1c; }""")
        btn_group_box.addWidget(btn_add)
        btn_group_box.addWidget(btn_del)
        left_layout.addWidget(lbl_list)
        left_layout.addWidget(self.list_groups)
        left_layout.addLayout(btn_group_box)
        right_frame = QFrame()
        right_frame.setStyleSheet("background-color: #252526; border-radius: 5px;")
        right_layout = QVBoxLayout(right_frame)
        self.lbl_editing = QLabel("Selecione um grupo")
        self.lbl_editing.setStyleSheet("font-weight: bold; color: #8be9fd;")
        self.edit_gatilhos = QLineEdit()
        self.edit_gatilhos.setPlaceholderText("Ex: oi, olá")
        self.edit_gatilhos.textChanged.connect(self.reset_save_button)
        self.container_cooldown, self.edit_cooldown = self.criar_spinbox_customizado(0, 999999, " seg")
        self.edit_cooldown.valueChanged.connect(self.reset_save_button)
        self.edit_respostas = QTextEdit()
        self.edit_respostas.setPlaceholderText("Digite uma resposta por linha...")
        self.edit_respostas.textChanged.connect(self.reset_save_button)
        self.btn_update_group = QPushButton("Gravar Alterações do Grupo")
        self.btn_update_group.setStyleSheet("""QPushButton { background-color: #6272a4; color: white; font-weight: bold; border-radius: 4px; } QPushButton:hover { background-color: #7080b5; } QPushButton:pressed { background-color: #536396; }""")
        self.btn_update_group.clicked.connect(self.atualizar_grupo_memoria)
        right_layout.addWidget(self.lbl_editing)
        right_layout.addWidget(QLabel("Gatilhos:"))
        right_layout.addWidget(self.edit_gatilhos)
        right_layout.addWidget(QLabel("Cooldown Global:"))
        right_layout.addWidget(self.container_cooldown)
        right_layout.addWidget(QLabel("Respostas (Randomizadas):"))
        right_layout.addWidget(self.edit_respostas)
        right_layout.addWidget(self.btn_update_group)
        main_layout.addWidget(left_frame, 1)
        main_layout.addWidget(right_frame, 2)
        self.tabs.addTab(tab_saudacoes, "Saudações")
        self.refresh_group_list()

    def refresh_command_list(self):
        self.list_cmds.clear()
        for canal, comandos in self.config.get("COMANDOS_CUSTOM", {}).items():
            for cmd_key in comandos.keys():
                self.list_cmds.addItem(f"[{canal}] {cmd_key}")

    def carregar_comando_selecionado(self, item):
        texto = item.text() 
        if "]" not in texto: return
        
        partes = texto.split("] ")
        canal = partes[0].replace("[", "")
        cmd_key = partes[1].replace("!", "")
        
        self.current_editing_cmd = (canal, cmd_key)

        data = self.config["COMANDOS_CUSTOM"].get(canal, {}).get(f"!{cmd_key}", {}) or self.config["COMANDOS_CUSTOM"].get(canal, {}).get(cmd_key, {})

        self.block_cmd_signals(True)
        self.lbl_cmd_editing.setText(f"Editando: {texto}")
        
        if isinstance(data, str):
            self.edit_cmd_response.setPlainText(data)
            self.spin_cmd_cd.setValue(10)
            self.combo_cmd_type.setCurrentText("global")
        else:
            self.edit_cmd_response.setPlainText(data.get("resposta", ""))
            self.spin_cmd_cd.setValue(int(data.get("cooldown", 10)))
            self.combo_cmd_type.setCurrentText(data.get("tipo", "global"))
        
        self.block_cmd_signals(False)
        self.reset_cmd_save_button()

    def atualizar_comando_memoria(self):
        if not hasattr(self, 'current_editing_cmd') or not self.current_editing_cmd:
            return
        
        canal, cmd_key = self.current_editing_cmd
        full_key = "!" + cmd_key.replace("!", "")

        novo_dado = {
            "resposta": self.edit_cmd_response.toPlainText(),
            "cooldown": self.spin_cmd_cd.value(),
            "tipo": self.combo_cmd_type.currentText()
        }
        
        if "COMANDOS_CUSTOM" not in self.config: self.config["COMANDOS_CUSTOM"] = {}
        if canal not in self.config["COMANDOS_CUSTOM"]: self.config["COMANDOS_CUSTOM"][canal] = {}
        
        self.config["COMANDOS_CUSTOM"][canal][full_key] = novo_dado
        
        btn = self.sender()
        btn.setText("Salvo!")
        btn.setStyleSheet("background-color: #50fa7b; color: #282a36; font-weight: bold; border-radius: 4px;")

    def adicionar_comando(self):
        canal, ok1 = QInputDialog.getText(self, 'Canal Alvo', 'Para qual canal? (ex: miiza)')
        if not ok1 or not canal: return
        
        cmd_nome, ok2 = QInputDialog.getText(self, 'Novo Comando', 'Nome do comando (ex: !insta):')
        if ok2 and cmd_nome:
            canal = canal.lower().strip()
            cmd_nome = cmd_nome.strip().lower()
            if not cmd_nome.startswith('!'): cmd_nome = "!" + cmd_nome
            
            if "COMANDOS_CUSTOM" not in self.config: self.config["COMANDOS_CUSTOM"] = {}
            if canal not in self.config["COMANDOS_CUSTOM"]: self.config["COMANDOS_CUSTOM"][canal] = {}
            
            self.config["COMANDOS_CUSTOM"][canal][cmd_nome] = {
                "resposta": "Edite a resposta...", "cooldown": 10, "tipo": "global"
            }
            self.refresh_command_list()

    def remover_comando(self):
        curr = self.list_cmds.currentItem()
        if curr and hasattr(self, 'current_editing_cmd'):
            canal, cmd_key = self.current_editing_cmd
            full_key = "!" + cmd_key.replace("!", "")
            
            if QMessageBox.question(self, "Excluir", f"Excluir {full_key} do canal {canal}?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes and (canal in self.config["COMANDOS_CUSTOM"] and full_key in self.config["COMANDOS_CUSTOM"][canal]):
                del self.config["COMANDOS_CUSTOM"][canal][full_key]
                self.refresh_command_list()
                self.edit_cmd_response.clear()
                self.lbl_cmd_editing.setText("Selecione um comando")

    def reset_cmd_save_button(self):
        self.btn_update_cmd.setText("Gravar Alterações do Comando")
        self.btn_update_cmd.setStyleSheet("""QPushButton { background-color: #6272a4; color: white; font-weight: bold; border-radius: 4px; } QPushButton:hover { background-color: #7080b5; } QPushButton:pressed { background-color: #536396; }""")

    def block_cmd_signals(self, block):
        self.edit_cmd_response.blockSignals(block)
        self.spin_cmd_cd.blockSignals(block)
        self.combo_cmd_type.blockSignals(block)

    def refresh_group_list(self):
        self.list_groups.clear()
        for key in self.config["SAUDACOES"].keys():
            self.list_groups.addItem(key)

    def carregar_grupo_selecionado(self, item):
        group_id = item.text()
        data = self.config["SAUDACOES"].get(group_id, {})
        self.edit_gatilhos.blockSignals(True)
        self.edit_cooldown.blockSignals(True)
        self.edit_respostas.blockSignals(True)
        self.lbl_editing.setText(f"Editando: {group_id}")
        self.edit_gatilhos.setText(", ".join(data.get("gatilhos", [])))
        self.edit_cooldown.setValue(int(data.get("cooldown", 30)))
        self.edit_respostas.setPlainText("\n".join(data.get("respostas", [])))
        self.edit_gatilhos.blockSignals(False)
        self.edit_cooldown.blockSignals(False)
        self.edit_respostas.blockSignals(False)
        self.reset_save_button()

    def atualizar_grupo_memoria(self):
        curr_item = self.list_groups.currentItem()
        if not curr_item: return
        group_id = curr_item.text()
        self.config["SAUDACOES"][group_id] = {
            "gatilhos": [x.strip() for x in self.edit_gatilhos.text().split(',') if x.strip()],
            "respostas": [x for x in self.edit_respostas.toPlainText().split('\n') if x.strip()],
            "cooldown": self.edit_cooldown.value()
        }
        btn = self.sender()
        btn.setText("Salvo!")
        btn.setStyleSheet("background-color: #50fa7b; color: #282a36; font-weight: bold; border-radius: 4px;")

    def reset_save_button(self):
        self.btn_update_group.setText("Gravar Alterações do Grupo")
        self.btn_update_group.setStyleSheet("""QPushButton { background-color: #6272a4; color: white; font-weight: bold; border-radius: 4px; } QPushButton:hover { background-color: #7080b5; } QPushButton:pressed { background-color: #536396; }""")

    def adicionar_grupo(self):
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, 'Novo Grupo', 'Nome do ID do grupo:')
        if ok and text:
            text = text.strip().replace(" ", "_")
            if text not in self.config["SAUDACOES"]:
                self.config["SAUDACOES"][text] = {"gatilhos": [text], "respostas": ["Olá!"], "cooldown": 30}
                self.refresh_group_list()

    def remover_grupo(self):
        if curr := self.list_groups.currentItem():
            group_id = curr.text()
            if QMessageBox.question(self, "Confirmar", f"Excluir '{group_id}'?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
                del self.config["SAUDACOES"][group_id]
                self.refresh_group_list()
                self.edit_gatilhos.clear()
                self.edit_respostas.clear()

    def salvar_tudo(self):
        self.config["NOME_DO_BOT"] = self.input_bot_name.text()
        self.config["APP_ID"] = self.input_app_id.text()
        self.config["APP_SECRET"] = self.input_app_secret.text()
        self.config["PALAVRAS_ALERTA"] = [x.strip() for x in self.input_alertas.text().split(",") if x.strip()]
        self.config["INICIAR_COM_WINDOWS"] = self.check_startup.isChecked()
        self.config["ATRASO_RESPOSTA_MIN"] = self.spin_min_delay.value()
        self.config["ATRASO_RESPOSTA_MAX"] = self.spin_max_delay.value()
        salvar_config(self.config)
        configurar_inicializacao_windows(self.config["INICIAR_COM_WINDOWS"])
        self.accept()

# --- JANELA PRINCIPAL (MAIN WINDOW) ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MiizaBot Pro")
        self.resize(900, 700)

        # Inicializa lógica e sinais
        self.signals = BotSignals()
        self.bot_logic = TwitchBotLogic(self.signals)

        # Conecta sinais às funções da interface
        self.signals.log.connect(self.append_log)
        self.signals.chat_message.connect(self.append_chat_message)
        self.signals.status.connect(self.update_status)
        self.signals.counter.connect(self.update_counter)
        self.signals.stats_update.connect(self.update_stats)
        self.signals.pop_alert.connect(lambda t, m: QMessageBox.warning(self, t, m))

        self.setup_ui()
        self.setup_style()

        # Carrega configs iniciais na tela
        cfg = carregar_config()
        self.entry_canais.setText(cfg.get("CANAIS", ""))
        self.input_channel_target.setText(cfg.get("CANAIS", "").split(',')[0].strip())

    # Configuração da Interface (Widgets)
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Barra Superior (Canais e Conectar)
        top_frame = QFrame()
        top_frame.setObjectName("Card")
        top_layout = QHBoxLayout(top_frame)
        self.entry_canais = QLineEdit()
        self.entry_canais.setPlaceholderText("Canais para monitorar (ex: canal1, canal2)")
        self.entry_canais.textChanged.connect(self.verificar_mudanca_canais)
        self.btn_connect = QPushButton("CONECTAR")
        self.btn_connect.setObjectName("BtnConnect")
        self.btn_connect.setCursor(Qt.PointingHandCursor)
        self.btn_connect.clicked.connect(self.toggle_connection)
        self.btn_config = QPushButton("⚙️")
        self.btn_config.setFixedSize(40, 30)
        self.btn_config.clicked.connect(self.open_config)
        top_layout.addWidget(QLabel("Canais:"))
        top_layout.addWidget(self.entry_canais)
        top_layout.addWidget(self.btn_connect)
        top_layout.addWidget(self.btn_config)
        main_layout.addWidget(top_frame)

        # Estatísticas (Subs)
        stats_layout = QHBoxLayout()
        self.lbl_subs = self.create_stat_card("💎 Subs", "0", "#bd93f9")
        stats_layout.addWidget(self.lbl_subs)
        stats_layout.addStretch() 
        main_layout.addLayout(stats_layout)

        # Log Principal
        self.log_viewer = LogBrowser()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setOpenLinks(False) # IMPORTANTE: Evita limpar tela ao clicar links
        self.log_viewer.setOpenExternalLinks(False)
        self.log_viewer.anchorClicked.connect(self.handle_link_click)
        self.log_viewer.setObjectName("LogViewer")
        main_layout.addWidget(self.log_viewer)

        # Barra de Status
        info_layout = QHBoxLayout()
        self.lbl_status = QLabel("Status: OFFLINE")
        self.lbl_status.setStyleSheet("color: #777; font-weight: bold;")
        self.lbl_counter = QLabel("Msgs: 0")
        self.lbl_counter.setStyleSheet("color: #777;")
        info_layout.addWidget(self.lbl_status)
        info_layout.addStretch()
        info_layout.addWidget(self.lbl_counter)
        main_layout.addLayout(info_layout)

        # Barra de Ação (Enviar mensagem manual)
        action_frame = QFrame()
        action_frame.setObjectName("Card")
        action_layout = QHBoxLayout(action_frame)
        self.input_channel_target = QLineEdit()
        self.input_channel_target.setPlaceholderText("Canal alvo")
        self.input_channel_target.setFixedWidth(100)
        self.input_message = QLineEdit()
        self.input_message.setPlaceholderText("Enviar mensagem como bot...")
        self.input_message.returnPressed.connect(self.send_message_action)
        btn_send = QPushButton("ENVIAR")
        btn_send.setObjectName("BtnAction")
        btn_send.clicked.connect(self.send_message_action)
        btn_logs = QPushButton("📂 Logs")
        btn_logs.clicked.connect(lambda: os.startfile(os.path.abspath(PASTA_LOGS)))
        action_layout.addWidget(btn_logs)
        action_layout.addWidget(self.input_channel_target)
        action_layout.addWidget(self.input_message)
        action_layout.addWidget(btn_send)
        main_layout.addWidget(action_frame)

    # Cria cartões visuais para stats
    def create_stat_card(self, title, value, color):
        frame = QFrame()
        frame.setObjectName("StatCard")
        frame.setStyleSheet(f"QFrame#StatCard {{ background-color: #252526; border-left: 5px solid {color}; border-radius: 5px; }}")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(15, 8, 15, 8)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11pt;")
        lbl_val = QLabel(value)
        lbl_val.setObjectName("Value")
        lbl_val.setStyleSheet("color: white; font-weight: bold; font-size: 12pt;")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_val)
        layout.addStretch() 
        return frame

    # Configuração do CSS (Estilo)
    def setup_style(self):
        qss = """
        QMainWindow { background-color: #1e1e1e; }
        QWidget { color: #e0e0e0; font-family: 'Segoe UI', Arial; font-size: 10pt; }
        QFrame#Card { background-color: #2d2d2d; border-radius: 8px; border: 1px solid #3d3d3d; }
        QFrame#StatCard { background-color: #252526; border-radius: 5px; border: 1px solid #3d3d3d; border-left-width: 5px; }
        QLineEdit, QTextEdit, QComboBox { background-color: #3c3c3c; border: 1px solid #555; border-radius: 4px; padding: 5px; color: white; }
        QComboBox::drop-down { border: none; }
        QSpinBox { background-color: #3c3c3c; border: 1px solid #555; border-radius: 4px; padding: 5px; color: white; }
        QPushButton { background-color: #444; border: none; padding: 6px 12px; border-radius: 4px; }
        QPushButton:hover { background-color: #555; }
        QPushButton:pressed { background-color: #333; }
        QPushButton#BtnSmall { background-color: #444; border: 1px solid #555; font-weight: bold; }
        QPushButton#BtnConnect { background-color: #4CAF50; color: white; font-weight: bold; }
        QPushButton#BtnAction { background-color: #2196F3; color: white; font-weight: bold; }
        QPushButton#BtnAction:hover { background-color: #42A5F5; }
        QTextBrowser#LogViewer { background-color: #121212; border: 1px solid #333; font-family: 'Consolas', monospace; }
        """
        self.setStyleSheet(qss)

    def verificar_mudanca_canais(self):
        if not self.bot_logic.is_connected:
            self.btn_connect.setText("CONECTAR")
            self.btn_connect.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; } QPushButton:hover { background-color: #45a049; }")
            return
        texto_input = self.entry_canais.text().lower()
        set_input = {c.strip() for c in texto_input.split(',') if c.strip()}
        set_conectados = self.bot_logic.canais_conectados
        if set_input != set_conectados:
            self.btn_connect.setText("ATUALIZAR CANAIS")
            self.btn_connect.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; } QPushButton:hover { background-color: #0b7dda; }")
        else:
            self.btn_connect.setText("DESCONECTAR")
            self.btn_connect.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; } QPushButton:hover { background-color: #d32f2f; }")

    @Slot()
    def toggle_connection(self):
        texto_botao = self.btn_connect.text()
        canais_str = self.entry_canais.text()
        if texto_botao == "ATUALIZAR CANAIS":
            asyncio.ensure_future(self.bot_logic.atualizar_canais_dinamico(canais_str))
            self.btn_connect.setText("DESCONECTAR")
            self.btn_connect.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
            return
        if not self.bot_logic.is_connected:
            if not canais_str:
                QMessageBox.warning(self, "Aviso", "Digite pelo menos um canal.")
                return
            cfg = carregar_config()
            cfg["CANAIS"] = canais_str
            salvar_config(cfg)
            self.btn_connect.setText("CONECTANDO...")
            self.btn_connect.setEnabled(False)
            asyncio.ensure_future(self.bot_logic.connect(canais_str.split(',')))
        else:
            asyncio.ensure_future(self.bot_logic.close())

    @Slot()
    def send_message_action(self):
        msg = self.input_message.text()
        canal = self.input_channel_target.text()
        if msg and canal:
            asyncio.ensure_future(self.bot_logic.send_message(msg, canal))
            self.input_message.clear()

    @Slot()
    def open_config(self):
        dialog = ModernConfigDialog(self)
        dialog.exec()

    # Gera cores consistentes para nomes de usuários (Hash)
    def get_consistent_color(self, string):
        if not string: return "#ffffff"
        colors = [
            "#FFB6C1", "#87CEFA", "#98FB98", "#DDA0DD", "#F0E68C", 
            "#FF7F50", "#00FFFF", "#ADFF2F", "#FF69B4", "#7B68EE",
            "#40E0D0", "#FFA07A", "#BA55D3", "#66CDAA", "#FFD700"
        ]
        hash_val = sum(ord(c) for c in string) 
        return colors[hash_val % len(colors)]

    # Trata cliques nos botões de moderação do chat (Ban, Timeout, Delete)
    @Slot(QUrl)
    def handle_link_click(self, url):
        link = url.toString()
        if ":" not in link: return
        parts = link.split(":")
        action = parts[0]
        target = parts[1]
        channel = parts[2]

        if action == "ban":
            resp = QMessageBox.question(self, "Confirmar Ban", f"Tem certeza que deseja BANIR {target} em #{channel}?", QMessageBox.Yes | QMessageBox.No)
            if resp == QMessageBox.Yes:
                asyncio.ensure_future(self.bot_logic.ban_user(channel, target))
        elif action == "delete":
            asyncio.ensure_future(self.bot_logic.delete_message(channel, target))
        elif action == "timeout":
            duracao, ok = QInputDialog.getInt(self, "Timeout", f"Tempo de Timeout para {target} (segundos):", 600, 1)
            if ok:
                asyncio.ensure_future(self.bot_logic.timeout_user(channel, target, duracao))
        
    # Formata e exibe mensagens de chat com botões e cores
    @Slot(dict)
    def append_chat_message(self, data):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        user = data['user']
        channel = data['channel']
        text = data['text']
        msg_id = data['msg_id']
        is_high = data['highlight']
        chan_color = self.get_consistent_color(channel)
        user_color = self.get_consistent_color(user)

        # Botões de ação (links falsos que acionam handle_link_click)
        btn_to = f'<a href="timeout:{user}:{channel}" style="text-decoration:none; color:#FFB86C;">[⏳]</a>'
        btn_ban = f'<a href="ban:{user}:{channel}" style="text-decoration:none; color:#FF5555;">[🚫]</a>'
        btn_del = f'<a href="delete:{msg_id}:{channel}" style="text-decoration:none; color:#6272a4;">[🗑️]</a>'
        
        html_msg = (
            f'<span style="color:#6272a4">[{timestamp}]</span> '
            f'<span style="color:{chan_color}; font-weight:bold;">[#{channel}]</span> '
            f'{btn_to} {btn_ban} {btn_del} '
            f'<span style="color:{user_color}; font-weight:bold;">{user}</span>: '
            f'<span style="color:#e0e0e0;">{text}</span>'
        )

        if is_high:
            html_msg = html_msg.replace('style="color:#e0e0e0;"', 'style="background-color: #44475a; color: #f1fa8c; font-weight:bold;"')

        self.log_viewer.append(html_msg)
        self.save_to_file(f"[#{channel}] {user}: {text}", "CHAT", channel)

    # Log de sistema
    @Slot(str, str, str)
    def append_log(self, message, type_log, channel):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        colors = {"sistema": "#50fa7b", "erro": "#ff5555", "moderacao": "#ffb86c", "evento": "#bd93f9"}
        color = colors.get(type_log, "#ffffff")
        html = f'<span style="color:#6272a4">[{timestamp}]</span> <span style="color:{color}">{message}</span>'
        self.log_viewer.append(html)
        self.save_to_file(message, type_log, channel)

    # Salva logs em arquivos organizados por data e canal
    def save_to_file(self, message, type_log, channel):
        try:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            clean_msg = message.replace("\n", " ")
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            daily_folder = os.path.join(PASTA_LOGS, date_str)
            if not os.path.exists(daily_folder): os.makedirs(daily_folder)
            filename = f"{channel.strip()}.txt" if channel and channel.strip() else "Geral_Sistema.txt"
            path = os.path.join(daily_folder, filename)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] [{type_log.upper()}] {clean_msg}\n")
        except Exception as e:
            print(f"Erro ao logar: {e}")

    @Slot(str)
    def update_status(self, status):
        color_status = "#777"
        if status == "ONLINE":
            color_status = "#50fa7b"
            self.lbl_status.setText("Status: ONLINE")
            self.btn_connect.setEnabled(True)
            self.verificar_mudanca_canais() 
        elif status == "RECONECTANDO...":
            color_status = "#ffb86c"
            self.lbl_status.setText(f"Status: {status}")
            self.btn_connect.setText("AGUARDE...")
            self.btn_connect.setEnabled(False)
            self.btn_connect.setStyleSheet("QPushButton { background-color: #ffb86c; color: #282a36; font-weight: bold; }")
        elif status in ["OFFLINE", "ERRO"]:
            color_status = "#ff5555" if status == "ERRO" else "#777"
            self.lbl_status.setText(f"Status: {status}")
            self.btn_connect.setText("CONECTAR")
            self.btn_connect.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; } QPushButton:hover { background-color: #45a049; }")
            self.btn_connect.setEnabled(True)
        self.lbl_status.setStyleSheet(f"color: {color_status}; font-weight: bold;")

    @Slot(int)
    def update_counter(self, val):
        self.lbl_counter.setText(f"Msgs: {val}")

    @Slot(str, int)
    def update_stats(self, tipo, val):
        if tipo == 'subs':
            lbl = self.lbl_subs.layout().itemAt(1).widget()
            lbl.setText(str(val))

    def closeEvent(self, event):
        if self.bot_logic.is_connected:
            asyncio.ensure_future(self.bot_logic.close())
        event.accept()

if __name__ == "__main__":
    # Configuração de DPI para telas de alta resolução
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion") # Estilo moderno padrão do Qt
    
    # Integração do Loop Asyncio com Qt
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = MainWindow()
    window.show()
    
    # Inicia o loop de eventos
    with loop:
        loop.run_forever()