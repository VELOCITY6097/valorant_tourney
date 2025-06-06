# utils/db.py

import os
from datetime import datetime
from typing import Optional, List, Dict
import motor.motor_asyncio
from bson import ObjectId

# ────────────────────────────────────────────────────────────────────────────────
# 0. MongoDB Client Setup
# ────────────────────────────────────────────────────────────────────────────────
MONGO_URI      = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME  = os.getenv("MONGO_DB_NAME", "valorant_bot")

_mongo_client  = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db             = _mongo_client[MONGO_DB_NAME]


def _oid_str(document: Dict) -> Dict:
    """
    Convert a MongoDB document’s ObjectId into a string for JSON‐friendly output.
    """
    if not document:
        return {}
    doc = document.copy()
    doc["_id"] = str(doc["_id"])
    return doc


# ────────────────────────────────────────────────────────────────────────────────
# 1. Settings (extended for core/setup command)
#
#    • create_or_update_guild_settings
#    • get_guild_settings
#    • add_premium_command
#    • remove_premium_command
# ────────────────────────────────────────────────────────────────────────────────

async def create_or_update_guild_settings(
    guild_id: int,

    # ── Legacy fields (unchanged) ────────────────────────────────────────────────
    admin_role_id: Optional[int]        = None,
    premium_enabled: Optional[bool]     = None,
    premium_commands: Optional[List[str]] = None,
    maintenance_mode: Optional[bool]    = None,
    maintenance_msg: Optional[str]      = None,
    default_timezone: Optional[str]     = None,

    # ── New /setup fields (core functionality) ─────────────────────────────────
    overwatch_role_id: Optional[int]    = None,
    staff_role_id: Optional[int]        = None,
    category_id: Optional[int]          = None,
    bot_updates_channel_id: Optional[int]  = None,
    tourney_log_channel_id: Optional[int]  = None,
    bot_controls_channel_id: Optional[int] = None,
    custom3_channel_id: Optional[int]      = None,
    admin_override_role_id: Optional[int]  = None
) -> None:
    """
    Create or update this guild’s unified settings document.  
    Contains both legacy settings (admin, premium, maintenance, etc.) and
    the new core/setup fields (overwatch/staff roles, category, channel IDs).
    """
    update_fields: Dict = {}

    # ── Legacy settings fields ───────────────────────────────────────────────────
    if admin_role_id is not None:
        update_fields["admin_role_id"] = admin_role_id
    if premium_enabled is not None:
        update_fields["premium_enabled"] = premium_enabled
    if premium_commands is not None:
        update_fields["premium_commands"] = premium_commands
    if maintenance_mode is not None:
        update_fields["maintenance_mode"] = maintenance_mode
    if maintenance_msg is not None:
        update_fields["maintenance_msg"] = maintenance_msg
    if default_timezone is not None:
        update_fields["default_timezone"] = default_timezone

    # ── New /setup fields ─────────────────────────────────────────────────────────
    if overwatch_role_id is not None:
        update_fields["overwatch_role_id"] = overwatch_role_id
    if staff_role_id is not None:
        update_fields["staff_role_id"] = staff_role_id
    if category_id is not None:
        update_fields["category_id"] = category_id
    if bot_updates_channel_id is not None:
        update_fields["bot_updates_channel_id"] = bot_updates_channel_id
    if tourney_log_channel_id is not None:
        update_fields["tourney_log_channel_id"] = tourney_log_channel_id
    if bot_controls_channel_id is not None:
        update_fields["bot_controls_channel_id"] = bot_controls_channel_id
    if custom3_channel_id is not None:
        update_fields["custom3_channel_id"] = custom3_channel_id
    if admin_override_role_id is not None:
        update_fields["admin_override_role_id"] = admin_override_role_id

    # Upsert into the 'settings' collection
    await db.settings.update_one(
        {"guild_id": guild_id},
        {"$set": update_fields},
        upsert=True
    )


