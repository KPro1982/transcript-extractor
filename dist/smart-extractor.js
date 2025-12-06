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
exports.SmartExtractor = void 0;

const pdf_to_image_external_1 = require("./pdf-to-image-external");
const ocr_engine_1 = require("./ocr-engine");
const text_reconstructor_1 = require("./text-reconstructor");
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));

/**
 * Smart extractor that prioritizes digital text extraction
 * and only falls back to OCR when digital extraction fails.
 * 
 * Strategy:
 * 1. First attempt digital text extraction using pdfjs-dist
 * 2. Check if digital extraction produced meaningful text
 * 3. Only use OCR as a fallback for pages with no/insufficient digital text
 * 
 * This is much faster for digitally-created PDFs while still
 * supporting scanned documents that require OCR.
 */
class SmartExtractor {
    constructor(options = {}) {
        this.imageConverter = new pdf_to_image_external_1.ExternalPDFToImageConverter({ 
            dpi: options.dpi || 300,
            outputDir: options.outputDir || './temp/images'
        });
        this.ocrEngine = new ocr_engine_1.OCREngine('eng');
        this.textReconstructor = new text_reconstructor_1.TextReconstructor();
        this.leftMarginPercent = options.leftMarginPercent || 0.12;
        this.topMarginPercent = options.topMarginPercent || 0.10;
        this.bottomMarginPercent = options.bottomMarginPercent || 0.90;
        // Minimum text items per page to consider digital extraction successful
        this.minTextItemsThreshold = options.minTextItemsThreshold || 10;
        this.ocrInitialized = false;
    }

    async extract(pdfPath) {
        console.log(`\n${'='.repeat(60)}`);
        console.log('SMART PDF Extraction (Digital First, OCR Fallback)');
        console.log(`${'='.repeat(60)}`);
        console.log(`Source: ${pdfPath}`);
        console.log(`Strategy: Digital extraction first, OCR only when needed`);
        console.log(`${'='.repeat(60)}\n`);

        // Step 1: Try digital extraction first
        console.log('[1/3] Attempting digital text extraction...');
        let digitalPages;
        try {
            digitalPages = await this.extractDigitalText(pdfPath);
            console.log(`  ✓ Processed ${digitalPages.length} pages digitally\n`);
        } catch (error) {
            console.log(`  ✗ Digital extraction failed: ${error.message}`);
            console.log('  → Will use OCR for all pages\n');
            digitalPages = [];
        }

        // Step 2: Analyze which pages need OCR
        console.log('[2/3] Analyzing extraction quality per page...');
        const pageAnalysis = this.analyzePages(digitalPages);
        
        const pagesNeedingOCR = pageAnalysis.filter(p => p.needsOCR).map(p => p.pageNumber);
        const pagesWithDigital = pageAnalysis.filter(p => !p.needsOCR).map(p => p.pageNumber);
        
        console.log(`  Digital extraction sufficient: ${pagesWithDigital.length} pages`);
        console.log(`  OCR fallback needed: ${pagesNeedingOCR.length} pages`);
        
        if (pagesNeedingOCR.length > 0) {
            console.log(`  Pages requiring OCR: ${pagesNeedingOCR.join(', ')}\n`);
        } else {
            console.log(`  ✓ All pages extracted digitally - no OCR needed!\n`);
        }

        // Step 3: Process pages - use digital where possible, OCR where needed
        console.log('[3/3] Building final results...');
        const results = [];
        let ocrImages = null;

        for (let i = 0; i < digitalPages.length; i++) {
            const digitalPage = digitalPages[i];
            const analysis = pageAnalysis[i];
            
            if (analysis.needsOCR) {
                // This page needs OCR
                console.log(`  Page ${analysis.pageNumber}: Using OCR fallback`);
                
                // Initialize OCR engine if needed
                if (!this.ocrInitialized) {
                    console.log('    Initializing OCR engine...');
                    await this.ocrEngine.initialize();
                    this.ocrInitialized = true;
                }
                
                // Convert to images if not done yet
                if (!ocrImages) {
                    console.log('    Converting PDF to images for OCR...');
                    ocrImages = await this.imageConverter.convert(pdfPath);
                }
                
                // Find the image for this page
                const pageImage = ocrImages.find(img => img.pageNumber === analysis.pageNumber);
                if (pageImage) {
                    const ocrResult = await this.ocrEngine.processImage(pageImage.imagePath, analysis.pageNumber);
                    const ocrPage = this.convertOCRToPageResult(ocrResult, analysis.pageNumber);
                    results.push(ocrPage);
                } else {
                    // Fallback: use whatever digital text we have
                    console.log(`    Warning: No image found for page ${analysis.pageNumber}, using partial digital text`);
                    results.push(this.convertDigitalToPageResult(digitalPage, analysis.pageNumber));
                }
            } else {
                // Digital extraction is sufficient
                console.log(`  Page ${analysis.pageNumber}: Using digital extraction (${digitalPage.textItems.length} items)`);
                results.push(this.convertDigitalToPageResult(digitalPage, analysis.pageNumber));
            }
        }

        // Cleanup
        console.log(`\nCleaning up...`);
        if (this.ocrInitialized) {
            await this.ocrEngine.terminate();
            this.ocrInitialized = false;
        }
        if (ocrImages) {
            this.imageConverter.cleanup(ocrImages);
        }

        console.log(`\n${'='.repeat(60)}`);
        console.log(`✓ Smart Extraction Complete - ${results.length} pages processed`);
        console.log(`  Digital: ${pagesWithDigital.length} pages | OCR: ${pagesNeedingOCR.length} pages`);
        console.log(`${'='.repeat(60)}\n`);

        return results;
    }

