#!/usr/bin/env python3
"""Fixture tests for the snapshot builder. No network."""

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fetch", ROOT / "scripts" / "fetch.py")
fetch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch)


def hitter(name, player_id, pa, ops, hr=0, rbi=0, sb=0, avg=".250"):
    return {
        "player": {"id": player_id, "fullName": name},
        "position": {"abbreviation": "RF"},
        "stat": {
            "plateAppearances": pa,
            "ops": ops,
            "avg": avg,
            "obp": ".320",
            "slg": ".450",
            "homeRuns": hr,
            "rbi": rbi,
            "stolenBases": sb,
            "gamesPlayed": 100,
        },
    }


def pitcher(name, player_id, ip, era, starts, saves=0, strikeouts=0, wins=0):
    return {
        "player": {"id": player_id, "fullName": name},
        "position": {"abbreviation": "P"},
        "stat": {
            "inningsPitched": ip,
            "era": era,
            "gamesStarted": starts,
            "saves": saves,
            "strikeOuts": strikeouts,
            "wins": wins,
            "losses": 1,
            "whip": "1.10",
            "baseOnBalls": 10,
            "gamesPlayed": 20,
        },
    }


def team_record(team_id, club, wins, losses, rank, gb, magic="-", elim="-", wc_elim="-", wc_gb="-"):
    return {
        "team": {
            "id": team_id,
            "name": f"City {club}",
            "teamName": club,
            "abbreviation": club[:3].upper(),
        },
        "wins": wins,
        "losses": losses,
        "winningPercentage": ".500",
        "gamesBack": gb,
        "wildCardGamesBack": wc_gb,
        "divisionRank": str(rank),
        "streak": {"streakCode": "W1"},
        "runsScored": 100,
        "runsAllowed": 90,
        "runDifferential": 10,
        "magicNumber": magic,
        "eliminationNumber": elim,
        "wildCardEliminationNumber": wc_elim,
        "clinched": False,
        "divisionChamp": False,
        "divisionLeader": rank == 1,
        "records": {
            "splitRecords": [
                {"type": "home", "wins": 10, "losses": 8},
                {"type": "away", "wins": 8, "losses": 10},
                {"type": "lastTen", "wins": 7, "losses": 3},
            ]
        },
    }


def standings(records):
    return {
        "records": [
            {
                "division": {"name": "American League Central"},
                "league": {"name": "American League"},
                "teamRecords": records,
            }
        ]
    }


def game(opponent_id, home, we_won, state="Final", game_type="R", when="2026-09-01T23:00:00Z", number=1, detail=None):
    us = {
        "team": {"id": 114, "name": "Cleveland Guardians", "teamName": "Guardians", "abbreviation": "CLE"},
        "score": 4 if we_won else 2,
        "isWinner": we_won if state == "Final" else None,
        "probablePitcher": {"fullName": "Our Starter"},
    }
    them = {
        "team": {"id": opponent_id, "name": "Chicago White Sox", "teamName": "White Sox", "abbreviation": "CWS"},
        "score": 2 if we_won else 4,
        "isWinner": (not we_won) if state == "Final" and we_won is not None else None,
        "probablePitcher": {"fullName": "Their Starter"},
    }
    away, home_side = (them, us) if home else (us, them)
    return {
        "gameType": game_type,
        "officialDate": when[:10],
        "gameDate": when,
        "gameNumber": number,
        "status": {
            "abstractGameState": state,
            "detailedState": detail or state,
            "startTimeTBD": False,
        },
        "venue": {"name": "Progressive Field"},
        "teams": {"away": away, "home": home_side},
        "decisions": {
            "winner": {"fullName": "Winner"},
            "loser": {"fullName": "Loser"},
            "save": {"fullName": "Saver"},
        },
    }


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0">
  <channel>
    <item>
      <title><![CDATA[With postseason berth in sight, Guardians fall to Red Sox]]></title>
      <link>https://www.mlb.com/guardians/news/example</link>
      <pubDate>Thu, 24 Sep 2026 02:03:33 GMT</pubDate>
      <dc:creator>Craig Forde</dc:creator>
      <image href="https://img.mlbstatic.com/example.jpg"/>
    </item>
    <item>
      <title>Solve today's Guardians trivia puzzle</title>
      <link>https://www.mlb.com/app/atbat/guardians/daily-walkoff</link>
      <pubDate>Tue, 03 Feb 2026 15:20:14 GMT</pubDate>
    </item>
    <item>
      <title>Stream Guardians games for $19.99</title>
      <link>https://www.mlb.com/guardians/news/cleguardians-tv-2026-season</link>
    </item>
  </channel>
