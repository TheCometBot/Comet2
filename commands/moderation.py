import discord
from discord.ext import commands
from discord import Embed
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


async def respond_with_view(ctx, embed: Embed, preferred_lang: str):
    embed_title = await translate_text(embed.title, preferred_lang)
    embed_description = await translate_text(embed.description, preferred_lang)
    new_embed = Embed(title=embed_title, description=embed_description, color=embed.color)
    
    class LangView(discord.ui.View):
        def __init__(self):
            super().__init__()
        
        @discord.ui.button(label="DE", style=discord.ButtonStyle.secondary, disabled=(preferred_lang=="de"))
        async def de_button(self, button, interaction):
            await interaction.response.edit_message(embed=new_embed, view=self)
        
        @discord.ui.button(label="EN", style=discord.ButtonStyle.secondary, disabled=(preferred_lang=="en"))
        async def en_button(self, button, interaction):
            en_embed = Embed(title=await translate_text(embed.title, "en"),
                             description=await translate_text(embed.description, "en"),
                             color=embed.color)
            await interaction.response.edit_message(embed=en_embed, view=self)
    
    view = LangView()
    await ctx.respond(embed=new_embed, view=view)

def register(bot: commands.Bot, db=None, ):

    mod_group = discord.SlashCommandGroup(
        name="moderation",
        description="Moderation-Befehle wie Kick, Ban, Mute, Warn"
    )

    def make_embed(title, description, color=discord.Color.blue()):
        return Embed(title=title, description=description, color=color)

    @mod_group.command(name="kick", description="Kickt ein Mitglied")
    @commands.has_permissions(kick_members=True)
    async def kick(ctx, member: discord.Member, reason: str = None, preferred_lang: str = "de"):
        await ctx.defer()
        if ctx.guild.me.top_role <= member.top_role:
            embed = make_embed("❌ Fehler", "Ich kann diesen Nutzer nicht kicken (höhere Rolle).", discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        await member.kick(reason=reason)
        embed = make_embed("✅ Mitglied gekickt", f"{member.mention} wurde gekickt.\nGrund: {reason or 'Keiner'}", discord.Color.green())
        await respond_with_view(ctx, embed, preferred_lang)

    @mod_group.command(name="ban", description="Bannt ein Mitglied")
    @commands.has_permissions(ban_members=True)
    async def ban(ctx, member: discord.Member, reason: str = None, preferred_lang: str = "de"):
        await ctx.defer()
        if ctx.guild.me.top_role <= member.top_role:
            embed = make_embed("❌ Fehler", "Ich kann diesen Nutzer nicht bannen (höhere Rolle).", discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        await member.ban(reason=reason)
        embed = make_embed("✅ Mitglied gebannt", f"{member.mention} wurde gebannt.\nGrund: {reason or 'Keiner'}", discord.Color.green())
        await respond_with_view(ctx, embed, preferred_lang)

    @mod_group.command(name="mute", description="Mute ein Mitglied")
    @commands.has_permissions(manage_roles=True)
    async def mute(ctx, member: discord.Member, reason: str = None, preferred_lang: str = "de"):
        await ctx.defer()
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not muted_role:
            muted_role = await ctx.guild.create_role(name="Muted")
            for channel in ctx.guild.channels:
                await channel.set_permissions(muted_role, speak=False, send_messages=False)
        await member.add_roles(muted_role, reason=reason)
        embed = make_embed("✅ Mitglied gemutet", f"{member.mention} wurde gemutet.\nGrund: {reason or 'Keiner'}", discord.Color.orange())
        await respond_with_view(ctx, embed, preferred_lang)

    @mod_group.command(name="unmute", description="Unmute ein Mitglied")
    @commands.has_permissions(manage_roles=True)
    async def unmute(ctx, member: discord.Member, preferred_lang: str = "de"):
        await ctx.defer()
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if muted_role in member.roles:
            await member.remove_roles(muted_role)
            embed = make_embed("✅ Mitglied entmutet", f"{member.mention} wurde entmutet.", discord.Color.green())
        else:
            embed = make_embed("ℹ️ Info", f"{member.mention} ist nicht gemutet.", discord.Color.blue())
        await respond_with_view(ctx, embed, preferred_lang)

    @mod_group.command(name="warn", description="Verwarnt ein Mitglied")
    @commands.has_permissions(manage_messages=True)
    async def warn(ctx, member: discord.Member, reason: str = None, preferred_lang: str = "de"):
        await ctx.defer()
        if member.bot:
            embed = make_embed("❌ Fehler", "Du kannst Bots nicht verwarnen.", discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        try:
            await member.send(f'⚠️ Du wurdest in {ctx.guild.name} verwarnt. Grund: {reason or "Keiner"}')
        except discord.Forbidden:
            pass
        db_path = f"servers/{ctx.guild.id}/users/{member.id}/moderation"
        warnings = db.get(f"{db_path}/warnings") or 0
        db.update(db_path, {"warnings": warnings + 1})
        embed = make_embed("⚠️ Verwarnung", f"{member.mention} wurde verwarnt.\nGrund: {reason or 'Keiner'}", discord.Color.orange())
        await respond_with_view(ctx, embed, preferred_lang)

    @mod_group.command(name="warnings", description="Zeigt die Anzahl der Verwarnungen eines Mitglieds an")
    async def warnings(ctx, member: discord.Member = None, preferred_lang: str = "de"):
        await ctx.defer()
        if member is None:
            member = ctx.author
        user_id = str(member.id)
        server_id = str(ctx.guild.id)
        warnings_count = db.get(f"servers/{server_id}/users/{user_id}/moderation/warnings") or 0
        if warnings_count > 0:
            embed = make_embed("⚠️ Verwarnungen", f"{member.mention} hat **{warnings_count} Verwarnung(en)**.", discord.Color.orange())
        else:
            embed = make_embed("✅ Verwarnungen", f"{member.mention} hat keine Verwarnungen.", discord.Color.green())
        await respond_with_view(ctx, embed, preferred_lang)

    @mod_group.command(name="clearwarnings", description="Löscht alle Verwarnungen eines Mitglieds")
    @commands.has_permissions(manage_messages=True)
    async def clearwarnings(ctx, member: discord.Member, preferred_lang: str = "de"):
        await ctx.defer()
        if member.bot:
            embed = make_embed("❌ Fehler", "Du kannst Bots keine Verwarnungen löschen.", discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        db_path = f"servers/{ctx.guild.id}/users/{member.id}/moderation"
        db.update(db_path, {"warnings": 0})
        embed = make_embed("✅ Verwarnungen gelöscht", f"Alle Verwarnungen von {member.mention} wurden gelöscht.", discord.Color.green())
        await respond_with_view(ctx, embed, preferred_lang)

    @mod_group.command(name="banlist", description="Zeigt die Liste der gebannten Mitglieder an")
    async def banlist(ctx, preferred_lang: str = "de"):
        await ctx.defer()
        bans = [ban async for ban in ctx.guild.bans()]
        if not bans:
            embed = make_embed("ℹ️ Info", "Es sind keine Mitglieder gebannt.", discord.Color.blue())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        embed = make_embed("🚫 Gebannte Mitglieder", "", discord.Color.red())
        for ban in bans:
            embed.add_field(name=str(ban.user), value=f"Grund: {ban.reason or 'Keiner'}", inline=False)
        await respond_with_view(ctx, embed, preferred_lang)

    bot.add_application_command(mod_group)
