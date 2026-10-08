"""Persistent, device-owned arrival alarms. Run one worker per database.

Delivery is at most once per alarm/window: an ambiguous send failure is exposed,
never retried into duplicate notifications. Browser tokens are stored as hashes.
"""
import base64
from datetime import datetime, time as day_time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
import weakref
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


UTC = timezone.utc
MAX_CLIENTS = 2000
MAX_ALARMS = 20
PUSH_HOSTS = {'fcm.googleapis.com', 'updates.push.services.mozilla.com', 'web.push.apple.com'}


def _b64(value, length):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}', value):
        raise ValueError('알림 구독 키가 올바르지 않습니다.')
    try:
        result = base64.b64decode(value.rstrip('=') + '=' * (-len(value.rstrip('=')) % 4),
                                  altchars=b'-_', validate=True)
    except (ValueError, TypeError):
        raise ValueError('알림 구독 키가 올바르지 않습니다.') from None
    if len(result) != length:
        raise ValueError('알림 구독 키가 올바르지 않습니다.')
    return result


def _subscription(value):
    if not isinstance(value, dict):
        raise ValueError('브라우저의 알림 구독이 필요합니다.')
    endpoint = value.get('endpoint')
    if not isinstance(endpoint, str) or not 1 <= len(endpoint) <= 4096:
        raise ValueError('알림 구독 주소가 올바르지 않습니다.')
    try:
        parsed = urlsplit(endpoint)
        valid = (parsed.scheme == 'https' and parsed.hostname in PUSH_HOSTS
                 and parsed.port in (None, 443) and not parsed.username and not parsed.password
                 and parsed.path.startswith('/') and not parsed.fragment
                 and not any(ord(char) <= 32 or char == '\\' for char in endpoint))
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('지원하지 않는 알림 구독 주소입니다.')
    keys = value.get('keys')
    if not isinstance(keys, dict):
        raise ValueError('알림 구독 키가 필요합니다.')
    _b64(keys.get('auth'), 16)
    if _b64(keys.get('p256dh'), 65)[0] != 4:
        raise ValueError('알림 구독 키가 올바르지 않습니다.')
    return {'endpoint': endpoint, 'keys': {'auth': keys['auth'], 'p256dh': keys['p256dh']}}


def _text(value, limit=120):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError('알림 설정을 확인해 주세요.')
    return value.strip()


def _active_window(rule, now):
    local = now.astimezone(ZoneInfo(rule['timezone']))
    start = day_time.fromisoformat(rule['startTime'])
    end = day_time.fromisoformat(rule['endTime'])
    date = local.date()
    if end < start and local.time() < end:
        date -= timedelta(days=1)
    begins = datetime.combine(date, start, local.tzinfo)
    ends = datetime.combine(date + timedelta(days=int(end < start)), end, local.tzinfo)
    if date.weekday() in rule['days'] and begins <= local < ends:
        return date.isoformat(), ends.astimezone(UTC)
    return None


