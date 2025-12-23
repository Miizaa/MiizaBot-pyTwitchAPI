import ctypes
import asyncio
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import scrolledtext, messagebox, simpledialog
import json
import datetime
import sys
import os
import signal
import time
import random
import webbrowser
import winshell
from win32com.client import Dispatch
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.chat import Chat, ChatMessage, ChatEvent
from twitchAPI.type import AuthScope

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

CONFIG_FILE = 'config.json'
PASTA_LOGS = 'logs'
MOD_LOG_FILE = os.path.join(PASTA_LOGS, 'moderation_history.txt')
SUB_LOG_FILE = os.path.join(PASTA_LOGS, 'subscription_history.txt')

SCOPES = [
    AuthScope.CHANNEL_MODERATE,
    AuthScope.CHAT_EDIT,
    AuthScope.CHAT_READ,
    AuthScope.MODERATION_READ,
    AuthScope.MODERATOR_MANAGE_BANNED_USERS,
    AuthScope.MODERATOR_MANAGE_CHAT_MESSAGES
]

def carregar_config_inicial():
    default_config = {
        "APP_ID": "",
        "APP_SECRET": "",
        "ACCESS_TOKEN": "",
        "REFRESH_TOKEN": "",
        "NOME_DO_BOT": "miiza",
        "CANAIS": "miiza",
        "PALAVRAS_ALERTA": ["miiza"],
        "COMANDOS_CUSTOM": {},
        "COOLDOWN_PADRAO": 10,
        "ATRASO_RESPOSTA_MIN": 2,
        "ATRASO_RESPOSTA_MAX": 5,
        "SAUDACOES": {"bom dia": {"respostas": ["Bom dia!"], "cooldown": 60}}
    }
    if not os.path.exists(PASTA_LOGS):
        os.makedirs(PASTA_LOGS)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            for k, v in default_config.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except:
        return None

def salvar_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def registrar_moderacao(acao, canal, alvo, admin, motivo=""):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] AÇÃO: {acao} | CANAL: #{canal} | ALVO: {alvo} | POR: {admin} | MOTIVO: {motivo}\n"

    with open(MOD_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_entry)

def registrar_chat(canal, usuario, mensagem):
    agora = datetime.datetime.now()
    pasta_dia = os.path.join(PASTA_LOGS, agora.strftime("%Y-%m"))
    if not os.path.exists(pasta_dia):
        os.makedirs(pasta_dia)

    nome_arquivo = f"chat_{canal}_{agora.strftime('%Y-%m-%d')}.txt"
    caminho = os.path.join(pasta_dia, nome_arquivo)

    timestamp = agora.strftime("%H:%M:%S")
    linha = f"[{timestamp}] {usuario}: {mensagem}\n"

    with open(caminho, 'a', encoding='utf-8') as f:
        f.write(linha)

def registrar_inscricao(canal, usuario, tier, meses, mensagem=""):
    if not os.path.exists(PASTA_LOGS):
        os.makedirs(PASTA_LOGS)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    info = f"[{timestamp}]CANAL: {canal} SUB: {usuario} | TIER: {tier} | MESES: {meses} | MSG: {mensagem}\n"

    with open(SUB_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(info)

def abrir_pasta_logs(self):
    if os.path.exists(PASTA_LOGS):
        os.startfile(os.path.abspath(PASTA_LOGS))
    else:
        messagebox.showwarning(
            "Aviso", "A pasta de logs ainda não foi criada.")

def assistente_configuracao():
    if os.path.exists("config.json"):
        return True

    setup = tk.Tk()
    setup.title("Configuração Inicial MiizaBot")
    setup.geometry("400x450")
    setup.configure(bg="#1e1e1e")

    style = {"bg": "#1e1e1e", "fg": "white", "font": ("Arial", 9, "bold")}

    tk.Label(setup, text="BEM-VINDO AO BOT DO MIIZA", font=("Arial",
             12, "bold"), bg="#1e1e1e", fg="#6441a5").pack(pady=15)

    inputs = {}
    campos = [
        ("NOME_DO_BOT", "Nome do Usuário do Bot:"),
        ("CANAIS", "Canais para monitorar (separados por vírgula):"),
        ("APP_ID", "Client ID (dev.twitch.tv/console):"),
        ("APP_SECRET", "Client Secret (dev.twitch.tv/console):")
    ]

    for chave, label in campos:
        tk.Label(setup, text=label, **style).pack(padx=20, anchor="w")
        ent = tk.Entry(setup, width=40, bg="#3d3d3d",
                       fg="white", insertbackground="white")
        ent.pack(pady=5, padx=20)
        inputs[chave] = ent

    def salvar_setup():
        novo_config = {
            "NOME_DO_BOT": inputs["NOME_DO_BOT"].get().strip(),
            "CANAIS": inputs["CANAIS"].get().strip(),
            "APP_ID": inputs["APP_ID"].get().strip(),
            "APP_SECRET": inputs["APP_SECRET"].get().strip(),
            "PALAVRAS_ALERTA": ["admin", "staff", "ajuda"],
            "ATRASO_RESPOSTA_MIN": 2,
            "ATRASO_RESPOSTA_MAX": 5
        }

        if not all([novo_config["NOME_DO_BOT"], novo_config["APP_ID"], novo_config["APP_SECRET"]]):
            messagebox.showerror(
                "Erro", "Por favor, preencha todos os campos obrigatórios!")
            return

        with open("config.json", "w", encoding='utf-8') as f:
            json.dump(novo_config, f, indent=4)

        setup.destroy()

    tk.Button(setup, text="FINALIZAR E ABRIR BOT", command=salvar_setup,
              bg="#6441a5", fg="white", font=("Arial", 10, "bold"), pady=10).pack(pady=20)

    setup.mainloop()
    return True

def configurar_inicializacao_windows(ativar):
    startup_path = winshell.startup()
    shortcut_path = os.path.join(startup_path, "MiizaBot.lnk")
    exe_path = sys.executable

    if ativar:
        if not os.path.exists(shortcut_path):
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = exe_path
            shortcut.WorkingDirectory = os.path.dirname(exe_path)
            shortcut.IconLocation = exe_path
            shortcut.save()
    else:
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)