async def get_guild_settings(guild_id: int) -> Dict:
    """
    Retrieve this guild’s settings document.  
    If none exists, return a dictionary of default values for all fields.
    """
    doc = await db.settings.find_one({"guild_id": guild_id})
    if not doc:
        # Default structure when no document exists in MongoDB
        return {
            "guild_id": guild_id,

            # ── Legacy defaults ─────────────────────────────────────────────────────
            "admin_role_id": None,
            "premium_enabled": False,
            "premium_commands": [],
            "maintenance_mode": False,
            "maintenance_msg": "",
            "default_timezone": "Asia/Kolkata",

            # ── New /setup defaults ─────────────────────────────────────────────────
            "overwatch_role_id": None,
            "staff_role_id": None,
            "category_id": None,
            "bot_updates_channel_id": None,
            "tourney_log_channel_id": None,
            "bot_controls_channel_id": None,
            "custom3_channel_id": None,
            "admin_override_role_id": None
        }

    doc.pop("_id", None)
    return doc


async def add_premium_command(guild_id: int, command_name: str) -> None:
    """
    Add a command name to this guild’s premium_commands array.
    """
    await db.settings.update_one(
        {"guild_id": guild_id},
        {"$addToSet": {"premium_commands": command_name}},
        upsert=True
    )


async def remove_premium_command(guild_id: int, command_name: str) -> None:
    """
    Remove a command name from this guild’s premium_commands array.
    """
    await db.settings.update_one(
        {"guild_id": guild_id},
        {"$pull": {"premium_commands": command_name}}
    )


# ────────────────────────────────────────────────────────────────────────────────
# 2. Tournaments
#
#    • create_tournament
#    • get_tournament_by_name
#    • get_tournament_by_id
#    • update_tournament_status
#    • update_tournament_field
#    • get_active_tournaments
#    • update_tournament_bracket_info
#    • get_tourney_by_reg_channel
#    • get_tourney_by_join_channel
# ────────────────────────────────────────────────────────────────────────────────

async def create_tournament(tourney_data: Dict) -> str:
    """
    Insert a new tournament document into the 'tournaments' collection.
    Includes:
      - guild_id, name, category_channel_id, overwatch_role_id, staff_role_id
      - is_paid, status, mode, sponsor_name, timezone
      - registration & staff_verify channel IDs
      - (NEW) rulebook_url, rules_text, banner_url
      - bracket‐related placeholders and timestamps
    """
    doc = {
        "guild_id":                  tourney_data["guild_id"],
        "name":                      tourney_data["name"],
        "category_channel_id":       tourney_data["category_channel_id"],
        "overwatch_role_id":         tourney_data["overwatch_role_id"],
        "staff_role_id":             tourney_data["staff_role_id"],
        "is_paid":                   tourney_data.get("is_paid", False),
        "status":                    tourney_data.get("status", "registration_open"),
        "mode":                      tourney_data.get("mode", "Standard"),
        "sponsor_name":              tourney_data.get("sponsor_name", ""),
        "timezone":                  tourney_data.get("timezone", "Asia/Kolkata"),
        "registration_channel_id":   tourney_data.get("registration_channel_id"),
        "staff_verify_channel_id":   tourney_data.get("staff_verify_channel_id"),

        # ── NEW FIELDS from CreateTournamentModal ───────────────────────────────
        "rulebook_url":              tourney_data.get("rulebook_url", None),
        "rules_text":                tourney_data.get("rules_text", ""),
        "banner_url":                tourney_data.get("banner_url", None),

        # ── bracket‐related (initially None) ─────────────────────────────────────
        "bracket_channel_id":        None,
        "bracket_msg_id":            None,
        "bracket_service_id":        None,
        "bracket_image_url":         None,
        "registration_menu_msg_id":  None,

        "created_at":                datetime.utcnow(),
        "deleted_at":                None
    }
    result = await db.tournaments.insert_one(doc)
    return str(result.inserted_id)


async def get_tournament_by_name(guild_id: int, name: str) -> Optional[Dict]:
    """
    Fetch a single tournament document by (guild_id, name), 
    provided it’s not marked deleted (deleted_at == None).
    """
    doc = await db.tournaments.find_one({
        "guild_id": guild_id,
        "name": name,
        "deleted_at": None
    })
    return _oid_str(doc) if doc else None


