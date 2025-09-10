import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import threading
from flask import Flask, request
from waitress import serve
import asyncio
import datetime

# ----------------------
# ENV laden
# ----------------------
try:
    load_dotenv('secrets/data.env')
except Exception:
    pass

TOKEN = os.getenv('DISCORD_TOKEN')
BOT_OWNER_API_KEY = os.getenv('BOT_OWNER_API_KEY')

# ----------------------
# Discord Bot Setup
# ----------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="§", intents=intents)

# Datenbankmodul importieren und initialisieren
from modules import firebase_db as firebase

cred_path = '/etc/secrets/db_key.json' 
db_url = 'https://comet-26ce9-default-rtdb.europe-west1.firebasedatabase.app/'
server_defaults = {
    "mod_log_channel": None,
}
user_defaults = {
    "moderation": {
        "warnings": 0,
        "mutes": 0,
        "kicks": 0,
        "bans": 0
    },
    "eco": {
        "balance": 0,
        "inventory": {"_init": True},
        "last_daily": 0,
        "daily_streak": 0
    },
    "points": {
        "points": 0,
    }
}
firebase_db = firebase.FirebaseDB(db_url, cred_path, server_defaults, user_defaults)

message_listeners = []

def get_language(guild_id):
    server_id = str(guild_id)
    lang = firebase_db.get(f"servers/{server_id}/settings/language") or "de"
    return lang

# Befehle aus anderen Dateien registrieren
from commands import moderation, eco, fun, utility, points, ai
points.register(bot, db=firebase_db)
utility.register(bot, firebase_db)
moderation.register(bot, db=firebase_db)
eco.register(bot, firebase_db)
fun.register(bot, firebase_db)
ai.register(bot, db=firebase_db, on_message_listener=message_listeners)

@bot.event
async def on_ready():
    print(f'Bot ist eingeloggt als {bot.user}')
    await firebase_db.init(bot)
    print("Datenbank initialisiert.")
    await bot.change_presence(activity=discord.Game(name="Comet 2.0 | /help"))
    print('Bot ist bereit!')

@bot.event
async def on_guild_join(guild):
    await firebase_db.init(bot)

@bot.event
async def on_member_join(member):
    await firebase_db.init(bot)

@bot.event
async def on_message(message):
    for listener in message_listeners:
        await listener(message)
    await bot.process_commands(message)

# ----------------------
# Discord-Bot Thread starten (mit Restart-Funktion)
# ----------------------
bot_thread = None

def run_bot():
    bot.run(TOKEN)

def start_bot_thread():
    global bot_thread
    if bot_thread and bot_thread.is_alive():
        print("Bot-Thread läuft bereits!")
        return
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("Bot-Thread gestartet!")

def restart_bot_thread():
    global bot_thread
    if bot_thread and bot_thread.is_alive():
        print("Bot-Thread wird beendet...")
        asyncio.run(bot.close())  # sauberes Herunterfahren
        bot_thread.join()
        print("Bot-Thread beendet.")
    start_bot_thread()
    return "Bot-Thread neu gestartet!"

def get_bot_stats(bot):
    stats = {}

    # Bot-Infos
    stats['bot_name'] = str(bot.user)
    stats['bot_id'] = bot.user.id
    stats['server_count'] = len(bot.guilds)
    stats['uptime'] = str(datetime.utcnow() - bot.uptime) if hasattr(bot, 'uptime') else "unknown"

    # Server-spezifische Infos
    guilds = []
    for guild in bot.guilds:
        guild_info = {
            "id": guild.id,
            "name": guild.name,
            "member_count": guild.member_count,
            "text_channels": len(guild.text_channels),
            "voice_channels": len(guild.voice_channels),
            "owner_id": guild.owner_id
        }
        guilds.append(guild_info)
    stats['guilds'] = guilds

    # Optional: Gesamte Userzahl (unique)
    unique_users = set()
    for guild in bot.guilds:
        for member in guild.members:
            unique_users.add(member.id)
    stats['unique_user_count'] = len(unique_users)

    # Optional: Aktive Commands
    stats['commands'] = [cmd.name for cmd in bot.commands]

    return stats

# ----------------------
# Flask Web API
# ----------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Comet Bot API is running."

@app.route('/api/restart', methods=['POST'])
def restart_bot_api():
    auth_header = request.headers.get('Authorization')
    if auth_header != f"Bearer {BOT_OWNER_API_KEY}":
        return "Forbidden", 403
    msg = restart_bot_thread()
    return msg

@app.route('/api/stats', methods=['GET'])
def bot_stats_api():
    auth_header = request.headers.get('Authorization')
    if auth_header != f"Bearer {BOT_OWNER_API_KEY}":
        return "Forbidden", 403
    stats = get_bot_stats(bot)
    return stats

# ----------------------
# Main
# ----------------------
if __name__ == "__main__":
    # Bot im Hintergrund starten
    start_bot_thread()

    # Flask im Hauptthread laufen lassen (Render Healthcheck)
    port = int(os.getenv("PORT", 10000))
    serve(app, host='0.0.0.0', port=port)