class TwitchChatHandler:
    def __init__(self, gui_app):
        self.gui = gui_app
        self.twitch = None
        self.chat = None
        self.bot_user_id = None
        self.is_connected = False
        self.total_mensagens = 0
        self.last_command_usage = {}
        self.stats = {"bans": 0, "timeouts": 0, "subs": 0}

    async def connect(self, channels_list):
        cfg = carregar_config_inicial()
        try:
            self.gui.log_message("1. Inicializando API Twitch...", "sistema")
            self.twitch = await Twitch(cfg["APP_ID"], cfg["APP_SECRET"])

            token = cfg.get("ACCESS_TOKEN")
            refresh = cfg.get("REFRESH_TOKEN")
            target_scopes = SCOPES

            auth = UserAuthenticator(self.twitch, target_scopes, force_verify=False)
            
            if not token or not refresh:
                token, refresh = await auth.authenticate()
            else:
                try:
                    await self.twitch.set_user_authentication(token, target_scopes, refresh)
                except:
                    self.gui.log_message("Token expirado, renovando...", "erro")
                    token, refresh = await auth.authenticate()

            await self.twitch.set_user_authentication(token, target_scopes, refresh)
            
            cfg["ACCESS_TOKEN"] = token
            cfg["REFRESH_TOKEN"] = refresh
            salvar_config(cfg)

            user_auth_scope = self.twitch.get_user_auth_scope()
            if AuthScope.CHANNEL_MODERATE in user_auth_scope:
                self.gui.log_message("✅ Permissão CHANNEL_MODERATE: OK", "sistema")
            else:
                self.gui.log_message("❌ FALTANDO PERMISSÃO DE MODERADOR!", "erro")

            user_info = await anext(self.twitch.get_users())
            login_token = user_info.login
            self.bot_user_id = user_info.id
            self.gui.log_message(f"🔑 BOT LOGADO COMO: {login_token.upper()}", "sistema")


            self.chat = await Chat(self.twitch)
            self.chat.register_event(ChatEvent.MESSAGE, self.on_message)
            self.chat.register_event(ChatEvent.SUB, self.on_sub)
            self.chat.start()
            
            await asyncio.sleep(1)

            self.canais_conectados = set()
            for canal in channels_list:
                c_nome = canal.strip().lower()
                if not c_nome: continue
                
                try:
                    await self.chat.join_room(c_nome)
                    self.canais_conectados.add(c_nome)
                    self.gui.log_message(f"💬 Conectado ao chat de #{c_nome}", "sistema")
                    

                except Exception as e:
                    self.gui.log_message(f"Erro ao conectar em #{c_nome}: {e}", "erro")

            self.is_connected = True
            self.gui.update_status("ONLINE")

        except Exception as e:
            self.gui.log_message(f"ERRO CRÍTICO: {str(e)}", "erro")
            import traceback
            traceback.print_exc()


    async def atualizar_canais_dinamico(self, nova_lista_str):
        if not self.is_connected or self.chat is None:
            return
        novos_canais = {c.strip().lower()
                        for c in nova_lista_str.split(',') if c.strip()}
        para_entrar = novos_canais - self.canais_conectados
        for c in para_entrar:
            await self.chat.join_room(c)
            self.canais_conectados.add(c)
            self.gui.after(0, lambda ch=c: self.gui.log_message(
                f"-> Entrou em #{ch}", "sistema"))
        para_sair = self.canais_conectados - novos_canais
        for c in para_sair:
            await self.chat.leave_room(c)
            self.canais_conectados.remove(c)
            self.gui.after(0, lambda ch=c: self.gui.log_message(
                f"<- Saiu de #{ch}", "sistema"))

    async def on_sub(self, sub):
        try:
            canal = sub.room.name
            usuario = "Doador_Anonimo"
            if hasattr(sub, 'system_message') and sub.system_message:
                mensagem_limpa = sub.system_message.replace(r'\s', ' ')
                usuario = mensagem_limpa.split(' ')[0]
            acao_tipo = "SUB"
            msg_sys_low = (sub.system_message or "").lower()
            if "gifted" in msg_sys_low:
                acao_tipo = "GIFT-SUB"
            tier_raw = getattr(sub, 'sub_plan', '1000')
            tier = "Prime" if tier_raw == 'Prime' else f"Tier {int(tier_raw)//1000}"
            meses = getattr(sub, 'cumulative_months', 1)
            msg_sub = getattr(sub, 'sub_message', "Sem mensagem")
            registrar_inscricao(canal, usuario, tier, meses,
                                f"[{acao_tipo}] {msg_sub}")
            log_msg = f"✨ {usuario} -> {acao_tipo} ({tier})!"
            self.gui.after(0, lambda: self.gui.incrementar_estatistica("subs"))
            self.gui.after(
                0, lambda m=log_msg: self.gui.log_message(m, "evento"))
        except Exception as e:
            self.gui.after(0, lambda m=str(
                e): self.gui.log_message(f"Erro Sub: {m}", "erro"))

    async def on_raid(self, raid):
        registrar_moderacao("RAID RECEBIDA", raid.room.name,
                            f"{raid.viewer_count} viewers", raid.raider.display_name)
        self.gui.after(0, lambda: self.gui.log_message(
            f"🚀 RAID: {raid.raider.display_name} ({raid.viewer_count})", "sistema"))

    async def clear_chat_api(self, channel_name, admin_name):
        try:
            broadcaster_id = None
            async for user in self.twitch.get_users(logins=[channel_name]):
                broadcaster_id = user.id
                break
            if broadcaster_id:
                await self.twitch.delete_chat_messages(broadcaster_id, self.bot_user_id)
                registrar_moderacao("LIMPAR CHAT", channel_name,
                                    "TODOS", admin_name, "Comando !limpar")
                self.gui.after(0, lambda: self.gui.log_message(
                    f"Chat de #{channel_name} limpo por {admin_name}", "moderacao"))
                return True
        except Exception as e:
            return str(e)

    async def get_ids(self, broadcaster_name, target_name):
        b_id, t_id = None, None
        async for user in self.twitch.get_users(logins=[broadcaster_name]):
            b_id = user.id
            break
        async for user in self.twitch.get_users(logins=[target_name]):
            t_id = user.id
            break
        return b_id, t_id

    async def timeout_user(self, channel_name, target_name, duration, reason, admin):
        try:
            b_id, t_id = await self.get_ids(channel_name, target_name)
            if not b_id or not t_id:
                return "Usuário não encontrado."
            await self.twitch.ban_user(broadcaster_id=b_id, moderator_id=self.bot_user_id, user_id=t_id, reason=reason, duration=duration)
            return True
        except Exception as e:
            return str(e)

    async def ban_user(self, channel_name, target_name, reason, admin):
        try:
            b_id, t_id = await self.get_ids(channel_name, target_name)
            if not b_id or not t_id:
                return "Usuário não encontrado."
            await self.twitch.ban_user(b_id, self.bot_user_id, t_id, reason)
            return True
        except Exception as e:
            return str(e)

    async def unban_user(self, channel_name, target_name, admin):
        try:
            b_id, t_id = await self.get_ids(channel_name, target_name)
            if not b_id or not t_id:
                return "Usuário não encontrado."
            await self.twitch.unban_user(b_id, self.bot_user_id, t_id)
            return True
        except Exception as e:
            return str(e)

    async def close(self):
        """Encerra todas as conexões de forma segura e avisa no log."""
        if not self.is_connected:
            return

        self.gui.after(0, lambda: self.gui.log_message("🔻 Iniciando desconexão...", "sistema"))
        self.gui.after(0, lambda: self.gui.update_status("Desconectando..."))

        
        if self.chat:
            try:
                self.chat.stop()
            except Exception as e:
                print(f"Aviso ao fechar Chat: {e}")

        if self.twitch:
            try:
                await self.twitch.close()
            except Exception as e:
                print(f"Aviso ao fechar Twitch: {e}")

        self.is_connected = False
        
        self.gui.after(0, lambda: self.gui.update_status("Desconectado"))
        self.gui.after(0, lambda: self.gui.log_message("🔴 BOT DESCONECTADO COM SUCESSO.", "sistema"))
        self.gui.after(0, lambda: self.gui.log_message("-" * 40, "sistema"))

    async def send_message(self, message, channel):
        if self.is_connected and self.chat:
            await self.chat.send_message(channel, message)
            self.gui.after(0, lambda: self.gui.log_message(
                f"[BOT -> #{channel}]: {message}", "proprio"))

    async def on_message(self, msg: ChatMessage):
        self.total_mensagens += 1
        self.gui.after(0, lambda: self.gui.update_counter(
            self.total_mensagens))

        cfg = carregar_config_inicial()
        texto_original = msg.text.strip()
        texto_low = texto_original.lower()
        usuario_display = msg.user.display_name
        usuario_nick = msg.user.name.lower()
        canal = msg.room.name

        registrar_chat(canal, usuario_display, texto_original)
        e_highlight = any(
            p.lower() in texto_low for p in cfg.get("PALAVRAS_ALERTA", []))
        self.gui.after(0, lambda: self.gui.log_chat_colorido(datetime.datetime.now(
        ).strftime("%H:%M"), canal, usuario_display, texto_original, e_highlight))

        is_mod = msg.user.mod or usuario_nick == canal
        partes = texto_original.split(' ')

        if is_mod and texto_low == '!limpar':
            res = await self.clear_chat_api(canal, usuario_display)
            if res is True:
                await msg.reply("O chat foi limpo.")
            else:
                self.gui.log_message(f"Erro limpar: {res}", "erro")
            return

        if is_mod and texto_low.startswith('!timeout') and len(partes) >= 3:
            alvo = partes[1].replace('@', '').lower()
            try:
                segundos = int(partes[2])
                motivo = " ".join(partes[3:]) if len(partes) > 3 else "Via Bot"
                res = await self.timeout_user(canal, alvo, segundos, motivo, usuario_display)
                if res is True:
                    registrar_moderacao("TIMEOUT", canal, alvo, usuario_display, motivo)
                    self.gui.after(0, lambda: self.gui.incrementar_estatistica("timeouts"))
                    self.gui.log_message(f"⏱️ {alvo} levou TIMEOUT de {usuario_display}", "moderacao")
            except ValueError:
                pass
            return

        if is_mod and texto_low.startswith('!ban') and len(partes) >= 2:
            alvo = partes[1].replace('@', '').lower()
            motivo = " ".join(partes[2:]) if len(partes) > 2 else "Via Bot"
            res = await self.ban_user(canal, alvo, motivo, usuario_display)
            if res is True:
                registrar_moderacao("BAN", canal, alvo, usuario_display, motivo)
                self.gui.after(0, lambda: self.gui.incrementar_estatistica("bans"))
                self.gui.log_message(f"🔨 {alvo} foi BANIDO por {usuario_display}", "moderacao")
            return

        if is_mod and (texto_low.startswith('!desbanir') or texto_low.startswith('!unban')) and len(partes) >= 2:
            alvo = partes[1].replace('@', '').lower()
            res = await self.unban_user(canal, alvo, usuario_display)
            if res is True:
                registrar_moderacao("UNBAN", canal, alvo, usuario_display, "Desbanido via Bot")
                self.gui.log_message(f"🕊️ {alvo} foi DESBANIDO por {usuario_display}", "moderacao")
            return

        saudacoes = cfg.get("SAUDACOES", {})
        
        for id_grupo, dados in saudacoes.items():
            if not isinstance(dados, dict): continue
            
            lista_gatilhos = dados.get("gatilhos", [])
            
            ativou = False
            for gatilho in lista_gatilhos:
                g_low = gatilho.lower()
                if texto_low == g_low or texto_low.startswith(g_low + " "):
                    ativou = True
                    break 
            
            if ativou:
                cd_val = dados.get("cooldown", 30)
                chave_cd = f"{canal}_{usuario_nick}_{id_grupo}"
                
                if time.time() - self.last_command_usage.get(chave_cd, 0) < cd_val:
                    return

                respostas = dados.get("respostas", [])
                if respostas:
                    self.last_command_usage[chave_cd] = time.time()
                    
                    atraso = random.uniform(cfg.get("ATRASO_RESPOSTA_MIN", 2), cfg.get("ATRASO_RESPOSTA_MAX", 5))
                    self.gui.log_message(f"   [Gatilho: {id_grupo}] Respondendo {usuario_display} em {atraso:.1f}s", "sistema")
                    
                    await asyncio.sleep(atraso)
                    
                    resp_escolhida = random.choice(respostas)
                    await msg.reply(resp_escolhida.format(user=usuario_display))
                    return

        if texto_original.startswith('!'):
            comando = partes[0][1:].lower()
            if comando in cfg.get("COMANDOS_CUSTOM", {}):
                c_data = cfg["COMANDOS_CUSTOM"][comando]
                res = c_data["resposta"] if isinstance(
                    c_data, dict) else c_data
                cd_v = c_data.get("cooldown", 10)
                if time.time() - self.last_command_usage.get(f"{canal}_{comando}", 0) < cd_v:
                    return
                await msg.reply(res)
                self.last_command_usage[f"{canal}_{comando}"] = time.time()


