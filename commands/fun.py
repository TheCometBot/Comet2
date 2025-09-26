import discord
from discord.ext import commands
import random
import aiohttp
import asyncio
from deep_translator import GoogleTranslator
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

class LangSwitchView(discord.ui.View):
    def __init__(self, message: discord.Message, original_embed: discord.Embed, preferred_lang: str):
        super().__init__(timeout=None)
        self.message = message
        self.original_embed = original_embed
        self.current_lang = preferred_lang
        self.add_item(discord.ui.Button(label="Deutsch", style=discord.ButtonStyle.primary, disabled=(preferred_lang=="de"), custom_id="lang_de"))
        self.add_item(discord.ui.Button(label="English", style=discord.ButtonStyle.primary, disabled=(preferred_lang=="en"), custom_id="lang_en"))

    async def switch_language(self, lang: str, interaction: discord.Interaction):
        if self.current_lang == lang:
            return
        new_embed = discord.Embed(title=self.original_embed.title, color=self.original_embed.color)
        new_embed.description = await translate_text(self.original_embed.description or "", lang)
        for f in self.original_embed.fields:
            new_embed.add_field(name=await translate_text(f.name, lang), value=await translate_text(f.value, lang), inline=f.inline)
        self.current_lang = lang
        self.clear_items()
        self.add_item(discord.ui.Button(label="Deutsch", style=discord.ButtonStyle.primary, disabled=(lang=="de"), custom_id="lang_de"))
        self.add_item(discord.ui.Button(label="English", style=discord.ButtonStyle.primary, disabled=(lang=="en"), custom_id="lang_en"))
        await interaction.response.edit_message(embed=new_embed, view=self)

    @discord.ui.button(label="Deutsch", style=discord.ButtonStyle.primary, custom_id="lang_de")
    async def switch_de(self, button, interaction: discord.Interaction):
        await self.switch_language("de", interaction)

    @discord.ui.button(label="English", style=discord.ButtonStyle.primary, custom_id="lang_en")
    async def switch_en(self, button, interaction: discord.Interaction):
        await self.switch_language("en", interaction)

