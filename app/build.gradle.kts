plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "dev.localflow.dictation"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.localflow.dictation"
        minSdk = 31
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"

        ndk {
            abiFilters += "arm64-v8a"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        buildConfig = true
    }

    sourceSets {
        getByName("main").assets.srcDir(rootProject.file("docs/evaluation"))
    }
}

dependencies {
    implementation("ai.liquid.leap:leap-sdk:0.10.9")
    implementation("ai.liquid.leap:leap-model-downloader:0.10.9")
    // LEAP exposes Flow and suspend APIs, but declares coroutines as a runtime dependency.
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")

    implementation("ai.moonshine:moonshine-voice:0.1.2") {
        // MicTranscriber.load() uses Moonshine's direct foreground downloader. The optional
        // WorkManager downloader would otherwise add unused boot/foreground-service permissions.
        exclude(group = "androidx.work", module = "work-runtime")
        // The library's Java API does not use Material widgets; this benchmark uses platform Views.
        exclude(group = "com.google.android.material", module = "material")
    }
    testImplementation("junit:junit:4.13.2")
}
