import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from mobile_app.tago import TagoClient, TagoError, parse_page
from mobile_app.service import BusService


def page(items, total=None, code="00"):
    return json.dumps({"response": {"header": {"resultCode": code, "resultMsg": "NORMAL SERVICE"},
        "body": {"items": {"item": items}, "totalCount": len(items) if total is None else total}}})


class TagoTests(unittest.TestCase):
    def test_single_item_and_empty_success(self):
        self.assertEqual(parse_page(page({"routeid": "R1"}, 1)), ([{"routeid": "R1"}], 1))
        self.assertEqual(parse_page(page([], 0)), ([], 0))

    def test_http_200_errors_and_incomplete_data_are_not_empty_success(self):
        for payload in [page([], 0, "30"), "<returnReasonCode>22</returnReasonCode>",
                        page([], 3), '{}', page([], -1)]:
            with self.subTest(payload=payload), self.assertRaises(TagoError):
                parse_page(payload)

    def test_all_pages_exact_match_and_key_encoded_once(self):
        urls = []
        def transport(url, timeout=8):
            urls.append(url)
            query = parse_qs(urlsplit(url).query)
            self.assertEqual(query['serviceKey'], ['a+b/c='])
            if query['pageNo'] == ['1']:
                return page([{'routeid': 'R1', 'routeno': '10'}, {'routeid': 'RX', 'routeno': '100'}], 3)
            return page([{'routeid': 'R2', 'routeno': '10', 'endnodenm': '종점'}], 3)
        client = TagoClient('a%2Bb%2Fc%3D', transport=transport, interval=0)
        self.assertEqual([r['routeId'] for r in client.routes('10')], ['R1', 'R2'])
        self.assertEqual(len(urls), 2)

    def test_vehicle_identity_gps_and_movement(self):
        sample = [{'vehicleno': '경남1', 'nodeord': '3', 'nodenm': '현재 정류장'}]
        client = TagoClient('key', transport=lambda _, **kw: page(sample), interval=0)
        result = client.vehicles('R1')[0]
        self.assertEqual(result['id'], 'R1|경남1')
        self.assertIsNone(result['lat'])
        self.assertIsNone(result['bearing'])
        sample[0].update(gpslati='nan', gpslong='128.1')
        self.assertIsNone(client.vehicles('R1')[0]['lat'])
        sample[0].update(gpslati='35.18', gpslong='128.1')
        self.assertEqual(client.vehicles('R1')[0]['lat'], 35.18)

    def test_shared_deadline_bounds_retries_and_rejects_late_success(self):
        clock = [0.0]
        def monotonic():
            return clock[0]
        def sleep(seconds):
            clock[0] += seconds
        def slow(url, timeout=8):
            clock[0] += timeout
            raise TagoError('NETWORK', 'temporary')
        client = TagoClient('key', transport=slow, interval=0)
        with patch('mobile_app.tago.time.monotonic', monotonic), patch('mobile_app.tago.time.sleep', sleep):
            with self.assertRaises(TagoError):
                client.routes('10', deadline=10)
        self.assertLessEqual(clock[0], 10)

    def test_service_deadline_spans_discovery_and_multiple_vehicle_pages(self):
        clock, attempts = [0.0], {}
        def transport(url, timeout=8):
            parsed = urlsplit(url)
            query = parse_qs(parsed.query)
            key = (parsed.path, query['pageNo'][0])
            attempts[key] = attempts.get(key, 0) + 1
            duration = 6 if attempts[key] < 3 else 8
            clock[0] += min(duration, timeout)
            if duration > timeout or attempts[key] < 3:
                raise TagoError('NETWORK', 'temporary')
            if 'getRouteNoList' in parsed.path:
                return page([{'routeid':'R1', 'routeno':'10'}], 1)
            return page([{'vehicleno':'1', 'nodeord':1}], 2)
        with patch('time.monotonic', lambda:clock[0]), patch('time.sleep', lambda seconds:clock.__setitem__(0,clock[0]+seconds)):
            service = BusService(TagoClient('key', transport=transport, interval=0), {})
            response = service.locations(['10'])
        self.assertLessEqual(clock[0], 30)
        self.assertTrue(response['errors'])
        self.assertEqual(response['routes'][0]['vehicles'], [])
        self.assertTrue(response['routes'][0]['stale'])


class FakeTago:
    def __init__(self):
        self.failed = set()
        self.empty = set()
        self.called = []
    def routes(self, bus, deadline=None):
        return [{'busNo': bus, 'routeId': bus + suffix, 'directionLabel': suffix} for suffix in ('A', 'B')]
    def vehicles(self, route, deadline=None):
        self.called.append(route)
        if route in self.failed:
            raise TagoError('NETWORK', '연결 실패')
        return [] if route in self.empty else [{'id': route + '|1', 'vehicleNo': '1', 'lat': 35.18,
            'lon': 128.1, 'bearing': 90, 'nodeOrd': 1, 'nodeName': '정류장'}]
    def stops(self, route, deadline=None):
        return [{'nodeOrd': 1, 'name': '정류장', 'lat': 35.18, 'lon': 128.1}]


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.clock = [1000]
        self.client = FakeTago()
        self.service = BusService(self.client, {}, now=lambda: self.clock[0])

    def test_multiple_variants_and_only_selected_routes(self):
        result = self.service.locations(['10'])
        self.assertEqual([r['routeId'] for r in result['routes']], ['10A', '10B'])
        self.assertEqual(self.client.called, ['10A', '10B'])
        self.assertEqual(self.service.locations([])['routes'], [])

    def test_partial_failure_preserves_timestamp_and_clears_bearing(self):
        first = self.service.locations(['10'])
        self.clock[0] += 16
        self.client.failed.add('10A')
        second = self.service.locations(['10'])
        stale, fresh = second['routes']
        self.assertTrue(stale['stale'])
        self.assertEqual(stale['updatedAt'], first['routes'][0]['updatedAt'])
        self.assertIsNone(stale['vehicles'][0]['bearing'])
        self.assertFalse(fresh['stale'])
        self.assertGreater(fresh['updatedAt'], stale['updatedAt'])

    def test_empty_success_removes_old_vehicles(self):
        self.service.locations(['10'])
        self.clock[0] += 16
        self.client.empty.add('10A')
        result = self.service.locations(['10'])
        self.assertEqual(result['routes'][0]['vehicles'], [])
        self.assertFalse(result['routes'][0]['stale'])

    def test_shared_cache_avoids_duplicate_upstream_calls(self):
        self.service.locations(['10'])
        self.service.locations(['10'])
        self.assertEqual(len(self.client.called), 2)

    def test_busy_request_does_not_modify_cache_or_selected_routes(self):
        self.service._lock.acquire()
        try:
            with self.assertRaises(TagoError) as caught:
                self.service.locations(['10'])
            self.assertEqual(caught.exception.code, 'BUSY')
        finally:
            self.service._lock.release()
        self.assertEqual(self.client.called, [])
        self.assertEqual(len(self.service.locations(['160'])['routes']), 2)


if __name__ == '__main__':
    unittest.main()
