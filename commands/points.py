import discord
from discord.ext import commands
from googletrans import Translator  # pip install googletrans==4.0.0-rc1

translator = Translator()

async def translate_text(text: str, target_lang: str):
    if target_lang == "de":
        return text
    try:
        return translator.translate(text, dest=target_lang).text
    except:
        return text

async def respond_with_view(ctx, embed: discord.Embed, preferred_lang: str):
    embed_title = await translate_text(embed.title, preferred_lang)
    embed_description = await translate_text(embed.description, preferred_lang)
    new_embed = discord.Embed(title=embed_title, description=embed_description, color=embed.color)
    
    class LangView(discord.ui.View):
        def __init__(self):
            super().__init__()
        
        @discord.ui.button(label="DE", style=discord.ButtonStyle.secondary, disabled=(preferred_lang=="de"))
        async def de_button(self, button, interaction):
            await interaction.response.edit_message(embed=new_embed, view=self)
        
        @discord.ui.button(label="EN", style=discord.ButtonStyle.secondary, disabled=(preferred_lang=="en"))
        async def en_button(self, button, interaction):
            en_embed = discord.Embed(title=await translate_text(embed.title, "en"),
                                     description=await translate_text(embed.description, "en"),
                                     color=embed.color)
            await interaction.response.edit_message(embed=en_embed, view=self)
    
    view = LangView()
    await ctx.respond(embed=new_embed, view=view)