class BotGui(tk.Tk):
    def __init__(self, asyncio_loop):
        super().__init__()
        self.asyncio_loop = asyncio_loop
        self.title("Miiza Bot")
        self.geometry("850x700")
        self.configure(bg="#2d2d2d")
        self.channels_var = tk.StringVar()
        self.channels_var.trace_add("write", self.verificar_mudanca_canais)
        self.create_widgets()
        self.chat_handler = TwitchChatHandler(self)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        cfg = carregar_config_inicial()
        if cfg:
            self.channels_entry.insert(0, cfg.get("CANAIS", ""))
            if cfg.get("CANAIS"):
                self.target_channel_entry.insert(
                    0, cfg["CANAIS"].split(',')[0].strip())
        self.after(100, self.run_asyncio_tasks)
        try:
            icon_path = resource_path("logo.ico")
            self.iconbitmap(icon_path)
        except Exception as e:
            print(f"Erro ao carregar ícone: {e}")

    def create_widgets(self):
        top = tk.Frame(self, bg="#2d2d2d", pady=10)
        top.pack(fill='x', padx=10)
        self.channels_entry = tk.Entry(
            top, bg="#3d3d3d", fg="white", insertbackground="white", textvariable=self.channels_var)
        self.channels_entry.pack(side='left', fill='x', expand=True, padx=5)
        self.connect_button = tk.Button(
            top, text="CONECTAR", command=self.toggle_connection, bg="#4CAF50", fg="white", width=15)
        self.connect_button.pack(side='right')
        self.reboot_button = tk.Button(top, text="🔁", command=self.reiniciar_bot,
                                       bg="#555555", fg="white", width=4, font=("Segoe UI Emoji", 8, "bold"))
        self.reboot_button.pack(side='left', padx=2)

        stats_f = tk.Frame(self, bg="#1e1e1e", pady=3)
        stats_f.pack(fill='x', side='bottom')

        self.lbl_bans = tk.Label(
            stats_f, text="🔨 Bans: 0", bg="#1e1e1e", fg="#ff5555", font=("Arial", 9, "bold"))
        self.lbl_bans.pack(side='left', padx=20)

        self.lbl_timeouts = tk.Label(
            stats_f, text="⏳ Timeouts: 0", bg="#1e1e1e", fg="#ffb86c", font=("Arial", 9, "bold"))
        self.lbl_timeouts.pack(side='left', padx=20)

        self.lbl_subs = tk.Label(
            stats_f, text="💎 Subs: 0", bg="#1e1e1e", fg="#bd93f9", font=("Arial", 9, "bold"))
        self.lbl_subs.pack(side='left', padx=20)

        stats = tk.Frame(self, bg="#1e1e1e", pady=5)
        stats.pack(fill='x', padx=10)
        self.status_var = tk.StringVar(value="Status: Desconectado")
        tk.Label(stats, textvariable=self.status_var, bg="#1e1e1e",
                 fg="#00ff00").pack(side='left', padx=10)
        self.counter_var = tk.StringVar(value="Mensagens: 0")
        tk.Label(stats, textvariable=self.counter_var, bg="#1e1e1e",
                 fg="#8be9fd").pack(side='right', padx=10)

        self.log_area = scrolledtext.ScrolledText(
            self, bg="#121212", fg="#e0e0e0", font=("Consolas", 10))
        self.log_area.pack(fill='both', expand=True, padx=10, pady=5)
        self.log_area.tag_config("hora", foreground="#888888")
        self.log_area.tag_config(
            "canal", foreground="#bd93f9", font=("Consolas", 10, "bold"))
        self.log_area.tag_config(
            "user", foreground="#ffb86c", font=("Consolas", 10, "bold"))
        self.log_area.tag_config("sistema", foreground="#50fa7b")
        self.log_area.tag_config("erro", foreground="#ff5555")
        self.log_area.tag_config("moderacao", foreground="#ffb86c")
        self.log_area.tag_config("proprio", foreground="#8be9fd")
        self.log_area.tag_config(
            "highlight", background="#f1fa8c", foreground="#282a36")
        self.log_area.config(state='disabled')

        mid_f = tk.Frame(self, bg="#2d2d2d", pady=5)
        mid_f.pack(fill='x', padx=10)

        tk.Button(mid_f, text="📂 LOGS", command=self.abrir_pasta_logs,
                  bg="#444444", fg="white", font=("Arial", 9, "bold")).pack(side='left', padx=(0, 10))
        tk.Button(mid_f, text="🧹 LIMPAR", command=self.limpar_tela_bot,
                  bg="#444444", fg="white", font=("Arial", 9, "bold")).pack(side='left')
        tk.Button(mid_f, text="⚙️ CONFIGS", command=self.abrir_janela_configs,
                  bg="#6441a5", fg="white", font=("Arial", 9, "bold")).pack(side='left', padx=2)

        bot_f = tk.Frame(self, bg="#2d2d2d", pady=10)
        bot_f.pack(fill='x', padx=10)
        self.target_channel_entry = tk.Entry(
            bot_f, width=12, bg="#3d3d3d", fg="white")
        self.target_channel_entry.pack(side='left')
        self.message_entry = tk.Entry(
            bot_f, bg="#3d3d3d", fg="white", insertbackground="white")
        self.message_entry.pack(side='left', fill='x', expand=True, padx=5)
        self.message_entry.bind(
            '<Return>', lambda e: self.send_button_action())
        tk.Button(bot_f, text="ENVIAR", command=self.send_button_action,
                  bg="#2196F3", fg="white").pack(side='right')

    def incrementar_estatistica(self, tipo):
        if tipo == "bans":
            valor = int(self.lbl_bans.cget("text").split(": ")[1]) + 1
            self.lbl_bans.config(text=f"🔨 Bans: {valor}")
        elif tipo == "timeouts":
            valor = int(self.lbl_timeouts.cget("text").split(": ")[1]) + 1
            self.lbl_timeouts.config(text=f"⏳ Timeouts: {valor}")
        elif tipo == "subs":
            valor = int(self.lbl_subs.cget("text").split(": ")[1]) + 1
            self.lbl_subs.config(text=f"💎 Subs: {valor}")

    def reiniciar_bot(self):
        """Fecha a conexão atual e inicia uma nova imediatamente"""
        if not messagebox.askyesno("Reiniciar", "Deseja reiniciar a conexão do bot agora?"):
            return

        self.log_message("♻️ Reiniciando sistemas do bot...", "sistema")

        async def seq_reiniciar():
            if self.chat_handler.is_connected:
                await self.chat_handler.close()

            await asyncio.sleep(1)

            canais = self.channels_var.get().strip()
            if canais:
                await self.chat_handler.connect(canais.split(','))

        asyncio.run_coroutine_threadsafe(seq_reiniciar(), self.asyncio_loop)

    def verificar_mudanca_canais(self, *args):
        """Muda o estado do botão dependendo do que foi digitado"""
        if not hasattr(self, 'chat_handler') or not self.chat_handler.is_connected:
            self.connect_button.config(text="CONECTAR", bg="#4CAF50")
            return

        canais_na_tela = self.channels_var.get().strip().lower()
        canais_atuais = ",".join(
            sorted(list(self.chat_handler.canais_conectados)))
        canais_novos = ",".join(
            sorted([c.strip().lower() for c in canais_na_tela.split(',') if c.strip()]))

        if canais_novos != canais_atuais:
            self.connect_button.config(text="ATUALIZAR", bg="#2196F3")
        else:
            self.connect_button.config(text="DESCONECTAR", bg="#f44336")

    def abrir_pasta_logs(self):
        """Abre a pasta onde os arquivos de log são salvos"""
        if not os.path.exists(PASTA_LOGS):
            os.makedirs(PASTA_LOGS)
        os.startfile(os.path.abspath(PASTA_LOGS))

    def limpar_tela_bot(self):
        """Limpa apenas a visualização de texto na interface do programa"""
        self.log_area.config(state='normal')
        self.log_area.delete('1.0', tk.END)
        self.log_area.config(state='disabled')
        self.log_message("--- Tela limpa pelo usuário ---", "sistema")

    def log_message(self, message, tipo="sistema"):
        """Insere mensagens com ícones e cores padronizadas"""
        icones = {
            "sistema": "🟢 ",
            "erro": "🔴 ",
            "moderacao": "🛡️ ",
            "evento": "✨ ",
            "proprio": "📩 ",
            "chat": "💬 "
        }

        icone = icones.get(tipo, "")
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{timestamp}] ", "hora")
        self.log_area.insert(tk.END, f"{icone}{message}\n", tipo)
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def log_chat_colorido(self, hora, canal, usuario, texto, highlight=False):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{hora}] ", "hora")
        self.log_area.insert(tk.END, f"[#{canal}] ", "canal")
        self.log_area.insert(tk.END, f"{usuario}: ", "user")
        tag_t = "highlight" if highlight else None
        self.log_area.insert(tk.END, f"{texto}\n", tag_t)
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def update_status(self, s): self.status_var.set(f"Status: {s}")
    def update_counter(self, v): self.counter_var.set(f"Mensagens: {v}")

    def toggle_connection(self):
        if self.connect_button.cget("text") == "DESCONECTAR":
            asyncio.run_coroutine_threadsafe(
                self.chat_handler.close(), self.asyncio_loop)
            self.connect_button.config(text="CONECTAR", bg="#4CAF50")
            return

        canais_input = self.channels_var.get().strip()
        if self.chat_handler.is_connected:
            asyncio.run_coroutine_threadsafe(
                self.chat_handler.atualizar_canais_dinamico(canais_input), self.asyncio_loop)
            self.verificar_mudanca_canais()
        else:
            canais_input = self.channels_entry.get()
            cfg = carregar_config_inicial()
            if cfg:
                cfg["CANAIS"] = canais_input
                salvar_config(cfg)
                self.connect_button.config(text="DESCONECTAR", bg="#f44336")
                asyncio.run_coroutine_threadsafe(self.chat_handler.connect(
                    canais_input.split(',')), self.asyncio_loop)

    def abrir_janela_configs(self):
        """Cria uma janela com abas para Geral e Saudações"""
        self.config_temp = carregar_config_inicial() 

        self.janela_config = tk.Toplevel(self)
        self.janela_config.title("Configurações do Bot")
        self.janela_config.geometry("600x550")
        self.janela_config.configure(bg="#2d2d2d")

        frame_rodape = tk.Frame(self.janela_config, bg="#2d2d2d", pady=10)
        frame_rodape.pack(side="bottom", fill="x")
        
        notebook = ttk.Notebook(self.janela_config)
        notebook.pack(side="top", fill="both", expand=True, padx=10, pady=10)

        tab_geral = tk.Frame(notebook, bg="#2d2d2d")
        notebook.add(tab_geral, text="Geral")

        tk.Label(tab_geral, text="Palavras de Alerta (separe por vírgula):", bg="#2d2d2d", fg="white").pack(pady=5)
        alertas_ent = tk.Entry(tab_geral, width=50)
        alertas_ent.pack(padx=10)
        alertas_ent.insert(0, ", ".join(self.config_temp.get("PALAVRAS_ALERTA", [])))

        tk.Label(tab_geral, text="Delay Mínimo (seg):", bg="#2d2d2d", fg="white").pack(pady=5)
        min_delay = tk.Scale(tab_geral, from_=0, to=10, orient='horizontal', bg="#2d2d2d", fg="white")
        min_delay.set(self.config_temp.get("ATRASO_RESPOSTA_MIN", 2))
        min_delay.pack()

        tk.Label(tab_geral, text="Delay Máximo (seg):", bg="#2d2d2d", fg="white").pack(pady=5)
        max_delay = tk.Scale(tab_geral, from_=1, to=30, orient='horizontal', bg="#2d2d2d", fg="white")
        max_delay.set(self.config_temp.get("ATRASO_RESPOSTA_MAX", 5))
        max_delay.pack()

        var_startup = tk.BooleanVar(value=self.config_temp.get("INICIAR_COM_WINDOWS", False))
        tk.Checkbutton(tab_geral, text="Iniciar junto com o Windows", variable=var_startup,
                       bg="#2d2d2d", fg="white", selectcolor="#1e1e1e",
                       activebackground="#2d2d2d", activeforeground="white").pack(pady=10)

        self.tab_saudacoes = tk.Frame(notebook, bg="#e1e1e1")
        notebook.add(self.tab_saudacoes, text="Saudações & Cooldown")

        frame_lista = tk.LabelFrame(self.tab_saudacoes, text="Grupos")
        frame_lista.pack(side="left", fill="y", padx=5, pady=5)

        self.listbox_grupos = tk.Listbox(frame_lista, width=20, exportselection=False)
        self.listbox_grupos.pack(fill="both", expand=True, padx=5, pady=5)
        self.listbox_grupos.bind("<<ListboxSelect>>", self.carregar_grupo_selecionado)

        frame_botoes_lista = tk.Frame(frame_lista)
        frame_botoes_lista.pack(fill="x", padx=5, pady=5)
        tk.Button(frame_botoes_lista, text="+", command=self.novo_grupo, width=3).pack(side="left", expand=True)
        tk.Button(frame_botoes_lista, text="-", command=self.remover_grupo, width=3).pack(side="left", expand=True)

        frame_edicao = tk.LabelFrame(self.tab_saudacoes, text="Editar Grupo")
        frame_edicao.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        tk.Label(frame_edicao, text="Gatilhos (virgula):").pack(anchor="w", padx=5)
        self.entry_gatilhos = tk.Entry(frame_edicao)
        self.entry_gatilhos.pack(fill="x", padx=5)

        tk.Label(frame_edicao, text="Cooldown (seg):").pack(anchor="w", padx=5, pady=(10,0))
        self.spin_cooldown = tk.Spinbox(frame_edicao, from_=0, to=9999)
        self.spin_cooldown.pack(anchor="w", padx=5)

        tk.Label(frame_edicao, text="Respostas (uma por linha):").pack(anchor="w", padx=5, pady=(10,0))
        self.txt_respostas = tk.Text(frame_edicao, height=8, width=30)
        self.txt_respostas.pack(fill="both", expand=True, padx=5, pady=5)

        tk.Button(frame_edicao, text="Gravar Alterações do Grupo", command=self.salvar_grupo_atual, bg="#dddddd").pack(fill="x", padx=5, pady=5)

        self.atualizar_lista_grupos()

        def salvar_tudo():
            self.salvar_grupo_atual(silent=True)
            
            self.config_temp["PALAVRAS_ALERTA"] = [x.strip() for x in alertas_ent.get().split(',') if x.strip()]
            self.config_temp["ATRASO_RESPOSTA_MIN"] = min_delay.get()
            self.config_temp["ATRASO_RESPOSTA_MAX"] = max_delay.get()
            self.config_temp["INICIAR_COM_WINDOWS"] = var_startup.get()
            
            configurar_inicializacao_windows(self.config_temp["INICIAR_COM_WINDOWS"])
            salvar_config(self.config_temp)
            
            messagebox.showinfo("Sucesso", "Todas as configurações salvas!", parent=self.janela_config)
            self.janela_config.destroy()

        tk.Button(frame_rodape, text="SALVAR TUDO E FECHAR", command=salvar_tudo,
                  bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), pady=10).pack(fill='x', padx=10)
        
    def atualizar_lista_grupos(self):
        self.listbox_grupos.delete(0, tk.END)
        saudacoes = self.config_temp.get("SAUDACOES", {})
        for key in saudacoes.keys():
            self.listbox_grupos.insert(tk.END, key)

    def carregar_grupo_selecionado(self, event):
        selecao = self.listbox_grupos.curselection()
        if not selecao: return
        
        grupo_id = self.listbox_grupos.get(selecao[0])
        dados = self.config_temp["SAUDACOES"].get(grupo_id, {})

        gatilhos_list = dados.get("gatilhos", [])
        self.entry_gatilhos.delete(0, tk.END)
        self.entry_gatilhos.insert(0, ", ".join(gatilhos_list))

        self.spin_cooldown.delete(0, tk.END)
        self.spin_cooldown.insert(0, str(dados.get("cooldown", 30)))

        respostas_list = dados.get("respostas", [])
        self.txt_respostas.delete("1.0", tk.END)
        self.txt_respostas.insert("1.0", "\n".join(respostas_list))

    def salvar_grupo_atual(self, silent=False):
        selecao = self.listbox_grupos.curselection()
        
        if not selecao:
            if not silent:
                messagebox.showwarning("Atenção", "Selecione um grupo na lista à esquerda antes de salvar!", parent=self.janela_config)
            return

        grupo_id = self.listbox_grupos.get(selecao[0])
        
        raw_gatilhos = self.entry_gatilhos.get()
        lista_gatilhos = [g.strip() for g in raw_gatilhos.split(",") if g.strip()]
        
        raw_respostas = self.txt_respostas.get("1.0", tk.END).strip()
        lista_respostas = [r for r in raw_respostas.split("\n") if r.strip()]
        
        try:
            cd_val = int(self.spin_cooldown.get())
        except:
            cd_val = 30

        if "SAUDACOES" not in self.config_temp:
            self.config_temp["SAUDACOES"] = {}

        self.config_temp["SAUDACOES"][grupo_id] = {
            "gatilhos": lista_gatilhos,
            "respostas": lista_respostas,
            "cooldown": cd_val
        }
        
        if not silent:
            messagebox.showinfo("Sucesso", f"Grupo '{grupo_id}' atualizado!\n(Clique em SALVAR TUDO para finalizar)", parent=self.janela_config)

    def novo_grupo(self):
        novo = simpledialog.askstring("Novo", "Nome do ID do grupo (sem espaços):", parent=self.janela_config)
        if novo:
            if "SAUDACOES" not in self.config_temp: self.config_temp["SAUDACOES"] = {}
            self.config_temp["SAUDACOES"][novo] = {
                "gatilhos": ["gatilho"], "respostas": ["Olá!"], "cooldown": 30
            }
            self.atualizar_lista_grupos()

    def remover_grupo(self):
        selecao = self.listbox_grupos.curselection()
        if not selecao: return
        grupo = self.listbox_grupos.get(selecao[0])
        
        if messagebox.askyesno("Confirmar", f"Excluir '{grupo}'?", parent=self.janela_config):
            del self.config_temp["SAUDACOES"][grupo]
            self.atualizar_lista_grupos()
            self.entry_gatilhos.delete(0, tk.END)
            self.txt_respostas.delete("1.0", tk.END)

    def send_button_action(self):
        m = self.message_entry.get()
        t = self.target_channel_entry.get().strip().lower()
        if m and t:
            asyncio.run_coroutine_threadsafe(
                self.chat_handler.send_message(m, t), self.asyncio_loop)
            self.message_entry.delete(0, tk.END)

    def run_asyncio_tasks(self):
        try:
            self.asyncio_loop.stop()
            self.asyncio_loop.run_forever()
        except:
            pass
        self.after(10, self.run_asyncio_tasks)

    def on_closing(self):
        if messagebox.askokcancel("Sair", "Deseja realmente fechar o MiizaBot?"):
            try:
                if hasattr(self, 'chat_handler') and self.chat_handler.is_connected:
                    asyncio.run_coroutine_threadsafe(
                        self.chat_handler.close(), self.asyncio_loop)

                self.after(500, self.destruir_processo)
            except:
                self.destruir_processo()

    def destruir_processo(self):
        self.destroy()
        os._exit(0)

if __name__ == "__main__":
    myappid = 'miiza.bot.twitch.v8.35'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    if assistente_configuracao():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app = BotGui(loop)
        app.mainloop()