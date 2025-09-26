import discord
from discord.ext import commands
import random
import aiohttp

def register(bot: commands.Bot, db=None, ):

    fun_group = discord.SlashCommandGroup(
        name="fun",
        description="Spaßbefehle"
    )

    # ---------------- Münzwurf ----------------
    @fun_group.command(name="coinflip", description="Spielt eine Runde Münzwurf")
    async def coinflip(ctx):
        await ctx.defer()
        result = random.choice(["Kopf", "Zahl"])
        embed = discord.Embed(
            title="🪙 Münzwurf",
            description=f"Das Ergebnis ist: **{result}**",
            color=discord.Color.gold()
        )
        await ctx.respond(embed=embed)

    # ---------------- Würfeln ----------------
    @fun_group.command(name="roll", description="Würfelt eine Zahl zwischen 1 und 6")
    async def roll(ctx):
        await ctx.defer()
        result = random.randint(1, 6)
        embed = discord.Embed(
            title="🎲 Würfeln",
            description=f"Du hast eine **{result}** gewürfelt!",
            color=discord.Color.blue()
        )
        await ctx.respond(embed=embed)

    # ---------------- RPS gegen Bot ----------------
    @fun_group.command(name="rps", description="Spielt Schere, Stein, Papier")
    @discord.option(
        "choice",
        description="Wähle Schere, Stein oder Papier",
        choices=["Schere", "Stein", "Papier"]
    )
    async def rps(ctx, choice: str):
        await ctx.defer()
        choices = ["Schere", "Stein", "Papier"]
        bot_choice = random.choice(choices)

        if choice == bot_choice:
            result = "🤝 Unentschieden!"
            color = discord.Color.greyple()
        elif (choice == "Schere" and bot_choice == "Papier") or \
             (choice == "Stein" and bot_choice == "Schere") or \
             (choice == "Papier" and bot_choice == "Stein"):
            result = "🎉 Du gewinnst!"
            color = discord.Color.green()
        else:
            result = "😈 Ich gewinne!"
            color = discord.Color.red()

        embed = discord.Embed(
            title="✂️🪨📜 Schere, Stein, Papier",
            description=f"Du hast **{choice}** gewählt.\nIch habe **{bot_choice}** gewählt.\n\n{result}",
            color=color
        )
        await ctx.respond(embed=embed)

    # ---------------- RPS Online ----------------
    @fun_group.command(name="rps-online", description="Spielt Schere, Stein, Papier gegen einen anderen Nutzer")
    @discord.option("opponent", description="Wähle einen Gegner (optional)", type=discord.Member, required=False)
    @discord.option("eco", description="Einsatz (optional)", type=int, required=False, default=0)
    async def rps_online(ctx, opponent: discord.Member = None, eco:int=0):
        await ctx.defer()
        if eco < 0:
            await ctx.respond("❌ Der Einsatz kann nicht unter 0 sein!", ephemeral=True)
            return
        if opponent and opponent.bot:
            await ctx.respond("❌ Du kannst keinen Bot herausfordern!", ephemeral=True)
            return
        if opponent and opponent == ctx.author:
            await ctx.respond("❌ Du kannst dich nicht selbst herausfordern!", ephemeral=True)
            return

        server_id = str(ctx.guild.id)
        user1_id = str(ctx.author.id)
        bal1 = db.get(f"servers/{server_id}/users/{user1_id}/eco/balance") or 0
        if bal1 < eco:
            await ctx.respond("❌ Du hast nicht genug Balance für diesen Einsatz!", ephemeral=True)
            return

        result = {"p1": None, "p2": None}

        class RPSView(discord.ui.View):
            def __init__(self, player1, player2=None, eco=0):
                super().__init__(timeout=60)
                self.player1 = player1
                self.player2 = player2
                self.eco = eco
                self.game_started = player2 is not None
                self.embed = discord.Embed(
                    title="✂️🪨📜 Schere, Stein, Papier - Online",
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
                await self.message.edit(embed=self.embed, view=None)
                self.stop()

            async def check_winner(self, interaction):
                if result["p1"] and result["p2"]:
                    p1, p2 = result["p1"], result["p2"]

                    if p1 == p2:
                        self.embed.title = "🤝 Unentschieden!"
                        self.embed.description = f"Beide haben **{p1}** gewählt.\nEinsatz zurück an beide."
                        await interaction.message.edit(embed=self.embed, view=None)
                        self.stop()
                        return

                    if (p1 == "Schere" and p2 == "Papier") or \
                       (p1 == "Stein" and p2 == "Schere") or \
                       (p1 == "Papier" and p2 == "Stein"):
                        winner, loser, wp, lp = self.player1, self.player2, p1, p2
                    else:
                        winner, loser, wp, lp = self.player2, self.player1, p2, p1

                    if self.eco > 0:
                        win_id, lose_id = str(winner.id), str(loser.id)
                        bal_w = db.get(f"servers/{server_id}/users/{win_id}/eco/balance") or 0
                        bal_l = db.get(f"servers/{server_id}/users/{lose_id}/eco/balance") or 0
                        db.update(f"servers/{server_id}/users/{win_id}/eco", {"balance": bal_w + self.eco})
                        db.update(f"servers/{server_id}/users/{lose_id}/eco", {"balance": bal_l - self.eco})

                    self.embed.title = f"🏆 {winner.display_name} gewinnt!"
                    self.embed.color = discord.Color.green()
                    self.embed.description = f"**{winner.display_name}** gewinnt mit **{wp}** gegen **{lp}**!\nEinsatz: **{self.eco} Coins**"
                    await interaction.message.edit(embed=self.embed, view=None)
                    self.stop()

            async def interaction_check(self, interaction):
                if not self.game_started:
                    if interaction.user != self.player1:
                        self.player2 = interaction.user
                        self.game_started = True

                        user2_id = str(self.player2.id)
                        bal2 = db.get(f"servers/{server_id}/users/{user2_id}/eco/balance") or 0
                        if bal2 < self.eco:
                            await interaction.response.send_message("❌ Du hast nicht genug Balance für den Einsatz!", ephemeral=True)
                            return False

                        self.embed.description = f"{self.player1.mention} fordert {self.player2.mention} zu einer Runde RPS heraus!\nEinsatz: **{self.eco} Coins**"
                        await interaction.response.edit_message(embed=self.embed, view=self)
                        return False
                elif interaction.user not in [self.player1, self.player2]:
                    await interaction.response.send_message("❌ Du bist nicht Teil dieses Spiels!", ephemeral=True)
                    return False
                return True

            @discord.ui.button(label="Schere ✂️", style=discord.ButtonStyle.primary)
            async def schere(self, button, interaction: discord.Interaction):
                if interaction.user == self.player1:
                    result["p1"] = "Schere"
                else:
                    result["p2"] = "Schere"
                await interaction.response.defer()
                if self.game_started:
                    await self.check_winner(interaction)

            @discord.ui.button(label="Stein 🪨", style=discord.ButtonStyle.success)
            async def stein(self, button, interaction: discord.Interaction):
                if interaction.user == self.player1:
                    result["p1"] = "Stein"
                else:
                    result["p2"] = "Stein"
                await interaction.response.defer()
                if self.game_started:
                    await self.check_winner(interaction)

            @discord.ui.button(label="Papier 📜", style=discord.ButtonStyle.danger)
            async def papier(self, button, interaction: discord.Interaction):
                if interaction.user == self.player1:
                    result["p1"] = "Papier"
                else:
                    result["p2"] = "Papier"
                await interaction.response.defer()
                if self.game_started:
                    await self.check_winner(interaction)

        view = RPSView(ctx.author, opponent, eco)
        if opponent:
            await ctx.respond(embed=view.embed, view=view)
        else:
            await ctx.respond(f"@here {ctx.author.mention} will eine Runde RPS spielen!\nEinsatz: **{eco} Coins**", embed=view.embed, view=view)

    @fun_group.command(name="useless-fact", description="Gibt einen nutzlosen Fakt aus")
    async def useless_fact(ctx):
        await ctx.defer()
        url = "https://uselessfacts.jsph.pl/random.json?language=de"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    fact = data.get("text", "Kein Fakt gefunden.")
                else:
                    fact = "Fehler beim Abrufen des Fakts."

        embed = discord.Embed(
            title="🤪 Nutzloser Fakt",
            description=fact,
            color=discord.Color.orange()
        )
        await ctx.respond(embed=embed)

    @fun_group.command(name="excuser", description="Gibt eine zufällige Ausrede aus")
    async def excuser(ctx):
        await ctx.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://excuser.herokuapp.com/v1/excuse") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    excuse = data[0].get("excuse", "Keine Ausrede gefunden.")
                else:
                    excuse = "Fehler beim Abrufen der Ausrede."

        embed = discord.Embed(
            title="🙊 Ausrede",
            description=excuse,
            color=discord.Color.teal()
        )
        await ctx.respond(embed=embed)

    @fun_group.command(name="chucknorris", description="Gibt einen Chuck Norris Witz aus")
    async def chucknorris(ctx):
        await ctx.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.chucknorris.io/jokes/random") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    joke = data.get("value", "Kein Witz gefunden.")
                else:
                    joke = "Fehler beim Abrufen des Witzes."

        embed = discord.Embed(
            title="🥋 Chuck Norris Witz",
            description=joke,
            color=discord.Color.dark_grey()
        )
        await ctx.respond(embed=embed)

    @fun_group.command(name="dog", description="Gibt ein zufälliges Hundebild aus")
    async def dog(ctx):
        await ctx.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    image_url = data.get("message", "")
                else:
                    image_url = ""

        embed = discord.Embed(
            title="🐶 Zufälliges Hundebild",
            color=discord.Color.light_grey()
        )
        if image_url:
            embed.set_image(url=image_url)
        else:
            embed.description = "Fehler beim Abrufen des Bildes."

        await ctx.respond(embed=embed)

    @fun_group.command(name="advice", description="Gibt eine zufällige Lebensweisheit aus")
    async def advice(ctx):
        await ctx.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.adviceslip.com/advice") as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    advice = data.get("slip", {}).get("advice", "Keine Lebensweisheit gefunden.")
                else:
                    advice = "Fehler beim Abrufen der Lebensweisheit."

        embed = discord.Embed(
            title="💡 Lebensweisheit",
            description=advice,
            color=discord.Color.dark_gold()
        )
        await ctx.respond(embed=embed)

    @fun_group.command(name="pokemon", description="Gibt Information über ein Pokémon aus")
    async def pokemon(ctx, name: str):
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

                    embed = discord.Embed(
                        title=f"Pokémon: {poke_name} (#{poke_id})",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Typen", value=", ".join(types) if types else "N/A", inline=False)
                    embed.add_field(name="Fähigkeiten", value=", ".join(abilities) if abilities else "N/A", inline=False)
                    if sprite:
                        embed.set_thumbnail(url=sprite)
                else:
                    embed = discord.Embed(
                        title="❌ Fehler",
                        description="Pokémon nicht gefunden. Bitte überprüfe den Namen.",
                        color=discord.Color.red()
                    )

        await ctx.respond(embed=embed)

    @fun_group.command(name="age", description="Schätzt das Alter einer Person basierend auf dem Namen")
    async def age(ctx, member: discord.Member = None):
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

        embed = discord.Embed(
            title="🎂 Namensbasierte Altersschätzung",
            description=f"Die geschätzte Alter von **{target.display_name}** ist **{age}** Jahre.",
            color=discord.Color.purple()
        )
        await ctx.respond(embed=embed)

    @fun_group.command(name="gender", description="Schätzt das Geschlecht einer Person basierend auf dem Namen")
    async def gender(ctx, target: str):
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
        
        text = f"Das Geschlecht von **{target}** ist zu **{probability:.2f}%** wahrscheinlich **{'männlich' if gender == 'male' else 'weiblich'}**."
        embed = discord.Embed(
            title="⚧ Namensbasierte Geschlechtsschätzung",
            description=text,
            color=discord.Color.purple()
        )
        await ctx.respond(embed=embed)

    # Gruppe registrieren
    bot.add_application_command(fun_group)
