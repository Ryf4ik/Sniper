"""
Telegram username sniper v3.

Режимы проверки:
  1 - HTTP (t.me), API не нужен, зависимостей нет
  2 - Telegram API (нужны api_id и api_hash, pip install telethon)
  3 - комбо: HTTP-фильтр, затем подтверждение через API

Добавить ключи позже:  python sniper_v3.py setup
"""
import asyncio
import json
import os
import random
import re
import string
import sys
import time
import urllib.error
import urllib.request

CFG, CHECKED, FOUND = "config.json", "checked.txt", "found.txt"
VALID = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


def ok_name(n):
    return bool(VALID.match(n)) and not n.endswith("_") and "__" not in n

LET, DIG = string.ascii_lowercase, string.digits
VOW, CON = "aeiou", "bcdfghjklmnpqrstvwxyz"
UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"


# ---------- конфиг ----------
def load_cfg():
    if not os.path.exists(CFG):
        save_cfg({"api_id": None, "api_hash": None})
    with open(CFG) as f:
        return json.load(f)


def save_cfg(c):
    with open(CFG, "w") as f:
        json.dump(c, f, indent=2)


def setup():
    c = load_cfg()
    c["api_id"] = int(input("API_ID: ").strip())
    c["api_hash"] = input("API_HASH: ").strip()
    save_cfg(c)
    print("Ключи сохранены в config.json")


def read_set(path):
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {l.strip().lower() for l in f if l.strip()}


# ---------- генераторы имён ----------
def gen_file(path, repeat):
    while os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            names = [l.strip().lstrip("@").lower() for l in f if l.strip()]
        yield from names
        if not repeat or not names:
            return


def gen_random(length, charset):
    while True:
        yield random.choice(LET) + "".join(random.choice(charset) for _ in range(length - 1))


def gen_pronounce(length):
    while True:
        start = random.choice([0, 1])
        yield "".join(random.choice(CON if (i + start) % 2 == 0 else VOW) for i in range(length))


def gen_mask(mask):
    pools = {"?": LET, "#": DIG, "*": LET + DIG + "_"}
    while True:
        yield "".join(random.choice(pools[ch]) if ch in pools else ch for ch in mask)


