#!/usr/bin/env python3
"""Build data/snapshot.json from the public MLB Stats API and Guardians RSS."""

from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://statsapi.mlb.com/api/v1"
RSS_URL = "https://www.mlb.com/guardians/feeds/news/rss.xml"
TEAM_ID = 114
HEADSHOT = (
    "https://img.mlbstatic.com/mlb-photos/image/upload/"
    "w_256,q_auto:best/v1/people/{player_id}/headshot/67/current"
)
NY = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "snapshot.json"

MIN_HITTER_PA = 150
MIN_STARTER_OUTS = 40 * 3
MIN_RELIEVER_OUTS = 15 * 3
MAX_RELIEVER_STARTS = 4
POSTSEASON_TYPES = ("F", "D", "L", "W")
SKIP_DETAILS = ("Postponed", "Cancelled")
PROMO = re.compile(
    r"trivia|daily walk-?off|subscription|presented by|\bstream\b.*(?:\$|games for)",
    re.IGNORECASE,
)
DC = {"dc": "http://purl.org/dc/elements/1.1/"}
GAME_LABELS = {
    "F": "Wild Card",
    "D": "Division Series",
    "L": "Championship Series",
    "W": "World Series",
}


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "guardians-tracker/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def fetch_json(url: str) -> dict:
    return json.loads(fetch_bytes(url).decode())


def innings_to_outs(value) -> int:
    """MLB writes innings as whole.thirds, so 183.1 is 183 and one out."""
    if value is None or value == "":
        return 0
    text = str(value).strip()
    if text in {"-.--", ".---"}:
        return 0
    if "." not in text:
        return int(float(text)) * 3
    whole, fraction = text.split(".", 1)
    thirds = int(fraction[0]) if fraction and fraction[0].isdigit() else 0
    return int(whole or "0") * 3 + thirds


def as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def blank(value) -> bool:
    return value is None or str(value).strip() in {"", "-", "—"}


def eliminated(value) -> bool:
    return str(value).strip().upper() == "E"


def games_back_value(value):
    if blank(value) or eliminated(value):
        return None
    text = str(value).strip().replace("−", "-")
    if text[0] in "+-":
        text = text[1:]
    return as_float(text)


def format_games_back(value) -> str:
    if blank(value):
        return "—"
    if eliminated(value):
        return "E"
    text = str(value).strip().replace("−", "-")
    sign = ""
    if text[0] in "+-":
        sign = text[0]
        text = text[1:]
    number = as_float(text)
    if number is None:
        return str(value)
    body = str(int(number)) if number.is_integer() else f"{number:.1f}"
    return f"{sign}{body}"


def games_back_words(value) -> str:
    number = games_back_value(value)
    if number is None:
        return "—"
    number = abs(number)
    if number == 0.5:
        return "a half-game"
    if number == 1:
        return "1 game"
    if number.is_integer():
        return f"{int(number)} games"
    return f"{number:.1f} games"


def magic_text(value):
    if blank(value) or eliminated(value):
        return None
    number = as_float(str(value).strip())
    if number is None or number < 0:
        return None
    return str(int(number)) if number.is_integer() else f"{number:.1f}"


def format_elim(value) -> str:
    if blank(value):
        return "—"
    if eliminated(value):
        return "E"
    return magic_text(value) or str(value)


def back_phrase(value) -> str:
    words = games_back_words(value)
    if words == "a half-game":
        return "A half-game back."
    return f"{words} back."


def record_line(wins, losses) -> str:
    return f"{wins}–{losses}."


