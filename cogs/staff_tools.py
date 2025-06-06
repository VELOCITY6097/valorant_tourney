 # cogs/staff_tools.py

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import (
    get_guild_settings,
    get_tournament_by_name,
    get_team,
    delete_team,
    delete_match,
    update_match_result
)
from utils.bracket_api import update_bracket_match

class StaffTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_staff(self, interaction: discord.Interaction) -> bool:
        settings = self.bot.loop.run_until_complete(get_guild_settings(interaction.guild.id))
        overwatch_id = settings["overwatch_role_id"]
        staff_id = settings["staff_role_id"]
        roles = [r.id for r in interaction.user.roles]
        return interaction.user.guild_permissions.administrator or overwatch_id in roles or staff_id in roles

    @app_commands.command(name="disqualify_team", description="Disqualify a team from a tournament.")
    @app_commands.describe(tourney_name="Tournament name", team_name="Exact team name")
    async def disqualify_team(self, interaction: discord.Interaction, tourney_name: str, team_name: str):
        if not self.is_staff(interaction):
            return await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
        tourney = await get_tournament_by_name(interaction.guild.id, tourney_name)
        if not tourney:
            return await interaction.response.send_message("❌ Tournament not found.", ephemeral=True)
        # Find the team by name
        teams = await get_verified_teams(tourney["_id"])
        target = next((t for t in teams if t["team_name"] == team_name), None)
        if not target:
            return await interaction.response.send_message("❌ Team not found.", ephemeral=True)
        await delete_team(target["_id"])
        await interaction.response.send_message(f"🚫 Team **{team_name}** has been disqualified.", ephemeral=False)

    @app_commands.command(name="ban_player", description="Ban a player from a team.")
    @app_commands.describe(tourney_name="Tournament name", team_name="Team name", player="Player to ban")
    async def ban_player(self, interaction: discord.Interaction, tourney_name: str, team_name: str, player: discord.Member):
        if not self.is_staff(interaction):
            return await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
        tourney = await get_tournament_by_name(interaction.guild.id, tourney_name)
        if not tourney:
            return await interaction.response.send_message("❌ Tournament not found.", ephemeral=True)
        teams = await get_verified_teams(tourney["_id"])
        team = next((t for t in teams if t["team_name"] == team_name), None)
        if not team:
            return await interaction.response.send_message("❌ Team not found.", ephemeral=True)
        # Remove the player's registration and role
        from utils.db import get_team_registrations, remove_registration
        regs = await get_team_registrations(team["_id"])
        for reg in regs:
            if reg["user_id"] == player.id and reg["approved"]:
                await remove_registration(reg["_id"])
                await player.remove_roles(discord.Object(id=team["team_role_id"]))
                return await interaction.response.send_message(f"🔨 <@{player.id}> has been banned from **{team_name}**.", ephemeral=False)
        await interaction.response.send_message("❌ Player not found on that team.", ephemeral=True)

    @app_commands.command(name="record_score", description="Record a match result and update bracket.")
    @app_commands.describe(tourney_name="Tournament name", match_id="Match ObjectId", score_a="Score for Team A", score_b="Score for Team B")
    async def record_score(self, interaction: discord.Interaction, tourney_name: str, match_id: str, score_a: int, score_b: int):
        if not self.is_staff(interaction):
            return await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
        tourney = await get_tournament_by_name(interaction.guild.id, tourney_name)
        if not tourney:
            return await interaction.response.send_message("❌ Tournament not found.", ephemeral=True)
        result = "team_a_win" if score_a > score_b else "team_b_win" if score_b > score_a else "draw"
        match = await update_match_result(match_id, score_a, score_b, result)
        # Push to external bracket service
        new_image_url = await update_bracket_match(
            tourney_name=tourney["bracket_service_id"],
            match_id=match["service_match_id"],
            score_a=score_a,
            score_b=score_b
        )
        # Update tournament doc
        from utils.db import update_tournament_bracket_info
        await update_tournament_bracket_info(
            tourney_id=tourney["_id"],
            bracket_channel_id=tourney["bracket_channel_id"],
            bracket_msg_id=tourney["bracket_msg_id"],
            service_id=tourney["bracket_service_id"],
            image_url=new_image_url
        )
        # Edit the bracket message
        bracket_ch = interaction.guild.get_channel(tourney["bracket_channel_id"])
        bracket_msg = await bracket_ch.fetch_message(tourney["bracket_msg_id"])
        embed = discord.Embed(
            title=f"📊 {tourney_name} Bracket (Updated)",
            description=(
                f"Mode: `{tourney['mode']}`  •  Sponsor: `{tourney['sponsor_name']}`\n"
                f"Updated on {get_current_time_str(tourney['timezone'])}"
            ),
            color=discord.Color.orange()
        )
        embed.set_image(url=new_image_url)
        await bracket_msg.edit(embed=embed)
        # Delete VCs if they exist
        from utils.db import get_match
        match_doc = await get_match(match_id)
        for vc_id in (match_doc["vc_a_id"], match_doc["vc_b_id"], match_doc["vc_spec_id"]):
            vc = interaction.guild.get_channel(vc_id)
            if vc:
                await vc.delete()
        await interaction.response.send_message("✅ Score recorded and bracket updated.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffTools(bot))
