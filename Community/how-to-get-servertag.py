import discord
from discord.ext import commands
import json
import os

file = discord.File("img/Logo.png", filename="Logo.png")
color = 0x2596be

class TranslateView(discord.ui.View):
    def __init__(self, embed_de, embed_en):
        super().__init__(timeout=None)
        self.embed_de = embed_de
        self.embed_en = embed_en
        self.showing_original = True

    @discord.ui.button(label="Translate", style=discord.ButtonStyle.primary, custom_id="translate_button")
    async def translate(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.showing_original = not self.showing_original
        embed = self.embed_de if self.showing_original else self.embed_en
        await interaction.response.edit_message(embed=embed, view=self)

class StartupEmbed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = 1378117380584247438  # <-- Ersetzen!

    async def send_or_update_embed(self):
        path = "Data/message.json"
        os.makedirs("Data", exist_ok=True)

        data = {"text_de": "Dies ist die deutsche Version.", "text_en": "This is the English version."}

        # Bestehende Daten einlesen oder neu anlegen
        if os.path.exists(path):
            with open(path, "r") as f:
                try:
                    data.update(json.load(f))
                except json.JSONDecodeError:
                    pass

        embed_de = discord.Embed(title="# <:servertag:1378701880183754872> Wie bekomme ich?", description=data.get("text_de", ""), color=color)
        embed_de.set_footer(text="Powered by gsv2.dev ⚡", icon_url="attachment://Logo.png")

        embed_en = discord.Embed(title="# <:servertag:1378701880183754872> How do I get?", description=data.get("text_en", ""), color=color)
        embed_en.set_footer(text="Powered by gsv2.dev ⚡", icon_url="attachment://Logo.png")

        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return

        view = TranslateView(embed_de, embed_en)

        msg_id = data.get("message_id")
        message = None

        if msg_id:
            try:
                message = await channel.fetch_message(msg_id)
                await message.edit(embed=embed_de, view=view)
                return
            except (discord.NotFound, discord.HTTPException):
                pass  # Fallback auf neu posten

        # Neue Nachricht posten
        message = await channel.send(embed=embed_de, file=file, view=view)
        data["message_id"] = message.id

        with open(path, "w") as f:
            json.dump(data, f, indent=4)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.send_or_update_embed()

def setup(bot):
    bot.add_cog(StartupEmbed(bot))