def register(bot: commands.Bot, db=None):
    points_group = discord.SlashCommandGroup(
        name="points",
        description="Verwaltet Punkte",
    )

    def make_embed(title, description, color=discord.Color.blue()):
        return discord.Embed(title=title, description=description, color=color)

    @points_group.command(name="show", description="Zeigt die Punkte eines Nutzers an")
    async def points(ctx, member: discord.Member = None, preferred_lang: str = "de"):
        await ctx.defer()
        member = member or ctx.author
        user_id = str(member.id)
        server_id = str(ctx.guild.id)
        points = db.get(f"servers/{server_id}/users/{user_id}/points/points") or 0
        embed = make_embed("⭐ Punkte", f"{member.mention} hat **{points} Punkte**", discord.Color.gold())
        await respond_with_view(ctx, embed, preferred_lang)

    @points_group.command(name="add", description="Fügt einem Nutzer Punkte hinzu")
    @commands.has_permissions(manage_guild=True)
    async def addpoints(ctx, member: discord.Member, amount: int, preferred_lang: str = "de"):
        await ctx.defer()
        if member.bot or amount <= 0:
            embed = make_embed("❌ Fehler", "Ungültiger Nutzer oder Betrag.", discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        user_id = str(member.id)
        server_id = str(ctx.guild.id)
        new_points = (db.get(f"servers/{server_id}/users/{user_id}/points/points") or 0) + amount
        db.update(f"servers/{server_id}/users/{user_id}/points", {"points": new_points})
        embed = make_embed("✅ Punkte hinzugefügt", f"{amount} Punkte wurden zu {member.mention} hinzugefügt.\nNeuer Punktestand: **{new_points} Punkte**", discord.Color.green())
        await respond_with_view(ctx, embed, preferred_lang)

    @points_group.command(name="remove", description="Entfernt Punkte von einem Nutzer")
    @commands.has_permissions(manage_guild=True)
    async def removepoints(ctx, member: discord.Member, amount: int, preferred_lang: str = "de"):
        await ctx.defer()
        if member.bot or amount <= 0:
            embed = make_embed("❌ Fehler", "Ungültiger Nutzer oder Betrag.", discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        user_id = str(member.id)
        server_id = str(ctx.guild.id)
        current_points = db.get(f"servers/{server_id}/users/{user_id}/points/points") or 0
        new_points = max(0, current_points - amount)
        db.update(f"servers/{server_id}/users/{user_id}/points", {"points": new_points})
        embed = make_embed("✅ Punkte entfernt", f"{amount} Punkte wurden von {member.mention} entfernt.\nNeuer Punktestand: **{new_points} Punkte**", discord.Color.orange())
        await respond_with_view(ctx, embed, preferred_lang)

    @points_group.command(name="set", description="Setzt die Punkte eines Nutzers auf einen bestimmten Wert")
    @commands.has_permissions(manage_guild=True)
    async def setpoints(ctx, member: discord.Member, amount: int, preferred_lang: str = "de"):
        await ctx.defer()
        if member.bot:
            embed = make_embed("❌ Fehler", "Bots können keine Punkte erhalten.", discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        user_id = str(member.id)
        server_id = str(ctx.guild.id)
        db.update(f"servers/{server_id}/users/{user_id}/points", {"points": amount})
        embed = make_embed("✅ Punkte gesetzt", f"Die Punkte von {member.mention} wurden auf **{amount} Punkte** gesetzt.", discord.Color.green())
        await respond_with_view(ctx, embed, preferred_lang)

    @points_group.command(name="leaderboard", description="Zeigt das Punkte-Ranking der Top 10 Nutzer an")
    async def pointsleaderboard(ctx, preferred_lang: str = "de"):
        await ctx.defer()
        server_id = str(ctx.guild.id)
        users_data = db.get(f"servers/{server_id}/users") or {}
        leaderboard = [(int(uid), data.get("points", {}).get("points", 0)) for uid, data in users_data.items() if data.get("points", {}).get("points", 0) > 0]
        leaderboard.sort(key=lambda x: x[1], reverse=True)
        top_10 = leaderboard[:10]

        if not top_10:
            embed = make_embed("🏆 Punkte-Ranking", "Es gibt keine Nutzer mit Punkten.", discord.Color.blue())
            await respond_with_view(ctx, embed, preferred_lang)
            return

        embed = make_embed("🏆 Punkte-Ranking", "Top 10 Nutzer mit den meisten Punkten", discord.Color.gold())
        for rank, (user_id, points) in enumerate(top_10, start=1):
            user = ctx.guild.get_member(user_id)
            if user:
                embed.add_field(name=f"{rank}. {user.display_name}", value=f"{points} Punkte", inline=False)
        await respond_with_view(ctx, embed, preferred_lang)

    @points_group.command(name="reset", description="Setzt die Punkte aller Nutzer auf 0 zurück")
    @commands.has_permissions(manage_guild=True)
    async def resetpoints(ctx, preferred_lang: str = "de"):
        await ctx.defer()
        server_id = str(ctx.guild.id)
        users_data = db.get(f"servers/{server_id}/users") or {}
        for user_id in users_data.keys():
            db.update(f"servers/{server_id}/users/{user_id}/points", {"points": 0})
        embed = make_embed("✅ Punkte zurückgesetzt", "Alle Punkte wurden auf 0 zurückgesetzt.", discord.Color.green())
        await respond_with_view(ctx, embed, preferred_lang)

    @points_group.command(name="give", description="Gibt einem anderen Nutzer Punkte von deinem Konto")
    async def givepoints(ctx, member: discord.Member, amount: int, preferred_lang: str = "de"):
        await ctx.defer()
        if member.bot or member.id == ctx.author.id or amount <= 0:
            embed = make_embed("❌ Fehler", "Ungültige Aktion.", discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        user_id = str(ctx.author.id)
        recipient_id = str(member.id)
        server_id = str(ctx.guild.id)
        sender_points = db.get(f"servers/{server_id}/users/{user_id}/points/points") or 0
        if sender_points < amount or sender_points < 50:
            embed = make_embed("❌ Fehler", "Du hast nicht genug Punkte, um diese Aktion durchzuführen.", discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        recipient_points = db.get(f"servers/{server_id}/users/{recipient_id}/points/points") or 0
        db.update(f"servers/{server_id}/users/{user_id}/points", {"points": sender_points - amount})
        db.update(f"servers/{server_id}/users/{recipient_id}/points", {"points": recipient_points + amount})
        embed = make_embed("✅ Punkte geschenkt", f"Du hast {amount} Punkte an {member.mention} gegeben.\nNeuer Punktestand: **{sender_points - amount} Punkte**", discord.Color.green())
        await respond_with_view(ctx, embed, preferred_lang)

    @points_group.command(name="change-to-coin", description="Wechselt Punkte in Coins um (1 Punkt = 2 Coins)")
    async def change_to_coin(ctx, amount: int, preferred_lang: str = "de"):
        await ctx.defer()
        if amount <= 0:
            embed = make_embed("❌ Fehler", "Der Betrag muss positiv sein.", discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        user_id = str(ctx.author.id)
        server_id = str(ctx.guild.id)
        user_points = db.get(f"servers/{server_id}/users/{user_id}/points/points") or 0
        if user_points < amount:
            embed = make_embed("❌ Fehler", "Du hast nicht genug Punkte.", discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        user_eco = db.get(f"servers/{server_id}/users/{user_id}/eco/balance") or 0
        db.update(f"servers/{server_id}/users/{user_id}/points", {"points": user_points - amount})
        db.update(f"servers/{server_id}/users/{user_id}/eco", {"balance": user_eco + amount * 2})
        embed = make_embed("✅ Punkte gewechselt", f"Du hast {amount} Punkte in **{amount*2} Coins** umgewandelt.\nNeuer Punktestand: {user_points - amount} Punkte\nKontostand: {user_eco + amount*2} Coins :coin:", discord.Color.green())
        await respond_with_view(ctx, embed, preferred_lang)

    bot.add_application_command(points_group)
