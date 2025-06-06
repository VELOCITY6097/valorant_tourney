import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict, List, Optional
from datetime import datetime

from utils.db import (
    create_or_update_guild_settings,
    get_guild_settings,
    get_tournament_by_name,
    create_tournament,
    update_tournament_field,
    update_tournament_status,
    insert_match,
    get_verified_teams
)
from utils.helpers import get_current_time_str
from utils.bracket_api import create_bracket_on_service


# ────────────────────────────────────────────────────────────────────────────────
# MODALS: CreateTournamentModal & DeleteTournamentModal
# ────────────────────────────────────────────────────────────────────────────────
class CreateTournamentModal(discord.ui.Modal, title="Create New Tournament"):
    name = discord.ui.TextInput(label="Tournament Name (no spaces)", max_length=32)
    is_paid = discord.ui.Select(
        placeholder="Is this a paid tournament?",
        options=[
            discord.SelectOption(label="Free", value="free", emoji="💰"),
            discord.SelectOption(label="Paid", value="paid", emoji="💵")
        ]
    )
    mode = discord.ui.Select(
        placeholder="Select game mode",
        options=[
            discord.SelectOption(label="Standard", value="Standard"),
            discord.SelectOption(label="Spike Rush", value="Spike Rush")
        ]
    )
    sponsor_name = discord.ui.TextInput(label="Sponsor Name (optional)", required=False, max_length=64)
    rulebook_url = discord.ui.TextInput(label="Rulebook URL (pdf/jpg/png)", required=False)
    rules_text = discord.ui.TextInput(
        label="Tournament Rules",
        style=discord.TextStyle.paragraph,
        required=False
    )
    banner_url = discord.ui.TextInput(label="Banner Image URL (optional)", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild  # invoked from button in guild context

        name = self.name.value.strip()
        is_paid_flag = (self.is_paid.values[0] == "paid")
        mode_val = self.mode.values[0]
        sponsor = self.sponsor_name.value.strip() or ""
        rulebook = self.rulebook_url.value.strip() or None
        rules = self.rules_text.value.strip() or ""
        banner = self.banner_url.value.strip() or None

        # Prevent duplicate
        existing = await get_tournament_by_name(guild.id, name)
        if existing:
            return await user.send(f"⚠️ A tournament named `{name}` already exists in **{guild.name}**.")

        # Create category & roles
        category = await guild.create_category(name=name)
        overwatch_role = await guild.create_role(
            name=f"🔒 {name}-Overwatch",
            permissions=discord.Permissions(manage_channels=True, manage_roles=True, view_channel=True),
            mentionable=False
        )
        staff_role = await guild.create_role(
            name=f"⭐ {name}-Staff",
            permissions=discord.Permissions(manage_channels=True, view_channel=True),
            mentionable=False
        )
        await user.add_roles(overwatch_role, staff_role)

        everyone = guild.default_role
        overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            overwatch_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        # Create tournament channels
        info_ch = await category.create_text_channel("📢-tournament-info", overwrites=overwrites)
        reg_ch = await category.create_text_channel("📝-registration", overwrites=overwrites)
        join_ch = await category.create_text_channel("🎟️-join-team", overwrites=overwrites)
        support_ch = await category.create_text_channel("🆘-support", overwrites=overwrites)
        bracket_ch = await category.create_text_channel("📊-brackets", overwrites=overwrites)

        staff_verify = await category.create_text_channel(
            "🔒-staff-verify",
            overwrites={
                everyone: discord.PermissionOverwrite(view_channel=False),
                staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                overwatch_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
        )

        # Insert into DB
        tourney_doc = {
            "guild_id": guild.id,
            "name": name,
            "category_channel_id": category.id,
            "overwatch_role_id": overwatch_role.id,
            "staff_role_id": staff_role.id,
            "is_paid": is_paid_flag,
            "status": "registration_open",
            "mode": mode_val,
            "sponsor_name": sponsor,
            "timezone": "Asia/Kolkata",
            "registration_channel_id": reg_ch.id,
            "staff_verify_channel_id": staff_verify.id
        }
        new_id = await create_tournament(tourney_doc)

        # Build and send embed into info_ch
        embed = discord.Embed(
            title=f"🎉 {name} is OPEN!",
            description=(
                f"**Mode:** {mode_val}\n"
                f"**Sponsor:** {sponsor or 'None'}\n"
                f"**Paid:** {'Yes' if is_paid_flag else 'No'}\n\n"
                f"**Rulebook:** {rulebook or '‒'}\n\n"
                f"**Rules:**\n{rules or '‒'}"
            ),
            color=discord.Color.green()
        )
        if banner:
            embed.set_image(url=banner)

        await info_ch.send(embed=embed)

        # Log to 🔔-bot-updates
        settings = await get_guild_settings(guild.id)
        log_ch = guild.get_channel(settings.get("bot_updates_channel_id"))
        if log_ch:
            await log_ch.send(f"🔔 **Tournament Created:** `{name}` by <@{user.id}>")

        # Confirm DM to user
        await user.send(f"✅ Tournament `{name}` created successfully in **{guild.name}**.")


class DeleteTournamentModal(discord.ui.Modal, title="Delete Tournament"):
    tourney_name = discord.ui.TextInput(label="Tournament Name (exact)", max_length=32)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        name = self.tourney_name.value.strip()
        tourney = await get_tournament_by_name(guild.id, name)
        if not tourney:
            return await user.send(f"❌ No active tournament named `{name}` found.")

        # Delete entire category (and child channels)
        cat = guild.get_channel(tourney["category_channel_id"])
        if cat:
            await cat.delete()

        # Delete Overwatch & Staff roles
        ow = guild.get_role(tourney["overwatch_role_id"])
        if ow:
            await ow.delete()
        st = guild.get_role(tourney["staff_role_id"])
        if st:
            await st.delete()

        # Mark tournament as deleted in MongoDB
        await update_tournament_field(tourney["_id"], {"deleted_at": datetime.utcnow()})

        # Log to 🔔-bot-updates
        settings = await get_guild_settings(guild.id)
        log_ch = guild.get_channel(settings.get("bot_updates_channel_id"))
        if log_ch:
            await log_ch.send(f"🗑️ **Tournament Deleted:** `{name}` by <@{user.id}>")

        # Confirm DM to user
        await user.send(f"✅ Tournament `{name}` has been deleted.")


# ────────────────────────────────────────────────────────────────────────────────
# VIEW: ControlButtonsView (Create/Delete Tournament buttons)
# ────────────────────────────────────────────────────────────────────────────────
class ControlButtonsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(custom_id="create_tourney_btn", label="Create Tournament", style=discord.ButtonStyle.primary)
    async def create_tourney_click(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateTournamentModal())

    @discord.ui.button(custom_id="delete_tourney_btn", label="Delete Tournament", style=discord.ButtonStyle.danger)
    async def delete_tourney_click(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(DeleteTournamentModal())


# ────────────────────────────────────────────────────────────────────────────────
# COG: Core (setup, settings, and posting Bot Controls view)
# ────────────────────────────────────────────────────────────────────────────────
class Core(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Initial setup for Valorant tournament bot.")
    async def setup(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 You must be a server Administrator to run this command.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        settings = await get_guild_settings(guild.id)

        recreated = {
            "category": False,
            "bot_updates_ch": False,
            "tourney_log_ch": False,
            "bot_controls_ch": False,
            "custom3_ch": False,
            "ow_role": False,
            "staff_role": False
        }

        # CATEGORY
        category = None
        cat_id = settings.get("category_id")
        if cat_id:
            category = guild.get_channel(cat_id)
        if not category:
            category = await guild.create_category(name="Valorant Tourney")
            recreated["category"] = True
            settings["category_id"] = category.id

        everyone = guild.default_role
        base_overwrites = {everyone: discord.PermissionOverwrite(view_channel=False)}

        # 🔔-bot-updates
        bot_updates_ch = None
        bu_id = settings.get("bot_updates_channel_id")
        if bu_id:
            bot_updates_ch = guild.get_channel(bu_id)
        if not bot_updates_ch:
            bot_updates_ch = await category.create_text_channel("🔔-bot-updates", overwrites=base_overwrites)
            recreated["bot_updates_ch"] = True
            settings["bot_updates_channel_id"] = bot_updates_ch.id

        # 📝-valorant-tourney-log
        tourney_log_ch = None
        tl_id = settings.get("tourney_log_channel_id")
        if tl_id:
            tourney_log_ch = guild.get_channel(tl_id)
        if not tourney_log_ch:
            tourney_log_ch = await category.create_text_channel("📝-valorant-tourney-log", overwrites=base_overwrites)
            recreated["tourney_log_ch"] = True
            settings["tourney_log_channel_id"] = tourney_log_ch.id

        # ⚙️-bot-controls
        bot_controls_ch = None
        bc_id = settings.get("bot_controls_channel_id")
        if bc_id:
            bot_controls_ch = guild.get_channel(bc_id)
        if not bot_controls_ch:
            bot_controls_ch = await category.create_text_channel("⚙️-bot-controls", overwrites=base_overwrites)
            recreated["bot_controls_ch"] = True
            settings["bot_controls_channel_id"] = bot_controls_ch.id

        # ⚙️-custom-3
        custom3_ch = None
        c3_id = settings.get("custom3_channel_id")
        if c3_id:
            custom3_ch = guild.get_channel(c3_id)
        if not custom3_ch:
            custom3_ch = await category.create_text_channel("⚙️-custom-3", overwrites=base_overwrites)
            recreated["custom3_ch"] = True
            settings["custom3_channel_id"] = custom3_ch.id

        # 🔒 Tournament Overwatch role
        ow_role = None
        ow_id = settings.get("overwatch_role_id")
        if ow_id:
            ow_role = guild.get_role(ow_id)
        if not ow_role:
            ow_permissions = discord.Permissions(manage_channels=True, manage_roles=True, view_channel=True)
            ow_role = await guild.create_role(name="🔒 Tournament Overwatch", permissions=ow_permissions, mentionable=False)
            recreated["ow_role"] = True
            settings["overwatch_role_id"] = ow_role.id

        # ⭐ Tournament Staff role
        staff_role = None
        st_id = settings.get("staff_role_id")
        if st_id:
            staff_role = guild.get_role(st_id)
        if not staff_role:
            staff_permissions = discord.Permissions(manage_channels=True, view_channel=True)
            staff_role = await guild.create_role(name="⭐ Tournament Staff", permissions=staff_permissions, mentionable=False)
            recreated["staff_role"] = True
            settings["staff_role_id"] = staff_role.id

        # Apply permissions on all four channels
        perms_overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            ow_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        for ch in (bot_updates_ch, tourney_log_ch, bot_controls_ch, custom3_ch):
            await ch.edit(overwrites=perms_overwrites)

        # Update DB if any piece was (re)created
        if any(recreated.values()):
            await create_or_update_guild_settings(
                guild_id=guild.id,
                admin_role_id=settings.get("admin_role_id"),
                premium_enabled=settings.get("premium_enabled"),
                premium_commands=settings.get("premium_commands"),
                maintenance_mode=settings.get("maintenance_mode"),
                maintenance_msg=settings.get("maintenance_msg"),
                default_timezone=settings.get("default_timezone"),
                overwatch_role_id=settings["overwatch_role_id"],
                staff_role_id=settings["staff_role_id"],
                category_id=settings["category_id"],
                bot_updates_channel_id=settings["bot_updates_channel_id"],
                tourney_log_channel_id=settings["tourney_log_channel_id"],
                bot_controls_channel_id=settings["bot_controls_channel_id"],
                custom3_channel_id=settings["custom3_channel_id"],
                admin_override_role_id=settings.get("admin_override_role_id")
            )

        # Post (or refresh) “Bot Controls” menu in ⚙️-bot-controls
        async for msg in bot_controls_ch.history(limit=50):
            if msg.author == self.bot.user and msg.embeds:
                e = msg.embeds[0]
                if e.title == "🤖 Bot Controls":
                    await msg.delete()

        bc_embed = discord.Embed(
            title="🤖 Bot Controls",
            description=(
                "Use the buttons below to manage tournaments:\n\n"
                "• **Create Tournament**\n"
                "• **Delete Tournament**\n\n"
                "Click a button to begin."
            ),
            color=discord.Color.blue()
        )
        view = ControlButtonsView()
        await bot_controls_ch.send(embed=bc_embed, view=view)

        # Final response
        if any(recreated.values()):
            created_list = []
            if recreated["category"]:
                created_list.append("• Category `Valorant Tourney`")
            if recreated["bot_updates_ch"]:
                created_list.append("• Channel 🔔-bot-updates")
            if recreated["tourney_log_ch"]:
                created_list.append("• Channel 📝-valorant-tourney-log")
            if recreated["bot_controls_ch"]:
                created_list.append("• Channel ⚙️-bot-controls")
            if recreated["custom3_ch"]:
                created_list.append("• Channel ⚙️-custom-3")
            if recreated["ow_role"]:
                created_list.append("• Role 🔒 Tournament Overwatch")
            if recreated["staff_role"]:
                created_list.append("• Role ⭐ Tournament Staff")

            resp_embed = discord.Embed(
                title="🔄 Valorant Tourney Setup Updated",
                description="Recreated missing resources:\n\n" + "\n".join(created_list),
                color=discord.Color.green()
            )
            return await interaction.followup.send(embed=resp_embed, ephemeral=True)

        resp_embed = discord.Embed(
            title="⚙️ Setup Already Completed",
            description="All resources are already in place. Use ⚙️-bot-controls to manage tournaments.",
            color=discord.Color.yellow()
        )
        await interaction.followup.send(embed=resp_embed, ephemeral=True)

    @app_commands.command(name="settings", description="View or change bot settings.")
    async def settings(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 You must be a server Administrator to view settings.",
                ephemeral=True
            )

        settings = await get_guild_settings(interaction.guild.id)
        ow = interaction.guild.get_role(settings.get("overwatch_role_id"))
        st = interaction.guild.get_role(settings.get("staff_role_id"))
        cat = interaction.guild.get_channel(settings.get("category_id"))
        bu = interaction.guild.get_channel(settings.get("bot_updates_channel_id"))
        tl = interaction.guild.get_channel(settings.get("tourney_log_channel_id"))
        bc = interaction.guild.get_channel(settings.get("bot_controls_channel_id"))
        c3 = interaction.guild.get_channel(settings.get("custom3_channel_id"))
        ao = (
            interaction.guild.get_role(settings.get("admin_override_role_id"))
            if settings.get("admin_override_role_id") else None
        )

        embed = discord.Embed(
            title="⚙️ Tournament Bot Settings",
            color=discord.Color.blue()
        )
        embed.add_field(name="🔒 Overwatch Role", value=(ow.mention if ow else "‒"), inline=False)
        embed.add_field(name="⭐ Staff Role", value=(st.mention if st else "‒"), inline=False)
        embed.add_field(name="Category", value=(cat.mention if cat else "‒"), inline=False)
        embed.add_field(name="🔔 Bot-Updates", value=(bu.mention if bu else "‒"), inline=False)
        embed.add_field(name="📝 Tourney-Log", value=(tl.mention if tl else "‒"), inline=False)
        embed.add_field(name="⚙️ Bot-Controls", value=(bc.mention if bc else "‒"), inline=False)
        embed.add_field(name="⚙️ Custom-3", value=(c3.mention if c3 else "‒"), inline=False)
        embed.add_field(
            name="Admin Override Role",
            value=(ao.mention if ao else "Not set (fallback to Admins)"),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


# ────────────────────────────────────────────────────────────────────────────────
# COG: Tournament (close_registration command)
# ────────────────────────────────────────────────────────────────────────────────
class Tournament(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="close_registration",
        description="Close registrations and generate bracket."
    )
    @app_commands.describe(name="Tournament name to close")
    async def close_registration(
        self,
        interaction: discord.Interaction,
        name: str
    ):
        guild = interaction.guild
        user = interaction.user

        # Permission check
        settings = await get_guild_settings(guild.id)
        overwatch_id = settings.get("overwatch_role_id")
        staff_id = settings.get("staff_role_id")
        user_roles = [r.id for r in user.roles]
        if not (
            user.guild_permissions.administrator
            or overwatch_id in user_roles
            or staff_id in user_roles
        ):
            return await interaction.response.send_message(
                "🚫 You need Overwatch/Staff or Administrator.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=False)

        tourney = await get_tournament_by_name(guild.id, name)
        if not tourney or tourney["status"] != "registration_open":
            return await interaction.followup.send(
                f"❌ `{name}` not open or not found.", ephemeral=True
            )

        teams = await get_verified_teams(tourney["_id"])
        if len(teams) < 2:
            return await interaction.followup.send(
                "⚠️ Need at least 2 verified teams.", ephemeral=True
            )

        for idx in range(0, len(teams), 2):
            team_a = teams[idx]["_id"]
            team_b = teams[idx + 1]["_id"] if idx + 1 < len(teams) else None
            await insert_match(
                tourney_id=tourney["_id"],
                round_number=1,
                bracket_slot_index=(idx // 2) + 1,
                team_a_id=team_a,
                team_b_id=team_b
            )

        await update_tournament_status(tourney["_id"], "in_progress")

        bracket_cog = self.bot.get_cog("Bracket")
        if bracket_cog:
            await bracket_cog.init_bracket.callback(bracket_cog, interaction, name)

        log_ch = guild.get_channel(settings.get("bot_updates_channel_id"))
        if log_ch:
            await log_ch.send(f"🔔 **Registration Closed** for `{name}` by <@{user.id}>")

        await user.send(f"✅ Registration for `{name}` closed and bracket generated.")


# ────────────────────────────────────────────────────────────────────────────────
# At startup, register Cogs and Views
# ────────────────────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    # Register Core and Tournament cogs
    await bot.add_cog(Core(bot))
    await bot.add_cog(Tournament(bot))

    # Register views so buttons/modals persist across restarts
    bot.add_view(ControlButtonsView())
    bot.add_view(CreateTournamentModal())
    bot.add_view(DeleteTournamentModal())

