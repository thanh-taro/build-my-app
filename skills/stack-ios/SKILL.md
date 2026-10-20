---
name: stack-ios
description: Stack pack for native iOS apps in build-my-app — Swift/SwiftUI project layout, build and test commands, simulator runs and screenshots, code generation targets, accessibility and performance tooling, TestFlight/App Store release steps. Use in phases 3–6 when the chosen platform is iOS.
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
- **Release**: user-owned — Apple Developer account, signing, App Store Connect record,
  TestFlight groups, privacy nutrition labels, submission. Claude prepares archives
  (`xcodebuild archive`/`-exportArchive`) and the checklist.
