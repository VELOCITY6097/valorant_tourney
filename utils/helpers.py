 # utils/helpers.py

import secrets
import string
from datetime import datetime
import pytz
import discord

def generate_key(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def get_current_time_str(timezone: str = "Asia/Kolkata") -> str:
    tz = pytz.timezone(timezone)
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z")


async def format_bracket_embed(tourney: dict, matches: list[dict]) -> discord.Embed:
    """
    Build a live bracket embed from match documents.
    tourney: the tournament dict
    matches: list of match dicts (with team_a_id, team_b_id, team_a_score, etc.)
    """
    embed = discord.Embed(
        title=f"📊 {tourney['name']} Bracket",
        description=(
            f"Mode: `{tourney['mode']}`  •  Sponsor: `{tourney['sponsor_name']}`\n"
            f"Updated on {get_current_time_str(tourney['timezone'])}"
        ),
        color=discord.Color.purple()
    )
    # Group by round
    rounds = {}
    for m in matches:
        rnd = m["round_number"]
        rounds.setdefault(rnd, []).append(m)

    for round_number, match_list in sorted(rounds.items(), key=lambda x: x[0]):
        lines = []
        match_list.sort(key=lambda x: x["bracket_slot_index"])
        for m in match_list:
            # You’d look up team names by ID in DB; placeholder here:
            team_a = m.get("team_a_name", "TBD")
            team_b = m.get("team_b_name", "TBD")
            if m["result"] == "pending":
                line = f"• Slot {m['bracket_slot_index']}: `{team_a}` vs `{team_b}`"
            else:
                if m["result"] == "team_a_win":
                    line = f"• Slot {m['bracket_slot_index']}: **✅ {team_a} ({m['team_a_score']})** vs ❌ {team_b} ({m['team_b_score']})"
                elif m["result"] == "team_b_win":
                    line = f"• Slot {m['bracket_slot_index']}: ❌ {team_a} ({m['team_a_score']}) vs **✅ {team_b} ({m['team_b_score']})**"
                else:
                    line = f"• Slot {m['bracket_slot_index']}: ⚖️ `{team_a} ({m['team_a_score']})` vs `{team_b} ({m['team_b_score']})`"
            lines.append(line)

        embed.add_field(
            name=f"🏅 Round {round_number}",
            value="\n".join(lines) or "Waiting for seeds...",
            inline=False
        )

    return embed
