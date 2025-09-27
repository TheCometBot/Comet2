from deep_translator import GoogleTranslator
import asyncio
import re
import uuid
import discord
from discord.ui import View

async def translate_text(text: str, dest_lang: str):
    loop = asyncio.get_event_loop()

    # Platzhalter wie :emoji: oder :text: merken
    placeholders = list(set(re.findall(r':[a-zA-Z0-9_]+:', text)))
    placeholder_map = {ph: str(uuid.uuid4()) for ph in placeholders}

    temp_text = text
    for ph, key in placeholder_map.items():
        temp_text = temp_text.replace(ph, key)

    try:
        translated = await loop.run_in_executor(
            None, lambda: GoogleTranslator(source="auto", target=dest_lang).translate(temp_text)
        )
        for ph, key in placeholder_map.items():
            translated = translated.replace(key, ph)
        return translated
    except Exception:
        return text

async def respond_with_view(
    ctx,
    embed: discord.Embed,
    preferred_lang: str,  # bleibt, wird aber ignoriert
    mode: str = "normal",
    message_to_edit: discord.Message = None,
    file: discord.File = None,
    ephemeral: bool = False
):
    """
    mode: "normal" | "followup" | "edit"
    message_to_edit: nur bei mode="edit"
    file: optional Datei für das Embed
    ephemeral: wenn True → nur der Command-User sieht die Nachricht
    """

    if mode == "edit" and message_to_edit:
        return await message_to_edit.edit(embed=embed, attachments=[file] if file else None)

    elif mode == "followup":
        return await ctx.followup.send(embed=embed, file=file, ephemeral=ephemeral)

    else:  # normal
        return await ctx.respond(embed=embed, file=file, ephemeral=ephemeral)