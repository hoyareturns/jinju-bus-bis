# 진주 버스 WEB APP · 서버 인계

버전 **2.1.0**. GitHub main `463749c`(2026-09-11)을 기반으로 구성했습니다. 외부 배포와 ZERIONA 프로젝트 변경은 수행하지 않았습니다. Android 앱과 기존 Streamlit 소스는 별도 유지합니다.

## 화면과 알림

지도는 사용하지 않습니다. 등록한 버스의 전체 정류소를 운행 순서로 보여주고, TAGO의 nodeOrd·nodeId로 현재 정류소와 다음 정류소를 표시합니다. 차량 GPS가 없어도 표시할 수 있습니다. 순서를 확인할 수 없는 차량에는 다음 정류소를 추측하지 않습니다.

등록 버스는 최대 10개입니다. 알림은 등록한 버스번호 → 진행 방향 → 그 방향의 경유 정류소 순으로 선택합니다. 동일 방향의 노선 변형은 실제 정류소 ID와 진행 순서를 확인해 묶습니다. 10번과 160번은 각각 두 방향입니다. 순환·특수 노선 등 두 방향으로 안전하게 합칠 수 없는 노선은 추가 경로를 구분해 표시합니다. 분기 운행의 정류소는 '일부 운행 경유'로 표시하며 해당 정류소를 지나는 차량만 감지합니다.

알림은 기기당 최대 20개이며 각각 추가·수정·삭제할 수 있습니다. 새 알림은 매일 **07:00~07:30**, 한국 시간입니다. 평일·주말·요일 선택, 분 단위 시간, 자정 넘김을 지원합니다. 시작 시각 포함/종료 시각 제외이며 자정 넘김은 시작한 날짜의 요일에 속합니다. 알림마다 해당 시간 구간의 첫 도착만 울립니다. 같은 조회에서 여러 알림이 도착하면 모두 화면에 남습니다.

도착은 최신 성공 응답에서 차량의 현재 정류소가 선택한 정류소와 일치할 때입니다. 오래된 데이터·오류·다른 방향은 울리지 않습니다. 15초 조회 사이에 지나간 경우나 TAGO 보고 지연은 놓칠 수 있습니다. 실제 정류장 도착 시간을 보장하는 교통 신호 시스템은 아닙니다.

화면 알림은 화면이 열려 있는 동안 동작합니다. 사용자 조작 후 소리를 사용할 수 있으며 다시 열었을 때 '소리 활성화 / 시험'으로 확인하세요. 백그라운드 알림음은 Android의 사이트 알림 설정을 따릅니다.

## 실행 환경

Python 3.11 이상, JavaScript 검사에 Node 20 이상을 사용합니다. 루트 requirements.txt는 Streamlit용입니다. 웹 서버의 의존성은 별도 파일입니다.

```powershell
python -m venv .venv-web
.venv-web\Scripts\python -m pip install -r mobile_app/requirements.txt
# 실행 환경의 TAGO_API_KEY 비밀값 설정 후
.venv-web\Scripts\python -m mobile_app.server
```

기본 주소는 http://127.0.0.1:8765/apps/bus/ 입니다. 서버는 `.env`, `.streamlit/secrets.toml`, Android local.properties를 자동으로 읽지 않습니다. 운영 플랫폼의 환경변수/비밀 설정 기능으로 주입하세요. 화면 조회만은 Python 표준 라이브러리로 실행 가능하며 푸시 라이브러리가 없으면 푸시 기능이 명시적으로 비활성화됩니다.

| 환경변수 | 기본값/용도 |
|---|---|
| TAGO_API_KEY | 서버 전용 공공데이터포털 서비스 키. 기존 API_KEY 별칭도 지원 |
| CITY_CODE | 38030, 진주시 |
| BUS_BASE_PATH | /apps/bus/, 루트 /도 지원 |
| HUB_PATH | /, 같은 출처의 허브 복귀 경로 |
| HOST / PORT | 127.0.0.1 / 8765 |
| BUS_PUBLIC_ORIGIN | 푸시 운영 시 실제 HTTPS 출처, 예: https://bus.example.com (경로 제외) |
| BUS_DATA_DIR | mobile_app/.state, 알림 DB와 작업자 잠금 파일의 영속 디렉터리 |
| VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY | Web Push 서버 키 쌍 |
| VAPID_SUBJECT | 실제 운영자의 mailto:이메일 또는 HTTPS 연락처 URL |

