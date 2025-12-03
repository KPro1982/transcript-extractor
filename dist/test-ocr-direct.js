"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const pdf_to_image_canvas_1 = require("./pdf-to-image-canvas");
const ocr_engine_1 = require("./ocr-engine");
const fs = __importStar(require("fs"));
/**
 * Direct OCR test to see what Tesseract is actually finding
 */
async function testOCR(pdfPath, pageNum = 3) {
    console.log('\n╔════════════════════════════════════════════════════════════╗');
    console.log('║              Direct OCR Test & Debug Tool                 ║');
    console.log('╚════════════════════════════════════════════════════════════╝\n');
    // Convert page to image
    console.log(`[1/3] Converting page ${pageNum} to image...`);
    const converter = new pdf_to_image_canvas_1.PDFToImageConverter({ dpi: 300 });
    const images = await converter.convert(pdfPath);
    const targetImage = images.find(img => img.pageNumber === pageNum);
    if (!targetImage) {
        console.error('Page not found!');
        return;
    }
    console.log(`  Image: ${targetImage.imagePath}`);
    console.log(`  Size: ${targetImage.width} x ${targetImage.height}\n`);
    // Run OCR
    console.log('[2/3] Running OCR...');
    const ocrEngine = new ocr_engine_1.OCREngine('eng');
    await ocrEngine.initialize();
    const result = await ocrEngine.processImage(targetImage.imagePath, pageNum);
    console.log(`  Confidence: ${result.confidence.toFixed(1)}%`);
    console.log(`  Words found: ${result.words.length}`);
    console.log(`  Lines found: ${result.lines.length}\n`);
    // Analyze left margin specifically
    console.log('[3/3] Analyzing left margin...\n');
    const leftMarginPercent = 0.12;
    const leftBoundary = targetImage.width * leftMarginPercent;
    console.log(`Left margin boundary: X < ${leftBoundary.toFixed(1)}`);
    console.log(`Page dimensions: ${targetImage.width} x ${targetImage.height}\n`);
    // Find all words in left margin
    const leftMarginWords = result.words.filter(word => {
        const centerX = word.bbox.x + word.bbox.width / 2;
        return centerX < leftBoundary;
    });
    console.log(`Words in left margin: ${leftMarginWords.length}\n`);
    if (leftMarginWords.length > 0) {
        console.log('LEFT MARGIN WORDS (sorted by Y position):');
        leftMarginWords
            .sort((a, b) => a.bbox.y - b.bbox.y)
            .forEach(word => {
            const isNumeric = /^\d+\.?\s*$/.test(word.text.trim());
            const marker = isNumeric ? ' 🔢' : '';
            console.log(`  [${word.bbox.x.toFixed(0)}, ${word.bbox.y.toFixed(0)}] "${word.text}" (${word.confidence.toFixed(1)}%)${marker}`);
        });
    }
    else {
        console.log('❌ NO WORDS FOUND IN LEFT MARGIN\n');
        console.log('Possible issues:');
        console.log('  1. Line numbers may be too faint in rendered image');
        console.log('  2. OCR confidence threshold filtering them out');
        console.log('  3. Image scaling/quality issues');
        console.log('  4. Need higher DPI\n');
        // Show first 20 words from anywhere for debugging
        console.log('First 20 words found ANYWHERE on page:');
        result.words.slice(0, 20).forEach(word => {
            console.log(`  [${word.bbox.x.toFixed(0)}, ${word.bbox.y.toFixed(0)}] "${word.text}" (${word.confidence.toFixed(1)}%)`);
        });
    }
    // Check if image file exists so user can inspect it
    console.log(`\n📸 Image saved at: ${targetImage.imagePath}`);
    console.log('   Open this image to visually check if line numbers are visible');
    await ocrEngine.terminate();
    // Don't cleanup so user can inspect the image
    console.log('\n💡 Image NOT deleted - inspect it to see what OCR sees');
}
async function main() {
    const args = process.argv.slice(2);
    if (args.length === 0) {
        console.log('Usage: npm run test-ocr <pdf-file> [page-number]');
        console.log('Example: npm run test-ocr "Transcripts/Deposition example.pdf" 3');
        process.exit(1);
    }
    const pdfPath = args[0];
    const pageNum = args[1] ? parseInt(args[1]) : 3;
    if (!fs.existsSync(pdfPath)) {
        console.error(`Error: PDF not found: ${pdfPath}`);
        process.exit(1);
    }
    await testOCR(pdfPath, pageNum);
}
if (require.main === module) {
    main();
}
