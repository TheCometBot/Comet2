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
    preferred_lang: str,
    mode: str = "normal",
    message_to_edit: discord.Message = None,
    file: discord.File = None,
    ephemeral: bool = False
) -> discord.Message:
    if mode == "edit" and message_to_edit:
        if file:
            return await message_to_edit.edit(embed=embed, file=file)
        return await message_to_edit.edit(embed=embed)

    elif mode == "followup":
        if file:
            return await ctx.followup.send(embed=embed, file=file, ephemeral=ephemeral)
        return await ctx.followup.send(embed=embed, ephemeral=ephemeral)

    else:  # normal
        if hasattr(ctx, "interaction"):  # Slash command
            if file:
                await ctx.respond(embed=embed, file=file, ephemeral=ephemeral)
            else:
                await ctx.respond(embed=embed, ephemeral=ephemeral)
            return await ctx.interaction.original_response()
        else:  # Prefix command
            if file:
                return await ctx.send(embed=embed, file=file)
            return await ctx.send(embed=embed)