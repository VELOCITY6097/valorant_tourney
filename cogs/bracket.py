# cogs/bracket.py

import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Dict, List, Optional  # ← Ensure these are imported
from datetime import datetime, timedelta

from utils.db import (
    get_guild_settings,
    get_tournament_by_name,
    update_tournament_bracket_info,
    get_verified_teams,
    get_matches_by_tourney,
    get_tournament_by_id,
    get_team,
    update_match_result,
    update_match_vcs,
    get_team_registrations
)
from utils.bracket_api import create_bracket_on_service, update_bracket_match
from utils.helpers import get_current_time_str, format_bracket_embed


class Bracket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.match_scheduler.start()

    def cog_unload(self):
        self.match_scheduler.cancel()

    @tasks.loop(seconds=60)
    async def match_scheduler(self):
        now = datetime.utcnow()
        cursor = db.matches.find({
            "scheduled_time": {"$gte": now, "$lte": now + timedelta(minutes=10)},
            "vc_a_id": None
        })

        async for match in cursor:
            tourney = await get_tournament_by_id(str(match["tourney_id"]))
            guild   = self.bot.get_guild(tourney["guild_id"])
            category= guild.get_channel(tourney["category_channel_id"])
            team_a  = await get_team(str(match["team_a_id"]))
            team_b  = await get_team(str(match["team_b_id"]))
            overwatch = guild.get_role(tourney["overwatch_role_id"])
            staff     = guild.get_role(tourney["staff_role_id"])
            everyone  = guild.default_role

            # Create VC for Team A
            overwrites_a = {
                everyone: discord.PermissionOverwrite(connect=False),
                discord.Object(id=team_a["team_role_id"]): discord.PermissionOverwrite(connect=True, speak=True),
                overwatch: discord.PermissionOverwrite(connect=True),
                staff: discord.PermissionOverwrite(connect=True)
            }
            vc_a = await category.create_voice_channel(f"VC-{team_a['team_name']}", overwrites=overwrites_a)

            # Create VC for Team B
            overwrites_b = {
                everyone: discord.PermissionOverwrite(connect=False),
                discord.Object(id=team_b["team_role_id"]): discord.PermissionOverwrite(connect=True, speak=True),
                overwatch: discord.PermissionOverwrite(connect=True),
                staff: discord.PermissionOverwrite(connect=True)
            }
            vc_b = await category.create_voice_channel(f"VC-{team_b['team_name']}", overwrites=overwrites_b)

            # Create Spectator VC
            overwrites_spec = {
                everyone: discord.PermissionOverwrite(connect=False),
                overwatch: discord.PermissionOverwrite(connect=True),
                staff: discord.PermissionOverwrite(connect=True)
            }
            vc_spec = await category.create_voice_channel("VC-Spectator", overwrites=overwrites_spec)

            # Update match document with VC IDs
            await update_match_vcs(str(match["_id"]), vc_a.id, vc_b.id, vc_spec.id)

            # Send DM reminders to players
            team_a_member_ids = [r["user_id"] for r in await get_team_registrations(str(match["team_a_id"])) if r.get("approved")]
            team_b_member_ids = [r["user_id"] for r in await get_team_registrations(str(match["team_b_id"])) if r.get("approved")]
            for player_id in team_a_member_ids:
                member = guild.get_member(player_id)
                if member:
                    try:
                        await member.send(f"🔔 Your match vs {team_b['team_name']} starts in 10 minutes!")
                    except:
                        pass
            for player_id in team_b_member_ids:
                member = guild.get_member(player_id)
                if member:
                    try:
                        await member.send(f"🔔 Your match vs {team_a['team_name']} starts in 10 minutes!")
                    except:
                        pass

    @match_scheduler.before_loop
    async def before_scheduler(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="init_bracket", description="Initialize bracket channel and image.")
    @app_commands.describe(tourney_name="Tournament name")
    async def init_bracket(self, interaction: discord.Interaction, tourney_name: str):
        guild = interaction.guild
        user  = interaction.user

        # Permission check
        settings     = await get_guild_settings(guild.id)
        overwatch_id = settings["overwatch_role_id"]
        staff_id     = settings["staff_role_id"]
        roles        = [r.id for r in user.roles]
        if not (user.guild_permissions.administrator or overwatch_id in roles or staff_id in roles):
            return await interaction.response.send_message("🚫 Staff only.", ephemeral=True)

        tourney = await get_tournament_by_name(guild.id, tourney_name)
        if not tourney:
            return await interaction.response.send_message("❌ Tournament not found.", ephemeral=True)
        if tourney.get("bracket_channel_id"):
            return await interaction.response.send_message("⚠️ Bracket already initialized.", ephemeral=True)

        category  = guild.get_channel(tourney["category_channel_id"])
        overwatch = guild.get_role(tourney["overwatch_role_id"])
        staff     = guild.get_role(tourney["staff_role_id"])
        everyone  = guild.default_role

        overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            overwatch: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            staff: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        bracket_ch = await category.create_text_channel("📊-bracket", overwrites=overwrites)

        teams = await get_verified_teams(tourney["_id"])
        if not teams:
            embed = discord.Embed(
                title=f"📊 {tourney_name} Bracket (Waiting for seeds)",
                color=discord.Color.blue()
            )
            msg = await bracket_ch.send(embed=embed)
            await update_tournament_bracket_info(
                tourney_id=tourney["_id"],
                bracket_channel_id=bracket_ch.id,
                bracket_msg_id=msg.id,
                service_id=None,
                image_url=None
            )
            return await interaction.response.send_message(f"✅ Bracket channel {bracket_ch.mention} created.", ephemeral=True)

        # Create bracket on external service
        team_names       = [t["team_name"] for t in teams]
        bracket_image_url = await create_bracket_on_service(tourney_name, team_names, "single elimination")
        service_id       = tourney_name  # Or capture actual ID from API

        embed = discord.Embed(
            title=f"📊 {tourney_name} Bracket",
            description=(
                f"Mode: `{tourney['mode']}` • Sponsor: `{tourney['sponsor_name']}`\n"
                f"Generated on {get_current_time_str(tourney['timezone'])}"
            ),
            color=discord.Color.purple()
        )
        embed.set_image(url=bracket_image_url)
        msg = await bracket_ch.send(embed=embed)

        await update_tournament_bracket_info(
            tourney_id=tourney["_id"],
            bracket_channel_id=bracket_ch.id,
            bracket_msg_id=msg.id,
            service_id=service_id,
            image_url=bracket_image_url
        )
        await interaction.response.send_message(f"✅ Bracket created in {bracket_ch.mention}.", ephemeral=True)

    @app_commands.command(name="refresh_bracket", description="Force-refresh bracket image.")
    @app_commands.describe(tourney_name="Tournament name")
    async def refresh_bracket(self, interaction: discord.Interaction, tourney_name: str):
        guild = interaction.guild
        user  = interaction.user

        # Permission check
        settings     = await get_guild_settings(guild.id)
        overwatch_id = settings["overwatch_role_id"]
        staff_id     = settings["staff_role_id"]
        roles        = [r.id for r in user.roles]
        if not (user.guild_permissions.administrator or overwatch_id in roles or staff_id in roles):
            return await interaction.response.send_message("🚫 Staff only.", ephemeral=True)

        tourney = await get_tournament_by_name(guild.id, tourney_name)
        if not tourney or not tourney.get("bracket_channel_id") or not tourney.get("bracket_service_id"):
            return await interaction.response.send_message("❌ Bracket not initialized.", ephemeral=True)

        bracket_ch = guild.get_channel(tourney["bracket_channel_id"])
        try:
            bracket_msg = await bracket_ch.fetch_message(tourney["bracket_msg_id"])
        except discord.NotFound:
            return await interaction.response.send_message("❌ Bracket message missing.", ephemeral=True)

        new_image_url = tourney["bracket_image_url"]
        embed = discord.Embed(
            title=f"📊 {tourney_name} Bracket (Refreshed)",
            description=(
                f"Mode: `{tourney['mode']}` • Sponsor: `{tourney['sponsor_name']}`\n"
                f"Refreshed on {get_current_time_str(tourney['timezone'])}"
            ),
            color=discord.Color.purple()
        )
        embed.set_image(url=new_image_url)
        await bracket_msg.edit(embed=embed)
        await interaction.response.send_message("✅ Bracket refreshed.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Bracket(bot))