def register(bot: commands.Bot, db=None):
    fun_group = discord.SlashCommandGroup(name="fun", description="Spaßbefehle")

    async def respond_with_view(ctx, embed: discord.Embed, preferred_lang: str = "de"):
        msg = await ctx.respond(embed=embed)
        msg_obj = await msg
        view = LangSwitchView(msg_obj, embed, preferred_lang)
        await msg_obj.edit(view=view)

    # ---------------- Münzwurf ----------------
    @fun_group.command(name="coinflip", description="Spielt eine Runde Münzwurf")
    async def coinflip(ctx, preferred_lang: str = "de"):
        await ctx.defer()
        result = random.choice(["Kopf", "Zahl"])
        embed = discord.Embed(title="🪙 Münzwurf", description=f"Das Ergebnis ist: **{result}**", color=discord.Color.gold())
        await respond_with_view(ctx, embed, preferred_lang)

    # ---------------- Würfeln ----------------
    @fun_group.command(name="roll", description="Würfelt eine Zahl zwischen 1 und 6")
    async def roll(ctx, preferred_lang: str = "de"):
        await ctx.defer()
        result = random.randint(1, 6)
        embed = discord.Embed(title="🎲 Würfeln", description=f"Du hast eine **{result}** gewürfelt!", color=discord.Color.blue())
        await respond_with_view(ctx, embed, preferred_lang)

    # ---------------- RPS gegen Bot ----------------
    @fun_group.command(name="rps", description="Spielt Schere, Stein, Papier")
    @discord.option("choice", description="Wähle Schere, Stein oder Papier", choices=["Schere", "Stein", "Papier"])
    async def rps(ctx, choice: str, preferred_lang: str = "de"):
        await ctx.defer()
        choices = ["Schere", "Stein", "Papier"]
        bot_choice = random.choice(choices)

        if choice == bot_choice:
            result_text = "🤝 Unentschieden!"
            color = discord.Color.greyple()
        elif (choice == "Schere" and bot_choice == "Papier") or (choice == "Stein" and bot_choice == "Schere") or (choice == "Papier" and bot_choice == "Stein"):
            result_text = "🎉 Du gewinnst!"
            color = discord.Color.green()
        else:
            result_text = "😈 Ich gewinne!"
            color = discord.Color.red()

        embed = discord.Embed(title="✂️🪨📜 Schere, Stein, Papier",
                              description=f"Du hast **{choice}** gewählt.\nIch habe **{bot_choice}** gewählt.\n\n{result_text}",
                              color=color)
        await respond_with_view(ctx, embed, preferred_lang)

        # ---------------- RPS Online ----------------
    @fun_group.command(name="rps-online", description="Spielt Schere, Stein, Papier gegen einen anderen Nutzer")
    @discord.option("opponent", description="Wähle einen Gegner (optional)", type=discord.Member, required=False)
    @discord.option("eco", description="Einsatz (optional)", type=int, required=False, default=0)
    async def rps_online(ctx, opponent: discord.Member = None, eco: int = 0, preferred_lang: str = "de"):
        await ctx.defer()
        if eco < 0:
            embed = discord.Embed(title="❌ Fehler", description="Der Einsatz kann nicht unter 0 sein!", color=discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        if opponent and opponent.bot:
            embed = discord.Embed(title="❌ Fehler", description="Du kannst keinen Bot herausfordern!", color=discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return
        if opponent and opponent == ctx.author:
            embed = discord.Embed(title="❌ Fehler", description="Du kannst dich nicht selbst herausfordern!", color=discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return

        server_id = str(ctx.guild.id)
        user1_id = str(ctx.author.id)
        bal1 = db.get(f"servers/{server_id}/users/{user1_id}/eco/balance") or 0
        if bal1 < eco:
            embed = discord.Embed(title="❌ Fehler", description="Du hast nicht genug Balance für diesen Einsatz!", color=discord.Color.red())
            await respond_with_view(ctx, embed, preferred_lang)
            return

        result = {"p1": None, "p2": None}

        class RPSOnlineView(discord.ui.View):
            def __init__(self, player1, player2=None):
                super().__init__(timeout=60)
                self.player1 = player1
                self.player2 = player2
                self.game_started = player2 is not None
                self.embed = discord.Embed(
                    title="✂️🪨📜 RPS Online",
                    description=f"{player1.mention} möchte spielen!" + (f"\nEinsatz: **{eco} Coins**" if eco > 0 else ""),
                    color=discord.Color.purple()
                )

            async def on_timeout(self):
                self.embed.title = "⏰ Spiel abgebrochen"
                self.embed.color = discord.Color.red()
                if not self.game_started:
                    self.embed.description = "❌ Kein Gegner hat sich beteiligt."
                else:
                    self.embed.description = "❌ Das Spiel wurde aufgrund von Zeitüberschreitung abgebrochen."
                await message.edit(embed=self.embed, view=None)
                self.stop()

            async def check_winner(self, interaction):
                if result["p1"] and result["p2"]:
                    p1, p2 = result["p1"], result["p2"]
                    if p1 == p2:
                        self.embed.title = "🤝 Unentschieden!"
                        self.embed.description = f"Beide haben **{p1}** gewählt.\nEinsatz zurück an beide."
                    else:
                        if (p1=="Schere" and p2=="Papier") or (p1=="Stein" and p2=="Schere") or (p1=="Papier" and p2=="Stein"):
                            winner, loser, wp, lp = self.player1, self.player2, p1, p2
                        else:
                            winner, loser, wp, lp = self.player2, self.player1, p2, p1
                        if eco > 0:
                            win_id, lose_id = str(winner.id), str(loser.id)
                            bal_w = db.get(f"servers/{server_id}/users/{win_id}/eco/balance") or 0
                            bal_l = db.get(f"servers/{server_id}/users/{lose_id}/eco/balance") or 0
                            db.update(f"servers/{server_id}/users/{win_id}/eco", {"balance": bal_w + eco})
                            db.update(f"servers/{server_id}/users/{lose_id}/eco", {"balance": bal_l - eco})
                        self.embed.title = f"🏆 {winner.display_name} gewinnt!"
                        self.embed.color = discord.Color.green()
                        self.embed.description = f"**{winner.display_name}** gewinnt mit **{wp}** gegen **{lp}**!\nEinsatz: **{eco} Coins**"
                    await interaction.response.edit_message(embed=self.embed, view=None)
                    self.stop()

            async def interaction_check(self, interaction):
                if not self.game_started and interaction.user != self.player1:
                    self.player2 = interaction.user
                    self.game_started = True
                    user2_id = str(self.player2.id)
                    bal2 = db.get(f"servers/{server_id}/users/{user2_id}/eco/balance") or 0
                    if bal2 < eco:
                        await interaction.response.send_message("❌ Nicht genug Coins!", ephemeral=True)
                        return False
                    self.embed.description = f"{self.player1.mention} fordert {self.player2.mention} zu RPS heraus!\nEinsatz: **{eco} Coins**"
                    await interaction.response.edit_message(embed=self.embed)
                    return False
                elif interaction.user not in [self.player1, self.player2]:
                    await interaction.response.send_message("❌ Du bist nicht Teil dieses Spiels!", ephemeral=True)
                    return False
                return True

            @discord.ui.button(label="Schere ✂️", style=discord.ButtonStyle.primary)
            async def schere(self, button, interaction):
                if interaction.user == self.player1:
                    result["p1"] = "Schere"
                else:
                    result["p2"] = "Schere"
                await interaction.response.defer()
                if self.game_started:
                    await self.check_winner(interaction)

            @discord.ui.button(label="Stein 🪨", style=discord.ButtonStyle.success)
            async def stein(self, button, interaction):
                if interaction.user == self.player1:
                    result["p1"] = "Stein"
                else:
                    result["p2"] = "Stein"
                await interaction.response.defer()
                if self.game_started:
                    await self.check_winner(interaction)

            @discord.ui.button(label="Papier 📜", style=discord.ButtonStyle.danger)
            async def papier(self, button, interaction):
                if interaction.user == self.player1:
                    result["p1"] = "Papier"
                else:
                    result["p2"] = "Papier"
                await interaction.response.defer()
                if self.game_started:
                    await self.check_winner(interaction)

        message = await ctx.respond(embed=discord.Embed(title="✂️🪨📜 RPS Online", description="Spiel wird gestartet...", color=discord.Color.purple()))
        msg_obj = await message.original_message()
        view = RPSOnlineView(ctx.author, opponent)
        await msg_obj.edit(embed=view.embed, view=view)


    # ---------------- Fun-API Befehle ----------------
    async def fetch_text_embed(ctx, url, title, json_path=None, preferred_lang="de"):
        await ctx.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if json_path:
                        for key in json_path:
                            data = data.get(key, {})
                    text = data if isinstance(data, str) else str(data)
                else:
                    text = "Fehler beim Abrufen der Daten."
        embed = discord.Embed(title=title, description=text, color=discord.Color.orange())
        await respond_with_view(ctx, embed, preferred_lang)

    @fun_group.command(name="useless-fact", description="Gibt einen nutzlosen Fakt aus")
    async def useless_fact(ctx, preferred_lang: str = "de"):
        await fetch_text_embed(ctx, "https://uselessfacts.jsph.pl/random.json?language=de", "🤪 Nutzloser Fakt", json_path=["text"], preferred_lang=preferred_lang)

    @fun_group.command(name="excuser", description="Gibt eine zufällige Ausrede aus")
    async def excuser(ctx, preferred_lang: str = "de"):
        await fetch_text_embed(ctx, "https://excuser.herokuapp.com/v1/excuse", "🙊 Ausrede", json_path=[0,"excuse"], preferred_lang=preferred_lang)

    @fun_group.command(name="chucknorris", description="Gibt einen Chuck Norris Witz aus")
    async def chucknorris(ctx, preferred_lang: str = "de"):
        await fetch_text_embed(ctx, "https://api.chucknorris.io/jokes/random", "🥋 Chuck Norris Witz", json_path=["value"], preferred_lang=preferred_lang)

    @fun_group.command(name="advice", description="Gibt eine zufällige Lebensweisheit aus")
    async def advice(ctx, preferred_lang: str = "de"):
        await fetch_text_embed(ctx, "https://api.adviceslip.com/advice", "💡 Lebensweisheit", json_path=["slip","advice"], preferred_lang=preferred_lang)

    @fun_group.command(name="dog", description="Gibt ein zufälliges Hundebild aus")
    async def dog(ctx, preferred_lang: str = "de"):
        await ctx.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    url = data.get("message", "")
                else:
                    url = ""
        embed = discord.Embed(title="🐶 Zufälliges Hundebild", color=discord.Color.light_grey())
        if url:
            embed.set_image(url=url)
        else:
            embed.description = "Fehler beim Abrufen des Bildes."
        await respond_with_view(ctx, embed, preferred_lang)

    @fun_group.command(name="pokemon", description="Gibt Information über ein Pokémon aus")
    async def pokemon(ctx, name: str, preferred_lang: str = "de"):
        await ctx.defer()
        url = f"https://pokeapi.co/api/v2/pokemon/{name.lower()}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    poke_name = data.get("name", "Unbekannt").title()
                    poke_id = data.get("id", "N/A")
                    types = [t['type']['name'].title() for t in data.get("types", [])]
                    abilities = [a['ability']['name'].title() for a in data.get("abilities", [])]
                    sprite = data.get("sprites", {}).get("front_default", "")
                    embed = discord.Embed(title=f"Pokémon: {poke_name} (#{poke_id})", color=discord.Color.red())
                    embed.add_field(name="Typen", value=", ".join(types) if types else "N/A", inline=False)
                    embed.add_field(name="Fähigkeiten", value=", ".join(abilities) if abilities else "N/A", inline=False)
                    if sprite:
                        embed.set_thumbnail(url=sprite)
                else:
                    embed = discord.Embed(title="❌ Fehler", description="Pokémon nicht gefunden.", color=discord.Color.red())
        await respond_with_view(ctx, embed, preferred_lang)

    @fun_group.command(name="age", description="Schätzt das Alter einer Person basierend auf dem Namen")
    async def age(ctx, member: discord.Member = None, preferred_lang: str = "de"):
        await ctx.defer()
        target = member or ctx.author
        url = f"https://api.agify.io?name={target.name}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    age = data.get("age", "unbekannt")
                else:
                    age = "unbekannt"
        embed = discord.Embed(title="🎂 Namensbasierte Altersschätzung",
                              description=f"Die geschätzte Alter von **{target.display_name}** ist **{age}** Jahre.",
                              color=discord.Color.purple())
        await respond_with_view(ctx, embed, preferred_lang)

    @fun_group.command(name="gender", description="Schätzt das Geschlecht einer Person basierend auf dem Namen")
    async def gender(ctx, target: str, preferred_lang: str = "de"):
        await ctx.defer()
        url = f"https://api.genderize.io?name={target}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    gender = data.get('gender')
                    probability = data.get('probability', 0) * 100
                else:
                    gender = "unbekannt"
                    probability = 100
        text = f"Das Geschlecht von **{target}** ist zu **{probability:.2f}%** wahrscheinlich **{'männlich' if gender=='male' else 'weiblich'}**."
        embed = discord.Embed(title="⚧ Namensbasierte Geschlechtsschätzung", description=text, color=discord.Color.purple())
        await respond_with_view(ctx, embed, preferred_lang)

    bot.add_application_command(fun_group)
