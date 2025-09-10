import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import threading
from flask import Flask

# ----------------------
# ENV laden
# ----------------------
try:
    load_dotenv('secrets/data.env')
except Exception:
    pass

TOKEN = os.getenv('DISCORD_TOKEN')

# ----------------------
# Discord Bot Setup
# ----------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

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
async def on_message(message):
    for listener in message_listeners:
        await listener(message)
    await bot.process_commands(message)

# ----------------------
# Discord-Bot Thread starten
# ----------------------
def run_bot():
    bot.run(TOKEN)

# ----------------------
# Flask Web API
# ----------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Comet Bot API is running."

# ----------------------
# Main
# ----------------------
if __name__ == "__main__":
    # Bot im Hintergrund starten
    threading.Thread(target=run_bot, daemon=True).start()

    # Flask im Hauptthread laufen lassen (Render Healthcheck)
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
