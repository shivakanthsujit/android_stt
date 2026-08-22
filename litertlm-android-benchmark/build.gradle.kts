plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "dev.localflow.litertlmbenchmark"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.localflow.litertlmbenchmark"
        minSdk = 31
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
        buildConfigField("String", "LITERT_LM_VERSION", "\"0.16.1\"")

        ndk {
            abiFilters += "arm64-v8a"
        }
    }

    buildTypes {
        release {
            isDebuggable = true
            isJniDebuggable = false
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        buildConfig = true
    }

    packaging {
        jniLibs.useLegacyPackaging = false
    }
}

dependencies {
    implementation("com.google.ai.edge.litertlm:litertlm-android:0.16.1")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
