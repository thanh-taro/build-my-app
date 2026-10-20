---
name: stack-android
description: Stack pack for native Android apps in build-my-app — Kotlin/Compose project layout, Gradle build and tests, emulator runs and screenshots, code generation, quality tooling, and Play Console release steps. Use in phases 3–6 when the chosen platform is Android.
---

# Stack pack — Android (Kotlin / Compose)

- **Layout**: app module + feature/core modules per spec.
- **Build/test**: `./gradlew assembleDebug test connectedAndroidTest`.
- **Run & screenshot**: `emulator`, `adb install`, `adb shell screencap`; Compose UI tests for
  state screenshots.
- **Codegen**: schema → data classes; tokens → theme; `copy.md` → `strings.xml`.
- **Quality**: accessibility scanner + TalkBack pass; macrobenchmarks for NFRs.
- **Release**: user-owned — Play Console account, signing keys, data safety form, review.
