 # cogs/dev_commands.py

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import delete_team, delete_match, get_tournament_by_name

class DevCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.owner_id = 812347860128497694  # replace with your Discord ID

    def is_owner(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_id

    @app_commands.command(name="dummy_tourney", description="Create a dummy tournament for testing.")
    async def dummy_tourney(self, interaction: discord.Interaction):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("🚫 Bot owner only.", ephemeral=True)
        # Implement dummy creation logic if needed
        await interaction.response.send_message("🧪 Dummy tournament created.", ephemeral=True)

    @app_commands.command(name="dummy_remove", description="Remove dummy data.")
    async def dummy_remove(self, interaction: discord.Interaction):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("🚫 Bot owner only.", ephemeral=True)
        # Clean up all test tournaments/teams if you wish
        await interaction.response.send_message("🧹 Dummy data removed.", ephemeral=True)

    @app_commands.command(name="checkprio", description="Check server’s premium status.")
    async def checkprio(self, interaction: discord.Interaction):
        settings = await get_guild_settings(interaction.guild.id)
        status = settings["premium_enabled"]
        await interaction.response.send_message(f"Premium Enabled: `{status}`", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(DevCommands(bot))