async def get_tournament_by_id(tourney_id: str) -> Optional[Dict]:
    """
    Fetch a single tournament document by its ObjectId string,
    provided it’s not marked deleted.
    """
    try:
        oid = ObjectId(tourney_id)
    except:
        return None
    doc = await db.tournaments.find_one({"_id": oid, "deleted_at": None})
    return _oid_str(doc) if doc else None


async def update_tournament_status(tourney_id: str, new_status: str) -> None:
    """
    Update only the 'status' field of a given tournament document.
    e.g. from 'registration_open' → 'in_progress'.
    """
    await db.tournaments.update_one(
        {"_id": ObjectId(tourney_id)},
        {"$set": {"status": new_status}}
    )


async def update_tournament_field(tourney_id: str, fields: Dict) -> None:
    """
    Update arbitrary fields in a tournament document.
    e.g. marking deleted_at or updating bracket info.
    """
    await db.tournaments.update_one(
        {"_id": ObjectId(tourney_id)},
        {"$set": fields}
    )


async def get_active_tournaments() -> List[Dict]:
    """
    Return a list of all tournaments where status == 'registration_open'.
    """
    cursor = db.tournaments.find({"status": "registration_open"})
    results = []
    async for doc in cursor:
        results.append(_oid_str(doc))
    return results


async def update_tournament_bracket_info(
    tourney_id: str,
    bracket_channel_id: int,
    bracket_msg_id: int,
    service_id: str,
    image_url: str
) -> None:
    """
    After generating or refreshing a bracket image, store the channel/message/service IDs.
    """
    await db.tournaments.update_one(
        {"_id": ObjectId(tourney_id)},
        {"$set": {
            "bracket_channel_id": bracket_channel_id,
            "bracket_msg_id": bracket_msg_id,
            "bracket_service_id": service_id,
            "bracket_image_url": image_url
        }}
    )


async def get_tourney_by_reg_channel(channel_id: int) -> Optional[Dict]:
    """
    Return the tournament document whose registration_channel_id matches the given channel_id.
    """
    doc = await db.tournaments.find_one({
        "registration_channel_id": channel_id,
        "deleted_at": None
    })
    return _oid_str(doc) if doc else None


async def get_tourney_by_join_channel(channel_id: int) -> Optional[Dict]:
    """
    Return the tournament document whose registration_channel_id (or join_channel_id) matches.
    If you store a separate 'join_channel_id', adjust the filter accordingly.
    """
    doc = await db.tournaments.find_one({
        "registration_channel_id": channel_id,  # replace with "join_channel_id" if needed
        "deleted_at": None
    })
    return _oid_str(doc) if doc else None


# ────────────────────────────────────────────────────────────────────────────────
# 3. Teams
#
#    • create_team
#    • get_team_by_key
#    • get_team
#    • get_verified_teams
#    • set_team_verified
#    • update_team_captain
#    • delete_team
# ────────────────────────────────────────────────────────────────────────────────

async def create_team(
    tourney_id: str,
    team_name: str,
    captain_user_id: int,
    team_role_id: int,
    registration_key: str,
    is_verified: bool,
    icon_url: Optional[str] = None
) -> str:
    """
    Insert a new team document under the specified tournament.  
    Fields:
      - tourney_id (ObjectId)
      - team_name, team_role_id, captain_user_id
      - registration_key, is_verified, icon_url
      - created_at timestamp
    """
    doc = {
        "tourney_id": ObjectId(tourney_id),
        "team_name": team_name,
        "team_role_id": team_role_id,
        "captain_user_id": captain_user_id,
        "registration_key": registration_key,
        "is_verified": is_verified,
        "icon_url": icon_url,
        "created_at": datetime.utcnow()
    }
    result = await db.teams.insert_one(doc)
    return str(result.inserted_id)


async def get_team_by_key(tourney_id: str, reg_key: str) -> Optional[Dict]:
    """
    Fetch a single team document by (tourney_id, registration_key).
    """
    doc = await db.teams.find_one({
        "tourney_id": ObjectId(tourney_id),
        "registration_key": reg_key
    })
    return _oid_str(doc) if doc else None