    /**
     * Extract digital text using pdfjs-dist
     */
    async extractDigitalText(pdfPath) {
        const pdfjsLib = await Promise.resolve().then(() => __importStar(require('pdfjs-dist')));
        
        // Set worker
        try {
            const workerPath = require.resolve('pdfjs-dist/build/pdf.worker.mjs');
            pdfjsLib.GlobalWorkerOptions.workerSrc = workerPath;
        } catch (e) {
            pdfjsLib.GlobalWorkerOptions.workerSrc = '';
        }

        const pdfBuffer = fs.readFileSync(pdfPath);
        const pdfBytes = new Uint8Array(pdfBuffer);
        const loadingTask = pdfjsLib.getDocument({ data: pdfBytes, useWorkerFetch: false, isEvalSupported: false });
        const pdfDoc = await loadingTask.promise;

        const pages = [];

        for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
            const page = await pdfDoc.getPage(pageNum);
            const viewport = page.getViewport({ scale: 1.0 });
            const textContent = await page.getTextContent();
            
            const textItems = [];
            const items = textContent.items || [];
            
            for (const item of items) {
                const str = item.str || '';
                if (!str.trim()) continue;
                
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

            const status = textItems.length >= this.minTextItemsThreshold ? '✓' : '⚠';
            console.log(`  ${status} Page ${pageNum}: ${textItems.length} text items`);
        }

        return pages;
    }

    /**
     * Analyze pages to determine which need OCR fallback
     */
    analyzePages(digitalPages) {
        return digitalPages.map(page => {
            const textCount = page.textItems.length;
            const hasSubstantialText = textCount >= this.minTextItemsThreshold;
            
            // Check if text items have reasonable content (not just whitespace/symbols)
            const meaningfulItems = page.textItems.filter(item => {
                const text = item.text.trim();
                return text.length > 0 && /[a-zA-Z0-9]/.test(text);
            });
            const hasMeaningfulContent = meaningfulItems.length >= this.minTextItemsThreshold / 2;

            return {
                pageNumber: page.pageNumber,
                textItemCount: textCount,
                meaningfulItemCount: meaningfulItems.length,
                needsOCR: !hasSubstantialText || !hasMeaningfulContent
            };
        });
    }

    /**
     * Convert digital extraction result to standard page format
     */
    convertDigitalToPageResult(digitalPage, pageNumber) {
        const { width, height, textItems } = digitalPage;
        
        // Calculate boundaries
        const leftMarginBoundary = width * this.leftMarginPercent;
        const topMarginBoundary = height * this.topMarginPercent;
        const bottomMarginBoundary = height * this.bottomMarginPercent;

        const lineNumbers = [];
        const headers = [];
        const footers = [];
        const mainContent = [];

        // Categorize text items
        for (const item of textItems) {
            const centerY = item.y + (item.height || 0) / 2;
            const centerX = item.x + (item.width || 0) / 2;
            
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

            // Check for line numbers in left margin
            const isNumeric = /^\d+\.?\s*$/.test(item.text.trim());
            const isInLeftMargin = centerX < leftMarginBoundary;

            if (centerY < topMarginBoundary) {
                textBlock.type = 'header';
                headers.push(textBlock);
            } else if (centerY > bottomMarginBoundary) {
                textBlock.type = 'footer';
                footers.push(textBlock);
            } else if (isInLeftMargin && isNumeric) {
                textBlock.type = 'line_number';
                lineNumbers.push(textBlock);
            } else if (centerX >= leftMarginBoundary) {
                textBlock.type = 'content';
                mainContent.push(textBlock);
            }
        }

        return {
            pageNumber,
            dimensions: { width, height },
            lineNumbers: this.sortByPosition(lineNumbers),
            headers: this.sortByPosition(headers),
            footers: this.sortByPosition(footers),
            mainContent: this.sortByPosition(mainContent),
            confidence: 100, // Digital extraction
            extractionMethod: 'digital'
        };
    }

    /**
     * Convert OCR result to standard page format
     */
    convertOCRToPageResult(ocrResult, pageNumber) {
        const { width, height, words } = ocrResult;
        
        // Calculate boundaries
        const leftMarginBoundary = width * this.leftMarginPercent;
        const topMarginBoundary = height * this.topMarginPercent;
        const bottomMarginBoundary = height * this.bottomMarginPercent;

        const lineNumbers = [];
        const headers = [];
        const footers = [];
        const mainContent = [];

        for (const word of words) {
            const { text, bbox, confidence } = word;
            const trimmedText = text.trim();
            if (!trimmedText) continue;

            const centerX = bbox.x + bbox.width / 2;
            const centerY = bbox.y + bbox.height / 2;

            const textBlock = {
                text: trimmedText,
                position: bbox,
                confidence,
                type: 'content',
            };

            // Check for line numbers
            const isNumeric = /^\d+\.?\s*$/.test(trimmedText);
            const isInLeftMargin = centerX < leftMarginBoundary;

            if (centerY < topMarginBoundary) {
                textBlock.type = 'header';
                headers.push(textBlock);
            } else if (centerY > bottomMarginBoundary) {
                textBlock.type = 'footer';
                footers.push(textBlock);
            } else if (isInLeftMargin && isNumeric) {
                textBlock.type = 'line_number';
                lineNumbers.push(textBlock);
            } else if (centerX >= leftMarginBoundary) {
                textBlock.type = 'content';
                mainContent.push(textBlock);
            }
        }

        return {
            pageNumber,
            dimensions: { width, height },
            lineNumbers: this.sortByPosition(lineNumbers),
            headers: this.sortByPosition(headers),
            footers: this.sortByPosition(footers),
            mainContent: this.sortByPosition(mainContent),
            confidence: ocrResult.confidence || 90,
            extractionMethod: 'ocr'
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

exports.SmartExtractor = SmartExtractor;