TAGO 버스노선정보·버스위치정보 서비스 권한이 필요합니다. 키가 설정되었다는 상태가 실제 인증 성공을 보장하지 않습니다.

## 앱을 닫아도 알림 받기

서버가 시간·요일 조건에 맞는 버스를 계속 조회해 Web Push를 보냅니다. 다음 운영 설정이 모두 필요합니다.

1. requirements 설치 및 지속 실행되는 서버 준비. 절전/자동 중지되는 무료 호스팅은 지속적인 알림을 제공하지 못합니다.
2. `python -m mobile_app.push_keys`로 키 생성. `mobile_app/.state/.env.vapid`에 기록되며 내용은 출력하지 않습니다. 기존 파일을 덮어쓰지 않습니다. 키와 실제 VAPID_SUBJECT를 운영 환경에 주입하세요. 키를 재시작마다 바꾸지 마세요.
3. 외부 HTTPS 주소 및 BUS_PUBLIC_ORIGIN 설정. 같은 출처 프록시가 앱 경로를 유지해야 합니다.
4. BUS_DATA_DIR를 지속 저장소로 지정. DB를 잃으면 알림·기기 구독·중복 방지 기록도 사라집니다. 하나의 DB에는 하나의 서버 작업자만 실행됩니다.
5. Android Chrome으로 열고 필요하면 메뉴에서 홈 화면에 설치. 알림 설정에서 '앱을 닫아도 알림 받기'를 선택하고 브라우저 알림을 허용한 뒤 저장하세요.
6. 실제 휴대폰에서 화면을 닫고 도착 알림을 검증하세요. 강제 종료·OS 알림 차단·통신 불능은 수신에 영향을 줍니다.

로컬 구현 검증에서는 실제 휴대폰으로 푸시를 발송하지 않았습니다. 서버 키가 없는 상태를 화면에서 명확히 안내합니다. localhost는 개발용이며 휴대폰 접속용 HTTPS 주소가 아닙니다.

서버 알림은 브라우저별 비밀 토큰으로 소유권을 구분합니다. 토큰 해시만 서버 DB에 저장합니다. 이것은 ZERIONA 계정 인증이나 계정 동기화가 아닙니다. 브라우저 저장소를 지우면 기존 서버 알림을 관리할 수 없으므로 알림을 먼저 삭제하세요. 수신 종료에는 사이트 알림 권한 해제도 사용할 수 있습니다. 노선 등록 해제 시 해당 알림도 삭제하며, 서버 상태를 확인하지 못하면 노선 해제를 보류합니다.

발송 기록을 먼저 저장해 재시작·동시 실행·응답 불명 상황의 중복을 막습니다. 따라서 발송 실패/결과 미확인은 그 시간 구간에 재시도하지 않습니다. UI에서 실패를 표시하며 다음 예약 구간에 다시 시도합니다. 만료 구독(404/410)은 비활성화되고 수정·저장으로 갱신합니다. 유효기간이 지난 늦은 알림은 표시하지 않습니다. Android의 실제 수신을 서버 발송 성공만으로 보장하지 않습니다.

## API

모든 경로 앞에 BUS_BASE_PATH를 붙입니다. JSON은 no-store이고, 키·구독 주소·인증 헤더를 로그에 남기지 않습니다.