def race_copy(
    *,
    season_state,
    wins,
    losses,
    division_champ,
    division_rank,
    tied,
    magic_number,
    games_back,
    elimination_number,
    wildcard_elimination_number,
    wildcard_games_back,
    clinched,
    rival_club,
    rival_games_back,
) -> dict:
    magic = magic_text(magic_number)
    out = eliminated(elimination_number) and eliminated(wildcard_elimination_number)
    leading = division_rank == 1 and not tied

    if season_state == "complete":
        hero = record_line(wins, losses)
        figure, figure_label = f"{wins}–{losses}", "Final record"
    elif division_champ:
        hero = "Central champions."
        figure, figure_label = f"{wins}–{losses}", "Clinched"
    elif out:
        hero = "Eliminated."
        figure, figure_label = "E", "Eliminated"
    elif leading and magic:
        hero = f"Magic number {magic}."
        figure, figure_label = magic, "Magic number"
    elif leading:
        hero = "First in the Central."
        figure, figure_label = "1st", "AL Central"
    elif tied:
        hero = "Tied atop the Central."
        figure, figure_label = "T1", "AL Central"
    else:
        hero = back_phrase(games_back)
        figure, figure_label = format_games_back(games_back).lstrip("+"), "Games back"

    rival = rival_club or "the field"
    if division_champ:
        summary = "The Guardians have clinched the AL Central."
        division_fact = "Clinched"
    elif out:
        summary = "The Guardians are eliminated from the postseason."
        division_fact = "Eliminated"
    elif season_state == "complete" and division_rank == 1 and not tied:
        summary = "The Guardians finished first in the AL Central."
        division_fact = "Finished first"
    elif leading:
        margin = games_back_words(rival_games_back)
        summary = f"The Guardians lead the AL Central by {margin} over the {rival}."
        division_fact = f"Up {margin} on the {rival}"
    elif tied:
        summary = f"The Guardians are tied atop the AL Central with the {rival}."
        division_fact = f"Tied with the {rival}"
    else:
        summary = (
            f"The Guardians are {games_back_words(games_back)} behind the {rival} in the AL Central."
        )
        division_fact = f"{games_back_words(games_back)} behind the {rival}"
        if not eliminated(wildcard_elimination_number):
            if blank(wildcard_games_back):
                summary += " They lead the wild card."
            else:
                summary += f" They are {games_back_words(wildcard_games_back)} out of the wild card."

    if out or eliminated(wildcard_elimination_number):
        wildcard_fact = "Eliminated"
    elif clinched and not division_champ:
        wildcard_fact = "Wild card clinched"
    elif division_champ or leading:
        wildcard_fact = "Ahead of the wild card"
    elif blank(wildcard_games_back):
        wildcard_fact = "Leading the wild card"
    else:
        wildcard_fact = f"{games_back_words(wildcard_games_back)} back"

    return {
        "heroLine": hero,
        "figure": figure,
        "figureLabel": figure_label,
        "summary": summary,
        "divisionFact": division_fact,
        "wildCardFact": wildcard_fact,
    }


def split_line(team_record: dict, kind: str) -> str:
    for row in (team_record.get("records") or {}).get("splitRecords") or []:
        if row.get("type") == kind:
            return f"{row.get('wins', 0)}–{row.get('losses', 0)}"
    return "—"


def division_rows(standings: dict) -> tuple[dict, list[dict]]:
    chosen = None
    for record in standings.get("records") or []:
        name = ((record.get("division") or {}).get("name")) or ""
        if "American League Central" in name:
            chosen = record
            break
    if chosen is None:
        raise LookupError("AL Central standings were not in the MLB response")
    rows = []
    for team_record in chosen.get("teamRecords") or []:
        team = team_record["team"]
        rows.append(
            {
                "id": team["id"],
                "club": team.get("teamName") or team.get("name"),
                "name": team.get("name"),
                "abbreviation": team.get("abbreviation") or "",
                "wins": as_int(team_record.get("wins")),
                "losses": as_int(team_record.get("losses")),
                "pct": str(team_record.get("winningPercentage") or "—"),
                "gamesBack": format_games_back(team_record.get("gamesBack")),
                "gamesBackRaw": team_record.get("gamesBack"),
                "wildCardGamesBackRaw": team_record.get("wildCardGamesBack"),
                "rank": as_int(team_record.get("divisionRank")),
                "streak": ((team_record.get("streak") or {}).get("streakCode")) or "",
                "runsScored": as_int(team_record.get("runsScored")),
                "runsAllowed": as_int(team_record.get("runsAllowed")),
                "runDifferential": as_int(team_record.get("runDifferential")),
                "lastTen": split_line(team_record, "lastTen"),
                "home": split_line(team_record, "home"),
                "road": split_line(team_record, "away"),
                "magicNumber": team_record.get("magicNumber"),
                "eliminationNumber": team_record.get("eliminationNumber"),
                "wildCardEliminationNumber": team_record.get("wildCardEliminationNumber"),
                "clinched": bool(team_record.get("clinched")),
                "divisionChamp": bool(team_record.get("divisionChamp")),
                "divisionLeader": bool(team_record.get("divisionLeader")),
                "isGuardians": team["id"] == TEAM_ID,
            }
        )
    rows.sort(key=lambda row: (row["rank"], row["club"]))
    meta = {
        "division": (chosen.get("division") or {}).get("name") or "American League Central",
        "league": (chosen.get("league") or {}).get("name") or "American League",
    }
    return meta, rows


