import discord
from discord.ext import commands
import os
import aiohttp
import uuid
from urllib.parse import quote
import asyncio
import time
from modules import translate as tl
from huggingface_hub import AsyncInferenceClient

def register(bot: commands.Bot, db=None, on_message_listener=[]):
    os.makedirs("../generated_images", exist_ok=True)

    ai_group = discord.SlashCommandGroup(
        name="ai",
        description="AI-bezogene Befehle"
    )

    # 🔹 HUGGING FACE SETUP
    HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
    HF_MODEL = db.get('ai-model') or "meta-llama/Llama-2-13b-chat-hf"
    client = AsyncInferenceClient(model=HF_MODEL, token=HF_TOKEN)

    # 🔹 Build AI History
    async def build_ai_history(message: discord.Message):
        """
        Baut die Konversation für den AI-Chat auf.
        Nutzt alle referenzierten Nachrichten (älteste zuerst).
        Rollen: 'user' und 'assistant'.
        """
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

        if root.interaction and root.interaction.command_name == "ask":
            options = root.interaction.data.get("options", [])
            prompt = next((opt.get("value") for opt in options if opt["name"] in ["prompt", "question"]), None)
            if prompt:
                history.append({"role": "user", "content": prompt})

        for msg in chain[1:]:
            if msg.author.bot:
                history.append({"role": "assistant", "content": msg.content})
            else:
                history.append({"role": "user", "content": msg.content})

        return history
        
    def clean_output(text: str) -> str:
        """Entfernt [INST] Tags aus dem Modelloutput"""
        import re
    # alles in [INST] [/INST] Blöcken extrahieren
        cleaned = re.sub(r"\[INST\]|\[/INST\]", "", text)
    # überflüssige Leerzeilen reduzieren
        cleaned = "\n".join([line for line in cleaned.splitlines() if line.strip()])
        return cleaned
        
    async def stream_response(bot_message, history):
        """
        Antwort wird nach und nach in Discord-Message gestreamt
        (mit Buffer & Edit-Limit-Handling)
        """
        try:
            buffer = ""
            last_edit = time.time()
            edit_interval = 0.5  # Sekunden zwischen Edits
            async with bot_message.channel.typing():
                stream = await client.chat_completion(messages=history,max_tokens=400,temperature=0.7,top_p=0.9,stream=True)
                async for event in stream:
                    delta = event.choices[0].delta.get("content", "")
                    if not delta:
                        continue

                    delta = clean_output(delta)
                    buffer += delta

                        # regelmäßig aktualisieren (um Rate-Limits zu vermeiden)
                    if time.time() - last_edit > edit_interval:
                        try:
                            await bot_message.edit(content=buffer[-1900:])  # Discord limit safety
                            last_edit = time.time()
                        except Exception:
                            pass  # falls z. B. edit zu schnell hintereinander passiert

                    # am Ende sicherstellen, dass alles da ist
                if buffer:
                    await bot_message.edit(content=buffer[-1900:])
                    
        except Exception as e:
            await bot_message.edit(content=f"Fehler beim Generkeren deiner Antwort:\n||{e}||")
        
    # 🔹 /ai ask Command
    @ai_group.command(name="ask", description="Stelle eine Frage an die AI")
    async def ai_ask(ctx, question: str):
        await ctx.defer()

        embed = discord.Embed(
            title="💬 Frage wird verarbeitet...",
            description=f"Frage: {question[:800]}",
            color=discord.Color.blue()
        )
        bot_message_obj = await tl.respond_with_view(ctx, embed, preferred_lang="de", mode="normal")

        ai_history = [
            {"role": "user", "content": "[SYSTEM] Du bist ein hilfreicher Assistent namens CometAI (Beta)."},
            {"role": "user", "content": question}
        ]

        loop = asyncio.get_event_loop()
        # streaming direkt in der Message
        await stream_response(bot_message_obj, ai_history)

    # 🔹 Message Listener für Antworten auf Referenzen
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
        await stream_response(bot_msg, history)

    # 🔹 Bildgenerierung bleibt unverändert
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
