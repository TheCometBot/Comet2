import discord 
from discord.ext import commands, tasks
import asyncio
import requests
from datetime import datetime
import os

API_KEY = os.getenv("YT_API_KEY")

def get_video_id(url: str) -> str:
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("/")[-1]
    return None

def fetch_youtube_info(video_id: str):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "snippet,liveStreamingDetails", "id": video_id, "key": API_KEY}
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    if not data["items"]:
        return None
    video = data["items"][0]
    snippet = video["snippet"]
    live = video.get("liveStreamingDetails", {})
    return {
        "title": snippet["title"],
        "broadcast_status": snippet.get("liveBroadcastContent"),
        "scheduled_start": live.get("scheduledStartTime"),
        "actual_start": live.get("actualStartTime"),
        "thumbnail": snippet["thumbnails"]["high"]["url"],
        "url": "https://www.youtube.com/watch?v=" + video_id
    }

def format_time(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))

def discord_timestamp(dt: datetime, fmt: str = "R") -> str:
    """Erstellt einen Discord-Timestamp aus einem datetime-Objekt"""
    ts = int(dt.timestamp())
    return f"<t:{ts}:{fmt}>"

async def update_countdown(msg: discord.Message, scheduled_start: datetime):
    """Aktualisiert den Embed mit Discord-Timestamp"""
    embed = msg.embeds[0]
    url = embed.footer.text.split("YTURL:")[1]
    ts = discord_timestamp(scheduled_start, "R")
    embed.description = f"|@everyone|\n[Premiere]({url}) startet {ts}"
    await msg.edit(embed=embed)
    # kein Loop nötig, Discord zeigt automatisch relative Zeit an

def register(bot):
    yt_group = discord.SlashCommandGroup(
        name="yt",
        description="Youtube Befehle"
    )

    @yt_group.command(name="premiere")
    async def premiere(ctx, url:str):
        await ctx.defer()
        guild = ctx.guild
        video_id = get_video_id(url)
        info = fetch_youtube_info(video_id)

        if not info or info["broadcast_status"] != "upcoming":
            return await ctx.send("Das Video wurde nicht gefunden oder ist keine Premiere.")
        
        category = discord.utils.get(guild.categories, name="Premieren")
        if not category:
            category = await guild.create_category("Premieren")

        channel_name = info["title"].replace(" ", "-")[:90]
        channel = await guild.create_text_channel(channel_name, category=category)

        embed = discord.Embed(title=info["title"])
        embed.set_footer(text=f"YTURL: {url}")
        msg = await channel.send(embed=embed)

        scheduled_start = format_time(info["scheduled_start"])
        await update_countdown(msg, scheduled_start)

        return await ctx.send(f"Premiere erstellt: {msg.jump_url}")

    bot.add_application_command(yt_group)
