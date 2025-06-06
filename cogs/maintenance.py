 # cogs/maintenance.py

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import create_or_update_guild_settings, get_guild_settings

class Maintenance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="maintenance", description="Toggle maintenance mode on/off.")
    @app_commands.describe(mode="on or off", message="Optional maintenance message")
    async def maintenance(self, interaction: discord.Interaction, mode: str, message: str = ""):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 Admin only.", ephemeral=True)
        mode = mode.lower()
        if mode not in ("on", "off"):
            return await interaction.response.send_message("Use `on` or `off`.", ephemeral=True)

        settings = await get_guild_settings(interaction.guild.id)
        if mode == "on":
            await create_or_update_guild_settings(
                guild_id=interaction.guild.id,
                maintenance_mode=True,
                maintenance_msg=message
            )
            # Create or edit a top‐level "🚧-maintenance" channel
            existing = discord.utils.get(interaction.guild.text_channels, name="🚧-maintenance")
            if existing:
                await existing.edit(topic=message)
            else:
                await interaction.guild.create_text_channel(
                    "🚧-maintenance", topic=message
                )
            await interaction.response.send_message("🔧 Maintenance mode enabled.", ephemeral=True)
        else:
            await create_or_update_guild_settings(
                guild_id=interaction.guild.id,
                maintenance_mode=False,
                maintenance_msg=""
            )
            existing = discord.utils.get(interaction.guild.text_channels, name="🚧-maintenance")
            if existing:
                await existing.delete()
            await interaction.response.send_message("✅ Maintenance mode disabled.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Maintenance(bot))
