# R8 rules for the release build.
#
# Flutter's engine references the Play Core deferred-components API, which is
# not on the classpath unless the app actually uses deferred components. With
# minification on, R8 treats those missing classes as a hard error and the
# build dies with:
#
#   Missing class com.google.android.play.core.tasks.Task
#     (referenced from PlayStoreDeferredComponentManager)
#   Execution failed for task ':app:minifyReleaseWithR8'
#
# The app does not use deferred components, so the right answer is to tell R8
# those references are expected to be absent rather than to disable
# minification — the release build stays smaller, and Play wants it that way.
-dontwarn com.google.android.play.core.**
-dontwarn com.google.android.play.core.splitcompat.**
-dontwarn com.google.android.play.core.splitinstall.**
-dontwarn com.google.android.play.core.tasks.**

# Flutter's engine is reached by reflection from the platform side, so R8 must
# not strip or rename it. Without these the release build starts and then dies
# on a missing class, which is a miserable thing to debug on a phone.
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# flutter_secure_storage stores the token through androidx.security, which is
# reflective. Losing these would silently break sign-in persistence.
-keep class androidx.security.crypto.** { *; }
