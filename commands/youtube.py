import discord 
from discord.ext import commands
from datetime import datetime


def discord_timestamp(dt: datetime, fmt: str = "R") -> str:
    """Erstellt einen Discord-Timestamp aus einem datetime-Objekt"""
    ts = int(dt.timestamp())
    return f"<t:{ts}:{fmt}>"

def register(bot):
    pass
