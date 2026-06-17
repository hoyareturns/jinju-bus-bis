# 진주 버스 모바일 앱(PWA)

휴대폰에서 앱처럼 설치해서 쓰기 위한 모바일 전용 PWA입니다.

## 실행

PowerShell에서 프로젝트 루트 기준:

```powershell
$env:API_KEY="공공데이터포털_서비스키"
$env:CITY_CODE="38030"
python mobile_app/server.py
```

브라우저에서 `http://localhost:8765`로 접속합니다.

## 휴대폰 설치

실제 휴대폰에서 앱처럼 설치하려면 HTTPS 주소가 필요합니다. 배포 후 삼성 인터넷/Chrome에서 접속한 뒤:

- Chrome: 메뉴 > 앱 설치 또는 홈 화면에 추가
- Samsung Internet: 메뉴 > 현재 페이지 추가 > 홈 화면

## Render 배포

저장소 루트의 `render.yaml`을 사용하면 Render에서 모바일 앱 서버를 바로 만들 수 있습니다.

1. Render Dashboard에서 New > Blueprint를 선택합니다.
2. `hoyareturns/jinju-bus-bis` 저장소를 연결합니다.
3. `API_KEY` 입력칸에 공공데이터포털 서비스키를 넣습니다.
4. 배포가 끝나면 `https://...onrender.com` 주소로 접속합니다.

`CITY_CODE`는 진주시 코드 `38030`으로 자동 설정됩니다. `API_KEY`는 저장소에 커밋하지 않고 Render 환경변수로만 등록합니다.

## 구조

- `server.py`: 정적 파일 제공 및 버스 위치 API 프록시
- `static/index.html`: 모바일 앱 화면
- `static/styles.css`: 모바일 UI
- `static/app.js`: 지도/정류장/노선 조회 로직
- `static/manifest.webmanifest`: 설치형 앱 설정
- `static/sw.js`: 앱 셸 캐시용 서비스 워커
