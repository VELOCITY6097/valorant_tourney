 # cogs/maps.py

import discord
from discord import app_commands
from discord.ext import commands

MAP_DATA = {
    "Ascent": {
        "description": "Central to everyone's strategies, Ascent is a map featuring mid control and open areas.",
        "image_url": "https://assets.valorant-api.com/maps/5ada98c5-4db9-68f3-0d38-29f8a643ea10/asset/largeicon.png"
    },
    "Bind": {
        "description": "Bind is known for its teleporters and dual spike sites.",
        "image_url": "https://assets.valorant-api.com/maps/d9605490-485e-a0af-3e03-e8b1ac95bd07/asset/largeicon.png"
    },
    "Haven": {
        "description": "Haven features three spike sites, making rotations vital.",
        "image_url": "https://assets.valorant-api.com/maps/bb6bf4b4-4cff-429a-0663-7c37f904eda7/asset/largeicon.png"
    },
    "Icebox": {
        "description": "Icebox is an ever-popular map with verticality and tight chokepoints.",
        "image_url": "https://assets.valorant-api.com/maps/4f764a78-5179-64f3-220f-b0d92fdcca19/asset/largeicon.png"
    },
    "Split": {
        "description": "Split demands strong site execution and wall-bang versatility.",
        "image_url": "https://assets.valorant-api.com/maps/7eaecc8f-459b-c1d8-0a0e-168923c8af15/asset/largeicon.png"
    }
    # Add Breeze, Fracture, Lotus, etc. similarly
}

class Maps(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="list_maps", description="List all Valorant maps.")
    async def list_maps(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🗺️ Available Valorant Maps",
            color=discord.Color.blue()
        )
        for name, data in MAP_DATA.items():
            embed.add_field(name=name, value=data["description"], inline=False)
        embed.set_footer(text="Use /show_map <map_name> to see a larger image.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="show_map", description="Show details and image of a specific map.")
    @app_commands.describe(map_name="Name of the map (e.g., Ascent, Bind)")
    async def show_map(self, interaction: discord.Interaction, map_name: str):
        key = map_name.title()
        data = MAP_DATA.get(key)
        if not data:
            return await interaction.response.send_message(f"❌ Map `{map_name}` not found.", ephemeral=True)
        embed = discord.Embed(
            title=f"🗺️ {key}",
            description=data["description"],
            color=discord.Color.blue()
        )
        embed.set_image(url=data["image_url"])
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Maps(bot))
