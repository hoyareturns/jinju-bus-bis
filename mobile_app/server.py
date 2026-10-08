"""Portable same-origin web/API host. Run: python -m mobile_app.server."""
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, unquote, urlsplit

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mobile_app.service import BusService
from mobile_app.tago import TagoClient, TagoError

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / 'static'
VERSION = '2.1.0'
BUS_PATTERN = re.compile(r'[0-9A-Za-z가-힣-]{1,16}')


@dataclass(frozen=True)
class Config:
    base_path: str = '/apps/bus/'
    hub_path: str = '/'
    api_key: str = ''
    city_code: str = '38030'
    public_origin: str = ''

    def __post_init__(self):
        base = self.base_path
        if not re.fullmatch(r'/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]*', base):
            raise ValueError('BUS_BASE_PATH must be / or a slash-separated URL path')
        hub = urlsplit(self.hub_path)
        if (not self.hub_path or hub.scheme or hub.netloc or '\\' in self.hub_path
                or '%' in self.hub_path or any(ord(c) < 32 for c in self.hub_path)
                or self.hub_path.startswith('//')):
            raise ValueError('HUB_PATH must be a same-origin relative URL path')
        if not self.city_code.isdigit():
            raise ValueError('CITY_CODE must be numeric')
        object.__setattr__(self, 'base_path', base.rstrip('/') + '/')
        if self.public_origin:
            origin = urlsplit(self.public_origin)
            if origin.scheme != 'https' or not origin.hostname or origin.path or origin.query or origin.fragment or origin.username:
                raise ValueError('BUS_PUBLIC_ORIGIN must be an HTTPS origin without a path')

    @classmethod
    def from_env(cls):
        return cls(base_path=os.environ.get('BUS_BASE_PATH', '/apps/bus/'),
                   hub_path=os.environ.get('HUB_PATH', '/'),
                   api_key=os.environ.get('TAGO_API_KEY', os.environ.get('API_KEY', '')).strip(),
                   city_code=os.environ.get('CITY_CODE', '38030'),
                   public_origin=os.environ.get('BUS_PUBLIC_ORIGIN', '').rstrip('/'))


def parse_buses(query):
    params = parse_qs(query, keep_blank_values=True, max_num_fields=10)
    values = params.get('buses', ['10'])
    if len(values) != 1 or set(params) - {'buses'}:
        raise ValueError('buses 파라미터 하나만 사용할 수 있습니다.')
    buses = list(dict.fromkeys(bus.strip() for bus in values[0].split(',') if bus.strip()))
    if len(buses) > 10 or any(not BUS_PATTERN.fullmatch(bus) for bus in buses):
        raise ValueError('노선은 16자 이내의 번호로 최대 10개까지 조회할 수 있습니다.')
    return buses