def public_division_row(row: dict) -> dict:
    keys = (
        "rank",
        "club",
        "abbreviation",
        "wins",
        "losses",
        "pct",
        "gamesBack",
        "runsScored",
        "runsAllowed",
        "runDifferential",
        "streak",
        "lastTen",
        "home",
        "road",
        "clinched",
        "isGuardians",
    )
    return {key: row[key] for key in keys}


def wildcard_rows(payload: dict) -> list[dict]:
    records = payload.get("records") or []
    team_records = records[0].get("teamRecords") if records else []
    rows = []
    for team_record in team_records or []:
        team = team_record["team"]
        rows.append(
            {
                "rank": as_int(team_record.get("wildCardRank")),
                "club": team.get("teamName") or team.get("name"),
                "abbreviation": team.get("abbreviation") or "",
                "wins": as_int(team_record.get("wins")),
                "losses": as_int(team_record.get("losses")),
                "gamesBack": format_games_back(team_record.get("wildCardGamesBack")),
                "elimination": format_elim(team_record.get("wildCardEliminationNumber")),
                "clinched": bool(team_record.get("clinched")),
                "isGuardians": team["id"] == TEAM_ID,
                "eliminated": eliminated(team_record.get("wildCardEliminationNumber")),
            }
        )
    rows.sort(key=lambda row: (row["rank"] or 99, row["club"]))
    kept = []
    for row in rows:
        if len(kept) >= 8:
            break
        public = {key: row[key] for key in row if key != "eliminated"}
        kept.append(public)
        if row["eliminated"]:
            break
    return kept


def headshot(player_id: int) -> str:
    return HEADSHOT.format(player_id=player_id)


def hitter_row(split: dict) -> dict:
    stat = split.get("stat") or {}
    player = split["player"]
    position = (split.get("position") or {}).get("abbreviation") or ""
    return {
        "id": player["id"],
        "name": player.get("fullName") or "",
        "position": position,
        "avg": stat.get("avg"),
        "obp": stat.get("obp"),
        "slg": stat.get("slg"),
        "ops": stat.get("ops"),
        "hr": as_int(stat.get("homeRuns")),
        "rbi": as_int(stat.get("rbi")),
        "sb": as_int(stat.get("stolenBases")),
        "pa": as_int(stat.get("plateAppearances")),
        "games": as_int(stat.get("gamesPlayed")),
        "headshot": headshot(player["id"]),
    }


def pitcher_row(split: dict, role: str) -> dict:
    stat = split.get("stat") or {}
    player = split["player"]
    return {
        "id": player["id"],
        "name": player.get("fullName") or "",
        "role": role,
        "era": stat.get("era"),
        "whip": stat.get("whip"),
        "ip": stat.get("inningsPitched"),
        "so": as_int(stat.get("strikeOuts")),
        "bb": as_int(stat.get("baseOnBalls")),
        "w": as_int(stat.get("wins")),
        "l": as_int(stat.get("losses")),
        "sv": as_int(stat.get("saves")),
        "games": as_int(stat.get("gamesPlayed")),
        "starts": as_int(stat.get("gamesStarted")),
        "outs": innings_to_outs(stat.get("inningsPitched")),
        "headshot": headshot(player["id"]),
    }


def dedupe(rows: list[dict], amount_key: str) -> list[dict]:
    best: dict[int, dict] = {}
    for row in rows:
        current = best.get(row["id"])
        if current is None or row[amount_key] > current[amount_key]:
            best[row["id"]] = row
    return list(best.values())


