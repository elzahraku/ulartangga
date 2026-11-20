"""Bot Ular Tangga + server Mini App (satu proses). Jalankan: python bot.py"""
import asyncio, hashlib, hmac, html, json, os
from urllib.parse import parse_qsl, quote

from aiohttp import web
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M, WebAppInfo

import game

load_dotenv()
API_ID, API_HASH = int(os.environ["API_ID"]), os.environ["API_HASH"]
TOKEN = os.environ["BOT_TOKEN"]
BASE_URL = os.environ["BASE_URL"].rstrip("/")      # wajib https, contoh https://game.domain.com
PORT = int(os.getenv("PORT", "8095"))
SHORTNAME = os.getenv("MINIAPP_SHORTNAME", "")      # opsional: short name Mini App dari BotFather /newapp
MIN_PLAYERS = int(os.getenv("MIN_PLAYERS", "2"))
EMO = ["🔴", "🔵", "🟢", "🟡"]
BOT_USER = ""

bot = Client("ular_tangga", api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN,
             in_memory=True, parse_mode=ParseMode.HTML)


# ───────────────────────── tampilan lobby ─────────────────────────
def private(r): return r["chat"] > 0


def lobby_text(r):
    rows = "\n".join(f"{EMO[i]} {html.escape(p['name'])}" + (" 👑" if p["id"] == r["host"] else "")
                     for i, p in enumerate(r["players"]))
    head = "🐍🪜 <b>ULAR TANGGA</b>\n"
    if r["status"] == "lobby":
        return (f"{head}Pemain {len(r['players'])}/{game.MAX_PLAYERS}:\n{rows}\n\n"
                "Tekan <b>Gabung</b>. Host menekan <b>Mulai</b> saat pemain sudah lengkap.")
    if r["status"] == "playing":
        return f"{head}Game berjalan!\n{rows}\n\nTekan <b>Main</b> untuk membuka papan."
    win = next(p for p in r["players"] if p["id"] == r["winner"])
    return f"{head}🏆 Pemenang: <b>{html.escape(win['name'])}</b>\n\n{rows}"


def play_button(r, in_private):
    if in_private:
        return B("🎲 Main", web_app=WebAppInfo(url=f"{BASE_URL}/app?room={r['id']}"))
    if SHORTNAME:
        return B("🎲 Main", url=f"https://t.me/{BOT_USER}/{SHORTNAME}?startapp={r['id']}")
    return B("🎲 Main", url=f"https://t.me/{BOT_USER}?start=g_{r['id']}")


def lobby_kb(r):
    i = r["id"]
    if r["status"] == "lobby":
        rows = [[B("🎲 Gabung", callback_data=f"j:{i}"), B("🚪 Keluar", callback_data=f"l:{i}")],
                [B(f"▶️ Mulai ({len(r['players'])}/{game.MAX_PLAYERS})", callback_data=f"s:{i}"),
                 B("❌ Tutup", callback_data=f"x:{i}")]]
        if private(r):
            link = quote(f"https://t.me/{BOT_USER}?start=j_{i}")
            rows.append([B("📨 Undang teman", url=f"https://t.me/share/url?url={link}&text=Ayo%20main%20Ular%20Tangga!")])
        return M(rows)
    if r["status"] == "playing":
        return M([[play_button(r, private(r))]])
    return None


async def refresh(r):
    try:
        await bot.edit_message_text(r["chat"], r["msg"], lobby_text(r), reply_markup=lobby_kb(r))
    except Exception:
        pass


async def maybe_announce(r):
    if r["status"] == "finished" and not r["announced"]:
        r["announced"] = True
        await refresh(r)
        win = next(p for p in r["players"] if p["id"] == r["winner"])
        try:
            await bot.send_message(r["chat"], f"🏆 <b>{html.escape(win['name'])}</b> menang Ular Tangga!")
        except Exception:
            pass


