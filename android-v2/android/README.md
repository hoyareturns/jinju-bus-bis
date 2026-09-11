# Jinju Bus Android

This private family APK calls the public TAGO API directly over HTTPS. No Python or hosted proxy is required. City code: 38030.

Set the real TAGO_API_KEY in ignored local.properties. Gradle injects BuildConfig.TAGO_API_KEY and refuses a blank key. The APK intentionally contains the key with the owner's authorization. Do not commit key-bearing artifacts.

Set JINJU_OFFLINE_MAP_DIR in the same ignored file to the directory containing the verified jinju-map.db and MAP_LICENSE.txt. On this machine it is D:/CodexBuildTools/jinju-bus-20260911/offline-map. The APK embeds Jinju's regional map; it does not require a first-run map download. Live bus queries still require internet access.

With JDK 17 and Android SDK 37 configured:

```powershell
./gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:lintDebug
```

Output: app/build/outputs/apk/debug/app-debug.apk.

First launch selects only 10. Add routes with +; long-press a chip or use the manager to delete. Empty selections persist. Selected routes refresh approximately every 15 seconds in the foreground. Last successful data is restored before network loading and is labeled as previous information.

See the root CODEX_APK_HANDOFF.md and IMPLEMENTATION_STATUS.md for actual API results, device verification and machine build paths. Build tools are stored on D: per the owner.
