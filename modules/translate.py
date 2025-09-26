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
):
    """
    mode: "normal" | "followup" | "edit"
    message_to_edit: nur bei mode="edit"
    file: optional Datei für das Embed
    ephemeral: wenn True → nur der Command-User sieht die Nachricht
    """

    embed_title = await translate_text(embed.title, preferred_lang)
    embed_description = await translate_text(embed.description, preferred_lang)
    new_embed = discord.Embed(title=embed_title, description=embed_description, color=embed.color)

    class LangView(View):
        def __init__(self):
            super().__init__()

        @discord.ui.button(label="DE", style=discord.ButtonStyle.secondary, disabled=(preferred_lang=="de"))
        async def de_button(self, button, interaction):
            de_title = await translate_text(embed.title, "de")
            de_desc = await translate_text(embed.description, "de")
            de_embed = discord.Embed(title=de_title, description=de_desc, color=embed.color)
            await self._edit_or_respond(interaction, de_embed)

        @discord.ui.button(label="EN", style=discord.ButtonStyle.secondary, disabled=(preferred_lang=="en"))
        async def en_button(self, button, interaction):
            en_title = await translate_text(embed.title, "en")
            en_desc = await translate_text(embed.description, "en")
            en_embed = discord.Embed(title=en_title, description=en_desc, color=embed.color)
            await self._edit_or_respond(interaction, en_embed)

        async def _edit_or_respond(self, interaction, embed_to_send):
            if mode == "edit" and message_to_edit:
                return await message_to_edit.edit(embed=embed_to_send, view=self, attachments=[file] if file else None)
            elif mode == "followup":
                return await interaction.followup.send(embed=embed_to_send, view=self, file=file, ephemeral=ephemeral)
            else:  # normal
                return await interaction.response.edit_message(embed=embed_to_send, view=self, attachments=[file] if file else None)

    view = LangView()

    if mode == "edit" and message_to_edit:
        return await message_to_edit.edit(embed=new_embed, view=view, attachments=[file] if file else None)
    elif mode == "followup":
        return await ctx.followup.send(embed=new_embed, view=view, file=file, ephemeral=ephemeral)
    else:  # normal
        return await ctx.respond(embed=new_embed, view=view, file=file, ephemeral=ephemeral)
