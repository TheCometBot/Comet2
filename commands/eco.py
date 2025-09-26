import discord
from discord.ext import commands
import random

def register(bot: commands.Bot, db=None, ):

    eco_group = discord.SlashCommandGroup(
        name="eco",
        description="Coins- und Economy-Befehle"
    )

    @eco_group.command(name="daily", description="Sammelt deinen täglichen Bonus")
    async def daily(ctx):
        await ctx.defer()
        user_id = str(ctx.author.id)
        server_id = str(ctx.guild.id)
        last_daily = db.get(f"servers/{server_id}/users/{user_id}/eco/last_daily")
        current_time = discord.utils.utcnow().timestamp()

        if last_daily and current_time - last_daily < 86400:
            embed = discord.Embed(title="❌ Bereits gesammelt", description=":coin: Du hast deinen täglichen Bonus bereits erhalten. Komm später wieder!", color=discord.Color.red())
            await ctx.respond(embed=embed)
            return

        old_streak = db.get(f"servers/{server_id}/users/{user_id}/eco/daily_streak") or 0
        daily_streak = 1 if not last_daily or current_time - last_daily > 172800 else old_streak + 1

        daily_bonus = int(random.randint(50, 150) * min(3, 1 + daily_streak * 0.1))
        balance = db.get(f"servers/{server_id}/users/{user_id}/eco/balance") or 0
        balance += daily_bonus

        db.update(f"servers/{server_id}/users/{user_id}/eco", {"balance": balance, "last_daily": current_time, "daily_streak": daily_streak})

        embed = discord.Embed(
            title="✅ Täglicher Bonus",
            description=f":coin: Du hast **{daily_bonus} Coins** erhalten!\n🔥 Streak: **{daily_streak} Tage**\n💰 Kontostand: **{balance} Coins**",
            color=discord.Color.green()
        )
        await ctx.respond(embed=embed)

    @eco_group.command(name="balance", description="Zeigt den Kontostand an")
    async def balance(ctx, member: discord.Member = None):
        await ctx.defer()
        member = member or ctx.author
        user_id = str(member.id)
        server_id = str(ctx.guild.id)
        bal = db.get(f"servers/{server_id}/users/{user_id}/eco/balance") or 0

        embed = discord.Embed(
            title=":coin: Kontostand",
            description=f"{member.mention} hat **{bal} Coins**.",
            color=discord.Color.blue()
        )
        await ctx.respond(embed=embed)

    @eco_group.command(name="pay", description="Zahlt einem anderen Nutzer Coins")
    async def pay(ctx, member: discord.Member, amount: int):
        await ctx.defer()
        if member.bot or member.id == ctx.author.id or amount <= 0:
            embed = discord.Embed(title="❌ Fehler", description="Ungültige Aktion.", color=discord.Color.red())
            await ctx.respond(embed=embed)
            return

        sender_id = str(ctx.author.id)
        receiver_id = str(member.id)
        server_id = str(ctx.guild.id)

        sender_balance = db.get(f"servers/{server_id}/users/{sender_id}/eco/balance") or 0
        if sender_balance < amount:
            embed = discord.Embed(title="❌ Fehler", description="Du hast nicht genug Coins.", color=discord.Color.red())
            await ctx.respond(embed=embed)
            return

        receiver_balance = db.get(f"servers/{server_id}/users/{receiver_id}/eco/balance") or 0
        db.update(f"servers/{server_id}/users/{sender_id}/eco", {"balance": sender_balance - amount})
        db.update(f"servers/{server_id}/users/{receiver_id}/eco", {"balance": receiver_balance + amount})

        embed = discord.Embed(
            title="✅ Coins gesendet",
            description=f":coin: {ctx.author.mention} hat **{amount} Coins** an {member.mention} geschickt!\n💰 Neuer Kontostand: **{sender_balance - amount} Coins**",
            color=discord.Color.green()
        )
        await ctx.respond(embed=embed)

    @eco_group.command(name="steal", description="Versucht, Coins von einem anderen Nutzer zu stehlen")
    async def steal(ctx, member: discord.Member):
        await ctx.defer()
        if member.bot or member.id == ctx.author.id:
            embed = discord.Embed(title="❌ Fehler", description="Ungültige Aktion.", color=discord.Color.red())
            await ctx.respond(embed=embed)
            return

        thief_id = str(ctx.author.id)
        victim_id = str(member.id)
        server_id = str(ctx.guild.id)

        thief_balance = db.get(f"servers/{server_id}/users/{thief_id}/eco/balance") or 0
        victim_balance = db.get(f"servers/{server_id}/users/{victim_id}/eco/balance") or 0

        if victim_balance < 50:
            embed = discord.Embed(title="❌ Fehler", description=":coin: Das Opfer hat zu wenig Coins (mindestens 50 benötigt).", color=discord.Color.red())
            await ctx.respond(embed=embed)
            return

        if random.random() < 0.4:
            steal_amount = random.randint(10, min(100, max(10, victim_balance // 10)))
            steal_amount = min(steal_amount, victim_balance)
            db.update(f"servers/{server_id}/users/{thief_id}/eco", {"balance": thief_balance + steal_amount})
            db.update(f"servers/{server_id}/users/{victim_id}/eco", {"balance": victim_balance - steal_amount})
            embed = discord.Embed(
                title="✅ Diebstahl erfolgreich",
                description=f":coin: {ctx.author.mention} hat **{steal_amount} Coins** von {member.mention} gestohlen!",
                color=discord.Color.green()
            )
        else:
            penalty = min(thief_balance, random.randint(5, 20))
            db.update(f"servers/{server_id}/users/{thief_id}/eco", {"balance": thief_balance - penalty})
            embed = discord.Embed(
                title="❌ Beim Stehlen erwischt",
                description=f":coin: {ctx.author.mention} wurde erwischt und musste **{penalty} Coins** Strafe zahlen!",
                color=discord.Color.red()
            )
        await ctx.respond(embed=embed)

    @eco_group.command(name="leaderboard", description="Zeigt die Top 10 Nutzer mit dem höchsten Kontostand an")
    async def leaderboard(ctx):
        await ctx.defer()
        server_id = str(ctx.guild.id)
        users = db.get(f"servers/{server_id}/users") or {}

        leaderboard = [(uid, data.get("eco", {}).get("balance", 0) if isinstance(data, dict) else 0) for uid, data in users.items()]
        leaderboard.sort(key=lambda x: x[1], reverse=True)
        top_10 = leaderboard[:10]

        embed = discord.Embed(title="🏆 Top 10 Kontostände", color=discord.Color.gold())
        for rank, (uid, balance) in enumerate(top_10, start=1):
            user = ctx.guild.get_member(int(uid))
            if user:
                embed.add_field(name=f"{rank}. {user.display_name}", value=f":coin: {balance} Coins", inline=False)

        await ctx.respond(embed=embed)

    @eco_group.command(name="change-to-points", description="Konvertiert deine Coins in Punkte (2 Coins = 1 Punkt)")
    async def change_to_points(ctx, amount: int):
        await ctx.defer()
        user_id = str(ctx.author.id)
        server_id = str(ctx.guild.id)

        if amount <= 0:
            embed = discord.Embed(title="❌ Fehler", description="Der Betrag muss positiv sein.", color=discord.Color.red())
            await ctx.respond(embed=embed)
            return

        coin_balance = db.get(f"servers/{server_id}/users/{user_id}/eco/balance") or 0
        if coin_balance < amount:
            embed = discord.Embed(title="❌ Fehler", description=":coin: Du hast nicht genug Coins.", color=discord.Color.red())
            await ctx.respond(embed=embed)
            return

        points_balance = db.get(f"servers/{server_id}/users/{user_id}/points/points") or 0
        db.update(f"servers/{server_id}/users/{user_id}/eco", {"balance": coin_balance - amount})
        db.update(f"servers/{server_id}/users/{user_id}/points", {"points": points_balance + amount // 2})

        embed = discord.Embed(
            title="✅ Coins umgewandelt",
            description=f":coin: Du hast **{amount} Coins** in **{amount // 2} Punkte** umgewandelt!\n💰 Neuer Kontostand: {coin_balance - amount} Coins\n⭐ Neuer Punktestand: {points_balance + amount // 2} Punkte",
            color=discord.Color.green()
        )
        await ctx.respond(embed=embed)

    bot.add_application_command(eco_group)
