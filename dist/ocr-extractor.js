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
exports.OCRExtractor = void 0;
const pdf_to_image_canvas_1 = require("./pdf-to-image-canvas");
const ocr_engine_1 = require("./ocr-engine");
const content_analyzer_1 = require("./content-analyzer");
const text_reconstructor_1 = require("./text-reconstructor");
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
class OCRExtractor {
    constructor(config = {}) {
        this.config = {
            dpi: config.dpi || 300,
            language: config.language || 'eng',
            margin: config.margin || {
                leftMarginPercent: 0.12,
                rightMarginPercent: 0.88,
                topMarginPercent: 0.10,
                bottomMarginPercent: 0.90,
            },
            lineNumberPattern: config.lineNumberPattern || /^\d+\.?\s*$/,
        };
        this.imageConverter = new pdf_to_image_canvas_1.PDFToImageConverter({ dpi: this.config.dpi });
        this.ocrEngine = new ocr_engine_1.OCREngine(this.config.language);
        this.contentAnalyzer = new content_analyzer_1.ContentAnalyzer(this.config.margin, this.config.lineNumberPattern);
        this.textReconstructor = new text_reconstructor_1.TextReconstructor();
    }
    async extract(pdfPath) {
        console.log(`\n${'='.repeat(60)}`);
        console.log('OCR PDF Extraction Starting');
        console.log(`${'='.repeat(60)}`);
        console.log(`Source: ${pdfPath}`);
        console.log(`DPI: ${this.config.dpi}`);
        console.log(`Language: ${this.config.language}`);
        console.log(`${'='.repeat(60)}\n`);
        // Step 1: Convert PDF to images
        console.log('[1/4] Converting PDF to images...');
        const images = await this.imageConverter.convert(pdfPath);
        console.log(`  ✓ Converted ${images.length} pages\n`);
        // Step 2: Initialize OCR engine
        console.log('[2/4] Initializing OCR engine...');
        await this.ocrEngine.initialize();
        console.log('');
        // Step 3: Process each page
        console.log(`[3/4] Processing ${images.length} pages with OCR...`);
        const results = [];
        for (const image of images) {
            console.log(`\nProcessing page ${image.pageNumber}/${images.length}:`);
            // OCR the image
            const ocrResult = await this.ocrEngine.processImage(image.imagePath, image.pageNumber);
            // Analyze content
            const analyzed = this.contentAnalyzer.analyze(ocrResult);
            results.push(analyzed);
        }
        console.log(`\n[4/4] Cleaning up...`);
        await this.ocrEngine.terminate();
        this.imageConverter.cleanup(images);
        console.log(`\n${'='.repeat(60)}`);
        console.log(`✓ Extraction Complete - ${results.length} pages processed`);
        console.log(`${'='.repeat(60)}\n`);
        return results;
    }
    async extractAndSave(pdfPath, outputPath, options) {
        const pages = await this.extract(pdfPath);
        console.log('Reconstructing text...');
        const text = this.textReconstructor.reconstructText(pages, options);
        // Ensure output directory exists
        const outputDir = path.dirname(outputPath);
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }
        fs.writeFileSync(outputPath, text, 'utf-8');
        console.log(`✓ Extracted text saved to: ${outputPath}`);
    }
}
exports.OCRExtractor = OCRExtractor;