</rss>
"""


class FetchTests(unittest.TestCase):
    def test_promo_filter_keeps_game_stories(self):
        items = fetch.parse_rss(RSS)
        self.assertEqual(items[0]["author"], "Craig Forde")
        self.assertEqual(items[0]["image"], "https://img.mlbstatic.com/example.jpg")
        kept = fetch.select_headlines(items)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["title"], "With postseason berth in sight, Guardians fall to Red Sox")
        self.assertTrue(fetch.is_promo({"title": "A subscription offer", "url": "https://www.mlb.com/x"}))

    def test_hitter_cutoff_and_home_run_leader_outside_ops_list(self):
        splits = [
            hitter("Low Sample", 1, 149, ".999", hr=40),
            hitter("Ops One", 2, 200, ".900", hr=10),
            hitter("Ops Two", 3, 200, ".850", hr=9),
            hitter("Ops Three", 4, 200, ".800", hr=8),
            hitter("Ops Four", 5, 200, ".750", hr=7),
            hitter("Ops Five", 6, 200, ".700", hr=6),
            hitter("Power", 7, 180, ".600", hr=39, avg=".240"),
        ]
        block = fetch.player_block(splits, [])
        names = [row["name"] for row in block["hitters"]]
        self.assertNotIn("Low Sample", names)
        self.assertNotIn("Power", names)
        self.assertEqual(names[0], "Ops One")
        self.assertEqual(block["leaders"]["hr"]["name"], "Power")
        self.assertEqual(block["leaders"]["hr"]["value"], 39)
        self.assertEqual(block["featured"]["hitter"]["name"], "Ops One")

    def test_pitcher_roles_ignore_tiny_samples(self):
        splits = [
            pitcher("Cup Of Coffee", 1, "2.0", "0.00", starts=1, strikeouts=3),
            pitcher("Long Reliever", 2, "39.2", "1.50", starts=10, strikeouts=40),
            pitcher("Ace", 3, "180.0", "2.40", starts=30, strikeouts=200, wins=14),
            pitcher("Innins Forty", 4, "40.0", "3.10", starts=8, strikeouts=50, wins=4),
            pitcher("Closer", 5, "70.1", "1.90", starts=0, saves=40, strikeouts=100, wins=5),
            pitcher("Setup", 6, "15.0", "2.50", starts=4, saves=2, strikeouts=20),
            pitcher("Not Quite", 7, "14.2", "1.00", starts=0, saves=8),
        ]
        starters, relievers = fetch.classified_pitchers(splits)
        self.assertEqual([row["name"] for row in starters], ["Ace", "Innins Forty"])
        self.assertEqual([row["name"] for row in relievers], ["Closer", "Setup"])
        block = fetch.player_block([], splits)
        self.assertEqual(block["leaders"]["era"]["name"], "Ace")
        self.assertEqual(block["leaders"]["so"]["name"], "Ace")
        self.assertEqual(block["leaders"]["saves"]["name"], "Closer")
        self.assertEqual(block["featured"]["pitcherStat"], "era")

    def test_season_series_and_schedule_windows(self):
        games = [
            game(145, True, True, when="2026-09-01T23:00:00Z"),
            game(145, False, False, when="2026-09-02T23:00:00Z"),
            game(145, True, None, state="Preview", when="2026-09-20T23:00:00Z"),
            game(145, True, None, state="Preview", detail="Postponed: Rain", when="2026-09-21T23:00:00Z"),
            game(999, True, True, when="2026-08-01T23:00:00Z"),
            game(116, False, True, when="2026-08-15T23:00:00Z"),
        ]
        opponents = [
            {"id": 145, "club": "White Sox", "abbreviation": "CWS"},
            {"id": 116, "club": "Tigers", "abbreviation": "DET"},
        ]
        series = fetch.season_series(games, opponents)
        self.assertEqual(series[0], {"club": "White Sox", "abbreviation": "CWS", "wins": 1, "losses": 1})
        self.assertEqual(series[1]["wins"], 1)
        classified = fetch.classify_games(games)
        self.assertEqual(classified["gamesRemaining"], 1)
        self.assertEqual(len(classified["upcoming"]), 1)
        self.assertEqual(classified["upcoming"][0]["opponent"], "White Sox")
        self.assertEqual(classified["recent"][0]["result"], "L")
        self.assertTrue(classified["recent"][0]["score"].startswith("2–"))

    def test_hero_and_summary_branches(self):
        common = dict(
            season_state="inProgress",
            wins=82,
            losses=76,
            division_champ=False,
            division_rank=1,
            tied=False,
            magic_number="4",
            games_back="-",
            elimination_number="-",
            wildcard_elimination_number="-",
            wildcard_games_back="-",
            clinched=False,
            rival_club="White Sox",
            rival_games_back="1.0",
        )
        leading = fetch.race_copy(**common)
        self.assertEqual(leading["heroLine"], "Magic number 4.")
        self.assertEqual(leading["figure"], "4")
        self.assertEqual(
            leading["summary"],
            "The Guardians lead the AL Central by 1 game over the White Sox.",
        )
        self.assertEqual(leading["wildCardFact"], "Ahead of the wild card")

        no_magic = fetch.race_copy(**{**common, "magic_number": "-"})
        self.assertEqual(no_magic["heroLine"], "First in the Central.")

        trailing = fetch.race_copy(
            **{
                **common,
                "division_rank": 2,
                "games_back": "1.5",
                "wildcard_games_back": "0.5",
                "rival_club": "White Sox",
            }
        )
        self.assertEqual(trailing["heroLine"], "1.5 games back.")
        self.assertIn("1.5 games behind the White Sox", trailing["summary"])
        self.assertIn("a half-game out of the wild card", trailing["summary"])

        half = fetch.race_copy(**{**common, "division_rank": 2, "games_back": "0.5"})
        self.assertEqual(half["heroLine"], "A half-game back.")

        gone = fetch.race_copy(
            **{**common, "division_rank": 4, "elimination_number": "E", "wildcard_elimination_number": "E"}
        )
        self.assertEqual(gone["heroLine"], "Eliminated.")

        champs = fetch.race_copy(**{**common, "division_champ": True})
        self.assertEqual(champs["heroLine"], "Central champions.")

        over = fetch.race_copy(**{**common, "season_state": "complete"})
        self.assertEqual(over["heroLine"], "82–76.")

        tied = fetch.race_copy(**{**common, "tied": True, "magic_number": "-"})
        self.assertEqual(tied["heroLine"], "Tied atop the Central.")
        self.assertIn("tied atop the AL Central with the White Sox", tied["summary"])

    def test_same_content_ignores_generated_at(self):
        base = {"generatedAt": "2026-09-24T00:00:00Z", "record": {"wins": 82}}
        later = {"generatedAt": "2026-09-24T03:00:00Z", "record": {"wins": 82}}
        changed = {"generatedAt": "2026-09-24T03:00:00Z", "record": {"wins": 83}}
        self.assertTrue(fetch.same_content(base, later))
        self.assertFalse(fetch.same_content(base, changed))
        self.assertFalse(fetch.same_content(None, base))

    def test_assemble_lead_and_series(self):
        rows = [
            team_record(114, "Guardians", 82, 76, 1, "-", magic="4"),
            team_record(145, "White Sox", 81, 77, 2, "1.0", elim="4"),
        ]
        payload = standings(rows)
        games = [game(145, True, True), game(145, False, False, when="2026-09-03T23:00:00Z")]
        snapshot = fetch.assemble(
            season_year=2026,
            season_state="inProgress",
            standings=payload,
            wildcard={"records": [{"teamRecords": [team_record(145, "White Sox", 81, 77, 2, "1.0", wc_gb="-")]}]},
            games=games,
            hitting_splits=[hitter("Chase DeLauter", 9, 500, ".820", hr=15, avg=".290")],
            pitching_splits=[pitcher("Cade Smith", 8, "72.0", "1.99", starts=0, saves=40, strikeouts=104)],
            headlines=fetch.parse_rss(RSS),
            generated_at="2026-09-24T00:00:00Z",
        )
        self.assertEqual(snapshot["heroLine"], "Magic number 4.")
        self.assertEqual(snapshot["playoff"]["division"][0]["club"], "Guardians")
        self.assertTrue(snapshot["playoff"]["division"][0]["isGuardians"])
        self.assertEqual(snapshot["playoff"]["division"][0]["lastTen"], "7–3")
        self.assertEqual(snapshot["division"]["seasonSeries"][0]["wins"], 1)
        self.assertEqual(snapshot["headlines"][0]["source"], "MLB.com")
        self.assertEqual(snapshot["players"]["featured"]["pitcher"]["name"], "Cade Smith")
        self.assertEqual(snapshot["players"]["featured"]["pitcherStat"], "saves")
        self.assertNotIn("generatedAt", fetch.substantive(snapshot))

    def test_season_boundaries(self):
        season = {
            "seasonId": "2026",
            "regularSeasonStartDate": "2026-03-25",
            "regularSeasonEndDate": "2026-09-27",
            "postSeasonStartDate": "2026-09-28",
            "postSeasonEndDate": "2026-10-31",
        }
        opening = fetch.date.fromisoformat("2026-03-20")
        self.assertTrue(fetch.needs_previous_season(opening, season))
        self.assertEqual(fetch.season_state_for(fetch.date.fromisoformat("2026-09-27"), season), "inProgress")
        self.assertEqual(fetch.season_state_for(fetch.date.fromisoformat("2026-09-28"), season), "complete")
        self.assertFalse(fetch.wants_postseason(fetch.date.fromisoformat("2026-09-23"), season))
        self.assertTrue(fetch.wants_postseason(fetch.date.fromisoformat("2026-09-28"), season))

    def test_innings_thirds(self):
        self.assertEqual(fetch.innings_to_outs("39.2"), 119)
        self.assertEqual(fetch.innings_to_outs("40.0"), 120)
        self.assertEqual(fetch.innings_to_outs("15.0"), 45)
        self.assertEqual(fetch.innings_to_outs("14.2"), 44)


if __name__ == "__main__":
    unittest.main()
