 # cogs/modes.py

import discord
from discord import app_commands
from discord.ext import commands

MODE_DATA = {
    "Standard": {
        "description": "Standard 5v5 mode; first to 13 rounds wins.",
        "image_url": "https://static.wikia.nocookie.net/valorant/images/7/7f/Match_Search_UI_StandardMode.png"
    },
    "Spike Rush": {
        "description": "Fast 4v4 mode; first to 4 points wins with random loadouts.",
        "image_url": "https://static.wikia.nocookie.net/valorant/images/d/d8/Spike_Rush_UI.png"
    },
    "Deathmatch": {
        "description": "Free-for-all; first to 40 kills wins. Good for warm-ups.",
        "image_url": "https://static.wikia.nocookie.net/valorant/images/6/6a/Deathmatch_UI.png"
    },
    "Custom": {
        "description": "Custom lobby settings; used for special tournament rules.",
        "image_url": "https://static.wikia.nocookie.net/valorant/images/3/31/Custom_Lobby_UI.png"
    }
}

class Modes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="list_modes", description="List Valorant game modes.")
    async def list_modes(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎮 Valorant Game Modes",
            color=discord.Color.green()
        )
        for name, data in MODE_DATA.items():
            embed.add_field(name=name, value=data["description"], inline=False)
        embed.set_footer(text="Use /show_mode <mode_name> to see an image.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="show_mode", description="Show details and image for a specific mode.")
    @app_commands.describe(mode_name="Name of the mode (e.g., Standard, Spike Rush)")
    async def show_mode(self, interaction: discord.Interaction, mode_name: str):
        key = mode_name.title()
        data = MODE_DATA.get(key)
        if not data:
            return await interaction.response.send_message(f"❌ Mode `{mode_name}` not found.", ephemeral=True)
        embed = discord.Embed(
            title=f"🎮 {key}",
            description=data["description"],
            color=discord.Color.green()
        )
        embed.set_image(url=data["image_url"])
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Modes(bot))
