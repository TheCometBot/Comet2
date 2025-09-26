import discord
from discord.ext import commands
from discord import Embed
from ..modules import translate as tl

def register(bot: commands.Bot, db=None, ):

    mod_group = discord.SlashCommandGroup(
        name="moderation",
        description="Moderation-Befehle wie Kick, Ban, Mute, Warn"
    )

    def make_embed(title, description, color=discord.Color.blue()):
        return Embed(title=title, description=description, color=color)

    @mod_group.command(name="kick", description="Kickt ein Mitglied")
    @commands.has_permissions(kick_members=True)
    async def kick(ctx, member: discord.Member, reason: str = None):
        await ctx.defer()
        if ctx.guild.me.top_role <= member.top_role:
            await ctx.respond(embed=make_embed("❌ Fehler", "Ich kann diesen Nutzer nicht kicken (höhere Rolle).", discord.Color.red()))
            return
        await member.kick(reason=reason)
        await tl.respond_with_view(ctx, make_embed("✅ Mitglied gekickt", f"{member.mention} wurde gekickt.\nGrund: {reason or 'Keiner'}", discord.Color.green()), preferred_lang="de", mode="normal")

    @mod_group.command(name="ban", description="Bannt ein Mitglied")
    @commands.has_permissions(ban_members=True)
    async def ban(ctx, member: discord.Member, reason: str = None):
        await ctx.defer()
        if ctx.guild.me.top_role <= member.top_role:
            await tl.respond_with_view(ctx, make_embed("❌ Fehler", "Ich kann diesen Nutzer nicht bannen (höhere Rolle).", discord.Color.red()), preferred_lang="de", mode="normal")
            return
        await member.ban(reason=reason)
        await tl.respond_with_view(ctx, make_embed("✅ Mitglied gebannt", f"{member.mention} wurde gebannt.\nGrund: {reason or 'Keiner'}", discord.Color.green()), preferred_lang="de", mode="normal")

    @mod_group.command(name="mute", description="Mute ein Mitglied")
    @commands.has_permissions(manage_roles=True)
    async def mute(ctx, member: discord.Member, reason: str = None):
        await ctx.defer()
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not muted_role:
            muted_role = await ctx.guild.create_role(name="Muted")
            for channel in ctx.guild.channels:
                await channel.set_permissions(muted_role, speak=False, send_messages=False)
        await member.add_roles(muted_role, reason=reason)
        await tl.respond_with_view(ctx, make_embed("✅ Mitglied gemutet", f"{member.mention} wurde gemutet.\nGrund: {reason or 'Keiner'}", discord.Color.green()), preferred_lang="de", mode="normal")

    @mod_group.command(name="unmute", description="Unmute ein Mitglied")
    @commands.has_permissions(manage_roles=True)
    async def unmute(ctx, member: discord.Member):
        await ctx.defer()
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if muted_role in member.roles:
            await member.remove_roles(muted_role)
            await tl.respond_with_view(ctx, make_embed("✅ Mitglied entmutet", f"{member.mention} wurde entmutet.", discord.Color.green()), preferred_lang="de", mode="normal")
        else:
            await tl.respond_with_view(ctx, make_embed("❌ Fehler", f"{member.mention} ist nicht gemutet.", discord.Color.red()), preferred_lang="de", mode="normal")

    @mod_group.command(name="warn", description="Verwarnt ein Mitglied")
    @commands.has_permissions(manage_messages=True)
    async def warn(ctx, member: discord.Member, reason: str = None):
        await ctx.defer()
        if member.bot:
            await tl.respond_with_view(ctx, make_embed("❌ Fehler", "Du kannst Bots nicht verwarnen.", discord.Color.red()), preferred_lang="de", mode="normal")
            return
        try:
            await member.send(f'⚠️ Du wurdest in {ctx.guild.name} verwarnt. Grund: {reason or "Keiner"}\n\n--\n\nYou were warned in {ctx.guild.name}. Reason: {reason or "None"}\n\n--\n\n*Dies ist eine automatische Nachricht. / This is an automated message.*')
        except discord.Forbidden:
            pass
        db_path = f"servers/{ctx.guild.id}/users/{member.id}/moderation"
        warnings = db.get(f"{db_path}/warnings") or 0
        db.update(db_path, {"warnings": warnings + 1})
        await tl.respond_with_view(ctx, make_embed("✅ Mitglied verwarnt", f"{member.mention} wurde verwarnt.\nGrund: {reason or 'Keiner'}\n\nAktuelle Verwarnungen: **{warnings}**", discord.Color.green()), preferred_lang="de", mode="normal")

    @mod_group.command(name="warnings", description="Zeigt die Anzahl der Verwarnungen eines Mitglieds an")
    async def warnings(ctx, member: discord.Member = None):
        await ctx.defer()
        if member is None:
            member = ctx.author
        user_id = str(member.id)
        server_id = str(ctx.guild.id)
        warnings = db.get(f"servers/{server_id}/users/{user_id}/moderation/warnings") or 0
        if warnings > 0:
            embed = make_embed("⚠️ Verwarnungen", f"{member.mention} hat **{warnings} Verwarnung(en)**.", discord.Color.orange())
        else:
            embed = make_embed("✅ Verwarnungen", f"{member.mention} hat keine Verwarnungen.", discord.Color.green())
        await tl.respond_with_view(ctx, embed, preferred_lang="de", mode="normal")

    @mod_group.command(name="clearwarnings", description="Löscht alle Verwarnungen eines Mitglieds")
    @commands.has_permissions(manage_messages=True)
    async def clearwarnings(ctx, member: discord.Member):
        await ctx.defer()
        if member.bot:
            await ctx.respond(embed=make_embed("❌ Fehler", "Du kannst Bots keine Verwarnungen löschen.", discord.Color.red()))
            return
        db_path = f"servers/{ctx.guild.id}/users/{member.id}/moderation"
        db.update(db_path, {"warnings": 0})
        await tl.respond_with_view(ctx, make_embed("✅ Verwarnungen gelöscht", f"Alle Verwarnungen von {member.mention} wurden gelöscht.", discord.Color.green()), preferred_lang="de", mode="normal")

    @mod_group.command(name="banlist", description="Zeigt die Liste der gebannten Mitglieder an")
    async def banlist(ctx):
        await ctx.defer()
        bans = [ban async for ban in ctx.guild.bans()]
        if not bans:
            await ctx.respond(embed=make_embed("ℹ️ Info", "Es sind keine Mitglieder gebannt.", discord.Color.blue()))
            return
        embed = make_embed("🚫 Gebannte Mitglieder", "", discord.Color.red())
        for ban in bans:
            embed.add_field(name=str(ban.user), value=f"Grund: {ban.reason or 'Keiner'}", inline=False)
        await tl.respond_with_view(ctx, embed, preferred_lang="de", mode="normal")

    bot.add_application_command(mod_group)
