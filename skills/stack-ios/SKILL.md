---
name: stack-ios
description: Stack pack for native iOS apps in build-my-app — Swift/SwiftUI project layout, build and test commands, simulator runs and screenshots, code generation targets, accessibility and performance tooling, TestFlight/App Store release and deploy steps. Use in phases 3–7 when the chosen platform is iOS.
---

# Stack pack — iOS (Swift / SwiftUI)

- **Layout**: app target + local Swift packages per module (from `specs/40-technical/modules/`).
- **Build/test**: `xcodebuild -scheme <App> -destination 'platform=iOS Simulator,name=<device>' build test`;
  Swift Testing / XCTest; test names per `adapters/tests.md`.
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
