plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val llamaCppSourceDir = providers.gradleProperty("llamaCppSourceDir")
    .orElse(rootProject.layout.projectDirectory.dir(".cache/llama.cpp-ece963f41").asFile.absolutePath)

android {
    namespace = "dev.localflow.llamacppbenchmark"
    compileSdk = 36
    ndkVersion = "28.0.13004108"

    defaultConfig {
        applicationId = "dev.localflow.llamacppbenchmark"
        minSdk = 31
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
        buildConfigField("String", "LLAMA_CPP_REVISION", "\"ece963f41\"")
        buildConfigField("String", "PINNED_NDK_VERSION", "\"28.0.13004108\"")
        buildConfigField("String", "PINNED_CMAKE_VERSION", "\"3.31.6\"")

        ndk {
            abiFilters += "arm64-v8a"
        }
        externalNativeBuild {
            cmake {
                arguments += "-DLLAMA_CPP_SOURCE_DIR=${llamaCppSourceDir.get()}"
                arguments += "-DANDROID_STL=c++_shared"
            }
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

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.31.6"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        buildConfig = true
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
