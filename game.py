"""Logika Ular Tangga (server-authoritative). Tanpa dependensi Telegram."""
import random, secrets, time

MAX_PLAYERS = 4
TURN_SEC = 60            # lewat waktu ini dadu dilempar otomatis
COLORS = ["#ef4444", "#3b82f6", "#22c55e", "#f59e0b"]
LADDERS = {2: 38, 7: 14, 8: 31, 15: 26, 21: 42, 28: 84, 36: 44, 51: 67, 71: 91, 78: 98}
SNAKES = {16: 6, 46: 25, 49: 11, 62: 19, 64: 60, 74: 53, 89: 68, 92: 88, 95: 75, 99: 80}
JUMPS = {**LADDERS, **SNAKES}
ROOMS: dict = {}


def new_room(chat, uid, name):
    for k in [k for k, r in ROOMS.items() if time.time() - r["created"] > 6 * 3600]:
        ROOMS.pop(k, None)
    rid = secrets.token_urlsafe(4)
    r = dict(id=rid, chat=chat, msg=None, host=uid, status="lobby", players=[], turn=0,
             seq=0, last=None, winner=None, deadline=0, created=time.time(), announced=False)
    ROOMS[rid] = r
    add_player(r, uid, name)
    return r


def add_player(r, uid, name):
    if r["status"] != "lobby":
        return "Game sudah dimulai."
    if any(p["id"] == uid for p in r["players"]):
        return "Kamu sudah bergabung."
    if len(r["players"]) >= MAX_PLAYERS:
        return f"Room penuh (maks {MAX_PLAYERS} pemain)."
    r["players"].append(dict(id=uid, name=name, pos=0, color=COLORS[len(r["players"])]))
    return None


def remove_player(r, uid):
    if r["status"] != "lobby":
        return "Game sudah dimulai."
    r["players"] = [p for p in r["players"] if p["id"] != uid]
    for i, p in enumerate(r["players"]):
        p["color"] = COLORS[i]
    if r["host"] == uid and r["players"]:
        r["host"] = r["players"][0]["id"]
    return None


def start(r, min_players=2):
    if len(r["players"]) < min_players:
        return f"Minimal {min_players} pemain untuk mulai."
    random.shuffle(r["players"])
    for i, p in enumerate(r["players"]):
        p["color"] = COLORS[i]
    r.update(status="playing", turn=0, deadline=time.time() + TURN_SEC)
    return None


def roll(r, uid, auto=False):
    if r["status"] != "playing":
        return None
    p = r["players"][r["turn"]]
    if p["id"] != uid:
        return None
    d = random.randint(1, 6)
    a = p["pos"]
    t = a + d
    path = [] if t > 100 else list(range(a + 1, t + 1))   # harus pas di 100
    to = a if t > 100 else t
    jump = JUMPS.get(to) if t <= 100 else None
    final = jump or to
    p["pos"] = final
    r["seq"] += 1
    r["last"] = dict(seq=r["seq"], uid=uid, dice=d, frm=a, path=path, jump=jump,
                     to=final, auto=auto)
    if final == 100:
        r.update(status="finished", winner=uid)
    else:
        if d != 6:                                     # angka 6 = giliran lagi
            r["turn"] = (r["turn"] + 1) % len(r["players"])
        r["deadline"] = time.time() + TURN_SEC
    return r["last"]


def tick(r):
    if r["status"] == "playing" and time.time() > r["deadline"]:
        roll(r, r["players"][r["turn"]]["id"], auto=True)


def public(r, uid):
    return dict(id=r["id"], status=r["status"], players=r["players"], turn=r["turn"],
                seq=r["seq"], last=r["last"], winner=r["winner"], me=uid,
                tleft=max(0, int(r["deadline"] - time.time())) if r["status"] == "playing" else 0,
                board=dict(ladders=LADDERS, snakes=SNAKES))
