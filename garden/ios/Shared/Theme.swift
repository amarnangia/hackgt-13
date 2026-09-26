import SwiftUI
import UIKit

enum Theme {
    static func dynamic(_ light: UInt32, _ dark: UInt32) -> Color {
        Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(RGB(dark).color) : UIColor(RGB(light).color) })
    }
    static let background = dynamic(0xf6f1e7, 0x0f1512)
    static let card = dynamic(0xfffdf8, 0x18221b)
    static let cardRaised = dynamic(0xf1ebdd, 0x223027)
    static let ink = dynamic(0x1d2a20, 0xedf2ea)
    static let ink2 = dynamic(0x55635a, 0xb2beb4)
    static let line = dynamic(0xe7dfcf, 0x2a362e)
    static let marigold = dynamic(0xd9700a, 0xf0a040)
    static let leaf = dynamic(0x3f8a4a, 0x6cc07a)
    static let soil = dynamic(0x8a5a33, 0xc69463)
    static let flame = dynamic(0xe0561b, 0xff8a4c)

    static func title(_ size: CGFloat) -> Font { .system(size: size, weight: .bold, design: .serif) }
}

extension Stage {
    var color: Color {
        switch self {
        case .seed: Theme.soil
        case .sprout: Theme.leaf
        case .bloom: Theme.marigold
        }
    }
    var symbol: String {
        switch self {
        case .seed: "circle.dotted"
        case .sprout: "leaf.fill"
        case .bloom: "camera.macro"
        }
    }
}

/// Stand-in plant for icons of a whole stage (not a real phrase).
extension Plant {
    static func example(_ stage: Stage, category: String = "food") -> Plant {
        let g = stage == .seed ? 2 : stage == .sprout ? 5 : 9
        return Plant(phrase: "example-\(stage.rawValue)", english: nil, category: category, note: nil, roman: nil,
                     heard: g, asked: 0, growth: g, firstHeard: nil, lastHeard: nil, stage: stage.rawValue, toNext: 0, thirsty: false)
    }
}
