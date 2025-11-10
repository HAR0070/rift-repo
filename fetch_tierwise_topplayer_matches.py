import time
import json
import requests
import boto3
import urllib3
from typing import List, Dict

def extract_player_stats(match_data: Dict, puuid: str) -> Dict:
    """
    Extract a comprehensive list of player stats (raw + derived) for the participant with given puuid.
    Returns None if the participant is not found.
    """

    try:
        info = match_data.get('info', {})
        metadata = match_data.get('metadata', {})
        participants = info.get('participants', [])
        if not participants:
            return None

        # find player participant and determine team participants
        player = None
        for p in participants:
            if p.get('puuid') == puuid:
                player = p
                break
        if not player:
            return None

        # derive team totals (kills, damage, damageTaken) for player's team
        team_id = player.get('teamId')
        team_participants = [p for p in participants if p.get('teamId') == team_id]
        enemy_participants = [p for p in participants if p.get('teamId') != team_id]

        team_total_kills = sum(p.get('kills', 0) for p in team_participants)
        team_total_damage = sum(p.get('totalDamageDealtToChampions', 0) for p in team_participants)
        team_total_damage_taken = sum(p.get('totalDamageTaken', 0) for p in team_participants)

        # helper to read nested 'challenges' safely
        challenges = player.get('challenges', {}) or {}

        # core raw values (with safe defaults)
        kills = int(player.get('kills', 0))
        deaths = int(player.get('deaths', 0))
        assists = int(player.get('assists', 0))
        total_damage = int(player.get('totalDamageDealtToChampions', 0))
        total_damage_taken = int(player.get('totalDamageTaken', 0))
        gold_earned = int(player.get('goldEarned', 0))
        vision_score = int(player.get('visionScore', 0))
        total_minions = int(player.get('totalMinionsKilled', 0))
        neutral_minions = int(player.get('neutralMinionsKilled', 0))
        time_ccing = float(player.get('timeCCingOthers', player.get('timeCCingOthers', 0)) or 0)

        # game duration in seconds -> convert to minutes for per-minute stats (avoid division by zero)
        game_duration_sec = info.get('gameDuration') or 0
        game_duration_min = max(game_duration_sec / 60.0, 1/60.0)

        # derived metrics
        kda = (kills + assists) / max(1, deaths)
        gold_per_min = gold_earned / game_duration_min
        damage_per_min = total_damage / game_duration_min
        vision_score_per_min = vision_score / game_duration_min

        team_damage_pct = (total_damage / team_total_damage * 100.0) if team_total_damage > 0 else 0.0
        damage_taken_team_pct = (total_damage_taken / team_total_damage_taken * 100.0) if team_total_damage_taken > 0 else 0.0

        kill_participation = ((kills + assists) / team_total_kills) if team_total_kills > 0 else 0.0

        # champion / positional fields
        champion_name = player.get('championName')
        team_position = player.get('teamPosition') or player.get('individualPosition') or "UNKNOWN"
        win = bool(player.get('win', False))

        # gather objective stats (prefer participant root fields, fallback to challenges)
        turret_takedowns = int(player.get('turretTakedowns', 0) or challenges.get('turretTakedowns', 0))
        dragon_kills = int(player.get('dragonKills', 0) or challenges.get('dragonTakedowns', 0) or challenges.get('dragonKills', 0))
        baron_kills = int(player.get('baronKills', 0) or challenges.get('baronTakedowns', 0) or challenges.get('baronKills', 0))
        objective_stolen = int(player.get('objectiveStolen', 0) or challenges.get('objectiveStolen', 0))
        objective_stolen_assists = int(player.get('objectivesStolenAssists', 0) or challenges.get('objectivesStolenAssists', 0))

        # early-game and micro metrics from challenges (many of these come from Riot's "challenges" object)
        lane_minions_first_10 = challenges.get('laneMinionsFirst10Minutes') or challenges.get('laneMinionsFirst10Minutes', 0)
        gold_per_min_challenge = challenges.get('goldPerMinute') or gold_per_min
        damage_per_min_challenge = challenges.get('damagePerMinute') or damage_per_min
        kills_under_own_turret = challenges.get('killsUnderOwnTurret') or 0
        kills_near_enemy_turret = challenges.get('killsNearEnemyTurret') or 0
        takedowns_before_jungle_spawn = challenges.get('takedownsBeforeJungleMinionSpawn') or 0
        first_blood_kill = bool(player.get('firstBloodKill', False) or challenges.get('firstBloodKill', False))
        first_tower_kill = bool(player.get('firstTowerKill', False) or challenges.get('firstTowerKill', False))

        # optional: fields that sometimes exist in participant for vision/wards
        wards_placed = int(player.get('wardsPlaced', 0) or challenges.get('wardsPlaced', 0))
        wards_killed = int(player.get('wardsKilled', 0) or challenges.get('wardsKilled', 0))
        vision_score_total = vision_score  # alias

        # kills under turret fields if present in participant root (some versions provide them)
        kills_under_own_turret = int(player.get('killsUnderOwnTurret', kills_under_own_turret) or kills_under_own_turret)
        kills_near_enemy_turret = int(player.get('killsNearEnemyTurret', kills_near_enemy_turret) or kills_near_enemy_turret)

        # additional interesting signals: team participation in objectives
        team_turret_takedowns = sum(int(p.get('turretTakedowns', 0) or p.get('challenges', {}).get('turretTakedowns', 0)) for p in team_participants)
        team_dragon_kills = sum(int(p.get('dragonKills', 0) or p.get('challenges', {}).get('dragonTakedowns', 0)) for p in team_participants)
        team_baron_kills = sum(int(p.get('baronKills', 0) or p.get('challenges', {}).get('baronTakedowns', 0)) for p in team_participants)

        # create final stats dictionary containing requested fields
        stats = {
            # identifiers & game meta
            'matchId': metadata.get('matchId'),
            'gameCreation': info.get('gameCreation'),
            'gameDuration': game_duration_sec,
            'gameMode': info.get('gameMode'),
            'queueId': info.get('queueId'),
            'puuid': puuid,
            'summonerName': player.get('summonerName', None),

            # core identifiers
            'championName': champion_name,
            'teamPosition': team_position,
            'win': win,

            # combat & performance
            'kills': kills,
            'deaths': deaths,
            'assists': assists,
            'kda': round(kda, 3),
            'totalDamageDealtToChampions': total_damage,
            'totalDamageTaken': total_damage_taken,
            'damagePerMinute': round(damage_per_min, 2),
            'damageTakenOnTeamPercentage': round(damage_taken_team_pct, 2),
            'teamDamagePercentage': round(team_damage_pct, 2),
            'killParticipation': round(kill_participation, 3),
            'timeCCingOthers': round(time_ccing, 2),

            # economy & objective impact
            'goldEarned': gold_earned,
            'goldPerMinute': round(gold_per_min, 2),
            'turretTakedowns': turret_takedowns,
            'dragonKills': dragon_kills,
            'baronKills': baron_kills,
            'objectiveStolen': objective_stolen,
            'objectiveStolenAssists': objective_stolen_assists,

            # vision & micro
            'visionScore': vision_score_total,
            'visionScorePerMinute': round(vision_score_per_min, 3),
            'wardsPlaced': wards_placed,
            'wardsKilled': wards_killed,

            # laning & minions
            'totalMinionsKilled': total_minions,
            'neutralMinionsKilled': neutral_minions,
            'laneMinionsFirst10Minutes': lane_minions_first_10,

            # optional/clutch indicators
            'killsUnderOwnTurret': kills_under_own_turret,
            'killsNearEnemyTurret': kills_near_enemy_turret,
            'takedownsBeforeJungleMinionSpawn': takedowns_before_jungle_spawn,
            'firstBloodKill': first_blood_kill,
            'firstTowerKill': first_tower_kill,

            # team context
            'teamTotalKills': team_total_kills,
            'teamTotalDamage': team_total_damage,
            'teamTotalDamageTaken': team_total_damage_taken,
            'teamTurretTakedowns': team_turret_takedowns,
            'teamDragonKills': team_dragon_kills,
            'teamBaronKills': team_baron_kills,
        }

        return stats

    except Exception as e:
        print(f"Error extracting player stats: {e}")
        return None