def create_server(config=None, host='127.0.0.1', port=8765, service=None, alert_manager=None):
    config = config or Config.from_env()
    database = json.loads((APP_DIR.parent / 'bus_data.json').read_text(encoding='utf-8'))
    service = service or BusService(TagoClient(config.api_key, config.city_code) if config.api_key else None, database)
    base = config.base_path

    class Handler(BaseHTTPRequestHandler):
        server_version = 'JinjuBus'

        def log_message(self, *_args):
            # Do not log query strings, credentials, headers, or upstream URLs.
            pass

        def respond(self, status, body, content_type='application/json; charset=utf-8', extra=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
            elif isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store' if content_type.startswith('application/json') else 'no-cache')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != 'HEAD':
                try:
                    self.wfile.write(body)
                except ConnectionError:
                    pass

        def do_HEAD(self):
            self.do_GET()

        def alert_request(self, relative, mutation=False):
            manager = self.server.alert_manager
            if not manager:
                self.respond(503, {'error': '서버 알림이 준비되지 않았습니다.'})
                return
            try:
                incoming = None
                if self.command == 'POST':
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 1 <= length <= 65536 or self.headers.get('Transfer-Encoding'):
                        raise ValueError('알림 요청 크기가 올바르지 않습니다.')
                    self.connection.settimeout(10)
                    incoming = self.rfile.read(length)
                if mutation:
                    expected = config.public_origin or f'http://127.0.0.1:{self.server.server_port}'
                    allowed = {expected}
                    if not config.public_origin:
                        allowed.add(f'http://localhost:{self.server.server_port}')
                    if self.headers.get('Origin') not in allowed:
                        self.respond(403, {'error': '같은 앱 화면에서 요청해 주세요.'})
                        return
                auth = self.headers.get('Authorization', '')
                token = auth[7:] if auth.startswith('Bearer ') else ''
                if self.command == 'POST':
                    if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                        raise ValueError('JSON 요청이 필요합니다.')
                    payload = json.loads(incoming)
                    if not isinstance(payload, dict):
                        raise ValueError('알림 설정이 올바르지 않습니다.')
                    if relative == 'api/alerts/session':
                        self.respond(201, {'token': manager.create_client()})
                    elif relative == 'api/alerts':
                        self.respond(200, manager.save(token, payload))
                    else:
                        self.respond(404, {'error': '알림 경로를 찾을 수 없습니다.'})
                elif self.command == 'DELETE' and relative.startswith('api/alerts/'):
                    manager.delete(token, relative[len('api/alerts/'):])
                    self.respond(200, {'deleted': True})
                elif self.command in ('GET', 'HEAD') and relative == 'api/alerts':
                    self.respond(200, manager.get(token))
                else:
                    self.respond(404, {'error': '알림 경로를 찾을 수 없습니다.'})
            except PermissionError:
                self.respond(401, {'error': '이 브라우저의 알림 설정을 확인해 주세요.'})
            except (ValueError, KeyError, TypeError):
                self.respond(400, {'error': '알림 설정 또는 구독 정보를 확인해 주세요.'})
            except TagoError as error:
                self.respond(503, {'error': str(error)})
            except TimeoutError:
                self.respond(408, {'error': '알림 요청 시간이 초과되었습니다.'})

        def do_POST(self):
            path = urlsplit(self.path).path
            if not path.startswith(base + 'api/alerts'):
                self.respond(404, {'error': '알림 경로를 찾을 수 없습니다.'})
                return
            self.alert_request(path[len(base):], mutation=True)

        do_DELETE = do_POST

        def do_GET(self):
            if len(self.path) > 2048:
                self.respond(414, {'error': '요청 주소가 너무 깁니다.'})
                return
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            if base != '/' and path == base.rstrip('/'):
                self.respond(308, b'', extra={'Location': base})
                return
            if not path.startswith(base):
                self.respond(404, {'error': '이 앱의 경로가 아닙니다.'})
                return
            relative = path[len(base):]
            if relative == 'api/push/config':
                manager = self.server.alert_manager
                self.respond(200, manager.config() if manager else {'available': False, 'publicKey': '', 'reason': '서버 알림이 준비되지 않았습니다.'})
                return
            if relative == 'api/alerts':
                self.alert_request(relative)
                return
            if '\\' in relative or any(p in ('.', '..') for p in relative.split('/')):
                self.respond(404, {'error': '파일을 찾을 수 없습니다.'})
                return
            if relative == 'api/bootstrap':
                self.respond(200, {'name': '진주 버스', 'version': VERSION, 'basePath': base,
                    'hubPath': config.hub_path, 'defaultBuses': ['10'], 'defaultCenter': [35.18, 128.1076],
                    'refreshSeconds': 15, 'apiConfigured': bool(config.api_key), 'storageMode': 'device',
                    'authentication': 'anonymous', 'accountSync': False,
                    'availableBuses': sorted(database, key=lambda value: (len(value), value))})
                return
            if relative == 'api/health':
                self.respond(200, {'status': 'ok', 'version': VERSION, 'apiConfigured': bool(config.api_key),
                    'upstreamVerified': False, 'basePath': base})
                return
            if relative in ('api/v2/locations', 'api/v2/routes'):
                try:
                    buses = parse_buses(parsed.query)
                    if buses and not config.api_key:
                        self.respond(503, {'error': '실시간 조회를 사용하려면 서버에 TAGO_API_KEY를 설정해 주세요.', 'code': 'CONFIG'})
                        return
                    result = service.locations(buses) if relative.endswith('/locations') else service.routes(buses)
                    self.respond(200, result)
                except ValueError as error:
                    self.respond(400, {'error': str(error)})
                except TagoError as error:
                    self.respond(503, {'error': str(error), 'code': error.code}, extra={'Retry-After': '15'})
                return
            if relative in ('manifest.webmanifest', 'app-manifest.json'):
                source = STATIC_DIR / relative
                if not source.exists():
                    self.respond(404, {'error': '연동 자료가 준비되지 않았습니다.'})
                    return
                data = json.loads(source.read_text(encoding='utf-8'))
                if relative == 'app-manifest.json':
                    data.update(launchPath=base, banner=base+'assets/banner.svg', icon=base+'assets/icon.svg',
                        healthPath=base+'api/health', version=VERSION)
                else:
                    data.update(id=base, start_url=base, scope=base)
                    for icon in data['icons']:
                        icon['src'] = base + 'assets/icon.svg'
                self.respond(200, data, 'application/manifest+json; charset=utf-8' if relative.endswith('webmanifest') else 'application/json; charset=utf-8')
                return
            if relative.startswith('api/'):
                self.respond(404, {'error': '지원하지 않는 API입니다.'})
                return
            filename = relative or 'index.html'
            allowed = {'index.html', 'app.js', 'state.mjs', 'stops.mjs', 'alarm-panel.mjs', 'styles.css', 'sw.js', 'worker-policy.js'}
            candidate = (STATIC_DIR / filename).resolve()
            if (filename not in allowed and not filename.startswith(('assets/', 'vendor/'))
                    or not candidate.is_relative_to(STATIC_DIR.resolve()) or not candidate.is_file()):
                self.respond(404, {'error': '파일을 찾을 수 없습니다.'})
                return
            mime = {'.mjs': 'text/javascript', '.js': 'text/javascript', '.svg': 'image/svg+xml'}.get(candidate.suffix)
            mime = mime or mimetypes.guess_type(str(candidate))[0] or 'application/octet-stream'
            extra = {'Service-Worker-Allowed': base} if filename == 'sw.js' else None
            self.respond(200, candidate.read_bytes(), mime, extra)

    server = ThreadingHTTPServer((host, port), Handler)
    server.bus_service = service
    server.alert_manager = alert_manager
    return server


def main():
    config = Config.from_env()
    host, port = os.environ.get('HOST', '127.0.0.1'), int(os.environ.get('PORT', '8765'))
    server = create_server(config, host, port)
    from mobile_app.alerts import AlertManager
    manager = AlertManager(Path(os.environ.get('BUS_DATA_DIR', str(APP_DIR / '.state'))) / 'alerts.sqlite3',
        server.bus_service, public_key=os.environ.get('VAPID_PUBLIC_KEY', ''),
        private_key=os.environ.get('VAPID_PRIVATE_KEY', ''), subject=os.environ.get('VAPID_SUBJECT', ''),
        base_path=config.base_path)
    server.alert_manager = manager
    manager.start()
    print(f'Jinju Bus {VERSION}: http://{host}:{port}{config.base_path}', flush=True)
    print('Live API configured: ' + ('yes' if config.api_key else 'no'), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop()
        server.server_close()


if __name__ == '__main__':
    main()