def qualified_hitters(splits: list[dict]) -> list[dict]:
    rows = []
    for split in splits:
        row = hitter_row(split)
        if row["pa"] >= MIN_HITTER_PA and as_float(row["ops"]) is not None:
            rows.append(row)
    rows = dedupe(rows, "pa")
    rows.sort(key=lambda row: (-(as_float(row["ops"]) or -1), row["name"]))
    return rows


def classified_pitchers(splits: list[dict]) -> tuple[list[dict], list[dict]]:
    starters = []
    relievers = []
    for split in splits:
        starts = as_int((split.get("stat") or {}).get("gamesStarted"))
        outs = innings_to_outs((split.get("stat") or {}).get("inningsPitched"))
        if outs >= MIN_STARTER_OUTS and starts > MAX_RELIEVER_STARTS:
            row = pitcher_row(split, "SP")
            role_list = starters
        elif outs >= MIN_RELIEVER_OUTS and starts <= MAX_RELIEVER_STARTS:
            row = pitcher_row(split, "RP")
            role_list = relievers
        else:
            continue
        if as_float(row["era"]) is None:
            continue
        role_list.append(row)
    starters = dedupe(starters, "outs")
    relievers = dedupe(relievers, "outs")
    starters.sort(key=lambda row: (as_float(row["era"]), row["name"]))
    relievers.sort(key=lambda row: (-row["sv"], as_float(row["era"]), row["name"]))
    return starters, relievers


def stat_leader(rows: list[dict], field: str, *, higher: bool = True, require_positive: bool = False):
    usable = [row for row in rows if as_float(row.get(field)) is not None]
    if not usable:
        return None
    chosen = max(usable, key=lambda row: as_float(row[field])) if higher else min(usable, key=lambda row: as_float(row[field]))
    if require_positive and as_float(chosen[field]) <= 0:
        return None
    value = chosen[field]
    return {
        "id": chosen["id"],
        "name": chosen["name"],
        "position": chosen.get("position") or chosen.get("role") or "",
        "value": value,
        "headshot": chosen["headshot"],
    }


def public_pitcher(row: dict) -> dict:
    return {key: value for key, value in row.items() if key != "outs"}


def player_block(hitting_splits: list[dict], pitching_splits: list[dict]) -> dict:
    hitters = qualified_hitters(hitting_splits)
    starters, relievers = classified_pitchers(pitching_splits)
    strikeout_pool = starters + relievers
    featured_pitcher = starters[0] if starters else (relievers[0] if relievers else None)
    return {
        "hitters": hitters[:5],
        "starters": [public_pitcher(row) for row in starters[:5]],
        "relievers": [public_pitcher(row) for row in relievers[:5]],
        "featured": {
            "hitter": hitters[0] if hitters else None,
            "pitcher": public_pitcher(featured_pitcher) if featured_pitcher else None,
            "pitcherStat": "era" if starters else "saves",
        },
        "leaders": {
            "avg": stat_leader(hitters, "avg"),
            "hr": stat_leader(hitters, "hr"),
            "rbi": stat_leader(hitters, "rbi"),
            "sb": stat_leader(hitters, "sb"),
            "ops": stat_leader(hitters, "ops"),
            "era": stat_leader(starters, "era", higher=False),
            "so": stat_leader(strikeout_pool, "so"),
            "wins": stat_leader(starters or relievers, "w"),
            "saves": stat_leader(relievers or starters, "sv", require_positive=True),
        },
    }


def skipped_game(game: dict) -> bool:
    detailed = ((game.get("status") or {}).get("detailedState")) or ""
    return detailed.startswith(SKIP_DETAILS)


def our_side(game: dict):
    teams = game.get("teams") or {}
    away = teams.get("away") or {}
    home = teams.get("home") or {}
    if (away.get("team") or {}).get("id") == TEAM_ID:
        return away, home, False
    if (home.get("team") or {}).get("id") == TEAM_ID:
        return home, away, True
    return None


def club_name(team: dict) -> str:
    return team.get("teamName") or team.get("clubName") or team.get("name") or "Opponent"


