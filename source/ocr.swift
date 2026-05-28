// macOS Vision OCR — reads an image, prints recognized text in reading order.
// Usage: swift ocr.swift <image_path>
import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count >= 2 else {
    FileHandle.standardError.write("usage: ocr.swift <image>\n".data(using: .utf8)!)
    exit(1)
}

let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("cannot load image: \(path)\n".data(using: .utf8)!)
    exit(2)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
request.recognitionLanguages = ["en-GB", "en-US"]

let handler = VNImageRequestHandler(cgImage: cg, options: [:])
do {
    try handler.perform([request])
} catch {
    FileHandle.standardError.write("ocr failed: \(error)\n".data(using: .utf8)!)
    exit(3)
}

guard let observations = request.results else { exit(0) }

// Sort observations top-to-bottom, then left-to-right (Vision origin is bottom-left).
struct Line { let text: String; let x: CGFloat; let y: CGFloat }
var lines: [Line] = []
for obs in observations {
    guard let top = obs.topCandidates(1).first else { continue }
    let box = obs.boundingBox
    lines.append(Line(text: top.string, x: box.minX, y: box.minY))
}
// Group into rows by y proximity, sort rows top→bottom, within row left→right
lines.sort { $0.y > $1.y }
var rows: [[Line]] = []
let yTol: CGFloat = 0.012
for line in lines {
    if var last = rows.last, let ref = last.first, abs(ref.y - line.y) < yTol {
        last.append(line)
        rows[rows.count - 1] = last
    } else {
        rows.append([line])
    }
}
var out = ""
for row in rows {
    let sorted = row.sorted { $0.x < $1.x }
    out += sorted.map { $0.text }.joined(separator: " ") + "\n"
}
print(out)
