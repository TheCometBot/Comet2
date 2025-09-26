import discord
from discord.ext import commands
from discord.ui import View, Button
from mailtm import Email
import imgkit
import io
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator  # pip install googletrans==4.0.0-rc1
import asyncio

async def translate_text(text: str, dest_lang: str):
    loop = asyncio.get_event_loop()
    try:
        # deep-translator ist blockierend, deshalb auch in Thread auslagern
        result = await loop.run_in_executor(
            None, lambda: GoogleTranslator(source="auto", target=dest_lang).translate(text)
        )
        return result
    except Exception:
        return text  # fallback


async def respond_with_view(ctx, embed: discord.Embed, preferred_lang: str):
    embed_title = await translate_text(embed.title, preferred_lang)
    embed_description = await translate_text(embed.description, preferred_lang)
    new_embed = discord.Embed(title=embed_title, description=embed_description, color=embed.color)

    class LangView(View):
        def __init__(self):
            super().__init__()

        @discord.ui.button(label="DE", style=discord.ButtonStyle.secondary, disabled=(preferred_lang=="de"))
        async def de_button(self, button, interaction):
            await interaction.response.edit_message(embed=new_embed, view=self)

        @discord.ui.button(label="EN", style=discord.ButtonStyle.secondary, disabled=(preferred_lang=="en"))
        async def en_button(self, button, interaction):
            en_embed = discord.Embed(
                title=await translate_text(embed.title, "en"),
                description=await translate_text(embed.description, "en"),
                color=embed.color
            )
            await interaction.response.edit_message(embed=en_embed, view=self)

    view = LangView()
    await ctx.respond(embed=new_embed, view=view)

def register(bot: commands.Bot, db=None):
    u_group = discord.SlashCommandGroup(
        name="utility",
        description="Verschiedene nützliche Befehle"
    )

    @u_group.command(name="teampmail", description="Erstellt eine temporäre E-Mail-Adresse")
    async def teampmail(ctx, preferred_lang: str = "de"):
        await ctx.defer()
        botmessage = await ctx.respond("Erstelle Postfach... ⏳", ephemeral=True)
        email = Email()
        email.register()
        emails = []

        embed = discord.Embed(
            title="📧 Temporäre E-Mail-Adresse",
            description=f"Deine temporäre E-Mail-Adresse lautet:\n``{email.address}``",
            color=discord.Color.blue()
        )
        embed.add_field(name="Warte auf neue E-Mails...", value="(Die E-Mails werden alle 10 Sekunden überprüft)", inline=False)

        async def mail_listener(message):
            subject = message['subject'] or "(Kein Betreff)"
            sender = message['from']['address'] or "(Unbekannter Absender)"
            body = message['text'] if message['text'] else None
            emails.append((subject, sender, body))

            embed.clear_fields()
            for idx, (subj, sndr, content) in enumerate(emails[-5:], start=1):
                if content:  # Textversion
                    embed.add_field(name=f"{idx}. {subj}", value=f"Von: {sndr}\n{content[:200]}...", inline=False)
                else:  # HTML als Bild rendern
                    html_data = message['html']
                    img_bytes = imgkit.from_string(html_data, False)
                    file = discord.File(io.BytesIO(img_bytes), filename=f"email_{idx}.png")
                    embed.add_field(name=f"{idx}. {subj}", value=f"Von: {sndr}", inline=False)
                    await botmessage.reply(file=file)

            embed.set_footer(text="Nur die letzten 5 E-Mails werden angezeigt.")
            await botmessage.edit(embed=embed)

        email.start(lambda msg: bot.loop.create_task(mail_listener(msg)), interval=10)
        await botmessage.edit(embed=embed)

    @u_group.command(name="ping", description="Zeigt die Latenz des Bots an")
    async def ping(ctx, preferred_lang: str = "de"):
        await ctx.defer()
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latenz: {round(bot.latency*1000)}ms",
            color=discord.Color.green()
        )
        await respond_with_view(ctx, embed, preferred_lang)

    @u_group.command(name="countdown", description="Erstellt einen Countdown")
    @discord.option(
        "time",
        description="Wähle entweder ein Datum+Uhrzeit(DD.MM.YYYY HH:MM) oder eine Interval(DD:HH:MM:SS)",
        type=str,
        required=True
    )
    async def countdown(ctx, time: str, preferred_lang: str = "de"):
        await ctx.defer()

        def discord_timestamp(dt: datetime, fmt: str = "R") -> str:
            ts = int(dt.timestamp())
            return f"<t:{ts}:{fmt}>"

        def format_dt(dt: str):
            return datetime.strptime(dt, "%d.%m.%Y %H:%M")

        def format_interval(interval: str):
            parts = list(map(int, interval.split(":")))
            while len(parts) < 4:
                parts.insert(0, 0)
            d, h, m, s = parts
            return datetime.now() + timedelta(days=d, hours=h, minutes=m, seconds=s)

        if "." in time:
            t = format_dt(time)
        else:
            t = format_interval(time)

        ts = discord_timestamp(t)
        tsf = discord_timestamp(t, fmt="F")

        embed = discord.Embed(
            title="⏳ Countdown",
            description=f"Countdown endet {ts} (am {tsf}).",
            color=discord.Color.random()
        )
        await respond_with_view(ctx, embed, preferred_lang)

    bot.add_application_command(u_group)
