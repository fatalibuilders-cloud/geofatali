# Flutter's engine is reached by reflection from the platform side, so R8 must
# not strip or rename it. Without these the release build starts and then dies
# on a missing class, which is a miserable thing to debug on a phone.
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# flutter_secure_storage uses androidx.security, which is reflective.
-keep class androidx.security.crypto.** { *; }
