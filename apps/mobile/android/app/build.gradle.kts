import java.util.Properties
import java.io.FileInputStream

// Release signing.
//
// The keystore never lives in the repository. Locally it is described by
// android/key.properties (gitignored); in CI the same four values arrive as
// secrets and are written to that file before the build.
//
// With no keystore present the build still works, but it is signed with the
// debug key: fine for sideloading onto your own phone to test, and NOT
// installable as an update over a properly signed build, nor acceptable to
// Google Play. The build prints which of the two happened.
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
val hasReleaseKeystore = keystorePropertiesFile.exists()
if (hasReleaseKeystore) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.fatalibuilders.geofatali"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.fatalibuilders.geofatali"
        // minSdk 24 (Android 7.0) covers the phones actually in use on site;
        // targetSdk tracks the latest stable, which Google Play requires.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasReleaseKeystore) {
            create("release") {
                keyAlias = keystoreProperties["keyAlias"] as String
                keyPassword = keystoreProperties["keyPassword"] as String
                storeFile = file(keystoreProperties["storeFile"] as String)
                storePassword = keystoreProperties["storePassword"] as String
            }
        }
    }

    buildTypes {
        release {
            signingConfig = if (hasReleaseKeystore) {
                logger.lifecycle("GeoFatali: signing release with the upload keystore.")
                signingConfigs.getByName("release")
            } else {
                logger.warn(
                    "GeoFatali: no android/key.properties found, so this release build is " +
                    "signed with the DEBUG key. Install it to test, but it cannot be " +
                    "uploaded to Google Play and cannot update a properly signed install."
                )
                signingConfigs.getByName("debug")
            }
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