def schedule_row(game: dict) -> dict | None:
    sides = our_side(game)
    if sides is None:
        return None
    us, them, is_home = sides
    opponent = them.get("team") or {}
    status = game.get("status") or {}
    abstract = status.get("abstractGameState") or ""
    our_runs = us.get("score")
    their_runs = them.get("score")
    decisions = game.get("decisions") or {}
    result = None
    if abstract == "Final":
        if us.get("isWinner"):
            result = "W"
        elif them.get("isWinner"):
            result = "L"
        elif us.get("isWinner") is False and them.get("isWinner") is False:
            result = "T"
    score = None
    if our_runs is not None and their_runs is not None:
        score = f"{as_int(our_runs)}–{as_int(their_runs)}"
    game_type = game.get("gameType") or "R"
    return {
        "date": game.get("officialDate") or "",
        "startTime": game.get("gameDate"),
        "startTimeTBD": bool(status.get("startTimeTBD")),
        "gameNumber": as_int(game.get("gameNumber"), 1),
        "gameType": game_type,
        "series": GAME_LABELS.get(game_type, ""),
        "opponent": club_name(opponent),
        "abbreviation": opponent.get("abbreviation") or "",
        "home": is_home,
        "status": abstract,
        "detail": status.get("detailedState") or "",
        "result": result,
        "score": score,
        "venue": (game.get("venue") or {}).get("name") or "",
        "probable": ((us.get("probablePitcher") or {}).get("fullName")) or "",
        "opponentProbable": ((them.get("probablePitcher") or {}).get("fullName")) or "",
        "winner": ((decisions.get("winner") or {}).get("fullName")) or "",
        "loser": ((decisions.get("loser") or {}).get("fullName")) or "",
        "save": ((decisions.get("save") or {}).get("fullName")) or "",
    }


def game_key(game: dict) -> tuple:
    return (game.get("gameDate") or game.get("officialDate") or "", as_int(game.get("gameNumber"), 1))


def classify_games(games: list[dict], limit: int = 8) -> dict:
    recent = []
    upcoming = []
    remaining = 0
    for game in games:
        game_type = game.get("gameType") or ""
        if game_type not in {"R", *POSTSEASON_TYPES}:
            continue
        if skipped_game(game):
            continue
        if our_side(game) is None:
            continue
        abstract = ((game.get("status") or {}).get("abstractGameState")) or ""
        if game_type == "R" and abstract != "Final":
            remaining += 1
        row = schedule_row(game)
        if row is None:
            continue
        if abstract == "Final":
            recent.append(row)
        else:
            upcoming.append(row)
    recent.sort(key=lambda row: (row["startTime"] or row["date"], row["gameNumber"]), reverse=True)
    upcoming.sort(key=lambda row: (row["startTime"] or row["date"], row["gameNumber"]))
    return {
        "recent": recent[:limit],
        "upcoming": upcoming[:limit],
        "gamesRemaining": remaining,
    }


def season_series(games: list[dict], opponents: list[dict]) -> list[dict]:
    tally = {
        opponent["id"]: {
            "club": opponent["club"],
            "abbreviation": opponent["abbreviation"],
            "wins": 0,
            "losses": 0,
        }
        for opponent in opponents
    }
    for game in games:
        if game.get("gameType") != "R":
            continue
        if ((game.get("status") or {}).get("abstractGameState")) != "Final":
            continue
        sides = our_side(game)
        if sides is None:
            continue
        us, them, _is_home = sides
        opponent_id = (them.get("team") or {}).get("id")
        if opponent_id not in tally:
            continue
        if us.get("isWinner"):
            tally[opponent_id]["wins"] += 1
        elif them.get("isWinner"):
            tally[opponent_id]["losses"] += 1
    return [tally[opponent["id"]] for opponent in opponents]


def is_promo(item: dict) -> bool:
    url = item.get("url") or ""
    title = item.get("title") or ""
    if "/app/atbat/" in url:
        return True
    return bool(PROMO.search(title) or PROMO.search(url))


