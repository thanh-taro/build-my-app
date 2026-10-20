---
name: stack-android
description: Stack pack for native Android apps in build-my-app — Kotlin/Compose project layout, Gradle build and tests, emulator runs and screenshots, code generation, quality tooling, and Play Console release and deploy steps. Use in phases 3–7 when the chosen platform is Android.
---

# Stack pack — Android (Kotlin / Compose)

- **Layout**: app module + feature/core modules per spec.
- **Build/test**: `./gradlew assembleDebug test connectedAndroidTest`.
- **Run & screenshot**: `emulator`, `adb install`, `adb shell screencap`; Compose UI tests for
  state screenshots.
- **Codegen**: schema → data classes; tokens → theme; `copy.md` → `strings.xml`.
- **Quality**: accessibility scanner + TalkBack pass; macrobenchmarks for NFRs.
- **Local env**: `debug` build type on the emulator against local services
  (`10.0.2.2` for host), product flavors per environment (`local`, `staging`, `prod`).
- **Release (phase 6)**: `./gradlew bundleRelease` (R8 on); install the release build on the
  emulator and run the flows locally. Upload keys are user-owned.
- **Deploy (phase 7)**: user-owned — Play Console account, data safety form, review.
  Staging = internal testing track; production = staged rollout percentage.
