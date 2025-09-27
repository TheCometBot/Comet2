import discord
from discord.ext import commands
from discord.ui import View, Button
from mailtm import Email
import imgkit
import io
from datetime import datetime, timedelta
from modules import translate as tl

def register(bot: commands.Bot, db=None, ):

    u_group = discord.SlashCommandGroup(
        name="utility",
        description="Verschiedene nützliche Befehle"
    )

    def make_poll_embed(question: str, options: list, votes: dict = None):
        embed = discord.Embed(
            title="📊 Umfrage",
            description=f"**{question}**",
            color=discord.Color.blue()
        )
        for idx, opt in enumerate(options, start=1):
            vote_count = votes.get(idx-1, 0) if votes else 0
            embed.add_field(name=f"{idx}. {opt}", value=f"Stimmen: {vote_count}", inline=False)
        return embed

    @u_group.command(name="create", description="Erstellt eine Umfrage")
    @discord.option(
        "method",
        description="Wähle die Art der Umfrage",
        choices=["buttons", "reactions"]
    )
    async def create(ctx, question: str, option1: str, option2: str, option3: str = None, option4: str = None, method: str = "buttons"):
        await ctx.defer()
        options = [option1, option2]
        if option3: options.append(option3)
        if option4: options.append(option4)

        if method == "buttons":
            votes = {i: 0 for i in range(len(options))}
            voters = {}
            view = View()

            async def button_callback(interaction: discord.Interaction):
                nonlocal votes, voters
                if interaction.user.id in voters:
                    old_vote = voters[interaction.user.id]
                    votes[old_vote] -= 1
                voters[interaction.user.id] = int(interaction.data["custom_id"])
                votes[int(interaction.data["custom_id"])] += 1

                new_embed = make_poll_embed(question, options, votes)
                await interaction.response.edit_message(embed=new_embed, view=view)

            for idx, opt in enumerate(options):
                btn = Button(label=opt, style=discord.ButtonStyle.primary, custom_id=str(idx))
                btn.callback = button_callback
                view.add_item(btn)

            await ctx.respond(embed=make_poll_embed(question, options), view=view)

        elif method == "reactions":
            msg = await ctx.respond(embed=make_poll_embed(question, options))
            msg_obj = await msg.original_message()
            emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
            for idx, _ in enumerate(options):
                await msg_obj.add_reaction(emojis[idx])

    @u_group.command(name="teampmail", description="Erstellt eine temporäre E-Mail-Adresse")
    async def teampmail(ctx):
        await ctx.defer()
        text = tl.translate_text("Erstelle Postfach... ⏳", "de")
        botmessage = await ctx.respond(text, ephemeral=True)
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
            await tl.respond_with_view(ctx, embed, preferred_lang="de", mode="edit", message_to_edit=botmessage, ephemeral=True)

        email.start(lambda msg: bot.loop.create_task(mail_listener(msg)), interval=10)
        await tl.respond_with_view(ctx, embed, preferred_lang="de", mode="edit", message_to_edit=botmessage, ephemeral=True)

    @u_group.command(name="ping", description="Zeigt die Latenz des Bots an")
    async def ping(ctx):
        await ctx.respond(f"Pong! 🏓 Latenz/Latency: {round(bot.latency * 1000)}ms")

    @u_group.command(name="countdown", description="Erstellt einen Countdown")
    @discord.option(
        "time",
        description="Wähle entweder ein Datum+Uhrzeit(DD.MM.YYYY HH:MM) oder eine Interval(DD:HH:MM:SS)",
        type=str,
        required=True
    )
    async def countdown(ctx, time):
        def discord_timestamp(dt: datetime, fmt: str = "R") -> str:
            ts = int(dt.timestamp())
            return f"<t:{ts}:{fmt}>"
        def format_dt(dt: str):
            return datetime.strptime(dt, "%d.%m.%y %h:%m:%s")
        def format_interval(interval: str):
            d, h, m, s = map(interval.split(":"))
            delta = timedelta(days=d, hours=h, minutes=m, seconds=s)
            return datetime.now + delta
        if "." in time:
            t = format_dt(time)
        else:
            t = format_interval(time)
        ts = discord_timestamp(t)
        tsf = discord_timestamp(t, fmt="F")
        embed = discord.Embed(
            "Countdown",
            description="Countdown endet {ts}(am {tsf}).",
            color=discord.Color.random()
        )
        await tl.respond_with_view(ctx, embed, preferred_lang="de", mode="normal")

    bot.add_application_command(u_group)
