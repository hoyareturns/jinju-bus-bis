"""TAGO HTTPS transport. Public payloads never contain the service key or request URL."""
import json
import math
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode
from urllib.request import urlopen


class TagoError(Exception):
    def __init__(self, code, message):
        self.code = str(code)
        super().__init__(message)


def api_error(code):
    code = str(code)
    message = ('공공 API 인증키 또는 이용 권한을 확인해 주세요.' if code in {'20', '30', '31', '32', '401', '403'}
               else '공공 API 요청 한도를 초과했습니다.' if code in {'22', '29', '429'}
               else '공공 API가 오류를 반환했습니다.')
    return TagoError(code, message)


def parse_page(payload):
    if payload.lstrip().startswith('<'):
        match = re.search(r'<(?:resultCode|returnReasonCode)>\s*([^<]+)', payload)
        if match:
            raise api_error(match[1].strip())
        raise TagoError('FORMAT', '공공 API 응답 형식을 확인할 수 없습니다.')
    try:
        response = json.loads(payload)['response']
        header = response['header']
        code = str(header['resultCode'])
        if not header['resultMsg']:
            raise ValueError()
        if code == '03':
            return [], 0
        if code not in {'00', '0'}:
            raise api_error(code)
        body = response['body']
        total = int(body['totalCount'])
        container = body['items']
        if container in ('', None):
            items = []
        else:
            items = container.get('item', [])
            if items in ('', None):
                items = []
            if isinstance(items, dict):
                items = [items]
        if (not isinstance(items, list) or any(not isinstance(i, dict) for i in items)
                or total < 0 or len(items) > total or (total and not items)):
            raise ValueError()
        return items, total
    except TagoError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError):
        raise TagoError('FORMAT', '공공 API 응답 형식을 확인할 수 없습니다.') from None


def gps(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180 and (lat or lon):
            return lat, lon
    except (ValueError, TypeError):
        pass
    return None, None


def integer(value, default=-1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class TagoClient:
    def __init__(self, key, city='38030', transport=None, interval=0.25):
        self.key = unquote(key.strip())
        self.city = city
        self.transport = transport or self._http
        self.interval = interval
        self._lock = threading.Lock()
        self._next = 0
        self._history = {}

    @staticmethod
    def _http(url, timeout=8):
        deadline = time.monotonic() + timeout
        try:
            with urlopen(url, timeout=timeout) as response:
                chunks, size = [], 0
                while True:
                    if time.monotonic() >= deadline:
                        raise TagoError('TIMEOUT', '공공 API 응답 시간이 초과되었습니다.')
                    chunk = response.read1(65536)
                    if not chunk:
                        return b''.join(chunks).decode('utf-8-sig')
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > 4_000_000:
                        raise TagoError('FORMAT', '공공 API 응답이 너무 큽니다.')
        except HTTPError as error:
            raise api_error(error.code) from None
        except (URLError, TimeoutError, OSError, UnicodeError):
            raise TagoError('NETWORK', '공공 API 연결을 확인하고 다시 갱신해 주세요.') from None

    @staticmethod
    def _remaining(deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TagoError('TIMEOUT', '공공 API 조회 시간이 초과되었습니다.')
        return remaining

    def _pages(self, path, parameter, value, deadline=None):
        result = []
        deadline = min(deadline if deadline is not None else float('inf'), time.monotonic() + 25)
        for page_no in range(1, 21):
            self._remaining(deadline)
            url = 'https://apis.data.go.kr/1613000/' + path + '?' + urlencode({
                'serviceKey': self.key, 'cityCode': self.city, parameter: value,
                '_type': 'json', 'pageNo': page_no, 'numOfRows': 1000})
            for attempt in range(3):
                with self._lock:
                    time.sleep(min(self._remaining(deadline), max(0, self._next - time.monotonic())))
                    self._remaining(deadline)
                    self._next = time.monotonic() + self.interval
                try:
                    payload = self.transport(url, timeout=min(8, self._remaining(deadline)))
                    self._remaining(deadline)
                    items, total = parse_page(payload)
                    break
                except TagoError as error:
                    if error.code not in {'NETWORK', '01', '02', '04', '05', '99', '500', '502', '503', '504'} or attempt == 2:
                        raise
                    time.sleep(min(attempt + 1, self._remaining(deadline)))
            result.extend(items)
            if len(result) >= total:
                return result
        raise TagoError('PAGING', '공공 API 응답 페이지가 너무 많습니다.')

    def routes(self, bus, deadline=None):
        rows = self._pages('BusRouteInfoInqireService/getRouteNoList', 'routeNo', bus, deadline)
        routes = {}
        for row in rows:
            route_id = str(row.get('routeid') or '').strip()
            if str(row.get('routeno', '')).strip() == bus and route_id:
                start, end = str(row.get('startnodenm') or ''), str(row.get('endnodenm') or '')
                routes[route_id] = {'busNo': bus, 'routeId': route_id, 'startName': start,
                    'endName': end, 'directionLabel': f'{end} 방면' if end else '방향 정보 없음'}
        return list(routes.values())

    def stops(self, route_id, deadline=None):
        rows = self._pages('BusRouteInfoInqireService/getRouteAcctoThrghSttnList', 'routeId', route_id, deadline)
        stops = []
        for row in rows:
            order = integer(row.get('nodeord'))
            if order < 0:
                continue
            lat, lon = gps(row.get('gpslati'), row.get('gpslong'))
            stops.append({'nodeId': str(row.get('nodeid') or ''), 'nodeOrd': order,
                'name': str(row.get('nodenm') or ''), 'lat': lat, 'lon': lon})
        return sorted(stops, key=lambda row: row['nodeOrd'])

    def _bearing(self, key, lat, lon):
        now = time.monotonic()
        self._history = {k: v for k, v in self._history.items() if now - v[2] <= 120}
        if lat is None:
            self._history.pop(key, None)
            return None
        old = self._history.get(key)
        self._history[key] = (lat, lon, now)
        if not old or not 0 < now - old[2] <= 120:
            return None
        p1, p2 = math.radians(old[0]), math.radians(lat)
        delta = math.radians(lon - old[1])
        h = min(1, max(0, math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(delta/2)**2))
        distance = 6371000 * 2 * math.atan2(math.sqrt(h), math.sqrt(1-h))
        if distance < 5 or distance / (now-old[2]) > 45:
            return None
        return math.degrees(math.atan2(math.sin(delta)*math.cos(p2),
            math.cos(p1)*math.sin(p2)-math.sin(p1)*math.cos(p2)*math.cos(delta))) % 360

    def vehicles(self, route_id, deadline=None):
        rows = self._pages('BusLcInfoInqireService/getRouteAcctoBusLcList', 'routeId', route_id, deadline)
        vehicles = {}
        for row in rows:
            number = str(row.get('vehicleno') or '').strip()
            if not number:
                continue
            lat, lon = gps(row.get('gpslati'), row.get('gpslong'))
            key = f'{route_id}|{number}'
            vehicles[key] = {'id': key, 'vehicleNo': number, 'lat': lat, 'lon': lon,
                'nodeId': str(row.get('nodeid') or ''), 'nodeOrd': integer(row.get('nodeord')),
                'nodeName': str(row.get('nodenm') or ''), 'bearing': self._bearing(key, lat, lon)}
        return list(vehicles.values())
