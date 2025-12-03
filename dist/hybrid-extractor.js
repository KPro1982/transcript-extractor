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
exports.HybridExtractor = void 0;
const pdf_to_image_external_1 = require("./pdf-to-image-external");
const ocr_engine_1 = require("./ocr-engine");
const text_reconstructor_1 = require("./text-reconstructor");
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
/**
 * Hybrid extractor that combines:
 * - Digital text extraction (fast, accurate) for main content
 * - OCR extraction (slower) ONLY for left margin line numbers
 *
 * Perfect for legal transcripts where line numbers are images
 * but the main text is digital.
 */
class HybridExtractor {
    constructor(options = {}) {
        this.imageConverter = new pdf_to_image_external_1.ExternalPDFToImageConverter({ dpi: options.dpi || 300 });
        this.ocrEngine = new ocr_engine_1.OCREngine('eng');
        this.textReconstructor = new text_reconstructor_1.TextReconstructor();
        this.leftMarginPercent = options.leftMarginPercent || 0.12;
        this.topMarginPercent = options.topMarginPercent || 0.10;
        this.bottomMarginPercent = options.bottomMarginPercent || 0.90;
    }
    async extract(pdfPath) {
        console.log(`\n${'='.repeat(60)}`);
        console.log('HYBRID PDF Extraction (Digital Text + OCR Line Numbers)');
        console.log(`${'='.repeat(60)}`);
        console.log(`Source: ${pdfPath}`);
        console.log(`Mode: Digital text + OCR margins`);
        console.log(`${'='.repeat(60)}\n`);
        // Step 1: Extract digital text using pdfjs-dist
        console.log('[1/5] Extracting digital text from PDF...');
        const digitalPages = await this.extractDigitalText(pdfPath);
        console.log(`  ✓ Extracted text from ${digitalPages.length} pages\n`);
        // Step 2: Convert PDF to images for OCR
        console.log('[2/5] Converting PDF to images for margin OCR...');
        const images = await this.imageConverter.convert(pdfPath);
        console.log(`  ✓ Converted ${images.length} pages\n`);
        // Step 3: Initialize OCR engine
        console.log('[3/5] Initializing OCR engine...');
        await this.ocrEngine.initialize();
        console.log('');
        // Step 4: OCR only the left margin of each page
        console.log('[4/5] OCR processing left margins for line numbers...');
        const results = [];
        for (let i = 0; i < images.length; i++) {
            const image = images[i];
            const digitalPage = digitalPages[i];
            console.log(`\n========== Processing Page ${image.pageNumber}/${images.length} ==========`);
            // OCR the full page (we'll filter to left margin after)
            const ocrResult = await this.ocrEngine.processImage(image.imagePath, image.pageNumber);
            // Extract line numbers from left margin
            const lineNumbers = this.extractLineNumbersFromOCR(ocrResult.words, ocrResult.width, ocrResult.height);
            console.log(`  [RESULT] Page ${image.pageNumber}: ${lineNumbers.length} line numbers found in left margin!`);
            // Combine with digital text
            const analyzed = this.combineDigitalAndOCR(digitalPage, lineNumbers, image.pageNumber);
            results.push(analyzed);
        }
        console.log(`\n[5/5] Cleaning up...`);
        await this.ocrEngine.terminate();
        this.imageConverter.cleanup(images);
        console.log(`\n${'='.repeat(60)}`);
        console.log(`✓ Hybrid Extraction Complete - ${results.length} pages processed`);
        console.log(`${'='.repeat(60)}\n`);
        return results;
    }
    async extractDigitalText(pdfPath) {
        const pdfjsLib = await Promise.resolve().then(() => __importStar(require('pdfjs-dist')));
        // Set worker
        try {
            const workerPath = require.resolve('pdfjs-dist/build/pdf.worker.mjs');
            pdfjsLib.GlobalWorkerOptions.workerSrc = workerPath;
        }
        catch (e) {
            pdfjsLib.GlobalWorkerOptions.workerSrc = '';
        }
        const pdfBuffer = fs.readFileSync(pdfPath);
        const pdfBytes = new Uint8Array(pdfBuffer);
        const loadingTask = pdfjsLib.getDocument({ data: pdfBytes });
        const pdfDoc = await loadingTask.promise;
        const pages = [];
        for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
            const page = await pdfDoc.getPage(pageNum);
            const viewport = page.getViewport({ scale: 1.0 });
            const textContent = await page.getTextContent();
            const textItems = [];
            // Process text items
            const items = textContent.items || [];
            for (const item of items) {
                const str = item.str || '';
                if (!str.trim())
                    continue;
                const transform = item.transform || [];
                const x = transform[4] || 0;
                const y = viewport.height - (transform[5] || 0);
                textItems.push({
                    text: str,
                    x,
                    y,
                    width: item.width || 0,
                    height: item.height || 12,
                });
            }
            pages.push({
                pageNumber: pageNum,
                width: viewport.width,
                height: viewport.height,
                textItems,
            });
            console.log(`  ✓ Page ${pageNum}: ${textItems.length} text items`);
        }
        return pages;
    }
    extractLineNumbersFromOCR(words, pageWidth, pageHeight) {
        const leftMarginBoundary = pageWidth * this.leftMarginPercent;
        const topMarginBoundary = pageHeight * this.topMarginPercent;
        const bottomMarginBoundary = pageHeight * this.bottomMarginPercent;
        const lineNumberPattern = /^[1-9]\d?$/; // Only 1-2 digit line numbers
        const lineNumbers = [];
        for (const word of words) {
            const { text, bbox, confidence } = word;
            const trimmedText = text.trim();
            if (!trimmedText)
                continue;
            const centerX = bbox.x + bbox.width / 2;
            const centerY = bbox.y + bbox.height / 2;
            // Check if in left margin, not in header/footer, and matches line number pattern
            const isInLeftMargin = centerX < leftMarginBoundary;
            const isInMainArea = centerY >= topMarginBoundary && centerY <= bottomMarginBoundary;
            const isLineNumber = lineNumberPattern.test(trimmedText);
            if (isInLeftMargin && isInMainArea && isLineNumber) {
                lineNumbers.push({
                    text: trimmedText,
                    position: bbox,
                    confidence,
                    type: 'line_number',
                });
            }
        }
        // Sort by Y position
        return lineNumbers.sort((a, b) => a.position.y - b.position.y);
    }
    combineDigitalAndOCR(digitalPage, lineNumbers, pageNumber) {
        const { width, height, textItems } = digitalPage;
        // Calculate boundaries
        const leftMarginBoundary = width * this.leftMarginPercent;
        const topMarginBoundary = height * this.topMarginPercent;
        const bottomMarginBoundary = height * this.bottomMarginPercent;
        const headers = [];
        const footers = [];
        const mainContent = [];
        // Categorize digital text
        for (const item of textItems) {
            const centerY = item.y + item.height / 2;
            const centerX = item.x + item.width / 2;
            const textBlock = {
                text: item.text,
                position: {
                    x: item.x,
                    y: item.y,
                    width: item.width,
                    height: item.height,
                },
                confidence: 100, // Digital text is 100% accurate
                type: 'content',
            };
            // Categorize by position
            if (centerY < topMarginBoundary) {
                textBlock.type = 'header';
                headers.push(textBlock);
            }
            else if (centerY > bottomMarginBoundary) {
                textBlock.type = 'footer';
                footers.push(textBlock);
            }
            else if (centerX >= leftMarginBoundary) {
                // Only include content that's NOT in the left margin
                textBlock.type = 'content';
                mainContent.push(textBlock);
            }
            // Ignore digital text in left margin (where line numbers are)
        }
        return {
            pageNumber,
            dimensions: { width, height },
            lineNumbers: lineNumbers, // From OCR
            headers: this.sortByPosition(headers),
            footers: this.sortByPosition(footers),
            mainContent: this.sortByPosition(mainContent),
            confidence: 100, // Digital text
        };
    }
    sortByPosition(blocks) {
        return blocks.sort((a, b) => {
            const yDiff = a.position.y - b.position.y;
            if (Math.abs(yDiff) > 5) {
                return yDiff;
            }
            return a.position.x - b.position.x;
        });
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
exports.HybridExtractor = HybridExtractor;
