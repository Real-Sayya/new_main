import discord
import datetime


async def admin(ctx):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            title="Fehlende Berechtigungen!",
            description="Du benötigst die Berechtigung `ADMINISTRATOR`, um diesen Befehl auszuführen.",
            color=0xF43E3E,
            timestamp=datetime.datetime.utcnow()
        )
        await ctx.respond(embed=embed, ephemeral=True)
        return True

