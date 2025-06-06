 # utils/bracket_api.py

import os
import aiohttp

BRACKET_API_KEY = os.getenv("BRACKET_API_KEY")
BRACKET_API_USERNAME = os.getenv("BRACKET_API_USERNAME")
BRACKET_BASE_URL = os.getenv("BRACKET_BASE_URL", "https://api.challonge.com/v1")


async def create_bracket_on_service(tourney_name: str, team_list: list[str], tournament_type: str = "single elimination") -> str:
    """
    Create a new bracket on an external service (e.g., Challonge).
    Returns the public PNG URL (e.g., https://challonge.com/your-tourney.png).
    """
    auth = aiohttp.BasicAuth(login=BRACKET_API_USERNAME, password=BRACKET_API_KEY)
    create_url = f"{BRACKET_BASE_URL}/tournaments.json"
    payload = {
        "tournament[name]": tourney_name,
        "tournament[tournament_type]": tournament_type,
        "tournament[private]": False
    }

    async with aiohttp.ClientSession(auth=auth) as session:
        async with session.post(create_url, data=payload) as resp:
            data = await resp.json()
            tournament_id = data["tournament"]["id"]
            # Add participants
            for team in team_list:
                participant_url = f"{BRACKET_BASE_URL}/tournaments/{tournament_id}/participants.json"
                part_payload = {"participant[name]": team}
                async with session.post(participant_url, data=part_payload) as _:
                    pass
            # Start the bracket
            start_url = f"{BRACKET_BASE_URL}/tournaments/{tournament_id}/start.json"
            async with session.post(start_url):
                pass
            view_url = data["tournament"]["full_challonge_url"]
            return view_url + ".png"


async def update_bracket_match(tourney_name: str, match_id: int, score_a: int, score_b: int) -> str:
    """
    Update a specific match’s score on the external service, then return
    the new public bracket PNG URL.
    """
    auth = aiohttp.BasicAuth(login=BRACKET_API_USERNAME, password=BRACKET_API_KEY)
    # In practice, you’d fetch service_tourney_id from your DB using tourney_name.
    service_tourney_id = tourney_name  # placeholder
    update_url = f"{BRACKET_BASE_URL}/tournaments/{service_tourney_id}/matches/{match_id}.json"
    payload = {"match[scores_csv]": f"{score_a}-{score_b}"}
    async with aiohttp.ClientSession(auth=auth) as session:
        async with session.put(update_url, data=payload):
            pass
    return f"https://challonge.com/{service_tourney_id}.png"
