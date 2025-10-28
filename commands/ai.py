import discord
from discord.ext import commands
import os
import aiohttp
import uuid
from urllib.parse import quote
import asyncio
import time
from modules import translate as tl
from huggingface_hub import InferenceClient


def register(bot: commands.Bot, db=None, on_message_listener=[]):
    os.makedirs("../generated_images", exist_ok=True)

    ai_group = discord.SlashCommandGroup(
        name="ai",
        description="AI-bezogene Befehle"
    )

    # 🔹 HUGGING FACE SETUP
    HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
    HF_MODEL = "stabilityai/stablelm-tuned-alpha-7b"

    client = InferenceClient(model=HF_MODEL, token=HF_TOKEN)

    def ask(history: list = None):
        """
        Nutzt Hugging Face Inference API für Chat-Antworten.
        """
        if not history:
            history = []

        conversation = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])

        response = client.chat_completion(
            messages=history,
            max_tokens=400,
            temperature=0.7,
            top_p=0.9,
        )

        return response.choices[0].message['content'].strip()

    @ai_group.command(name="ask", description="Stelle eine Frage an die AI")
    async def ai_ask(ctx, question: str):
        await ctx.defer()

        bot_message_obj = await tl.respond_with_view(
            ctx,
            discord.Embed(
                title="💬 Frage wird verarbeitet...",
                description=f"Frage: {question[:800]}",
                color=discord.Color.blue()
            ),
            preferred_lang="de",
            mode="normal"
        )

        ai_history = [
            {"role": "user", "content": "[SYSTEM] Du bist ein hilfreicher Assistent namens CometAI (Beta)."},
            {"role": "user", "content": question}
        ]

        loop = asyncio.get_event_loop()
        try:
            answer = await loop.run_in_executor(None, ask, ai_history)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Fehler",
                description=f"Es gab einen Fehler bei der Verarbeitung deiner Anfrage: {str(e)}",
                color=discord.Color.red()
            )
            await tl.respond_with_view(
                ctx,
                embed,
                preferred_lang="de",
                mode="edit",
                message_to_edit=bot_message_obj
            )
            return
            

        def chunk_text(text, size=2000):
            return [text[i:i+size] for i in range(0, len(text), size)]

        chunks = chunk_text(answer, 2000)

        await bot_message_obj.edit(content=chunks[0], view=None, embed=None)

        for chunk in chunks[1:]:
            msg = await bot_message_obj.interaction.original_message()
            bot_message_obj = await msg.reply(chunk)

    async def build_ai_history(message: discord.Message):
        history = []
        chain = []
        current = message

        while current:
            chain.append(current)
            if current.reference and isinstance(current.reference.resolved, discord.Message):
                current = current.reference.resolved
            else:
                break

        chain = list(reversed(chain))
        root = chain[0]
        if not root.interaction:
            return []

        if root.interaction.command_name != "ask":
            return []

        options = root.interaction.data.get("options", [])
        prompt = None
        for opt in options:
            if opt["name"] in ["prompt", "question"]:
                prompt = opt.get("value")
                break

        if not prompt:
            return []

        history.append({"role": "user", "content": prompt})

        for msg in chain[1:]:
            if msg.author.bot:
                history.append({"role": "assistant", "content": msg.content})
            else:
                history.append({"role": "user", "content": msg.content})

        return history

    async def message_listener(message: discord.Message):
        if message.author.bot:
            return

        history = await build_ai_history(message)
        if not history:
            return
            
        embed = discord.Embed(
            title="💬 Frage wird verarbeitet...",
            description=f"Frage: {message.content[:800]}",
            color=discord.Color.blue()
        )
        
        bot_msg = await message.reply(embed=embed)

        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, ask, history)

        def chunk_text(text, size=2000):
            return [text[i:i+size] for i in range(0, len(text), size)]

        chunks = chunk_text(answer, 2000)
        await bot_msg.edit(content=chunks[0], embed=None)
        for chunk in chunks[1:]:
            bot_msg = await bot_msg.reply(chunk)

    async def generate_image(prompt: str):
        url = "https://image.pollinations.ai/prompt/" + quote(prompt)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    name = f"image_{uuid.uuid4()}.png"
                    path = os.path.join("..", "generated_images", name)
                    with open(path, 'wb') as f:
                        f.write(await resp.read())
                    return path
                else:
                    return None

    @ai_group.command(name="draw", description="Erstelle ein Bild mit der AI")
    async def ai_draw(ctx, prompt: str):
        await ctx.defer()
        embed = discord.Embed(
            title="🖼️ Bild wird generiert...",
            description=f"Prompt: {prompt[:800]}",
            color=discord.Color.blue()
        )
        bot_message_obj = await tl.respond_with_view(ctx, embed, preferred_lang="de", mode="normal")

        start_time = time.time()
        image_path = await generate_image(prompt)

        if image_path:
            end_time = time.time()
            file = discord.File(image_path, filename="generated_image.png")
            embed = discord.Embed(
                title="🖼️ Generiertes Bild",
                description=f"Prompt: {prompt[:800]}",
                color=discord.Color.blue()
            )
            embed.set_image(url="attachment://generated_image.png")
            embed.set_footer(
                text=f"Bild generiert von Pollinations AI in ~{end_time - start_time:.2f} Sekunden"
            )
            await tl.respond_with_view(ctx, embed, preferred_lang="de", mode="edit", message_to_edit=bot_message_obj, file=file)
            os.remove(image_path)
        else:
            embed = discord.Embed(
                title="❌ Fehler",
                description="Das Bild konnte nicht generiert werden.",
                color=discord.Color.red()
            )
            await tl.respond_with_view(ctx, embed, preferred_lang="de", mode="edit", message_to_edit=bot_message_obj)

    on_message_listener.append(message_listener)
    bot.add_application_command(ai_group)