def parse_rss(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.findall("./channel/item"):
        image = item.find("image")
        if image is None:
            image = item.find("{https://www.mlb.com/rss/}image")
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "url": (item.findtext("link") or "").strip(),
                "published": (item.findtext("pubDate") or "").strip(),
                "author": (item.findtext("dc:creator", default="", namespaces=DC) or "").strip(),
                "image": image.get("href") if image is not None else None,
            }
        )
    return items


def select_headlines(items: list[dict], limit: int = 6) -> list[dict]:
    kept = []
    for item in items:
        if not item.get("title") or not item.get("url") or is_promo(item):
            continue
        kept.append(
            {
                "title": item["title"],
                "url": item["url"],
                "published": item.get("published") or "",
                "author": item.get("author") or "",
                "image": item.get("image"),
                "source": "MLB.com",
            }
        )
        if len(kept) >= limit:
            break
    return kept


def needs_previous_season(today: date, season: dict) -> bool:
    start = date.fromisoformat(season["regularSeasonStartDate"])
    return today < start


def season_state_for(today: date, season: dict) -> str:
    end = date.fromisoformat(season["regularSeasonEndDate"])
    if today > end:
        return "complete"
    return "inProgress"


def wants_postseason(today: date, season: dict) -> bool:
    start = date.fromisoformat(season["postSeasonStartDate"])
    end = date.fromisoformat(season["postSeasonEndDate"])
    return start <= today <= end


def rival_for(rows: list[dict], guardians: dict, tied: bool):
    others = [row for row in rows if not row["isGuardians"]]
    if guardians["rank"] == 1 and not tied:
        rival = others[0] if others else None
        back = rival["gamesBackRaw"] if rival else None
    elif tied:
        rival = next((row for row in others if row["rank"] == guardians["rank"]), others[0] if others else None)
        back = None
    else:
        rival = rows[0] if rows and not rows[0]["isGuardians"] else (others[0] if others else None)
        back = guardians["gamesBackRaw"]
    return rival, back


def is_tied(rows: list[dict], guardians: dict) -> bool:
    if guardians["rank"] != 1:
        return False
    leaders = [row for row in rows if row["rank"] == 1]
    if len(leaders) > 1:
        return True
    return games_back_value(guardians["gamesBackRaw"]) == 0


def assemble(
    *,
    season_year: int,
    season_state: str,
    standings: dict,
    wildcard: dict,
    games: list[dict],
    hitting_splits: list[dict],
    pitching_splits: list[dict],
    headlines: list[dict],
    generated_at: str,
) -> dict:
    meta, rows = division_rows(standings)
    guardians = next(row for row in rows if row["isGuardians"])
    tied = is_tied(rows, guardians)
    rival, rival_back = rival_for(rows, guardians, tied)
    copy = race_copy(
        season_state=season_state,
        wins=guardians["wins"],
        losses=guardians["losses"],
        division_champ=guardians["divisionChamp"],
        division_rank=guardians["rank"],
        tied=tied,
        magic_number=guardians["magicNumber"],
        games_back=guardians["gamesBackRaw"],
        elimination_number=guardians["eliminationNumber"],
        wildcard_elimination_number=guardians["wildCardEliminationNumber"],
        wildcard_games_back=guardians["wildCardGamesBackRaw"],
        clinched=guardians["clinched"],
        rival_club=(rival or {}).get("club"),
        rival_games_back=rival["gamesBackRaw"] if rival and guardians["rank"] == 1 and not tied else rival_back,
    )
    schedule = classify_games(games)
    opponents = [row for row in rows if not row["isGuardians"]]
    return {
        "generatedAt": generated_at,
        "season": season_year,
        "seasonState": season_state,
        "heroLine": copy["heroLine"],
        "team": {
            "id": TEAM_ID,
            "name": guardians["name"],
            "club": guardians["club"],
            "abbreviation": guardians["abbreviation"],
            "division": meta["division"],
            "league": meta["league"],
        },
        "record": {
            "wins": guardians["wins"],
            "losses": guardians["losses"],
            "pct": guardians["pct"],
            "divisionRank": guardians["rank"],
            "gamesBack": guardians["gamesBack"],
            "streak": guardians["streak"],
            "runDifferential": guardians["runDifferential"],
            "runsScored": guardians["runsScored"],
            "runsAllowed": guardians["runsAllowed"],
            "magicNumber": magic_text(guardians["magicNumber"]),
            "eliminationNumber": format_elim(guardians["eliminationNumber"]),
            "wildCardEliminationNumber": format_elim(guardians["wildCardEliminationNumber"]),
            "clinched": guardians["clinched"],
            "divisionChamp": guardians["divisionChamp"],
            "lastTen": guardians["lastTen"],
            "home": guardians["home"],
            "road": guardians["road"],
        },
        "playoff": {
            "headline": copy["heroLine"],
            "figure": copy["figure"],
            "figureLabel": copy["figureLabel"],
            "summary": copy["summary"],
            "divisionFact": copy["divisionFact"],
            "wildCardFact": copy["wildCardFact"],
            "gamesRemaining": schedule["gamesRemaining"],
            "division": [public_division_row(row) for row in rows],
            "wildCard": wildcard_rows(wildcard),
        },
        "division": {
            "name": meta["division"],
            "seasonSeries": season_series(games, opponents),
        },
        "players": player_block(hitting_splits, pitching_splits),
        "schedule": {"recent": schedule["recent"], "upcoming": schedule["upcoming"]},
        "headlines": select_headlines(headlines),
    }