def main(event, context):
    """
    Fetches League of Legends match history for top players tierwise and stores summarized player stats in S3.
    Expected event keys:
      - top_page (int): pages per division to fetch (default 3)
      - top_player (int): top players per page (default 15)
      - platform (str): optional, e.g., "JP1" (default JP1)
    """

    # Configuration - UPDATE THIS WITH YOUR BUCKET NAME OR PASS IN EVENT
    bucket_name = event.get('s3_bucket', 'rift-rewind-rag-ai-documents')

    try:
        PAGES = int(event.get('top_page', 3))
        TOP_PER_PAGE = int(event.get('top_player', 15))
        PLATFORM = event.get('platform', 'JP1').upper()  # platform e.g., NA1, EUW1, KR, JP1

        # Get API key from Parameter Store (SSM)
        ssm = boto3.client('ssm')
        try:
            parameter = ssm.get_parameter(
                Name='/rift-rewind/riot-api-key',
                WithDecryption=True
            )
            API_KEY = parameter['Parameter']['Value']
        except Exception as e:
            print(f"Failed to get API key from SSM: {str(e)}")
            return {'statusCode': 500, 'error': 'Failed to retrieve API key'}

        # Initialize HTTP client and S3 client after API_KEY available
        SESSION = requests.Session()
        HEADERS = {"X-Riot-Token": API_KEY, "User-Agent": "riot-client-example/1.0"}
        SESSION.headers.update(HEADERS)
        s3 = boto3.client('s3')
        http = urllib3.PoolManager()

        QUEUE = "RANKED_SOLO_5x5"
        # League base uses platform-specific host
        LEAGUE_BASE = f"https://{PLATFORM}.api.riotgames.com"

        # region routing for match-v5 (approx common mappings)
        PLATFORM_TO_REGION = {
            "NA1": "americas",
            "BR1": "americas",
            "LA1": "americas",
            "LA2": "americas",
            "OC1": "sea",
            "KR": "asia",
            "JP1": "asia",
            "EUN1": "europe",
            "EUW1": "europe",
            "TR1": "europe",
            "RU": "europe",
        }
        REGION = PLATFORM_TO_REGION.get(PLATFORM, "asia")
        MATCH_BASE = f"https://{REGION}.api.riotgames.com"

        # tiers to iterate (kept from your original list; adjust if necessary)
        TIERS = ['BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'EMERALD', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']

        # Helper functions
        def safe_get(url: str, params: Dict = None, max_retries=4, backoff=1.2):
            for attempt in range(max_retries):
                r = SESSION.get(url, params=params, timeout=12)
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 404:
                    return None
                if r.status_code in (429, 500, 502, 503, 504):
                    wait = backoff * (2 ** attempt)
                    retry_after = r.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = max(wait, float(retry_after))
                        except Exception:
                            pass
                    print(f"warn: {r.status_code} from {url} -> retrying in {wait:.1f}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
            raise RuntimeError(f"Failed to GET {url} after {max_retries} retries")

        def fetch_leaderboard_for_top_tier(tier: str) -> Dict:
            """
            Fetch the non-paginated leaderboard object for MASTER/GRANDMASTER/CHALLENGER.
            Returns JSON dict (or None) depending on response.
            """
            tier_upper = (tier or "").upper()
            if tier_upper == "MASTER":
                endpoint = "masterleagues"
            elif tier_upper == "GRANDMASTER":
                endpoint = "grandmasterleagues"
            elif tier_upper == "CHALLENGER":
                endpoint = "challengerleagues"
            else:
                raise ValueError("fetch_leaderboard_for_top_tier only for MASTER/GRANDMASTER/CHALLENGER")

            url = f"{LEAGUE_BASE}/lol/league/v4/{endpoint}/by-queue/{QUEUE}"
            return safe_get(url)
        
        def fetch_entries_page(page: int, tier: str, division: str) -> List[Dict]:

            tier_upper = (tier or "").upper()
            division_upper = (division or "").upper()

            # Do not attempt to page the top tiers here
            if tier_upper in ("MASTER", "GRANDMASTER", "CHALLENGER"):
                # caller should call the leaderboard endpoints for these tiers instead
                return fetch_leaderboard_for_top_tier(tier)

            url = f"{LEAGUE_BASE}/lol/league/v4/entries/{QUEUE}/{tier_upper}/{division_upper}"
            params = {"page": page}
            return safe_get(url, params=params) or []

        def fetch_recent_match_ids(puuid: str, count: int = 3) -> List[str]:
            url = f"{MATCH_BASE}/lol/match/v5/matches/by-puuid/{puuid}/ids"
            params = {"start": 0, "count": count}
            return safe_get(url, params=params) or []

        def fetch_match(match_id: str) -> Dict:
            url = f"{MATCH_BASE}/lol/match/v5/matches/{match_id}"
            return safe_get(url)

        # Ensure consistent S3 path structure
        def save_to_s3(key: str, obj):
            s3.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=json.dumps(obj, indent=2, ensure_ascii=False),
                ContentType='application/json'
            )

        # MAIN LOOP
        match_processed = 0
        seen_puuids = set()

        for tier in TIERS:
            if tier in ("Master", "Grandmaster", "Challenger"):
                divisions = ["I"]
            else:
                divisions = ["IV", "III", "II", "I"]

            for division in divisions:
                for page in range(1, PAGES + 1):
                    print(f"Fetching entries page {page} for {tier} {division}...")
                    entries = fetch_entries_page(page, tier, division)
                    time.sleep(0.25)
                    if not isinstance(entries, list):
                        print(f"Unexpected response for entries page {page}: {type(entries)} - skipping")
                        continue

                    # select top unique players from page
                    top_entries = []
                    for e in entries:
                        puuid = e.get("puuid") or e.get("summonerId") or e.get("encryptedSummonerId")
                        if not puuid or puuid in seen_puuids:
                            continue
                        top_entries.append(e)
                        seen_puuids.add(puuid)
                        if len(top_entries) >= TOP_PER_PAGE:
                            break

                    print(f" -> selected {len(top_entries)} top entries from page {page}")

                    for entry in top_entries:
                        puuid = entry.get("puuid")
                        # fallback to summonerId if puuid absent: you'd need to call Summoner API to convert (not included here)
                        if not puuid:
                            print("No PUUID in entry; skipping (convert using Summoner API if required).")
                            continue

                        summ_info = {"entry": entry, "recent_matches": []}
                        try:
                            match_ids = fetch_recent_match_ids(puuid, count=3)
                            print(f"   {puuid[:8]}... -> matches found: {len(match_ids)}")

                            summoner_name = None
                            LP = entry.get("leaguePoints", "unknown")

                            for i, match_id in enumerate(match_ids):
                                print(f"    Processing match {i+1}/{len(match_ids)}: {match_id}")
                                match_data = fetch_match(match_id)
                                # polite pause to reduce likelihood of rate limiting
                                time.sleep(1.25)
                                if not match_data:
                                    print(f"     match {match_id} not found -> skipping")
                                    continue

                                player_stats = extract_player_stats(match_data, puuid)
                                if player_stats:
                                    match_processed += 1
                                    summ_info['recent_matches'].append(player_stats)
                                    # retain summoner name for storage key if present
                                    if not summoner_name:
                                        summoner_name = player_stats.get('summonerName') or player_stats.get('championName') or puuid[:8]

                            # save per-player summary to S3
                            safe_name = (summoner_name or puuid[:8]).replace("/", "_")
                            stats_key = f"match-history/{tier}/{division}/{LP}/{safe_name}.json"
                            save_to_s3(stats_key, summ_info)
                            print(f"   Saved stats for {puuid} to s3://{bucket_name}/{stats_key}")

                        except Exception as ex:
                            print(f"   Error fetching matches for {puuid}: {ex}")

        return {
            'statusCode': 200,
            'message': f'Successfully processed {match_processed} matches and stored in S3 bucket {bucket_name}.'
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'statusCode': 500, 'error': str(e)}

if __name__ == "__main__":
    # For local testing, you can define a sample event and context
    sample_event = {
        'top_page': 3,
        'top_player': 15,
        'platform': 'JP1',
        's3_bucket': 'rift-rewind-rag-ai-documents'  # replace with your bucket name
    }
    sample_context = {}
    result = main(sample_event, sample_context)
    print(result)
