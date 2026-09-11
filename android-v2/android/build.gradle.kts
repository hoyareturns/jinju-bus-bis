plugins {
    id("com.android.application") version "9.3.1" apply false
    id("org.jetbrains.kotlin.android") version "2.4.20" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.4.20" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "2.4.20" apply false
}

// Keep generated files off small/system or cloud-synced drives when requested.
val externalBuildRoot = providers.gradleProperty("JINJU_BUILD_ROOT").orNull
if (externalBuildRoot != null) {
    allprojects {
        layout.buildDirectory.set(file("$externalBuildRoot/${if (this == rootProject) "root" else name}"))
    }
}
