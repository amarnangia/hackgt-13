import XCTest

/// Puts the Weave widgets on the simulator's home screen (drives SpringBoard like a person would).
/// Run: xcodebuild test -project Weave.xcodeproj -scheme Weave -destination 'platform=iOS Simulator,name=iPhone 16 Pro' -only-testing:WeaveUITests/AddWidgetTests
final class AddWidgetTests: XCTestCase {
    let sb = XCUIApplication(bundleIdentifier: "com.apple.springboard")

    func testAddWidgets() throws {
        XCUIApplication().launch()   // iOS lists an app's widgets only after the app has run once
        sleep(3)
        let sizes = (ProcessInfo.processInfo.environment["WIDGET_SIZES"] ?? "Medium,Small").split(separator: ",").map(String.init)
        for size in sizes { try addWidget(size: size) }
        XCUIDevice.shared.press(.home)
        print("HOME:", sb.icons.allElementsBoundByIndex.filter { $0.label.contains("Weave") }.map { "\($0.label)/\($0.value ?? "")" })
    }

    func button(_ label: String) -> XCUIElement {
        sb.buttons.matching(NSPredicate(format: "label ENDSWITH %@", label)).firstMatch
    }

    func tap(_ e: XCUIElement, _ what: String) {
        XCTAssert(e.waitForExistence(timeout: 5), "\(what) not found. Buttons: " + sb.buttons.allElementsBoundByIndex.map(\.label).joined(separator: " | "))
        e.tap()
        sleep(1)
    }

    func addWidget(size: String) throws {
        XCUIDevice.shared.press(.home)
        sleep(1)
        let icon = sb.icons.allElementsBoundByIndex.first { $0.isHittable && $0.frame.width > 0 && $0.frame.width < 100 }
        XCTAssertNotNil(icon, "no visible app icon to long-press")
        icon?.press(forDuration: 1.5)
        tap(button("Edit Home Screen"), "Edit Home Screen")
        tap(button("Edit"), "Edit")
        tap(button("Add Widget"), "Add Widget")
        sleep(1)
        let search = sb.searchFields.matching(NSPredicate(format: "identifier != 'dewey-search-field'")).firstMatch
        tap(search, "widget search")
        search.typeText("Weave")
        sleep(2)
        let app = sb.cells.matching(NSPredicate(format: "label CONTAINS 'Weave'")).firstMatch
        let text = sb.staticTexts.matching(NSPredicate(format: "label == 'Weave'")).firstMatch
        for _ in 0..<10 where !app.exists && !text.exists { sleep(1) }
        tap(app.exists ? app : text, "Weave in widget gallery")
        sleep(1)
        // Size pages: Small, Medium, Large. Tap the right side of the page dots to step forward.
        let steps = ["Small": 0, "Medium": 1, "Large": 2][size] ?? 0
        let dots = sb.pageIndicators.matching(NSPredicate(format: "value BEGINSWITH 'page '")).firstMatch
        for _ in 0..<steps where dots.exists {
            dots.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5)).tap()
            sleep(1)
        }
        if steps > 0 { XCTAssertEqual(dots.value as? String, "page \(steps + 1) of 3") }
        // Each size page has its own Add Widget button; press the one on screen.
        let confirm = sb.buttons.matching(NSPredicate(format: "label ENDSWITH 'Add Widget'")).allElementsBoundByIndex
            .first { $0.isHittable && sb.frame.contains(CGPoint(x: $0.frame.midX, y: $0.frame.midY)) }
        XCTAssertNotNil(confirm, "no visible Add Widget button")
        confirm?.tap()
        sleep(1)
        let done = button("Done")
        if done.waitForExistence(timeout: 3) { done.tap() }
        sleep(1)
    }
}
