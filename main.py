import requests
import os
import json
import time

# =====================
# 環境変数
# =====================
RIOT_API_KEY = os.environ["RIOT_API_KEY"]
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK"]

# =====================
# 対象プレイヤー（Riot ID）
# =====================
GAME_NAME = "パクノダ"
TAG_LINE = "旅団Win"

# Account / Match API 用（JP・KR・TWすべて asia）
REGION = "asia"

HEADERS = {"X-Riot-Token": RIOT_API_KEY}
STATE_FILE = "state.json"


def get_json(url):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()


# =====================
# state 読み込み
# =====================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)
else:
    state = {}


# =====================
# 1. Riot ID → PUUID
# =====================
acc = get_json(
    f"https://{REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{GAME_NAME}/{TAG_LINE}"
)

puuid = acc["puuid"]


# =====================
# 2. 最新試合ID取得
# =====================
match_ids = get_json(
    f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=1"
)

latest_match = match_ids[0]

# 既に投稿済みなら終了
if state.get("last_match_id") == latest_match:
    exit()


# =====================
# 3. 試合詳細取得
# =====================
match = get_json(
    f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{latest_match}"
)

info = match["info"]
player = next(p for p in info["participants"] if p["puuid"] == puuid)

result = "WIN 🟢" if player["win"] else "LOSE 🔴"


# =====================
# 4. summonerId / PLATFORM（ここが重要）
# =====================
summoner_id = player["summonerId"]

# KR / JP1 / NA1 など → API用に小文字化
platform = info["platformId"].lower()


# =====================
# 5. LP反映待ち（仕様対策）
# =====================
time.sleep(90)


# =====================
# 6. ランク情報取得
# =====================
entries = get_json(
    f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
)

rank_entry = next(
    (e for e in entries if e["queueType"] == "RANKED_SOLO_5x5"),
    None
)

if rank_entry:
    tier = rank_entry["tier"]
    division = rank_entry["rank"]
    current_lp = rank_entry["leaguePoints"]
else:
    tier = division = "UNRANKED"
    current_lp = None


# =====================
# 7. LP差分計算
# =====================
prev_lp = state.get("last_lp")
lp_diff = None

if current_lp is not None and prev_lp is not None:
    lp_diff = current_lp - prev_lp

if lp_diff is None:
    lp_text = "不明"
else:
    lp_text = f'{("+" if lp_diff >= 0 else "")}{lp_diff} LP'


# =====================
# 8. Discord 投稿
# =====================
content = {
    "embeds": [{
        "title": "🎮 LoL ランク戦結果",
        "fields": [
            {"name": "サモナー", "value": f"{GAME_NAME}#{TAG_LINE}", "inline": True},
            {"name": "チャンピオン", "value": player["championName"], "inline": True},
            {"name": "結果", "value": result, "inline": True},
            {"name": "K / D / A",
             "value": f'{player["kills"]}/{player["deaths"]}/{player["assists"]}',
             "inline": True},
            {"name": "CS",
             "value": str(player["totalMinionsKilled"]),
             "inline": True},
            {"name": "試合時間",
             "value": f'{info["gameDuration"]//60}:{info["gameDuration"]%60:02}',
             "inline": True},
            {"name": "ランク",
             "value": f"{tier} {division}" if tier != "UNRANKED" else "UNRANKED",
             "inline": True},
            {"name": "LP変動", "value": lp_text, "inline": True},
            {"name": "現在LP",
             "value": str(current_lp) if current_lp is not None else "―",
             "inline": True}
        ]
    }]
}

requests.post(WEBHOOK_URL, json=content)


# =====================
# 9. state 保存
# =====================
state["last_match_id"] = latest_match
if current_lp is not None:
    state["last_lp"] = current_lp

with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
