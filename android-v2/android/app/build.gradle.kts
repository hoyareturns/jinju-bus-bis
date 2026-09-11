import java.util.Properties
import java.security.MessageDigest

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

val localBuildProperties = Properties().apply {
    rootProject.file("local.properties").takeIf { it.exists() }?.inputStream()?.use { load(it) }
}
val tagoApiKey = providers.gradleProperty("TAGO_API_KEY")
    .orElse(localBuildProperties.getProperty("TAGO_API_KEY", "")).get().trim()
check(tagoApiKey.isNotBlank()) { "TAGO_API_KEY is required in local.properties; refusing to build an unconfigured APK." }
val tagoKeyLiteral = "\"" + tagoApiKey.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
val mapStyleUrl = providers.gradleProperty("MAP_STYLE_URL")
    .orElse("https://tiles.openfreemap.org/styles/liberty")
    .get()
val offlineMapDirectory = providers.gradleProperty("JINJU_OFFLINE_MAP_DIR")
    .orElse(localBuildProperties.getProperty("JINJU_OFFLINE_MAP_DIR", "")).get()
val offlineMapFile = file("$offlineMapDirectory/jinju-map.db")
// Explicit developer-only bootstrap for PrepareJinjuMapTest; normal builds still require the map.
val prepareMapOnly = providers.gradleProperty("PREPARE_JINJU_MAP").orNull == "true"
check(prepareMapOnly || (offlineMapDirectory.isNotBlank() && offlineMapFile.isFile)) {
    "JINJU_OFFLINE_MAP_DIR must contain the verified jinju-map.db regional map package."
}
val offlineMapVersion = if (!offlineMapFile.isFile) "preparation-only" else MessageDigest.getInstance("SHA-256").let { digest ->
    offlineMapFile.inputStream().use { input ->
        val buffer = ByteArray(64 * 1024)
        while (true) { val count = input.read(buffer); if (count < 0) break; digest.update(buffer, 0, count) }
    }
    digest.digest().joinToString("") { "%02x".format(it) }.take(16)
}

android {
    namespace = "kr.co.jinjubus"
    compileSdk = 37

    defaultConfig {
        applicationId = "kr.co.jinjubus"
        minSdk = 26
        targetSdk = 37
        versionCode = 2
        versionName = "1.1"
        buildConfigField("String", "TAGO_API_KEY", tagoKeyLiteral)
        buildConfigField("String", "MAP_STYLE_URL", "\"$mapStyleUrl\"")
        buildConfigField("String", "OFFLINE_MAP_VERSION", "\"$offlineMapVersion\"")
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    if (offlineMapDirectory.isNotBlank()) sourceSets.getByName("main").assets.srcDir(offlineMapDirectory)
    androidResources { noCompress += "db" }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources.excludes += setOf("/META-INF/{AL2.0,LGPL2.1}")
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

tasks.withType<Test>().configureEach {
    inputs.property("tagoLiveCheck", providers.environmentVariable("TAGO_LIVE_CHECK").orElse("false"))
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.08.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.10.0")
    implementation("androidx.datastore:datastore-preferences:1.2.1")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.11.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.11.0")
    implementation("com.squareup.okhttp3:okhttp:5.3.0")
    implementation("org.maplibre.gl:android-sdk-opengl:13.6.1")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.3.0")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
