import discord, asyncio
from discord.ui import Button

class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bewerbung abschließen", style=discord.ButtonStyle.red, custom_id="button:partnerbewerbung")
    async def on_close_click(self, button: Button, interaction: discord.Interaction):
        closeApplication = discord.Embed(
                    title="Partnerbewerbung abgeschlossen",
                    description="Deine Bewerbung wird geprüft. Der Kanal wird in 3 Sekunden geschlossen.",
                    color=discord.Color.red())
        await interaction.response.send_message(embed=closeApplication)
        await asyncio.sleep(3)
        await interaction.channel.delete()