# 진주 버스 Android

가족용 Android 앱입니다. **APK → 공공데이터포털 TAGO HTTPS 직접 호출**로 동작하며 별도 서버를 사용하지 않습니다. 진주 지역 지도는 APK에 내장되고 지도 엔진은 오프라인으로 동작합니다. 실시간 버스 조회에는 인터넷이 필요합니다.

- 최초 선택은 10번 하나입니다. +로 추가, 길게 눌러 삭제하며 전체 삭제도 가능합니다.
- 선택 목록은 기기에 저장됩니다. 선택한 노선만 foreground에서 약 15초마다 조회합니다.
- 같은 번호의 모든 routeId를 조회합니다. 실제 GPS가 없으면 정류장 좌표로 버스 위치를 만들어 내지 않습니다.
- 마지막 정상 응답을 복원하고 이전 정보임을 표시합니다. 진주 지도는 네트워크 없이도 표시됩니다.

## 저장소에 포함하지 않는 파일

APK/AAB/EXE/JAR, 빌드·테스트 출력, 캐시, 지도 DB, 생성된 routes_snapshot.json, 실제 키가 든 local.properties, 서명 키를 올리지 않습니다. 기존 저장소 루트의 bus_data.json은 노선 스냅샷 생성의 입력 자료로 사용합니다.

## 빌드 준비

JDK 17, Android SDK Platform 37 / Build Tools 36.0.0, Python 3, Gradle 9.5.0 Wrapper가 필요합니다. 도구와 출력 디렉터리는 D: 사용을 권장합니다.

아래 명령은 이 android-v2 디렉터리에서 실행합니다.

```powershell
./tools/bootstrap_wrapper.ps1
python ./tools/build_route_snapshot.py ../bus_data.json
Copy-Item ./android/local.properties.example ./android/local.properties
```

local.properties에 자신의 SDK 경로, 실제 TAGO_API_KEY, JINJU_OFFLINE_MAP_DIR을 설정합니다. 실제 키는 커밋하지 않습니다. 키는 BuildConfig.TAGO_API_KEY로 APK에 포함되며, 비어 있으면 빌드가 실패합니다.

## 진주 지도 DB 재생성

이미 로컬에 검증된 jinju-map.db가 있다면 해당 디렉터리를 JINJU_OFFLINE_MAP_DIR로 지정합니다. 이 작업 PC의 자료는 D:/CodexBuildTools/jinju-bus-20260911/offline-map에 있습니다.

처음부터 생성할 경우 네트워크가 연결된 테스트용 Android 기기/에뮬레이터에서 다음과 같이 실행합니다. **PREPARE_JINJU_MAP은 지도 생성 도구를 실행하기 위한 개발용 설정이며 최종 앱 빌드에는 사용하지 않습니다.**

```powershell
$env:JAVA_HOME = 'D:/CodexBuildTools/jinju-bus-20260911/jdk/jdk-17.0.20.1+1'
$env:ANDROID_HOME = 'D:/CodexBuildTools/jinju-bus-20260911/sdk'
$env:GRADLE_USER_HOME = 'D:/CodexBuildTools/jinju-bus-20260911/gradle-home'
$env:Path = "$env:ANDROID_HOME/platform-tools;" + $env:Path
$buildRoot = 'D:/JinjuBuild/output'
$mapDirectory = 'D:/JinjuBuild/offline-map'
New-Item -ItemType Directory -Force $mapDirectory | Out-Null
Push-Location android
./gradlew.bat :app:assembleDebug :app:assembleDebugAndroidTest -PPREPARE_JINJU_MAP=true "-PJINJU_BUILD_ROOT=$buildRoot" --project-cache-dir D:/JinjuBuild/project-cache
Pop-Location
adb install -r "$buildRoot/app/outputs/apk/debug/app-debug.apk"
adb install -r "$buildRoot/app/outputs/apk/androidTest/debug/app-debug-androidTest.apk"
adb shell am instrument -w -e class kr.co.jinjubus.PrepareJinjuMapTest kr.co.jinjubus.test/androidx.test.runner.AndroidJUnitRunner
adb pull /sdcard/Android/data/kr.co.jinjubus/files/jinju-map.db "$mapDirectory/jinju-map.db"
python ./tools/fetch_map_notices.py $mapDirectory
```

지역 범위는 위도 35.03–35.47 / 경도 127.87–128.46, zoom 7–14입니다. 글꼴·아이콘도 포함하며 그 이상 확대는 벡터 확대를 사용합니다. 지도 데이터는 생성 시점의 OpenFreeMap 자료이므로 시간이 지나면 크기/해시가 달라질 수 있습니다. 지도와 원본 고지는 APK에 같이 포함됩니다.

local.properties의 JINJU_OFFLINE_MAP_DIR을 생성한 디렉터리로 지정한 뒤, **PREPARE_JINJU_MAP 없이** 최종 빌드합니다.

```powershell
Push-Location android
./gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:lintDebug "-PJINJU_BUILD_ROOT=$buildRoot" --project-cache-dir D:/JinjuBuild/project-cache
Pop-Location
```

출력: D:/JinjuBuild/output/app/outputs/apk/debug/app-debug.apk. 지도 DB가 없는 일반 빌드는 실패합니다.

## 검증 기록

2026-09-11 기준 Android 단위 테스트 33개, 실제 TAGO 호출, 10/160 노선 UI, 추가·전체 삭제·선택 저장, 네트워크를 끈 새 설치의 지도 표시, 실제 응답 캐시 복원을 검증했습니다. 10번 API는 당시 정상 응답 0대였고, 160번은 실제 차량 정보가 표시됐으나 응답에 GPS가 없었습니다. 실기기는 미연결이며 Android 9 x86 에뮬레이터에서 설치·실행했습니다.

- 상세 구현/검증: [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)
- 당시 로컬 환경 인계: [CODEX_APK_HANDOFF.md](CODEX_APK_HANDOFF.md)

기존 웹 앱은 저장소 루트에 있으며 이 Android 앱의 실행에 사용되지 않습니다.
