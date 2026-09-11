"""Read the local build key and verify real TAGO responses without logging credentials."""
import json
import pathlib
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
key = next((line.split('=', 1)[1].strip() for line in
            (ROOT / 'android/local.properties').read_text(encoding='utf-8-sig').splitlines()
            if line.startswith('TAGO_API_KEY=')), '')
if not key:
    raise SystemExit('TAGO_API_KEY is missing')
key = urllib.parse.unquote(key) if '%' in key else key

def call(service, operation, **params):
    query = urllib.parse.urlencode(dict(serviceKey=key, cityCode='38030',
                                        _type='json', pageNo=1, numOfRows=9999, **params))
    url = f'https://apis.data.go.kr/1613000/{service}/{operation}?{query}'
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            payload = response.read().decode('utf-8-sig')
    except urllib.error.HTTPError as exc:
        print(json.dumps({'operation': operation, 'httpStatus': exc.code}))
        raise SystemExit(1)
    except Exception as exc:
        print(json.dumps({'operation': operation, 'errorType': type(exc).__name__}))
        raise SystemExit(1)
    if payload.lstrip().startswith('<'):
        xml = ET.fromstring(payload)
        print(json.dumps({'operation': operation, 'resultCode': xml.findtext('.//resultCode') or xml.findtext('.//returnReasonCode'),
                          'resultMsg': xml.findtext('.//resultMsg') or xml.findtext('.//returnAuthMsg')}, ensure_ascii=False))
        raise SystemExit(1)
    result = json.loads(payload)['response']
    header = result['header']
    print(json.dumps({'operation': operation, **header}, ensure_ascii=False))
    if str(header.get('resultCode')) not in ('00', '0'):
        raise SystemExit(1)
    items = (result.get('body', {}).get('items') or {})
    rows = items.get('item', []) if isinstance(items, dict) else []
    return [rows] if isinstance(rows, dict) else rows

records = {}
for bus_no in ('10', '160'):
    routes = call('BusRouteInfoInqireService', 'getRouteNoList', routeNo=bus_no)
    routes = [row for row in routes if str(row.get('routeno')) == bus_no]
    print(json.dumps({'busNo': bus_no, 'routeIds': [row['routeid'] for row in routes]}, ensure_ascii=False))
    records[bus_no] = []
    for route in routes:
        vehicles = call('BusLcInfoInqireService', 'getRouteAcctoBusLcList', routeId=route['routeid'])
        print(json.dumps({'routeId': route['routeid'], 'vehicleCount': len(vehicles),
                          'samples': [{k: v.get(k) for k in ('gpslati', 'gpslong', 'vehicleno', 'nodeid', 'nodeord', 'nodenm')} for v in vehicles[:2]]}, ensure_ascii=False))
        records[bus_no].append({'route': route, 'vehicles': vehicles})
output = ROOT / 'android/build/verification/tago-live-probe.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
print('Probe evidence saved; key was not logged.')