class AlertManager:
    def __init__(self, path, service, public_key='', private_key='', subject='',
                 base_path='/apps/bus/', sender=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.service = service
        self.public_key, self.private_key, self.subject = public_key, private_key, subject
        self.base_path = base_path
        self._lock = threading.RLock()
        self._alarm_locks = weakref.WeakValueDictionary()
        self._stop = threading.Event()
        self._thread = None
        self._worker_file = None
        self._sender = sender
        self._reason = ''
        if sender is None:
            self._configure_sender()
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS clients (
                    token_hash TEXT PRIMARY KEY, subscription TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS alarms (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES clients(token_hash),
                    rule TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
                    delivery_status TEXT NOT NULL DEFAULT 'pending', last_sent_at TEXT);
                CREATE INDEX IF NOT EXISTS alarms_owner ON alarms(owner);
                CREATE TABLE IF NOT EXISTS deliveries (
                    alarm_id TEXT NOT NULL REFERENCES alarms(id) ON DELETE CASCADE,
                    window_date TEXT NOT NULL, PRIMARY KEY(alarm_id, window_date));
                CREATE INDEX IF NOT EXISTS deliveries_window ON deliveries(window_date);
            ''')

    def _configure_sender(self):
        if not all((self.public_key, self.private_key, self.subject)):
            self._reason = '서버에 Web Push 알림 키와 운영자 연락처가 설정되지 않았습니다.'
            return
        try:
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
            from pywebpush import webpush
            import requests
            private = ec.derive_private_key(int.from_bytes(_b64(self.private_key, 32), 'big'), ec.SECP256R1())
            public = private.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
            if public != _b64(self.public_key, 65):
                raise ValueError()
            if not (re.fullmatch(r'mailto:[^\s@]+@[^\s@]+\.[^\s@]+', self.subject)
                    or (urlsplit(self.subject).scheme == 'https' and urlsplit(self.subject).hostname)):
                raise ValueError()

            class NoRedirectSession(requests.Session):
                def request(self, method, url, **kwargs):
                    kwargs['allow_redirects'] = False
                    return super().request(method, url, **kwargs)

            def send(**kwargs):
                # Construct transport only when sending, never during import/startup.
                with NoRedirectSession() as session:
                    response = webpush(**kwargs, requests_session=session)
                    if not 200 <= response.status_code < 300:
                        raise RuntimeError('push delivery failed')
                    return response
            self._sender = send
        except ImportError:
            self._reason = '서버에 Web Push 알림 라이브러리가 설치되지 않았습니다.'
        except (ValueError, TypeError):
            self._reason = '서버의 Web Push 알림 키 또는 운영자 연락처를 확인해 주세요.'

    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        # sqlite connection context managers commit but do not close connections.
        from contextlib import closing, contextmanager
        @contextmanager
        def connection():
            with closing(db), db:
                yield db
        return connection()

    def config(self):
        available = self._sender is not None
        return {'available': available, 'publicKey': self.public_key if available else '',
                'reason': self._reason or None}

    @staticmethod
    def _authorize(db, token):
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            raise PermissionError('이 브라우저의 알림 인증을 다시 설정해 주세요.')
        digest = hashlib.sha256(token.encode()).hexdigest()
        if not db.execute('SELECT 1 FROM clients WHERE token_hash=?', (digest,)).fetchone():
            raise PermissionError('이 브라우저의 알림 인증을 다시 설정해 주세요.')
        return digest

    def create_client(self):
        with self._lock, self._db() as db:
            if db.execute('SELECT COUNT(*) FROM clients').fetchone()[0] >= MAX_CLIENTS:
                raise ValueError('알림 등록 가능 수를 초과했습니다. 운영자에게 문의해 주세요.')
            token = secrets.token_urlsafe(32)
            db.execute('INSERT INTO clients(token_hash, created_at) VALUES(?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), datetime.now(UTC).isoformat()))
            return token

    @staticmethod
    def _public(row):
        status = row['delivery_status']
        return {'id': row['id'], 'rule': json.loads(row['rule']), 'enabled': bool(row['enabled']),
                'deliveryStatus': 'delivery_unknown' if status == 'sending' else status,
                'lastSentAt': row['last_sent_at']}

    def get(self, token):
        with self._lock, self._db() as db:
            owner = self._authorize(db, token)
            return {'alarms': [self._public(row) for row in db.execute(
                'SELECT * FROM alarms WHERE owner=? ORDER BY rowid', (owner,))]}

    def _alarm_lock(self, alarm_id):
        # Only a send/update/delete for this alarm waits on its delivery. Weak
        # references keep deleted alarm IDs from accumulating for this process.
        with self._lock:
            lock = self._alarm_locks.get(alarm_id)
            if lock is None:
                lock = threading.RLock()
                self._alarm_locks[alarm_id] = lock
            return lock

    @staticmethod
    def _editable_alarm(db, owner, alarm_id):
        if alarm_id is not None:
            if not isinstance(alarm_id, str):
                raise ValueError('알림을 확인해 주세요.')
            existing = db.execute('SELECT * FROM alarms WHERE id=? AND owner=?', (alarm_id, owner)).fetchone()
            if existing is None:
                raise PermissionError('이 브라우저에 등록한 알림만 변경할 수 있습니다.')
            return existing
        if db.execute('SELECT COUNT(*) FROM alarms WHERE owner=?', (owner,)).fetchone()[0] >= MAX_ALARMS:
            raise ValueError('알림은 브라우저별 최대 20개까지 등록할 수 있습니다.')
        return None

    def _rule(self, payload):
        rule = payload.get('rule')
        registered = payload.get('registeredBuses')
        if (not isinstance(rule, dict) or not isinstance(registered, list)
                or not 1 <= len(registered) <= 10
                or any(not isinstance(bus, str) or not re.fullmatch(r'[0-9A-Za-z가-힣-]{1,20}', bus) for bus in registered)):
            raise ValueError('등록한 버스와 알림 설정을 확인해 주세요.')
        bus = rule.get('busNo')
        if not isinstance(bus, str) or bus not in registered:
            raise ValueError('등록한 버스만 알림을 설정할 수 있습니다.')
        for field in ('startTime', 'endTime'):
            if not isinstance(rule.get(field), str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', rule[field]):
                raise ValueError('알림 시간을 확인해 주세요.')
        days = rule.get('days')
        if (rule['startTime'] == rule['endTime'] or rule.get('timezone') != 'Asia/Seoul'
                or not isinstance(days, list) or not 1 <= len(days) <= 7
                or any(type(day) is not int or not 0 <= day <= 6 for day in days)
                or len(set(days)) != len(days)):
            raise ValueError('알림 시간과 반복 요일을 확인해 주세요.')
        name = _text(rule.get('stopName'))
        label = _text(rule.get('directionLabel'), 300)
        targets = rule.get('targets')
        if not isinstance(targets, list) or not 1 <= len(targets) <= 30:
            raise ValueError('알림 정류장을 선택해 주세요.')
        normalized = []
        for target in targets:
            if not isinstance(target, dict) or type(target.get('nodeOrd')) is not int or not 0 <= target['nodeOrd'] <= 10000:
                raise ValueError('알림 정류장을 확인해 주세요.')
            route_id = _text(target.get('routeId'))
            node_id = target.get('nodeId', '')
            if not isinstance(node_id, str) or len(node_id) > 120:
                raise ValueError('알림 정류장을 확인해 주세요.')
            normalized.append({'routeId': route_id, 'nodeOrd': target['nodeOrd'], 'nodeId': node_id})
        if len({target['nodeId'] for target in normalized}) > 1:
            raise ValueError('같은 정류장을 지나는 노선만 하나의 알림으로 등록할 수 있습니다.')
        # Only the selected registered bus reaches TAGO. Client route IDs never do.
        result = self.service.routes([bus])
        routes = {row['routeId']: row for row in result.get('routes', []) if row.get('busNo') == bus
                  and row.get('source') == 'tago' and row.get('stale') is False}
        for target in normalized:
            route = routes.get(target['routeId'])
            if not route or not any(stop.get('nodeOrd') == target['nodeOrd']
                    and str(stop.get('nodeId') or '') == target['nodeId'] and stop.get('name') == name
                    for stop in route.get('stops', [])):
                raise ValueError('최신 노선에서 해당 정류장을 확인할 수 없습니다. 정류장을 다시 선택해 주세요.')
        if len({(target['routeId'], target['nodeOrd']) for target in normalized}) != len(normalized):
            raise ValueError('중복된 알림 정류장입니다.')
        return {'busNo': bus, 'directionLabel': label, 'stopName': name, 'targets': normalized,
                'startTime': rule['startTime'], 'endTime': rule['endTime'],
                'days': sorted(days), 'timezone': 'Asia/Seoul'}

    def save(self, token, payload):
        with self._lock, self._db() as db:
            owner = self._authorize(db, token)
            if not isinstance(payload, dict):
                raise ValueError('알림 설정을 확인해 주세요.')
            requested_id = payload.get('id')
            self._editable_alarm(db, owner, requested_id)
        if not self.config()['available']:
            raise ValueError(self._reason)
        subscription = _subscription(payload.get('subscription'))
        # Fresh route validation may take 30 seconds. Never hold shared locks
        # across TAGO or web-push requests.
        rule = self._rule(payload)
        alarm_id = requested_id or secrets.token_urlsafe(16)
        with self._alarm_lock(alarm_id), self._lock, self._db() as db:
            # Recheck after I/O: another request may have deleted this alarm or
            # filled the client's capacity while validation was outstanding.
            owner = self._authorize(db, token)
            existing = self._editable_alarm(db, owner, requested_id)
            db.execute('UPDATE clients SET subscription=? WHERE token_hash=?', (json.dumps(subscription), owner))
            if existing:
                db.execute('UPDATE alarms SET rule=?, enabled=1, delivery_status=? WHERE id=?',
                           (json.dumps(rule, ensure_ascii=False), existing['delivery_status']
                            if existing['enabled'] else 'pending', alarm_id))
            else:
                db.execute('INSERT INTO alarms(id,owner,rule) VALUES(?,?,?)',
                           (alarm_id, owner, json.dumps(rule, ensure_ascii=False)))
            return self._public(db.execute('SELECT * FROM alarms WHERE id=?', (alarm_id,)).fetchone())

    def delete(self, token, alarm_id):
        with self._lock, self._db() as db:
            owner = self._authorize(db, token)
            if not isinstance(alarm_id, str):
                raise PermissionError('이 브라우저에 등록한 알림만 삭제할 수 있습니다.')
            self._editable_alarm(db, owner, alarm_id)
        # Once a push is already being sent it cannot be recalled; wait for
        # that one send before acknowledging deletion. No unrelated API waits.
        with self._alarm_lock(alarm_id), self._lock, self._db() as db:
            if not db.execute(
                    'DELETE FROM alarms WHERE id=? AND owner=?', (alarm_id, owner)).rowcount:
                raise PermissionError('이 브라우저에 등록한 알림만 삭제할 수 있습니다.')
        return {'deleted': True}

    @staticmethod
    def _arrived(rule, routes, now):
        for route in routes:
            if route.get('busNo') != rule['busNo'] or route.get('status') != 'ok' or route.get('stale') is not False:
                continue
            try:
                updated = datetime.fromisoformat(route['updatedAt'])
                if updated.tzinfo is None or not 0 <= (now - updated).total_seconds() <= 90:
                    continue
            except (ValueError, TypeError, KeyError):
                continue
            for target in rule['targets']:
                if route.get('routeId') != target['routeId']:
                    continue
                for vehicle in route.get('vehicles', []):
                    if vehicle.get('nodeOrd') == target['nodeOrd'] and (
                            not target['nodeId'] or vehicle.get('nodeId') == target['nodeId']):
                        return True
        return False

    def tick(self, now=None):
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError('tick requires a timezone-aware datetime')
        if self._sender is None:
            return
        started = time.monotonic()
        today = now.astimezone(ZoneInfo('Asia/Seoul')).date()
        with self._lock, self._db() as db:
            rows = db.execute('SELECT alarms.*,clients.subscription FROM alarms JOIN clients '
                              'ON alarms.owner=clients.token_hash WHERE enabled=1 AND subscription IS NOT NULL').fetchall()
            reserved_rows = db.execute('SELECT alarm_id,window_date FROM deliveries WHERE window_date BETWEEN ? AND ?',
                ((today - timedelta(days=1)).isoformat(), today.isoformat())).fetchall()
        reserved = {(row['alarm_id'], row['window_date']) for row in reserved_rows}
        active = []
        for row in rows:
            rule = json.loads(row['rule'])
            window = _active_window(rule, now)
            if window and (row['id'], window[0]) not in reserved:
                active.append((row, rule, window))
        live = {}
        for row, rule, window in active:
            if self._stop.is_set():
                break
            bus = rule['busNo']
            if bus not in live:
                try:
                    live[bus] = self.service.locations([bus]).get('routes', [])
                except Exception:
                    live[bus] = []
            with self._alarm_lock(row['id']):
                current = now + timedelta(seconds=time.monotonic() - started)
                if self._stop.is_set() or current >= window[1] or not self._arrived(rule, live[bus], current):
                    continue
                with self._lock, self._db() as db:
                    # Atomically reserve before external send; restarts cannot duplicate it.
                    fresh = db.execute('SELECT alarms.*,clients.subscription FROM alarms JOIN clients '
                        'ON alarms.owner=clients.token_hash WHERE alarms.id=? AND enabled=1 '
                        'AND subscription IS NOT NULL', (row['id'],)).fetchone()
                    if fresh is None or fresh['rule'] != row['rule']:
                        continue
                    row = fresh
                    inserted = db.execute('INSERT OR IGNORE INTO deliveries VALUES(?,?)', (row['id'], window[0])).rowcount
                    if not inserted:
                        continue
                    db.execute("UPDATE alarms SET delivery_status='sending' WHERE id=?", (row['id'],))
                    db.execute('DELETE FROM deliveries WHERE window_date<?', ((current.date() - timedelta(days=366)).isoformat(),))
                expiry = min(current + timedelta(seconds=60), window[1])
                data = {'title': f"{rule['busNo']}번 버스 도착", 'body': f"{rule['directionLabel']} · {rule['stopName']} 도착이 확인되었습니다.",
                        'url': self.base_path, 'tag': 'bus-arrival-' + row['id'],
                        'alarmId': row['id'], 'expiresAt': expiry.isoformat()}
                try:
                    response = self._sender(subscription_info=json.loads(row['subscription']),
                        data=json.dumps(data, ensure_ascii=False), ttl=max(0, int((expiry-current).total_seconds())),
                        timeout=8, vapid_private_key=self.private_key, vapid_claims={'sub': self.subject},
                        headers={'Urgency': 'high'})
                    if response is not None and hasattr(response, 'status_code') and not 200 <= response.status_code < 300:
                        error = RuntimeError('push delivery failed')
                        error.response = response
                        raise error
                except Exception as error:
                    expired = getattr(getattr(error, 'response', None), 'status_code', None) in (404, 410)
                    with self._lock, self._db() as db:
                        if expired:
                            cleared = db.execute('UPDATE clients SET subscription=NULL WHERE token_hash=? '
                                'AND subscription=?', (row['owner'], row['subscription'])).rowcount
                            if cleared:
                                db.execute("UPDATE alarms SET enabled=0,delivery_status='subscription_expired' WHERE owner=?", (row['owner'],))
                            else:
                                db.execute("UPDATE alarms SET delivery_status='failed' WHERE id=?", (row['id'],))
                        else:
                            db.execute("UPDATE alarms SET delivery_status='failed' WHERE id=?", (row['id'],))
                else:
                    with self._lock, self._db() as db:
                        db.execute("UPDATE alarms SET delivery_status='sent',last_sent_at=? WHERE id=?", (current.isoformat(), row['id']))

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            if self._sender is None:
                return
            # OS lock is released if the process exits; no stale lease after restart.
            lock_file = open(str(self.path) + '.worker.lock', 'a+b')
            try:
                lock_file.seek(0)
                if __import__('os').name == 'nt':
                    import msvcrt
                    if not lock_file.read(1):
                        lock_file.write(b'0')
                        lock_file.flush()
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                lock_file.close()
                raise RuntimeError('알림 작업자가 이미 실행 중입니다.') from None
            self._worker_file = lock_file
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name='bus-arrival-alerts', daemon=True)
            self._thread.start()

    def _run(self):
        try:
            while not self._stop.is_set():
                try:
                    self.tick()
                except Exception:
                    # No endpoints, browser secrets, VAPID keys, or raw errors in logs.
                    pass
                self._stop.wait(15)
        finally:
            if self._worker_file:
                self._worker_file.close()
                self._worker_file = None

    def stop(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=40)
