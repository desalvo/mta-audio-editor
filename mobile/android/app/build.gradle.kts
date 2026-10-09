plugins {
    id("com.android.application")
}

android {
    namespace = "com.desalvo.mtaaudioeditor.mobile"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.desalvo.mtaaudioeditor.mobile"
        minSdk = 26
        targetSdk = 35
        versionCode = 20265
        versionName = "0.2.0"
        buildConfigField("String", "MTA_REVISION", "\"265\"")
    }

    signingConfigs {
        val path = System.getenv("MTA_ANDROID_KEYSTORE_PATH")
        if (!path.isNullOrBlank()) {
            create("releaseFromEnv") {
                storeFile = file(path)
                storePassword = System.getenv("MTA_ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("MTA_ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("MTA_ANDROID_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfigs.findByName("releaseFromEnv")?.let { signingConfig = it }
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources.excludes += setOf("META-INF/LICENSE*", "META-INF/NOTICE*")
    }
}


dependencies {
    implementation("androidx.core:core:1.19.1")
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.30.0")
}
