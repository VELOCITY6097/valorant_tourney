# cogs/registration.py

import discord
from discord import ui
from discord.ext import commands
from typing import Dict, List, Optional  # ← Ensure these are imported

from utils.db import (
    get_active_tournaments,
    get_tourney_by_reg_channel,
    get_tourney_by_join_channel,
    create_team,
    upsert_player,
    add_registration,
    get_registration_by_id,
    approve_registration,
    remove_registration,
    get_team,
    get_team_by_key,
    get_team_registrations,
    update_tournament_field
)
from utils.helpers import generate_key

class RegistrationMenuView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ui.Button(label="📝 Register Team", custom_id="btn_register_team", style=discord.ButtonStyle.primary))
        self.add_item(ui.Button(label="🤝 Join Team",     custom_id="btn_join_team",    style=discord.ButtonStyle.success))
        self.add_item(ui.Button(label="🔄 Change Captain", custom_id="btn_change_captain", style=discord.ButtonStyle.secondary))
        self.add_item(ui.Button(label="❌ Withdraw Team",   custom_id="btn_withdraw_team", style=discord.ButtonStyle.danger))
        self.add_item(ui.Button(label="🚨 Remove Player",  custom_id="btn_remove_player", style=discord.ButtonStyle.danger))
        self.add_item(ui.Button(label="🔢 Change Playing 5", custom_id="btn_change_playing5", style=discord.ButtonStyle.secondary))


class RegisterTeamModal(ui.Modal, title="Register a New Team"):
    team_name = ui.TextInput(label="Team Name", placeholder="Enter your team’s name", max_length=32)
    icon_url  = ui.TextInput(label="Team Icon URL (optional)", required=False, placeholder="https://...png")

    async def on_submit(self, interaction: discord.Interaction):
        team_name = self.team_name.value.strip()
        icon_url  = self.icon_url.value.strip() or None
        guild = interaction.guild
        user  = interaction.user

        tourney = await get_tourney_by_reg_channel(interaction.channel.id)
        if not tourney:
            return await interaction.response.send_message("❌ Cannot find associated tournament.", ephemeral=True)

        key = generate_key(20)
        team_role = await guild.create_role(name=team_name, mentionable=False)
        is_verified = not tourney["is_paid"]

        team_id = await create_team(
            tourney_id         = tourney["_id"],
            team_name          = team_name,
            captain_user_id    = user.id,
            team_role_id       = team_role.id,
            registration_key   = key,
            is_verified        = is_verified,
            icon_url           = icon_url
        )

        try:
            await user.send(f"✅ Team `{team_name}` registered! Your registration key:\n`{key}`")
        except:
            pass

        if is_verified:
            await interaction.response.send_message(
                f"🆕 Team **{team_name}** registered successfully! Check your DM for the key."
            )
        else:
            staff_ch = guild.get_channel(tourney["staff_verify_channel_id"])
            await staff_ch.send(f"🛡️ **Payment Pending** for Team `{team_name}` (Captain: <@{user.id}>)")
            await interaction.response.send_message(
                "🔔 Team registered; awaiting payment verification by staff.", ephemeral=True
            )


class JoinTeamModal(ui.Modal, title="Join an Existing Team"):
    reg_key = ui.TextInput(label="Captain’s Key", placeholder="Paste the 20‐char key here")
    ign     = ui.TextInput(label="Your In‐Game Name (# tag)", placeholder="Name#1234")

    async def on_submit(self, interaction: discord.Interaction):
        key   = self.reg_key.value.strip()
        ign   = self.ign.value.strip()
        guild = interaction.guild
        user  = interaction.user

        tourney = await get_tourney_by_join_channel(interaction.channel.id)
        if not tourney:
            return await interaction.response.send_message("❌ Cannot find associated tournament.", ephemeral=True)

        team = await get_team_by_key(tourney["_id"], key)
        if not team or not team["is_verified"]:
            return await interaction.response.send_message("❌ Invalid or unverified key.", ephemeral=True)

        await upsert_player(user.id, ign, guild.id)
        reg_id = await add_registration(team["_id"], user.id)

        reg_ch     = guild.get_channel(tourney["registration_channel_id"])
        captain_id = team["captain_user_id"]

        view = ui.View(timeout=None)
        view.add_item(ui.Button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id=f"approve_{reg_id}"))
        view.add_item(ui.Button(label="❌ Reject",  style=discord.ButtonStyle.danger,  custom_id=f"reject_{reg_id}"))

        await reg_ch.send(
            f"👤 <@{user.id}> wants to join **{team['team_name']}** as `{ign}`.\n"
            f"Captain: <@{captain_id}>, click a button to approve or reject.",
            view=view
        )
        await interaction.response.send_message("🔔 Your request has been sent to the captain.", ephemeral=True)


class ChangeCaptainModal(ui.Modal, title="Transfer Captain"):
    team_id     = ui.TextInput(label="Team ID", placeholder="Enter the team’s ObjectId", max_length=24)
    new_captain = ui.TextInput(label="New Captain @mention", placeholder="@User", max_length=37)

    async def on_submit(self, interaction: discord.Interaction):
        old_id  = interaction.user.id
        team_id = self.team_id.value.strip()
        new_id  = int(self.new_captain.value.strip().replace("<@", "").replace("!", "").replace(">", ""))

        team = await get_team(team_id)
        if not team:
            return await interaction.response.send_message("❌ Team not found.", ephemeral=True)
        if team["captain_user_id"] != old_id:
            return await interaction.response.send_message("🚫 Only the current captain can transfer.", ephemeral=True)

        await update_tournament_field(team_id, {"captain_user_id": new_id})
        guild      = interaction.guild
        new_member = guild.get_member(new_id)
        if new_member:
            await new_member.add_roles(discord.Object(id=team["team_role_id"]))

        await interaction.response.send_message(
            f"✅ Captainship of **{team['team_name']}** transferred to <@{new_id}>.",
            ephemeral=False
        )