async def get_team(team_id: str) -> Optional[Dict]:
    """
    Fetch a single team document by its ObjectId string.
    """
    try:
        oid = ObjectId(team_id)
    except:
        return None
    doc = await db.teams.find_one({"_id": oid})
    return _oid_str(doc) if doc else None


async def get_verified_teams(tourney_id: str) -> List[Dict]:
    """
    Return all teams under a tournament where is_verified == True.
    """
    cursor = db.teams.find({
        "tourney_id": ObjectId(tourney_id),
        "is_verified": True
    })
    results = []
    async for doc in cursor:
        results.append(_oid_str(doc))
    return results


async def set_team_verified(team_id: str, verified: bool = True) -> None:
    """
    Flip the 'is_verified' flag for a given team (e.g., after payment verification).
    """
    await db.teams.update_one(
        {"_id": ObjectId(team_id)},
        {"$set": {"is_verified": verified}}
    )


async def update_team_captain(team_id: str, new_captain_id: int) -> None:
    """
    Change the 'captain_user_id' for a team when captainship is transferred.
    """
    await db.teams.update_one(
        {"_id": ObjectId(team_id)},
        {"$set": {"captain_user_id": new_captain_id}}
    )


async def delete_team(team_id: str) -> None:
    """
    Delete a team document, and also remove all its related registrations.
    """
    await db.teams.delete_one({"_id": ObjectId(team_id)})
    await db.registrations.delete_many({"team_id": ObjectId(team_id)})


# ────────────────────────────────────────────────────────────────────────────────
# 4. Players
#
#    • upsert_player
#    • get_player_by_user_id
# ────────────────────────────────────────────────────────────────────────────────

async def upsert_player(user_id: int, riot_tag: str, guild_id: int) -> str:
    """
    Insert or update a player’s riot_tag and keep track of which guilds they’ve registered in.
    If a player record already exists, append this guild_id to 'registered_servers'.
    """
    doc = await db.players.find_one({"user_id": user_id})
    if doc:
        registered = set(doc.get("registered_servers", []))
        registered.add(guild_id)
        await db.players.update_one(
            {"_id": doc["_id"]},
            {"$set": {"riot_tag": riot_tag, "registered_servers": list(registered)}}
        )
        return str(doc["_id"])
    else:
        new = {
            "user_id": user_id,
            "riot_tag": riot_tag,
            "registered_servers": [guild_id],
            "created_at": datetime.utcnow()
        }
        result = await db.players.insert_one(new)
        return str(result.inserted_id)


async def get_player_by_user_id(user_id: int) -> Optional[Dict]:
    """
    Fetch a player document by Discord user ID.
    """
    doc = await db.players.find_one({"user_id": user_id})
    return _oid_str(doc) if doc else None


# ────────────────────────────────────────────────────────────────────────────────
# 5. Registrations
#
#    • add_registration
#    • get_registration_by_id
#    • approve_registration
#    • remove_registration
#    • get_team_registrations
# ────────────────────────────────────────────────────────────────────────────────

async def add_registration(team_id: str, user_id: int) -> str:
    """
    Insert a new registration request document (user wants to join a team).
    """
    doc = {
        "team_id": ObjectId(team_id),
        "user_id": user_id,
        "approved": False,
        "requested_at": datetime.utcnow()
    }
    result = await db.registrations.insert_one(doc)
    return str(result.inserted_id)


async def get_registration_by_id(registration_id: str) -> Optional[Dict]:
    """
    Fetch a single registration document by its ObjectId string.
    """
    try:
        oid = ObjectId(registration_id)
    except:
        return None
    doc = await db.registrations.find_one({"_id": oid})
    return _oid_str(doc) if doc else None


async def approve_registration(registration_id: str) -> None:
    """
    Mark a registration as approved (add 'approved_at' timestamp).
    """
    await db.registrations.update_one(
        {"_id": ObjectId(registration_id)},
        {"$set": {"approved": True, "approved_at": datetime.utcnow()}}
    )


