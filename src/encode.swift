import Foundation
import AVFoundation
import AppKit

// Run from the project root after render_basketball.py.
let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let output = root.appendingPathComponent("outputs/basketball_shot_revised.mp4")
try? FileManager.default.removeItem(at: output)
let writer = try AVAssetWriter(outputURL: output, fileType: .mp4)
let input = AVAssetWriterInput(mediaType: .video, outputSettings: [AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: 1280, AVVideoHeightKey: 720, AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 4000000, AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel]])
let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB,kCVPixelBufferWidthKey as String:1280,kCVPixelBufferHeightKey as String:720,kCVPixelBufferCGImageCompatibilityKey as String:true,kCVPixelBufferCGBitmapContextCompatibilityKey as String:true])
writer.add(input)
guard writer.startWriting() else { fatalError("\(writer.error!)") }
writer.startSession(atSourceTime: .zero)
for i in 0..<150 {
    while !input.isReadyForMoreMediaData { Thread.sleep(forTimeInterval: 0.002) }
    let url=root.appendingPathComponent(String(format:"work/frames/%04d.png",i))
    let source=CGImageSourceCreateWithURL(url as CFURL,nil)!
    let image=CGImageSourceCreateImageAtIndex(source,0,nil)!
    var buffer: CVPixelBuffer?
    CVPixelBufferPoolCreatePixelBuffer(nil,adaptor.pixelBufferPool!,&buffer)
    let pb=buffer!
    CVPixelBufferLockBaseAddress(pb,[])
    let ctx=CGContext(data:CVPixelBufferGetBaseAddress(pb),width:1280,height:720,bitsPerComponent:8,bytesPerRow:CVPixelBufferGetBytesPerRow(pb),space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.noneSkipFirst.rawValue)!
    ctx.draw(image,in:CGRect(x:0,y:0,width:1280,height:720))
    CVPixelBufferUnlockBaseAddress(pb,[])
    guard adaptor.append(pb,withPresentationTime:CMTime(value:Int64(i),timescale:30)) else { fatalError("\(writer.error!)") }
}
input.markAsFinished()
writer.endSession(atSourceTime:CMTime(value:5,timescale:1))
let sem=DispatchSemaphore(value:0)
writer.finishWriting { sem.signal() }
sem.wait()
guard writer.status == .completed else { fatalError("\(writer.error!)") }
let asset=AVURLAsset(url:output)
let track=asset.tracks(withMediaType:.video).first!
let reader=try AVAssetReader(asset:asset)
let readout=AVAssetReaderTrackOutput(track:track,outputSettings:[kCVPixelBufferPixelFormatTypeKey as String:kCVPixelFormatType_32BGRA])
reader.add(readout); reader.startReading()
var count=0
while readout.copyNextSampleBuffer() != nil { count += 1 }
let report="duration=\(CMTimeGetSeconds(asset.duration)) size=\(track.naturalSize) fps=\(track.nominalFrameRate) audio_tracks=\(asset.tracks(withMediaType:.audio).count) decoded_frames=\(count) reader_status=\(reader.status.rawValue)"
print(report)
try report.write(to:root.appendingPathComponent("work/video_validation.txt"),atomically:true,encoding:.utf8)
