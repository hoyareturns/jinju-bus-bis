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

## 구조

- `server.py`: 정적 파일 제공 및 버스 위치 API 프록시
- `static/index.html`: 모바일 앱 화면
- `static/styles.css`: 모바일 UI
- `static/app.js`: 지도/정류장/노선 조회 로직
- `static/manifest.webmanifest`: 설치형 앱 설정
- `static/sw.js`: 앱 셸 캐시용 서비스 워커

