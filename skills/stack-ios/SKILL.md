---
name: stack-ios
description: Stack pack for native iOS apps in build-my-app — Swift/SwiftUI project layout, build and test commands, simulator runs and screenshots, code generation targets, accessibility and performance tooling, TestFlight/App Store release and deploy steps. Use in phases 3–7 when the chosen platform is iOS.
---

# Stack pack — iOS (Swift / SwiftUI)

- **Layout**: app target + local Swift packages per module (from `specs/40-technical/modules/`).
- **Build/test**: `xcodebuild -scheme <App> -destination 'platform=iOS Simulator,name=<device>' build test`;
  Swift Testing / XCTest; test names per `adapters/tests.md`.
- **Resource limits** (always add these flags): `-parallel-testing-worker-count ${BMA_TEST_WORKERS:-2}
  -maximum-concurrent-test-simulator-destinations 1 -jobs ${BMA_TEST_WORKERS:-2}`. Parallel
  testing clones the simulator once per worker, so a high count multiplies memory. While
  iterating, use `-only-testing:<Target>/<Suite>` and `test-without-building` after one
  `build-for-testing`. Use one named simulator for every worktree, and do not boot more.
  `xcrun simctl shutdown all` when the run ends. Give each worktree its own
  `-derivedDataPath .build/DerivedData` so `rm -rf` cleans it up with the worktree.
- **Run & screenshot**: `xcrun simctl boot`, `xcrun simctl install`, `xcrun simctl launch`,
  `xcrun simctl io booted screenshot <file>`; UI tests for repeatable state screenshots.
- **Codegen**: schema → Codable types; tokens → `DesignTokens.swift`; `copy.md` →
  `Localizable.xcstrings`; registry → acknowledgements.
- **Quality**: Accessibility Inspector audit; Instruments (Time Profiler, Allocations) for
  NFRs; real-device checks listed as manual items.
- **Licensing**: avoid GPL/LGPL in App Store builds; register every package.
- **Local env**: Debug builds on the simulator against local services (`localhost`, local
  containers) via a `Local` build configuration / scheme; release-only settings in a
  separate configuration.
- **Release (phase 6)**: `xcodebuild archive` + `-exportArchive` with the Release
  configuration; install the exported build on a simulator/device and run the flows locally.
  Signing identities and profiles are user-owned.
- **Deploy (phase 7)**: user-owned — Apple Developer account, App Store Connect record,
  privacy nutrition labels. Staging = TestFlight internal group; production = App Store
  submission (phased release recommended). Upload only with the user's approval.
