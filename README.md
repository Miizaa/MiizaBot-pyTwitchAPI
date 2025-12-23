# 🤖 MiizaBot - Twitch Bot

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Twitch API](https://img.shields.io/badge/Twitch_API-EventSub-purple?style=for-the-badge&logo=twitch&logoColor=white)
![Status](https://img.shields.io/badge/Status-Stable-green?style=for-the-badge)

Um bot de Twitch **portátil** e com **Interface Gráfica (GUI)**, focado em moderação manual, logs de eventos e interação inteligente com espectadores. Desenvolvido para rodar localmente no Windows sem necessidade de servidores complexos.

## ✨ Funcionalidades

### 🛡️ Moderação & Segurança
* **Comandos de Moderação:** `!ban`, `!timeout`, `!unban` e `!limpar` com logs automáticos.
* **Histórico de Moderação:** Salva todas as ações (quem baniu quem e por qual motivo, mas, apenas as ações via comando do bot.) em arquivo de texto (`logs/moderation_history.txt`).
* **Log de Chat Colorido:** Interface visual que destaca mensagens, subs e alertas do sistema.

### 💬 Interação & Chat
* **Sistema de Saudações Inteligente:** Agrupa variações de "Oi" (ex: *olá, eai, opa*) para responder com um cooldown compartilhado, evitando spam.
* **Multi-Canal:** Pode conectar e monitorar múltiplos canais simultaneamente.

### ⚙️ Sistema & Usabilidade
* **100% GUI:** Configuração visual (sem precisar editar JSON na mão).
* **Portátil:** Pode ser compilado em um único arquivo `.exe`.
* **Logs Locais:** Salva histórico de chat e subs separadamente por dia e mês.

---

## 🚀 Como Usar

### Pré-requisitos
1.  Python 3.8 ou superior instalado.
2.  Uma aplicação criada no [Twitch Developer Console](https://dev.twitch.tv/console).

### Instalação (Código Fonte)

1.  Clone este repositório:
    ```bash
    git clone [https://github.com/SEU_USUARIO/MiizaBot.git](https://github.com/SEU_USUARIO/MiizaBot.git)
    cd MiizaBot
    ```

2.  Instale as dependências:
    ```bash
    pip install twitchAPI pywin32 winshell
    ```
    *(Nota: Se usar ambiente virtual, ative-o antes)*

3.  Execute o bot:
    ```bash
    python bot.py
    ```

4.  Na primeira execução, o **Assistente de Configuração** abrirá. Insira seu `Client ID`, `Client Secret` e nome do bot.

---

## 🛠️ Compilando para .EXE (Portátil)

Se você deseja criar um executável para rodar em computadores sem Python instalado, utilize o **PyInstaller**.

1.  Instale o PyInstaller:
    ```bash
    pip install pyinstaller
    ```

2.  Execute o comando de build (certifique-se de ter o arquivo `logo.ico` na pasta):
    ```bash
    python -m PyInstaller --noconfirm --onefile --windowed --name "MiizaBot" --collect-all twitchAPI --hidden-import="winshell" --hidden-import="win32com" --clean bot.py
    ```

3.  O executável estará na pasta `dist/`.

---

## 🎮 Comandos do Chat

| Comando | Permissão | Descrição | Exemplo |
| :--- | :--- | :--- | :--- |
| `!ban <user> <motivo>` | Mod/Streamer | Bane um usuário permanentemente. | `!ban @troll Spam` |
| `!timeout <user> <seg> <motivo>` | Mod/Streamer | Aplica silêncio temporário. | `!timeout @user 600 Calma` |
| `!unban <user>` | Mod/Streamer | Remove o banimento. | `!unban @user` |
| `!limpar` | Mod/Streamer | Apaga o histórico recente do chat. | `!limpar` |
| `!comando` | Todos | Comandos customizados criados na config. | `!discord` |

---

## 📂 Estrutura de Arquivos

O bot cria e gerencia os seguintes arquivos automaticamente:

* `config.json`: Armazena tokens e configurações (Não compartilhe este arquivo!).
* `logs/`: Pasta contendo:
    * `moderation_history.txt`: Log perpétuo de bans/timeouts.
    * `subscription_history.txt`: Histórico de inscritos.
    * `YYYY-MM/`: Pastas mensais com logs diários de todo o chat.

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para abrir uma **Issue** ou enviar um **Pull Request**.

1.  Faça um Fork do projeto.
2.  Crie uma Branch para sua feature (`git checkout -b feature/NovaFeature`).
3.  Commit suas mudanças (`git commit -m 'Adicionando nova feature'`).
4.  Push para a Branch (`git push origin feature/NovaFeature`).
5.  Abra um Pull Request.

---

## 📝 Licença

Este projeto está sob a licença MIT.

---

<div align="center">
  <sub>Desenvolvido com ❤️ por Miiza</sub>
</div>