# ───────────────────────── handler bot ─────────────────────────
@bot.on_message(filters.command(["start", "ulartangga"]))
async def cmd_start(c, m):
    arg = m.command[1] if len(m.command) > 1 else ""
    u = m.from_user
    if m.chat.type == ChatType.PRIVATE and arg[:2] in ("g_", "j_"):
        r = game.ROOMS.get(arg[2:])
        if not r:
            return await m.reply("Room sudah tidak ada. Buat yang baru dengan /ulartangga.")
        if arg.startswith("j_"):
            err = game.add_player(r, u.id, u.first_name)
            if err and "sudah bergabung" not in err:
                return await m.reply(err)
            await refresh(r)
            return await m.reply("✅ Kamu masuk room. Tunggu host menekan <b>Mulai</b>, "
                                 "tombol Main akan dikirim ke sini.")
        return await m.reply("🎲 Papan sudah siap!", reply_markup=M([[play_button(r, True)]]))
    r = game.new_room(m.chat.id, u.id, u.first_name)
    sent = await m.reply(lobby_text(r), reply_markup=lobby_kb(r))
    r["msg"] = sent.id


@bot.on_callback_query(filters.regex(r"^[jlsx]:"))
async def cb(c, q):
    act, rid = q.data.split(":")
    r = game.ROOMS.get(rid)
    if not r:
        return await q.answer("Room sudah tidak ada.", show_alert=True)
    u, err = q.from_user, None
    if act == "j":
        err = game.add_player(r, u.id, u.first_name)
    elif act == "l":
        err = game.remove_player(r, u.id)
        if not r["players"]:
            game.ROOMS.pop(rid, None)
            await q.answer()
            return await q.message.edit_text("Room ditutup (semua pemain keluar).")
    elif u.id != r["host"]:
        err = "Hanya host yang bisa melakukan ini."
    elif act == "s":
        err = game.start(r, MIN_PLAYERS)
    elif act == "x":
        game.ROOMS.pop(rid, None)
        await q.answer()
        return await q.message.edit_text("Room ditutup oleh host.")
    if err:
        return await q.answer(err, show_alert=True)
    await q.answer()
    await refresh(r)
    if act == "s" and private(r):                       # room privat: kirim tombol ke tiap pemain
        for p in r["players"]:
            if p["id"] != r["host"]:
                try:
                    await bot.send_message(p["id"], "🎲 Game dimulai!",
                                           reply_markup=M([[play_button(r, True)]]))
                except Exception:
                    pass


# ───────────────────────── API Mini App ─────────────────────────
def verify(init: str):
    d = dict(parse_qsl(init, keep_blank_values=True))
    h = d.pop("hash", "")
    check = "\n".join(f"{k}={v}" for k, v in sorted(d.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    if not h or not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), h):
        return None
    try:
        return json.loads(d["user"])
    except Exception:
        return None


async def api(req, do_roll):
    b = await req.json()
    u = verify(b.get("init", ""))
    if not u:
        return web.json_response({"error": "Buka game ini lewat Telegram."}, status=401)
    r = game.ROOMS.get(b.get("room"))
    if not r:
        return web.json_response({"error": "Room tidak ditemukan atau sudah selesai."}, status=404)
    if do_roll:
        game.roll(r, u["id"])
    else:
        game.tick(r)
    await maybe_announce(r)
    return web.json_response(game.public(r, u["id"]))


async def page(req):
    return web.FileResponse(os.path.join(os.path.dirname(__file__), "webapp", "index.html"),
                            headers={"Cache-Control": "no-store"})


async def main():
    global BOT_USER
    await bot.start()
    BOT_USER = (await bot.get_me()).username
    app = web.Application()
    app.add_routes([web.get("/app", page),
                    web.post("/api/state", lambda r: api(r, False)),
                    web.post("/api/roll", lambda r: api(r, True))])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    print(f"Bot @{BOT_USER} aktif, Mini App di port {PORT}")
    await idle()
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
