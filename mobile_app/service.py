"""Shared public route cache, independent of browser selections and future accounts."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import threading
import time

from mobile_app.tago import TagoError, gps, integer


def timestamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


class BusService:
    def __init__(self, client, database, now=time.time):
        self.client, self.database, self.now = client, database, now
        self.registry, self.live, self.stop_cache = OrderedDict(), OrderedDict(), OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _put(cache, key, value):
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > 512:
            cache.popitem(last=False)

    def _variants(self, bus, deadline):
        cached = self.registry.get(bus)
        if cached and self.now() - cached[0] < 86400:
            return cached[1]
        if not self.client:
            raise TagoError('CONFIG', '실시간 조회를 사용하려면 서버에 TAGO_API_KEY를 설정해 주세요.')
        variants = self.client.routes(bus, deadline=deadline)
        self._put(self.registry, bus, (self.now(), variants))
        return variants

    def _run(self, buses, operation):
        if not buses:
            return {'generatedAt': timestamp(self.now()), 'routes': [], 'errors': []}
        if not self._lock.acquire(blocking=False):
            raise TagoError('BUSY', '다른 조회가 진행 중입니다. 잠시 후 자동으로 다시 조회합니다.')
        try:
            routes, errors = [], []
            deadline = time.monotonic() + 30
            for bus in buses:
                try:
                    if time.monotonic() >= deadline:
                        raise TagoError('TIMEOUT', '조회 시간이 초과되었습니다. 노선 수를 줄여 주세요.')
                    variants = self._variants(bus, deadline)
                    if not variants:
                        errors.append({'busNo': bus, 'code': 'NOT_FOUND', 'message': '노선 정보 없음'})
                    for route in variants:
                        try:
                            if time.monotonic() >= deadline:
                                raise TagoError('TIMEOUT', '조회 시간이 초과되었습니다. 잠시 후 다시 갱신합니다.')
                            routes.append(operation(route, deadline))
                        except TagoError as error:
                            errors.append({'busNo': bus, 'routeId': route['routeId'], 'code': error.code, 'message': str(error)})
                            if operation == self._location:
                                routes.append(self._failed_location(route, error))
                            else:
                                routes.append(self._fallback_stops(route, str(error)))
                except TagoError as error:
                    errors.append({'busNo': bus, 'code': error.code, 'message': str(error)})
            return {'generatedAt': timestamp(self.now()), 'routes': routes, 'errors': errors}
        finally:
            self._lock.release()

    def locations(self, buses):
        return self._run(buses, self._location)

    def routes(self, buses):
        return self._run(buses, self._stops)

    def _location(self, route, deadline):
        cached = self.live.get(route['routeId'])
        if cached and self.now() - cached[0] < 12:
            return deepcopy(cached[1])
        vehicles = self.client.vehicles(route['routeId'], deadline=deadline)
        result = {**route, 'vehicles': vehicles, 'updatedAt': timestamp(self.now()),
            'stale': False, 'status': 'ok', 'message': None if vehicles else '현재 조회되는 차량 없음'}
        self._put(self.live, route['routeId'], (self.now(), result))
        return deepcopy(result)

    def _failed_location(self, route, error):
        cached = self.live.get(route['routeId'])
        result = deepcopy(cached[1]) if cached else {**route, 'vehicles': [], 'updatedAt': None}
        result.update(stale=True, status='error', message=str(error))
        for vehicle in result['vehicles']:
            vehicle['bearing'] = None
        return result

    def _stops(self, route, deadline):
        cached = self.stop_cache.get(route['routeId'])
        if cached and self.now() - cached[0] < 86400:
            return deepcopy(cached[1])
        result = {**route, 'stops': self.client.stops(route['routeId'], deadline=deadline), 'source': 'tago', 'stale': False}
        self._put(self.stop_cache, route['routeId'], (self.now(), result))
        return deepcopy(result)

    def _fallback_stops(self, route, message):
        cached = self.stop_cache.get(route['routeId'])
        if cached:
            return {**deepcopy(cached[1]), 'stale': True, 'message': message}
        nodes = self.database.get(route['busNo'], {}).get(route['routeId'], [])
        stops = []
        for node in nodes:
            lat, lon = gps(node.get('gpslati'), node.get('gpslong'))
            stops.append({'nodeOrd': integer(node.get('nodeord')), 'name': str(node.get('nodenm', '')),
                'lat': lat, 'lon': lon})
        return {**route, 'stops': sorted(stops, key=lambda row: row['nodeOrd']), 'source': 'bundled',
            'stale': True, 'message': message}