def substantive(snapshot: dict) -> dict:
    return {key: value for key, value in snapshot.items() if key != "generatedAt"}


def same_content(previous: dict | None, current: dict) -> bool:
    if previous is None:
        return False
    return substantive(previous) == substantive(current)


def flatten_schedule(payload: dict) -> list[dict]:
    games = []
    for day in payload.get("dates") or []:
        games.extend(day.get("games") or [])
    return games


def load_season(today: date) -> tuple[int, str, dict]:
    payload = fetch_json(f"{API}/seasons?sportId=1")
    season = payload["seasons"][0]
    if needs_previous_season(today, season):
        year = int(season["seasonId"]) - 1
        payload = fetch_json(f"{API}/seasons?sportId=1&season={year}")
        season = payload["seasons"][0]
    year = int(season["seasonId"])
    return year, season_state_for(today, season), season


def stats_url(group: str, year: int) -> str:
    return (
        f"{API}/stats?stats=season&group={group}&season={year}&sportIds=1"
        f"&teamId={TEAM_ID}&playerPool=ALL&gameType=R&limit=200"
    )


def schedule_url(year: int, game_type: str) -> str:
    return (
        f"{API}/schedule?sportId=1&teamId={TEAM_ID}&season={year}"
        f"&gameType={game_type}&hydrate=team,decisions,probablePitcher"
    )


def collect(today: date | None = None) -> dict:
    today = today or datetime.now(NY).date()
    year, state, season = load_season(today)
    standings = fetch_json(
        f"{API}/standings?leagueId=103&season={year}&standingsTypes=regularSeason&hydrate=team,division,league"
    )
    wildcard = fetch_json(
        f"{API}/standings?leagueId=103&season={year}&standingsTypes=wildCard&hydrate=team"
    )
    games = flatten_schedule(fetch_json(schedule_url(year, "R")))
    if wants_postseason(today, season):
        for game_type in POSTSEASON_TYPES:
            games.extend(flatten_schedule(fetch_json(schedule_url(year, game_type))))
    hitting = fetch_json(stats_url("hitting", year))
    pitching = fetch_json(stats_url("pitching", year))
    hitting_splits = ((hitting.get("stats") or [{}])[0].get("splits")) or []
    pitching_splits = ((pitching.get("stats") or [{}])[0].get("splits")) or []
    headlines = parse_rss(fetch_bytes(RSS_URL))
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return assemble(
        season_year=year,
        season_state=state,
        standings=standings,
        wildcard=wildcard,
        games=games,
        hitting_splits=hitting_splits,
        pitching_splits=pitching_splits,
        headlines=headlines,
        generated_at=generated_at,
    )


def main() -> int:
    fresh = collect()
    previous = None
    if SNAPSHOT.exists():
        previous = json.loads(SNAPSHOT.read_text())
    if same_content(previous, fresh):
        print("unchanged")
        return 0
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(fresh, indent=2, sort_keys=True) + "\n")
    print("updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