def gen_pretty(length):
    while True:
        kind = random.choice(["pal", "rep", "abab", "aabb"])
        a, b = random.choice(LET), random.choice(LET)
        if kind == "pal":
            half = "".join(random.choice(LET) for _ in range((length + 1) // 2))
            yield (half + half[::-1][length % 2:])[:length]
        elif kind == "rep":
            yield a * length
        elif kind == "abab":
            yield ((a + b) * length)[:length]
        else:
            yield ((a * 2 + b * 2) * length)[:length]


WORDS = """
alpha amber angel apex arrow aspen atlas aura azure beast blade blaze bliss bolt boss
brave breeze bronze cadet cargo chaos charm chief cipher cloud cobra comet coral crown
crypto cyber dagger dance dark dawn delta demon diesel dragon dream drift dusk eagle
echo eclipse elite ember empire energy epic falcon fenix flame flash frost fury galaxy
ghost giant glory gold gotham grand gravity hawk hero hydra icon ivory jade jazz joker
jungle karma king knight laser legend lemon light lion lotus lunar magic matrix mirage
moon mystic neon nexus night ninja noble nova oasis omega onyx orbit oracle panda
phoenix pilot pixel planet pluto power prime pulse quest radar raven rebel rider rocket
royal ruby saber saint scout shade shadow shark sigma silver smoke solar sonic spark
spirit steel storm swift sword talon tiger titan toxic turbo ultra vector venom vertex
viper vision vortex wave wizard xenon zeus
""".split()

_WS = None


def wordset():
    """Встроенные слова + свои из words.txt (по одному в строке)."""
    global _WS
    if _WS is None:
        s = set(WORDS)
        if os.path.exists("words.txt"):
            with open("words.txt", encoding="utf-8") as f:
                s |= {l.strip().lower() for l in f if l.strip().isalpha()}
        _WS = s
    return _WS


def gen_imba(lo, hi):
    allw = sorted(wordset())
    words = [w for w in allw if lo <= len(w) <= hi]
    while True:
        r = random.random()
        ln = random.randint(lo, hi)
        if words and r < 0.45:
            yield random.choice(words)
        elif words and r < 0.70:
            w = random.choice(allw)
            cand = random.choice([
                w + random.choice("xoz"), "x" + w, w[:-1] + random.choice(LET),
                w + random.choice(LET), w + w[-1],
            ])
            if lo <= len(cand) <= hi:
                yield cand
        elif r < 0.88:
            yield next(gen_pronounce(ln))
        else:
            yield next(gen_pretty(ln))


def score(name):
    n = len(name)
    s = {5: 50, 6: 35, 7: 25, 8: 15}.get(n, 5)
    if name in wordset():
        s += 30
    if name == name[::-1]:
        s += 25
    if len(set(name)) <= 2:
        s += 25
    if re.search(r"(.)\1\1", name):
        s += 10
    if re.fullmatch(r"([bcdfghjklmnpqrstvwxyz][aeiou])+[bcdfghjklmnpqrstvwxyz]?", name):
        s += 10
    if any(c.isdigit() for c in name):
        s -= 10
    if "_" in name:
        s -= 15
    return s


def label(s):
    return "🔥 ИМБА" if s >= 80 else "⭐ круто" if s >= 55 else "обычный"


def menu():
    print("\nГде брать имена:")
    print("1 - из names.txt (один проход)")
    print("2 - случайные буквы")
    print("3 - случайные буквы+цифры")
    print("4 - произносимые")
    print("5 - по маске (? буква, # цифра, * любой)")
    print("6 - красивые (палиндромы, повторы)")
    print("7 - слежка за names.txt (по кругу)")
    print("8 - ИМБОВЫЕ (слова, красивые, произносимые, с рейтингом)")
    m = input("Выбор: ").strip()
    if m == "8":
        lo = max(5, int(input("Мин. длина (5-8) [5]: ") or 5))
        hi = max(lo, int(input("Макс. длина [6]: ") or 6))
        return gen_imba(lo, hi), True
    if m == "1":
        return gen_file("names.txt", False), True
    if m == "7":
        return gen_file("names.txt", True), False
    if m == "5":
        return gen_mask(input("Маска, напр. ab??#: ").strip().lower()), True
    ln = max(5, min(32, int(input("Длина (5-32): "))))
    if m == "2":
        return gen_random(ln, LET), True
    if m == "3":
        return gen_random(ln, LET + DIG), True
    if m == "4":
        return gen_pronounce(ln), True
    return gen_pretty(ln), True


# ---------- проверка через HTTP (без API) ----------
def _http_sync(name):
    req = urllib.request.Request(f"https://t.me/{name}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return "flood" if e.code == 429 else "error"
    except Exception:
        return "error"
    # у занятого имени на странице есть заголовок профиля
    return "taken" if "tgme_page_title" in html else "free"


async def http_check(name):
    for _ in range(5):
        res = await asyncio.to_thread(_http_sync, name)
        if res == "flood":
            print("t.me просит подождать, пауза 60с")
            await asyncio.sleep(60)
            continue
        return res
    return "error"


# ---------- проверка через Telegram API ----------
class TgChecker:
    def __init__(self, cfg):
        self.cfg = cfg
        self.client = None

    async def start(self):
        from telethon import TelegramClient
        self.client = TelegramClient("sniper", self.cfg["api_id"], self.cfg["api_hash"])
        await self.client.start()

    async def check(self, name):
        from telethon import errors, functions
        while True:
            try:
                ok = await self.client(functions.account.CheckUsernameRequest(username=name))
                return "free" if ok else "taken"
            except (errors.UsernameInvalidError, errors.UsernameOccupiedError):
                return "taken"
            except errors.FloodWaitError as e:
                print(f"FloodWait: жду {e.seconds} сек")
                await asyncio.sleep(e.seconds + 1)
            except Exception as e:
                print(f"[API ошибка] {e}")
                return "error"

    async def claim(self, name, how):
        from telethon import functions
        if how == "1":
            res = await self.client(functions.channels.CreateChannelRequest(
                title=name, about="", broadcast=True))
            await self.client(functions.channels.UpdateUsernameRequest(
                channel=res.chats[0], username=name))
        elif how == "2":
            await self.client(functions.account.UpdateUsernameRequest(username=name))

    async def notify(self, text):
        try:
            await self.client.send_message("me", text)
        except Exception:
            pass

    async def stop(self):
        if self.client:
            await self.client.disconnect()


# ---------- основной цикл ----------
async def run():
    cfg = load_cfg()
    has_api = bool(cfg.get("api_id") and cfg.get("api_hash"))
    print("API:", "ключи найдены" if has_api else "ключей нет, доступен только HTTP-режим")
    print("\nКак проверять:\n1 - HTTP (t.me), без API\n2 - Telegram API\n3 - комбо")
    mode = input("Выбор: ").strip() or "1"
    if mode in ("2", "3") and not has_api:
        print("Нет ключей. Запусти: python sniper_v3.py setup")
        return

    gen, use_cache = menu()

    tg, how = None, "3"
    if mode in ("2", "3"):
        tg = TgChecker(cfg)
        await tg.start()
        print("\nЧто делать с найденным:")
        print("1 - занять каналом\n2 - поставить себе на аккаунт\n3 - только уведомить")
        how = input("Выбор: ").strip() or "3"

    d_http = max(1.0, float(input("Пауза HTTP, сек (мин 1) [1.5]: ") or 1.5))
    d_tg = max(3.0, float(input("Пауза API, сек (мин 3) [5]: ") or 5)) if tg else 0

    print("\nРейтинг имени: 5 букв ~50, слово +30, палиндром/повтор +25.")
    min_score = int(input("Мин. рейтинг для показа и занятия (0 = всё) [0]: ") or 0)

    checked = read_set(CHECKED) if use_cache else set()
    cache_f = open(CHECKED, "a", encoding="utf-8")
    checks = found = skips = 0
    t0 = time.time()
    print("\nСтарт. Остановка: Ctrl+C\n")

    try:
        for name in gen:
            name = name.lower()
            if not ok_name(name):
                continue
            if name in checked:
                skips += 1
                if skips > 2000:
                    print("Новых вариантов не осталось.")
                    break
                continue
            skips = 0

            status = "taken"
            if mode in ("1", "3"):
                status = await http_check(name)
                if status == "error":
                    await asyncio.sleep(d_http)
                    continue
                await asyncio.sleep(d_http)
            if mode == "2" or (mode == "3" and status == "free"):
                status = await tg.check(name)
                await asyncio.sleep(d_tg)
                if status == "error":
                    continue

            if status == "free" and score(name) < min_score:
                continue

            checks += 1
            if status == "free":
                found += 1
                sc = score(name)
                confirmed = mode != "1"
                tag = "СВОБОДЕН" if confirmed else "возможно свободен (HTTP)"
                print(f"[{tag}] @{name}  {label(sc)} ({sc})")
                with open(FOUND, "a", encoding="utf-8") as f:
                    f.write(f"{name}\t{'api' if confirmed else 'http'}\t{sc}\n")
                if tg:
                    await tg.notify(f"Свободен: @{name} {label(sc)} ({sc})")
                    if how in ("1", "2"):
                        try:
                            await tg.claim(name, how)
                            print(f"[ЗАНЯТ] @{name}")
                            await tg.notify(f"Занял: @{name}")
                        except Exception as e:
                            print(f"[claim ошибка] @{name}: {e}")
            elif use_cache:
                checked.add(name)
                cache_f.write(name + "\n")
                cache_f.flush()

            if checks % 25 == 0:
                mins = max((time.time() - t0) / 60, 0.01)
                print(f"-- проверено {checks}, найдено {found}, {checks / mins:.1f}/мин")
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        cache_f.close()
        print(f"\nИтог: проверено {checks}, найдено {found}. Список: {FOUND}")
        if tg:
            await tg.stop()




"""Приложение-интерфейс для sniper_v3.py. Положи рядом с ним и запусти:
    python sniper_app.py
Потом открой в браузере телефона: http://127.0.0.1:8080
(Chrome -> меню -> «Добавить на главный экран» = иконка как у приложения)
"""
import asyncio
import json
import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


S = {"running": False, "stop": False, "log": [], "found": [], "checks": 0, "t0": 0, "err": ""}


def add(msg):
    S["log"].append(time.strftime("%H:%M:%S ") + msg)
    del S["log"][:-80]


def build_gen(p):
    src, ln = p["source"], int(p.get("length") or 5)
    if src == "imba":
        return gen_imba(ln, ln + 1), True
    if src == "pretty":
        return gen_pretty(ln), True
    if src == "pron":
        return gen_pronounce(ln), True
    if src == "random":
        return gen_random(ln, LET), True
    if src == "alnum":
        return gen_random(ln, LET + DIG), True
    if src == "mask":
        return gen_mask((p.get("mask") or "?????").lower()), True
    if src == "watch":
        return gen_file("names.txt", True), False
    return gen_file("names.txt", False), True


async def worker(p):
    gen, cache_on = build_gen(p)
    mode, how = p["mode"], p.get("how", "3")
    d_http = max(1.0, float(p.get("delay") or 1.5))
    d_tg = max(3.0, float(p.get("delay") or 5))
    min_score = int(p.get("min_score") or 0)
    tg = None
    if mode != "http":
        tg = TgChecker(load_cfg())
        await tg.start()
    checked = read_set(CHECKED) if cache_on else set()
    cf = open(CHECKED, "a", encoding="utf-8")
    skips = 0
    try:
        for name in gen:
            if S["stop"]:
                break
            name = name.lower()
            if not ok_name(name):
                continue
            if name in checked:
                skips += 1
                if skips > 2000:
                    add("Новых вариантов не осталось")
                    break
                continue
            skips = 0
            status = "taken"
            if mode in ("http", "combo"):
                status = await http_check(name)
                if status == "error":
                    await asyncio.sleep(d_http)
                    continue
                await asyncio.sleep(d_http)
            if mode == "api" or (mode == "combo" and status == "free"):
                status = await tg.check(name)
                await asyncio.sleep(d_tg)
                if status == "error":
                    continue
            if status == "free" and score(name) < min_score:
                continue
            S["checks"] += 1
            if status == "free":
                sc = score(name)
                item = {"name": name, "score": sc, "label": label(sc), "ok": mode != "http"}
                S["found"].insert(0, item)
                add(f"СВОБОДЕН @{name} {item['label']} ({sc})")
                with open(FOUND, "a", encoding="utf-8") as f:
                    f.write(f"{name}\t{'api' if item['ok'] else 'http'}\t{sc}\n")
                if tg:
                    await tg.notify(f"Свободен: @{name} {item['label']} ({sc})")
                    if how in ("1", "2"):
                        try:
                            await tg.claim(name, how)
                            add(f"ЗАНЯТ @{name}")
                        except Exception as e:
                            add(f"claim ошибка: {e}")
            elif cache_on:
                checked.add(name)
                cf.write(name + "\n")
                cf.flush()
    finally:
        cf.close()
        if tg:
            await tg.stop()


def run_thread(p):
    S.update(running=True, stop=False, checks=0, t0=time.time(), err="")
    S["found"].clear()
    add("Старт")
    try:
        asyncio.run(worker(p))
    except Exception as e:
        S["err"] = str(e)
        add(f"Ошибка: {e}")
    S["running"] = False
    add("Остановлено")


def tg_login(step, p):
    from telethon import TelegramClient, errors
    cfg = load_cfg()

    async def go():
        c = TelegramClient("sniper", cfg["api_id"], cfg["api_hash"])
        await c.connect()
        try:
            if step == "code":
                r = await c.send_code_request(p["phone"].strip())
                cfg["phone"], cfg["hash"] = p["phone"].strip(), r.phone_code_hash
                save_cfg(cfg)
                return "Код отправлен в Telegram. Введи его ниже и нажми «Войти»"
            if p.get("password"):
                await c.sign_in(password=p["password"])
            else:
                try:
                    await c.sign_in(cfg["phone"], p["code"].strip(), phone_code_hash=cfg["hash"])
                except errors.SessionPasswordNeededError:
                    return "Нужен пароль 2FA: введи его и нажми «Войти» ещё раз"
            cfg["logged_in"] = True
            save_cfg(cfg)
            return "Вход выполнен ✓"
        finally:
            await c.disconnect()

    return asyncio.run(go())


def state():
    c = load_cfg()
    mins = max((time.time() - S["t0"]) / 60, 0.01) if S["t0"] else 1
    return {**S, "log": S["log"][-40:], "rate": round(S["checks"] / mins, 1),
            "has_api": bool(c.get("api_id") and c.get("api_hash")),
            "has_session": bool(c.get("logged_in"))}


PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0b1020"><title>Username Sniper</title><style>
:root{--bg:#0b1020;--card:#151b33;--line:#232b4d;--tx:#e8ecff;--mut:#8b94c4;--ac:#6c7bff;--ac2:#b06cff;--ok:#2ee59d;--bad:#ff5d7a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px system-ui,sans-serif;padding:env(safe-area-inset-top) 14px 40px}
h1{font-size:22px;margin:18px 0 4px;background:linear-gradient(90deg,var(--ac),var(--ac2));-webkit-background-clip:text;color:transparent}
.sub{color:var(--mut);margin-bottom:14px;font-size:13px}.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:14px;margin-bottom:12px}
label{display:block;color:var(--mut);font-size:12px;margin:10px 0 4px}select,input{width:100%;padding:12px;border-radius:12px;border:1px solid var(--line);background:#0f1530;color:var(--tx);font-size:15px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.st{background:#0f1530;border-radius:14px;padding:10px;text-align:center}.st b{display:block;font-size:22px}.st span{font-size:11px;color:var(--mut)}
button{width:100%;padding:15px;border:0;border-radius:14px;font-size:16px;font-weight:600;color:#fff;background:linear-gradient(90deg,var(--ac),var(--ac2));margin-top:12px}
button.stop{background:var(--bad)}button:disabled{opacity:.5}
.f{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}.f:last-child{border:0}
.f a{color:var(--ok);font-weight:600;text-decoration:none}.tag{font-size:12px;color:var(--mut)}
#log{font:12px monospace;color:var(--mut);max-height:170px;overflow:auto;white-space:pre-wrap}.warn{color:var(--bad);font-size:13px;margin-top:8px}
</style></head><body>
<h1>Username Sniper</h1><div class="sub" id="sub">загрузка…</div>
<div class="card"><div class="stats"><div class="st"><b id="c">0</b><span>проверено</span></div>
<div class="st"><b id="f" style="color:var(--ok)">0</b><span>найдено</span></div><div class="st"><b id="r">0</b><span>в минуту</span></div></div>
<button id="btn" onclick="toggle()">Запустить</button><div class="warn" id="err"></div></div>
<div class="card"><label>Как проверять</label><select id="mode"><option value="http">HTTP (без API)</option>
<option value="api">Telegram API</option><option value="combo">Комбо (HTTP + API)</option></select>
<label>Откуда имена</label><select id="source"><option value="imba">🔥 Имбовые</option><option value="pretty">Красивые</option>
<option value="pron">Произносимые</option><option value="random">Случайные буквы</option><option value="alnum">Буквы+цифры</option>
<option value="mask">По маске</option><option value="file">Из names.txt</option><option value="watch">Слежка за names.txt</option></select>
<div class="row"><div><label>Длина</label><input id="length" type="number" value="5" min="5" max="32"></div>
<div><label>Мин. рейтинг</label><input id="min_score" type="number" value="0"></div></div>
<div class="row"><div><label>Пауза, сек</label><input id="delay" type="number" value="1.5" step="0.5"></div>
<div><label>Маска (? # *)</label><input id="mask" placeholder="ab??#"></div></div>
<label>Найденное (нужен API)</label><select id="how"><option value="3">Только уведомить</option>
<option value="1">Занять каналом</option><option value="2">Поставить себе на аккаунт</option></select></div>
<div class="card"><b>Вход в Telegram (для API-режимов)</b>
<label>API ID</label><input id="aid" inputmode="numeric"><label>API HASH</label><input id="ah">
<label>Телефон (+7...)</label><input id="ph" inputmode="tel">
<button onclick="login('keys')">Сохранить ключи и получить код</button>
<label>Код из Telegram</label><input id="cd" inputmode="numeric"><label>Пароль 2FA (если есть)</label><input id="pw" type="password">
<button onclick="login('signin')">Войти</button><div class="tag" id="lm" style="margin-top:8px"></div></div>
<div class="card"><b>Найденные</b><div id="found"><div class="tag" style="margin-top:8px">пока пусто</div></div></div>
<div class="card"><b>Лог</b><div id="log"></div></div>
<script>
const $=i=>document.getElementById(i);let run=false;
async function toggle(){if(run){await fetch('/api/stop',{method:'POST'});return}
const p={};['mode','source','length','min_score','delay','mask','how'].forEach(k=>p[k]=$(k).value);
await fetch('/api/start',{method:'POST',body:JSON.stringify(p)})}
async function login(step){const b={step,api_id:$('aid').value,api_hash:$('ah').value,phone:$('ph').value,code:$('cd').value,password:$('pw').value};
$('lm').textContent='…';try{const r=await(await fetch('/api/login',{method:'POST',body:JSON.stringify(b)})).json();$('lm').textContent=r.msg}catch(e){$('lm').textContent='Ошибка связи'}}
async function tick(){try{const s=await(await fetch('/api/state')).json();run=s.running;
$('btn').textContent=run?'Остановить':'Запустить';$('btn').className=run?'stop':'';
$('c').textContent=s.checks;$('f').textContent=s.found.length;$('r').textContent=s.rate;
$('sub').textContent='API: '+(s.has_api?(s.has_session?'готов':'ключи есть, нужен вход в Telegram (карточка ниже)'):'нет ключей, работает HTTP-режим');
$('err').textContent=s.err;$('log').textContent=s.log.join('\\n');
if(s.found.length)$('found').innerHTML=s.found.map(x=>`<div class="f"><a href="https://t.me/${x.name}" target="_blank">@${x.name}</a><span class="tag">${x.label} · ${x.score} · ${x.ok?'API ✓':'HTTP'}</span></div>`).join('')}catch(e){}}
setInterval(tick,1000);tick();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype="application/json", code=200):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/api/state":
            self.send(json.dumps(state()))
        else:
            self.send(PAGE, "text/html")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode() if n else "{}"
        if self.path == "/api/start" and not S["running"]:
            p = json.loads(body or "{}")
            st = state()
            if p.get("mode") != "http" and not (st["has_api"] and st["has_session"]):
                S["err"] = "Для API-режима войди в Telegram (карточка ниже)"
            else:
                threading.Thread(target=run_thread, args=(p,), daemon=True).start()
        elif self.path == "/api/stop":
            S["stop"] = True
        elif self.path == "/api/login":
            p = json.loads(body or "{}")
            try:
                if p.get("api_id") and p.get("api_hash"):
                    c = load_cfg()
                    c["api_id"], c["api_hash"] = int(p["api_id"]), p["api_hash"].strip()
                    save_cfg(c)
                msg = tg_login("code" if p.get("step") == "keys" else "signin", p)
            except Exception as e:
                msg = f"Ошибка: {e}"
            self.send(json.dumps({"msg": msg}))
            return
        self.send("{}")


if __name__ == "__main__":
    print("Открой в браузере: http://127.0.0.1:8080  (Ctrl+C - выход)")
    ThreadingHTTPServer(("127.0.0.1", 8080), H).serve_forever()
