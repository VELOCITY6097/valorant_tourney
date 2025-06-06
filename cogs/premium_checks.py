 # cogs/premium_checks.py

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import get_guild_settings, add_premium_command, remove_premium_command

class PremiumChecks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_guild_premium(self, guild_id: int) -> bool:
        settings = await get_guild_settings(guild_id)
        return settings.get("premium_enabled", False)

    async def get_premium_commands(self, guild_id: int) -> list:
        settings = await get_guild_settings(guild_id)
        return settings.get("premium_commands", [])

    async def add_premium_command_db(self, guild_id: int, command_name: str):
        await add_premium_command(guild_id, command_name)

    async def remove_premium_command_db(self, guild_id: int, command_name: str):
        await remove_premium_command(guild_id, command_name)

    def premium_check(self, command_name: str):
        async def predicate(interaction: discord.Interaction):
            guild_id = interaction.guild.id
            premium_cmds = await self.get_premium_commands(guild_id)
            if command_name in premium_cmds:
                if await self.is_guild_premium(guild_id):
                    return True
                await interaction.response.send_message(
                    f"🚫 `{command_name}` is a premium command. Activate premium to use it.", ephemeral=True
                )
                return False
            return True
        return app_commands.check(predicate)

    @app_commands.command(name="add_premium_command", description="Add a command to the premium list.")
    @app_commands.describe(command_name="Name of the command to mark as premium")
    async def add_premium_command(self, interaction: discord.Interaction, command_name: str):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 Administrator only.", ephemeral=True)
        await self.add_premium_command_db(interaction.guild.id, command_name)
        await interaction.response.send_message(f"✅ `{command_name}` added to premium commands.", ephemeral=True)

    @app_commands.command(name="remove_premium_command", description="Remove a command from the premium list.")
    @app_commands.describe(command_name="Name of the command to remove")
    async def remove_premium_command(self, interaction: discord.Interaction, command_name: str):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 Administrator only.", ephemeral=True)
        await self.remove_premium_command_db(interaction.guild.id, command_name)
        await interaction.response.send_message(f"✅ `{command_name}` removed from premium commands.", ephemeral=True)

    @app_commands.command(name="list_premium_commands", description="List all premium commands for this server.")
    async def list_premium_commands(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 Administrator only.", ephemeral=True)
        premium_cmds = await self.get_premium_commands(interaction.guild.id)
        if not premium_cmds:
            return await interaction.response.send_message("ℹ No commands are set as premium.", ephemeral=True)
        embed = discord.Embed(
            title="📄 Premium Commands",
            description="\n".join(f"• `{cmd}`" for cmd in premium_cmds),
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="toggle_premium", description="Toggle a command’s premium status.")
    @app_commands.describe(command_name="Name of the command to toggle")
    async def toggle_premium(self, interaction: discord.Interaction, command_name: str):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 Administrator only.", ephemeral=True)
        premium_cmds = await self.get_premium_commands(interaction.guild.id)
        if command_name in premium_cmds:
            await self.remove_premium_command_db(interaction.guild.id, command_name)
            await interaction.response.send_message(f"❎ `{command_name}` removed from premium.", ephemeral=True)
        else:
            await self.add_premium_command_db(interaction.guild.id, command_name)
            await interaction.response.send_message(f"✅ `{command_name}` added to premium.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(PremiumChecks(bot))