async def remove_registration(registration_id: str) -> None:
    """
    Delete a registration document when it’s rejected or withdrawn.
    """
    await db.registrations.delete_one({"_id": ObjectId(registration_id)}) 


async def get_team_registrations(team_id: str) -> List[Dict]:
    """
    Return all registration documents belonging to a given team.
    """
    cursor = db.registrations.find({"team_id": ObjectId(team_id)})
    results = []
    async for doc in cursor:
        results.append(_oid_str(doc))
    return results


# ────────────────────────────────────────────────────────────────────────────────
# 6. Matches
#
#    • insert_match
#    • get_match
#    • get_matches_by_tourney
#    • update_match_result
#    • update_match_vcs
#    • delete_match
# ────────────────────────────────────────────────────────────────────────────────

async def insert_match(
    tourney_id: str,
    round_number: int,
    bracket_slot_index: int,
    team_a_id: Optional[str],
    team_b_id: Optional[str],
    scheduled_time: Optional[datetime]   = None,
    service_match_id: Optional[int]      = None
) -> str:
    """
    Insert a new match document under a specific tournament.
    Fields:
      - tourney_id (ObjectId), round_number, bracket_slot_index
      - team_a_id, team_b_id, scheduled_time
      - scores (0), result ("pending"), service_match_id
      - vc_a_id, vc_b_id, vc_spec_id (initially None)
      - created_at timestamp
    """
    doc = {
        "tourney_id":         ObjectId(tourney_id),
        "round_number":       round_number,
        "bracket_slot_index": bracket_slot_index,
        "team_a_id":          ObjectId(team_a_id) if team_a_id else None,
        "team_b_id":          ObjectId(team_b_id) if team_b_id else None,
        "scheduled_time":     scheduled_time,
        "team_a_score":       0,
        "team_b_score":       0,
        "result":             "pending",
        "service_match_id":   service_match_id,
        "vc_a_id":            None,
        "vc_b_id":            None,
        "vc_spec_id":         None,
        "created_at":         datetime.utcnow()
    }
    result = await db.matches.insert_one(doc)
    return str(result.inserted_id)


async def get_match(match_id: str) -> Optional[Dict]:
    """
    Fetch a single match document by its ObjectId string.
    """
    try:
        oid = ObjectId(match_id)
    except:
        return None
    doc = await db.matches.find_one({"_id": oid})
    return _oid_str(doc) if doc else None


async def get_matches_by_tourney(tourney_id: str) -> List[Dict]:
    """
    Return all match documents for a given tournament, sorted by (round_number, bracket_slot_index).
    """
    cursor = db.matches.find({"tourney_id": ObjectId(tourney_id)}).sort([
        ("round_number", 1),
        ("bracket_slot_index", 1)
    ])
    results = []
    async for doc in cursor:
        results.append(_oid_str(doc))
    return results


async def update_match_result(
    match_id: str,
    team_a_score: int,
    team_b_score: int,
    result: str,
    service_match_id: Optional[int] = None
) -> Optional[Dict]:
    """
    Update scores and result for a specific match. Optionally set service_match_id.
    Returns the updated match document.
    """
    update_fields = {
        "team_a_score": team_a_score,
        "team_b_score": team_b_score,
        "result": result,
        "updated_at": datetime.utcnow()
    }
    if service_match_id is not None:
        update_fields["service_match_id"] = service_match_id

    await db.matches.update_one(
        {"_id": ObjectId(match_id)},
        {"$set": update_fields}
    )
    return await get_match(match_id)


async def update_match_vcs(match_id: str, vc_a_id: int, vc_b_id: int, vc_spec_id: int) -> None:
    """
    Store the voice channel IDs for a match (team A VC, team B VC, spectate VC).
    """
    await db.matches.update_one(
        {"_id": ObjectId(match_id)},
        {"$set": {
            "vc_a_id": vc_a_id,
            "vc_b_id": vc_b_id,
            "vc_spec_id": vc_spec_id
        }}
    )


async def delete_match(match_id: str) -> None:
    """
    Delete a match document by its ObjectId string.
    """
    await db.matches.delete_one({"_id": ObjectId(match_id)})

