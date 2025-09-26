import discord
from discord.ext import commands
import openai
import os
import aiohttp
import uuid
from urllib.parse import quote
import asyncio
import time

def register(bot: commands.Bot, db=None, on_message_listener=[], ):
    os.makedirs("../generated_images", exist_ok=True)
    ai_group = discord.SlashCommandGroup(
        name="ai",
        description="AI-bezogene Befehle"
    )
    client = openai.OpenAI(
        base_url="https://api.aimlapi.com/v1",
        api_key=os.getenv('AI_API_KEY')
    )
    
    def ask(question: str, history: list = None):
        response = client.chat.completions.create(
            model="google/gemma-3n-e4b-it",
            messages=[
                {"role": "user", "content": "[SYSTEM] Du bist ein hilfreicher Assistent nahmens CometAI(in Beta)."},
                *(history or []),
                {"role": "user", "content": question}
            ]
        )
        return response.choices[0].message.content
    
    @ai_group.command(name="ask", description="Stelle eine Frage an die AI")
    async def ai_ask(ctx, question: str):
        await ctx.defer()

        bot_message_obj = await ctx.respond("Die AI denkt nach... ⏳")

        bot_message_obj.history_start = True
        bot_message_obj.ai_history = [{"role": "user", "content": "[SYSTEM] Start der Konversation."}]

        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, ask, question, bot_message_obj.ai_history)
        bot_message_obj.ai_history.append({"role": "user", "content": question})
        bot_message_obj.ai_history.append({"role": "assistant", "content": answer})
        def chunk_text(text, size=2000):
            return [text[i:i+size] for i in range(0, len(text), size)]
        chunks = chunk_text(answer, 2000)
        await bot_message_obj.edit(content=chunks[0])
        for chunk in chunks[1:]:
            await ctx.send(chunk)

    async def message_listener(message):
        if message.author.bot:
            return
        
        if message.reference and isinstance(message.reference.resolved, discord.Message):
            ref = message.reference.resolved

            history = []
            current = ref
            while current:
                if getattr(current, 'history_start', False):
                    history = getattr(current, 'ai_history', [])
                    break
                current = getattr(current, 'reference', None)
                if isinstance(current, discord.Message):
                    current = current
                else:
                    current = None

                if history:
                    reply_message = await message.reply("Die AI denkt nach... ⏳", mention_author=False)
                    user_content = message.content
                    history.append({"role": "user", "content": user_content})
                    loop = asyncio.get_event_loop()
                    reply = await loop.run_in_executor(None, ask, user_content, history)
                    history.append({"role": "assistant", "content": reply})
                    def chunk_text(text, size=2000):
                        return [text[i:i+size] for i in range(0, len(text), size)]
                    chunks = chunk_text(reply, 2000)
                    await reply_message.edit(content=chunks[0])
                    for chunk in chunks[1:]:
                        await message.channel.send(chunk)

    async def generate_image(prompt: str):
        url = "https://image.pollinations.ai/prompt/" + quote(prompt)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    name = f"image_{uuid.uuid4()}.png"
                    with open("../generated_images/" + name, 'wb') as f:
                        f.write(await resp.read())
                    return "../generated_images/" + name
                else:
                    return None
                
    @ai_group.command(name="draw", description="Erstelle ein Bild mit der AI")
    async def ai_draw(ctx, prompt: str):
        await ctx.defer()
        bot_message_obj = await ctx.respond("Die AI erstellt dein Bild... ⏳")
        start_time = time.time()
        image_path = await generate_image(prompt)
        if image_path:
            end_time = time.time()
            print(f"Image generated in {end_time - start_time} seconds.")
            file = discord.File(image_path, filename="generated_image.png")
            embed = discord.Embed(
                title="🖼️ Generiertes Bild",
                description=f"Prompt: {prompt[:800]}",
                color=discord.Color.blue()
            )
            embed.set_image(url="attachment://generated_image.png")
            embed.set_footer(text="Bild generiert von Pollinations AI in ~{:.2f} Sekunden".format(end_time - start_time))
            await bot_message_obj.edit(content=None, embed=embed, file=file)
        else:
            await bot_message_obj.edit(content="Fehler beim Erstellen des Bildes. Bitte versuche es später erneut.")

    on_message_listener.append(message_listener)
    bot.add_application_command(ai_group)