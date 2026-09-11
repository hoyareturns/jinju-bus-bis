# Implementation status — direct TAGO Android

Updated: 2026-09-11. This report supersedes the earlier proxy-only implementation and build limitations.

## Runtime

The private family APK calls the official TAGO HTTPS service directly, cityCode=38030. No JINJU_BUS_API_BASE_URL, example.invalid, /api/v2/routes, /api/v2/locations, Python server or Render service is used by Android. Historical server_v2 code is not part of the APK runtime.

The real key is read from ignored android/local.properties into BuildConfig.TAGO_API_KEY. A blank key fails the build. Encoding keys are decoded once and query values encoded once; the key is not printed in logs or committed in source.

All exact route-number matches and all result pages are queried. Route 10 resolves to JJB381101010, JJB381101020, JJB381001010 and JJB381001020. Actual location responses for all four IDs succeeded with zero vehicles at verification time. The UI correctly says 현재 조회되는 차량 없음; this does not establish that service has ended.

Route 160 resolves to eight IDs. Real vehicles and their vehicle numbers/current stop names were received and displayed in Android. Those service responses omitted GPS. The app preserves the vehicle details and labels GPS as unavailable instead of plotting stop coordinates as vehicle locations.

## Behavior preserved and corrected

- First installation selects only 10; + adds routes; long-press or the manager deletes any route, including 10 and every route. Selections, including empty selections, persist in DataStore.
- Only selected routes are queried every approximately 15 seconds in foreground. Removing a route cancels its pending requests; backgrounding cancels unnecessary calls.
- Successful per-route responses are cached and restored before network refresh. Partial failures retain earlier successful data and clear unreliable direction arrows.
- GPS is validated; bearing uses sufficiently recent, meaningful movement only. Stable routeId|vehicleNo markers update in place. Periodic refresh does not refit the camera.
- Public API resultCode/resultMsg/items are validated, including HTTP-200 errors, empty results, authentication, quota and malformed responses. Request starts are spaced to avoid observed burst limits; transient upstream/network errors have bounded retries.
- A route is marked queried only after its own successful response arrives.
- MapLibre uses the OpenGL artifact 13.6.1: the default Vulkan artifact crashed on the test GPU. OpenFreeMap Liberty supplies detailed roads. An actual Android screenshot confirms Jinju roads and the Nam River render.

## Build and validation

JDK 17, Gradle 9.5.0, AGP 9.3.1, Kotlin 2.4.20, compile/target SDK 37, minimum SDK 26. Application kr.co.jinjubus, debug variant, version 1.1 (2).

Build tools, Gradle cache, SDK, emulator and current build outputs live under D:/CodexBuildTools/jinju-bus-20260911. The C: task-installed .build-tools directory was removed only after 27,187 copied files / 21,608,777,622 bytes were verified with no mismatches. The user's project/source and pre-existing runtimes were retained.

Use tools/build_windows.ps1 -LiveApiCheck. It builds through an ASCII D: junction and redirects project cache/build outputs to D: to avoid Korean-path test-worker problems and OneDrive output locks.

- Android unit tests: 33 passed, including opt-in real TAGO calls using the actual Android BusApi.
- assembleDebug and lintDebug succeeded. APK installed and launched on an Android 9 x86 emulator on D:.
- Actual 10 response and 160 vehicle details displayed; Jinju map rendering screenshot verified.
- Final embedded-map APK live UI test passed (embedded-map-live-ui-test.log): a fresh actual 10 response with all four IDs, offline map engine with rendered roads, add 160, three actual vehicle details, delete 160 and 10, persist empty selection across recreation, restore only 10. OfflineCacheUiTest also passed after a new process start with Wi-Fi/mobile data disabled: the real saved response timestamp, 10-only selection, previous-information label and embedded map were restored.
- No physical phone is connected; physical-device verification is not claimed.

APK: D:/CodexBuildTools/jinju-bus-20260911/build-output/app/outputs/apk/debug/app-debug.apk
Evidence: D:/CodexBuildTools/jinju-bus-20260911/verification/

## Embedded Jinju map (owner follow-up)

- APK contains the verified MapLibre database (74,293,248 bytes), with 985 regional tiles and 774 map/style/glyph/sprite resources. Bounds: 35.03–35.47 latitude, 127.87–128.46 longitude; zoom 7–14, with vector overzoom above 14.
- Both sprite densities and CJK glyphs are included. OpenFreeMap / OpenMapTiles / OpenStreetMap attribution is retained; MAP_LICENSE.txt is packaged.
- Source package is stored on D: and supplied through ignored local.properties JINJU_OFFLINE_MAP_DIR. Gradle refuses to build without it and derives a map version from the database SHA-256.
- Fresh installs atomically place the uncompressed bundled database before MapLibre opens it. Existing map databases use the supported offline-region merge API. Later starts reuse the installed version.
- OfflineMapUiTest passed on a freshly cleared Android emulator profile with Wi-Fi and mobile data disabled: no previous online map cache existed. The captured screen visibly contains Jinju roads and the Nam River. This proves APK-contained map rendering; it is not a phone performance benchmark.
- Evidence: verification/offline-map-fast-test.log and verification/offline-first-install-map.png under the D: tool root.
- Bus live requests still need internet. The map engine is explicitly offline and displays only bundled map coverage; the separate TAGO client retains internet access.



## Final delivered artifact

- Build: assembleDebug / debug succeeded after device verification; unit tests 33/33, lint 0 errors.
- Delivery: D:/JinjuBus/진주버스-debug.apk
- Exact size: 129,774,487 bytes.
- SHA-256: 6c23cf98e98c899e256f8463810eb044aea7c67ea624c20517c8bd154d670304
- APK key presence, embedded map database hash, five upstream license notices, ZIP CRC, APK v2 signature and 16 KB alignment were verified. The key was not printed.
- Device tests: embedded-map-live-ui-test.log, offline-map-fast-test.log, final-offline-cache-test.log all passed. Final screenshots include actual 160 vehicle details with the map and offline-cache.png showing 이전 정보 · 2분 전 with Jinju roads.
- Physical phone: not connected. Installation/execution verification used the local Android 9 x86 emulator.
- Final details are recorded in D:/CodexBuildTools/jinju-bus-20260911/verification/apk-final-verification.json.
