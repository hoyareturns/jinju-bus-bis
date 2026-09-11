# Android APK handoff — direct TAGO (2026-09-11)

For this source-only GitHub checkout, use [README.md](README.md) to regenerate excluded files. The machine paths and historical server references below describe the original local build workspace.

The owner's latest instruction authorizes embedding the TAGO key in this private family APK and supersedes the old proxy-only design. Android calls https://apis.data.go.kr/1613000/ directly with cityCode=38030. No backend deployment is needed. server_v2/ is historical code, unused by Android.

## Build

- JDK 17; Gradle Wrapper 9.5.0; AGP 9.3.1; Kotlin 2.4.20.
- Android compile/target SDK 37, minimum 26; Build Tools 36.0.0.
- Real key: TAGO_API_KEY in ignored android/local.properties. Gradle injects BuildConfig.TAGO_API_KEY and refuses a blank key. Never copy the key into source, logs, tests or documentation.
- Regional map: JINJU_OFFLINE_MAP_DIR in ignored android/local.properties points to D:/CodexBuildTools/jinju-bus-20260911/offline-map. Its verified jinju-map.db is included in the APK; a missing map package fails the build. Preserve this directory when moving the project to another machine.
- Encoding keys are decoded once, then OkHttp encodes the query value once. A decoded literal plus remains a plus.
- Machine build tools: D:/CodexBuildTools/jinju-bus-20260911 (JDK under jdk/, SDK under sdk/, Gradle cache under gradle-home/).
- On this Windows host, run Gradle through the ASCII workspace junction D:/CodexBuildTools/jinju-bus-20260911/project/android to avoid Kotlin test-worker problems with Korean paths.

From the project root on this configured Windows host:

```powershell
./tools/build_windows.ps1 -LiveApiCheck
```

Windows APK: D:/CodexBuildTools/jinju-bus-20260911/build-output/app/outputs/apk/debug/app-debug.apk; variant debug; application ID kr.co.jinjubus; version 1.1 (2).

## Actual service and device verification

Run python tools/verify_tago_live.py from the project root. It reads the ignored key and records sanitized real responses in android/build/verification/tago-live-probe.json, querying every matching ID for 10 and 160. It does not print the key.

```powershell
$root = 'D:/CodexBuildTools/jinju-bus-20260911'
# Run after tools/build_windows.ps1 has configured this PowerShell session.
Push-Location "$root/project/android"
./gradlew.bat :app:assembleDebugAndroidTest "-PJINJU_BUILD_ROOT=$root/build-output" --project-cache-dir "$root/project-cache"
Pop-Location
$env:Path = "$root/sdk/platform-tools;" + $env:Path
adb install -r "$root/build-output/app/outputs/apk/debug/app-debug.apk"
adb install -r "$root/build-output/app/outputs/apk/androidTest/debug/app-debug-androidTest.apk"
adb shell am instrument -w -e class kr.co.jinjubus.LiveTagoUiTest kr.co.jinjubus.test/androidx.test.runner.AndroidJUnitRunner
adb logcat -d -s TAGO:I TAGO_TEST:I AndroidRuntime:E
```

The opt-in device test uses the real service: 10 API/UI, add 160 through the UI, stored selection/cache, delete 160 and 10, persist the empty selection, then restore 10. A successful empty response is not evidence of a visible live bus marker. Never fabricate GPS or claim a device test passed without its output.

Run LiveTagoUiTest on a fresh test-emulator app profile. OfflineCacheUiTest is a separate opt-in test: run after the live test, with the app force-stopped and test-emulator networking disabled, without clearing app data. It verifies the actual persisted response, selected route, timestamp and previous-information label after a new process starts. Re-enable networking afterwards.

Map style: OpenFreeMap Liberty, using org.maplibre.gl:android-sdk-opengl:13.6.1. The default Vulkan artifact crashed on the test GPU; the OpenGL build renders Jinju roads successfully. Polling updates stable markers; the camera fits on first content and explicit 전체 보기 only. Missing GPS remains absent; stop coordinates are never substituted for vehicle GPS.

## Bundled Jinju map

The owner's follow-up requests an embedded regional map. The APK includes a MapLibre offline database for latitude 35.03–35.47 / longitude 127.87–128.46, zoom 7–14, including CJK glyphs and both sprite densities. It contains 985 map tiles and 774 other map resources; the database is 74,293,248 bytes. Higher zoom uses vector overzoom. The map engine uses only bundled data; areas outside this regional package are not provided. Live bus data still needs internet access.

BundledMapStore atomically copies the uncompressed database on fresh installs before initializing MapLibre, and uses the supported merge API for existing databases. It records the SHA-256-derived version and reuses the on-device map on later starts. The first import reads APK storage and performs no map download. An interrupted import can be retried. Attribution is preserved in the map and MAP_LICENSE.txt.

PrepareJinjuMapTest is an explicitly invoked build-time utility for regenerating the regional database. It is never called by the normal app. OfflineMapUiTest must run on a freshly cleared test-emulator app profile with Wi-Fi and mobile data disabled, to prove that first-install rendering is independent of a prior online cache.


Final delivery: D:/JinjuBus/진주버스-debug.apk — 129,774,487 bytes. See IMPLEMENTATION_STATUS.md for the verified hash and completed device test evidence.