| 메서드·경로 | 내용 |
|---|---|
| GET api/bootstrap | 버전, 등록 가능 버스, 기본값, 익명·기기 저장 상태 |
| GET api/health | 프로세스 상태, 키 설정 여부. upstreamVerified는 false |
| GET api/v2/routes?buses=10,160 | 동일 번호의 모든 routeId와 정류소 순서 |
| GET api/v2/locations?buses=10,160 | 차량의 현재 정류소·조회 시각·오류/이전 정보 구분 |
| GET api/push/config | 푸시 사용 가능 여부, 공개 키, 비활성 사유 |
| POST api/alerts/session | 브라우저 관리 토큰 발급 |
| GET api/alerts | 해당 브라우저의 여러 알림 목록 |
| POST api/alerts | 알림 추가 또는 id가 있으면 해당 알림 수정 |
| DELETE api/alerts/{id} | 소유한 알림 삭제 |

알림 API는 Authorization: Bearer 토큰을 사용합니다. 변경 요청은 정확한 Origin을 검사하고 JSON만 받습니다. 최대 본문 64KiB, 알림 20개/브라우저, 익명 기기 2000개 제한이 있습니다. 서버는 등록 버스와 실제 최신 노선의 정류소를 다시 확인하고, FCM/Mozilla/Apple의 지정된 HTTPS 푸시 호스트만 허용하며 리디렉션을 따르지 않습니다. 프록시에서 요청·연결·세션 생성 빈도를 제한하세요.

알림 저장 요청 형식:

```json
{
  "registeredBuses": ["160"],
  "subscription": {"endpoint":"<브라우저에서 받은 주소>","keys":{"auth":"<키>","p256dh":"<키>"}},
  "rule": {
    "busNo":"160", "directionLabel":"석교 방면", "stopName":"<정류소>",
    "targets":[{"routeId":"<실제 노선 ID>","nodeOrd":1,"nodeId":"<정류소 ID>"}],
    "startTime":"07:00", "endTime":"07:30", "days":[0,1,2,3,4,5,6], "timezone":"Asia/Seoul"
  }
}
```

요일은 0=월요일, 6=일요일입니다. 새 알림에는 id를 생략합니다. labels는 표시용이고 감지는 검증된 targets만 사용합니다. 토큰·구독 endpoint·키는 비밀값으로 취급하세요.

## ZERIONA와 같은 서버 운영

브라우저 → 공통 HTTPS 프록시 → 버스 서버 구조입니다. `/apps/bus/` 접두 경로를 제거하지 않습니다. `deploy/Caddyfile.example`은 템플릿이며 실행 중인 ZERIONA 설정은 변경하지 않았습니다.

Docker 사용 시 mobile_app/.env.example을 .env로 복사해 운영 값을 설정하고 해당 폴더에서 `docker compose up --build -d`를 실행합니다. 로컬 포트8765에 바인딩하고 /data 볼륨에 알림을 보존합니다. Docker 이미지는 의존성을 설치하며 비특권 사용자로 실행합니다. 이 환경에서는 실제 Docker 빌드를 실행하지 않았습니다.

허브 연동 자료: `app-manifest.json`, `assets/icon.svg`, `assets/banner.svg`. 배너·아이콘·launchPath·healthPath는 설정한 base path를 따릅니다. 익명 기기 저장이며 계정 저장을 가장하지 않습니다. 고정 PC 절대 경로를 사용하지 않아 서버 이전 시 환경변수·비밀값·알림 DB를 함께 이전하면 됩니다.

서비스 워커는 자기 경로의 명시된 앱 자산만 캐시합니다. API·다른 허브·지도 타일은 캐시하지 않습니다. 지도 라이브러리는 로드하지 않습니다. 서버는 소규모 자체 운영용 Python HTTP 서버이므로 외부 공개 시 프록시의 TLS/요청 제한을 사용하세요.

## 검증

```powershell
python -m unittest discover -s mobile_app/tests -p 'test_*.py'
node --test mobile_app/tests/state.test.mjs mobile_app/tests/stops.test.mjs mobile_app/tests/alarm-panel.test.mjs mobile_app/tests/worker.test.mjs
```

자세한 검증 범위와 미검증 항목은 VERIFICATION.md에 기록합니다.