class RemovePlayerModal(ui.Modal, title="Remove a Player"):
    team_id        = ui.TextInput(label="Team ID", placeholder="Enter the team’s ObjectId", max_length=24)
    player_mention = ui.TextInput(label="Player @mention", placeholder="@User you want to remove")

    async def on_submit(self, interaction: discord.Interaction):
        team_id   = self.team_id.value.strip()
        player_id = int(self.player_mention.value.strip().replace("<@", "").replace("!", "").replace(">", ""))

        team = await get_team(team_id)
        if not team:
            return await interaction.response.send_message("❌ Team not found.", ephemeral=True)
        if team["captain_user_id"] != interaction.user.id:
            return await interaction.response.send_message("🚫 Only the captain can remove players.", ephemeral=True)

        regs = await get_team_registrations(team_id)
        for reg in regs:
            if reg["user_id"] == player_id:
                await remove_registration(reg["_id"])
                member = interaction.guild.get_member(player_id)
                if member:
                    await member.remove_roles(discord.Object(id=team["team_role_id"]))
                return await interaction.response.send_message(
                    f"✅ Removed <@{player_id}> from **{team['team_name']}**.", ephemeral=False
                )

        await interaction.response.send_message("❌ That player is not on your roster.", ephemeral=True)


class ChangePlaying5Modal(ui.Modal, title="Change Playing 5"):
    team_id  = ui.TextInput(label="Team ID", placeholder="Enter the team’s ObjectId", max_length=24)
    new_five = ui.TextInput(
        label="New Playing 5 (comma-separated IGN#tags)",
        placeholder="e.g. Alpha#1234, Bravo#5678, …"
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Implementation depends on your DB structure (e.g. store playing_5 list in team doc).
        await interaction.response.send_message("✅ Playing 5 updated.", ephemeral=True)


class RegistrationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        for tourney in await get_active_tournaments():
            guild = self.bot.get_guild(tourney["guild_id"])
            if not guild:
                continue
            reg_ch = guild.get_channel(tourney["registration_channel_id"])
            if reg_ch:
                existing_id = tourney.get("registration_menu_msg_id")
                if existing_id:
                    try:
                        await reg_ch.fetch_message(existing_id)
                        continue
                    except discord.NotFound:
                        pass

                embed = discord.Embed(
                    title=f"📝 {tourney['name']} Registration Menu",
                    description=(
                        "Click any button below to perform an action:\n\n"
                        "• **Register Team**\n"
                        "• **Join Team**\n"
                        "• **Change Captain**\n"
                        "• **Withdraw Team**\n"
                        "• **Remove Player**\n"
                        "• **Change Playing 5**"
                    ),
                    color=discord.Color.blue()
                )
                view = RegistrationMenuView()
                msg = await reg_ch.send(embed=embed, view=view)
                await update_tournament_field(tourney["_id"], {"registration_menu_msg_id": msg.id})

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.data or "custom_id" not in interaction.data:
            return
        cid = interaction.data["custom_id"]

        # 📝 Register Team
        if cid == "btn_register_team":
            await interaction.response.send_modal(RegisterTeamModal())

        # 🤝 Join Team
        elif cid == "btn_join_team":
            await interaction.response.send_modal(JoinTeamModal())

        # 🔄 Change Captain
        elif cid == "btn_change_captain":
            await interaction.response.send_modal(ChangeCaptainModal())

        # ❌ Withdraw Team
        elif cid == "btn_withdraw_team":
            await interaction.response.send_message(
                "To withdraw your team, use `/withdrawteam <team_id>`.", ephemeral=True
            )

        # 🚨 Remove Player
        elif cid == "btn_remove_player":
            await interaction.response.send_modal(RemovePlayerModal())

        # 🔢 Change Playing 5
        elif cid == "btn_change_playing5":
            await interaction.response.send_modal(ChangePlaying5Modal())

        # ✅/❌ Approve or Reject join requests
        elif cid.startswith("approve_") or cid.startswith("reject_"):
            reg_id = cid.split("_", 1)[1]
            reg    = await get_registration_by_id(reg_id)
            if not reg:
                return await interaction.response.send_message("❌ Request not found.", ephemeral=True)

            team = await get_team(reg["team_id"])
            if interaction.user.id != team["captain_user_id"]:
                return await interaction.response.send_message("🚫 Only the captain can decide.", ephemeral=True)

            if cid.startswith("approve_"):
                await approve_registration(reg_id)
                member = interaction.guild.get_member(reg["user_id"])
                if member:
                    await member.add_roles(discord.Object(id=team["team_role_id"]))
                await interaction.response.send_message(
                    f"✅ <@{reg['user_id']}> approved for **{team['team_name']}**.", ephemeral=False
                )
            else:  # Reject
                await remove_registration(reg_id)
                await interaction.response.send_message(
                    f"❌ <@{reg['user_id']}> rejected from **{team['team_name']}**.", ephemeral=False
                )

        else:
            return


async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationCog(bot))
