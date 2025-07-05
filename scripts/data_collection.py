import requests
import pandas as pd
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
FACEIT_API_KEY = os.getenv("FACEIT_API_KEY")
if not FACEIT_API_KEY or FACEIT_API_KEY == "YOUR_FACEIT_API_KEY":
    raise ValueError("Please set your FACEIT_API_KEY in the .env file")

HEADERS = {'Authorization': f'Bearer {FACEIT_API_KEY}'}
PLAYER_NICKNAMES = ["vari0us", "s1mple", "m0NESY", "ZywOo"] 
MATCHES_LIMIT = 1000

# --- Helper Functions (No Changes Needed) ---
def get_player_id(nickname):
    url = f"https://open.faceit.com/data/v4/players?nickname={nickname}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json().get('player_id')
    except requests.exceptions.RequestException as e:
        print(f"Error fetching player ID for {nickname}: {e}")
        return None

def get_match_history(player_id, limit):
    url = f"https://open.faceit.com/data/v4/players/{player_id}/history?game=cs2&offset=0&limit={limit}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return [item['match_id'] for item in response.json().get('items', [])]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching match history: {e}")
        return []

def get_match_stats(match_id):
    url = f"https://open.faceit.com/data/v4/matches/{match_id}/stats"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        json_response = response.json()
        rounds = json_response.get('rounds')
        if rounds:
            teams_data = rounds[0].get('teams', [])
            map_name = rounds[0].get('round_stats', {}).get('Map')
            return teams_data, map_name
        return [], None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching match stats for {match_id}: {e}")
        return [], None

# --- Main Script Logic ---
if __name__ == "__main__":
    all_match_player_data = []
    processed_match_ids = set()

    # --- Step 1: Gather all unique match IDs ---
    print("--- Step 1: Gathering all unique match IDs ---")
    all_match_ids = set()
    for nickname in PLAYER_NICKNAMES:
        player_id = get_player_id(nickname)
        if player_id:
            print(f"Fetching match history for {nickname}...")
            history = get_match_history(player_id, MATCHES_LIMIT)
            all_match_ids.update(history)
    
    print(f"\nFound {len(all_match_ids)} unique matches to process.")

    # --- Step 2: Process each match and calculate team/opponent context ---
    print("\n--- Step 2: Processing matches and engineering features ---")
    for i, match_id in enumerate(list(all_match_ids)):
        time.sleep(1.1)
        print(f"Processing match {i+1}/{len(all_match_ids)}: {match_id}")

        teams_data, map_name = get_match_stats(match_id)
        if not teams_data or not map_name:
            continue
        
        # Structure all 10 players' stats for easy access
        match_players = []
        for team_idx, team in enumerate(teams_data):
            for p in team.get('players', []):
                stats = p.get('player_stats', {})
                match_players.append({
                    'player_id': p.get('player_id'),
                    'nickname': p.get('nickname'),
                    'team_id': team_idx, # 0 for team 1, 1 for team 2
                    'player_kd_ratio': float(stats.get('K/D Ratio', 0.0)),
                    'player_kr_ratio': float(stats.get('K/R Ratio', 0.0)),
                    'kills': int(stats.get('Kills', 0)),
                    'deaths': int(stats.get('Deaths', 0)),
                    'assists': int(stats.get('Assists', 0)),
                    'headshots_percent': float(stats.get('Headshots %', 0.0)),
                    'team_win': 1 if stats.get('Result') == '1' else 0
                })
        
        if len(match_players) != 10: continue # Skip incomplete matches

        # For each player, calculate teammate and opponent averages
        for player in match_players:
            teammates = [p for p in match_players if p['team_id'] == player['team_id'] and p['player_id'] != player['player_id']]
            opponents = [p for p in match_players if p['team_id'] != player['team_id']]

            player['avg_teammate_kr'] = sum(p['player_kr_ratio'] for p in teammates) / len(teammates) if teammates else 0
            player['avg_opponent_kr'] = sum(p['player_kr_ratio'] for p in opponents) / len(opponents) if opponents else 0
            
            player['match_id'] = match_id
            player['map'] = map_name
            
            all_match_player_data.append(player)

    # --- Step 3: Create DataFrame and save ---
    df = pd.DataFrame(all_match_player_data)
    df['performed_well'] = (df['player_kr_ratio'] > 0.7).astype(int)

    output_dir = './data'
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'faceit_match_data_v2.csv') # Save to a new file
    df.to_csv(output_path, index=False)
    
    print(f"\nData collection complete. Total unique player performances collected: {len(df)}")
    print(f"File saved to {output_path}")

