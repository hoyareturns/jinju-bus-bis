# 진주 버스 WEB APP 2.1

지도 없이 **전체 정류소 → 현재 정류소 → 다음 정류소**를 보여주는 휴대폰용 웹 앱입니다. Android APK 소스는 `android-v2/`에 별도로 유지됩니다.

- 등록한 버스 → 해당 방향 → 경유 정류소 순서의 알림 설정
- 여러 알림(최대 20개), 기본 **매일 07:00–07:30**, 요일·시간 개별 지정
- 시간 구간마다 첫 도착 한 번. 화면 알림과 서버 Web Push 지원
- 현재 로컬 실행에서는 서버 푸시 키가 없어 화면 알림을 사용할 수 있습니다.

```powershell
python -m pip install -r mobile_app/requirements.txt
# TAGO_API_KEY를 실행 환경의 비밀값으로 설정
python -m mobile_app.server
```

접속: http://127.0.0.1:8765/apps/bus/

[운영·알림·ZERIONA 연동 안내](HANDOFF.md) · [검증 결과](VERIFICATION.md)
