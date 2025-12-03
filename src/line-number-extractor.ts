import { createWorker, PSM, OEM } from 'tesseract.js';
import * as sharp from 'sharp';
import * as fs from 'fs';
import * as path from 'path';

interface LineNumberResult {
    lineNumber: string;
    y: number;
    confidence: number;
}

interface LineNumberExtractionResult {
    pageNumber: number;
    lineNumbers: LineNumberResult[];
    marginWidth: number;
    pageHeight: number;
}

/**
 * Specialized extractor for image-based line numbers in legal transcripts.
 * Legal depositions typically have:
 * - Line numbers 1-25 in a narrow left margin (about 5-8% of page width)
 * - Numbers are often images, not selectable text
 * - Consistent vertical spacing between line numbers
 */
export class LineNumberExtractor {
    private worker: Awaited<ReturnType<typeof createWorker>> | null = null;
    private language: string;
    private tempDir: string;

    constructor(language: string = 'eng', tempDir: string = './temp') {
        this.language = language;
        this.tempDir = tempDir;
    }

    async initialize(): Promise<void> {
        console.log('Initializing Line Number Extractor...');
        this.worker = await createWorker(this.language);
        
        // Configure Tesseract for single column of numbers
        // PSM.SINGLE_COLUMN (4) works well for a column of line numbers
        // PSM.SPARSE_TEXT (11) can also work for scattered numbers
        await this.worker.setParameters({
            tessedit_pageseg_mode: PSM.SINGLE_COLUMN,
            tessedit_ocr_engine_mode: OEM.LSTM_ONLY,
            // Only allow digits for line numbers
            tessedit_char_whitelist: '0123456789',
            preserve_interword_spaces: '0',
        });
        
        console.log('  ✓ Line Number Extractor ready');
    }

    /**
     * Extract line numbers from the left margin of a page image.
     * 
     * @param imagePath Path to the full page image
     * @param pageNumber Page number for logging
     * @param marginPercent Percentage of page width to use as margin (default 8%)
     * @param topMarginPercent Top margin to skip (headers) - default 5%
     * @param bottomMarginPercent Bottom margin to skip (footers) - default 5%
     */
    async extractLineNumbers(
        imagePath: string,
        pageNumber: number,
        marginPercent: number = 0.08,
        topMarginPercent: number = 0.05,
        bottomMarginPercent: number = 0.05
    ): Promise<LineNumberExtractionResult> {
        if (!this.worker) {
            throw new Error('Line Number Extractor not initialized. Call initialize() first.');
        }

        console.log(`  [LineNum] Processing page ${pageNumber}...`);

        // Get image dimensions
        const metadata = await sharp(imagePath).metadata();
        const width = metadata.width || 2550;
        const height = metadata.height || 3300;

        // Calculate margin region to crop
        const marginWidth = Math.floor(width * marginPercent);
        const topMargin = Math.floor(height * topMarginPercent);
        const bottomMargin = Math.floor(height * bottomMarginPercent);
        const contentHeight = height - topMargin - bottomMargin;

        console.log(`  [LineNum] Image: ${width}x${height}, Margin crop: ${marginWidth}px wide`);

        // Crop the left margin region
        const croppedPath = path.join(this.tempDir, `margin-page-${pageNumber}.png`);
        
        await sharp(imagePath)
            .extract({
                left: 0,
                top: topMargin,
                width: marginWidth,
                height: contentHeight
            })
            // Preprocess for better OCR
            .greyscale()
            // Increase contrast to make numbers stand out
            .normalize()
            // Sharpen text edges
            .sharpen({ sigma: 1.5 })
            // Convert to high-contrast black and white
            .threshold(128)
            // Negate if needed (dark text on light background is better for Tesseract)
            .negate({ alpha: false })
            .negate({ alpha: false }) // Double negate to ensure dark text on light bg
            .toFile(croppedPath);

        console.log(`  [LineNum] Cropped margin saved to: ${croppedPath}`);

        // OCR the cropped margin
        const { data } = await this.worker.recognize(croppedPath);
        
        const lineNumbers: LineNumberResult[] = [];
        
        // Process words/blocks from OCR result
        if (data.blocks && data.blocks.length > 0) {
            for (const block of data.blocks) {
                if (block.lines) {
                    for (const line of block.lines) {
                        if (line.words) {
                            for (const word of line.words) {
                                const text = word.text.trim();
                                // Match valid line numbers (1-25 typically, but allow up to 99)
                                if (/^[1-9]\d?$/.test(text)) {
                                    const num = parseInt(text, 10);
                                    // Legal transcripts typically have 25 lines per page
                                    if (num >= 1 && num <= 25) {
                                        // Calculate Y position relative to full page
                                        const yInCrop = (word.bbox.y0 + word.bbox.y1) / 2;
                                        const yInPage = yInCrop + topMargin;
                                        
                                        lineNumbers.push({
                                            lineNumber: text,
                                            y: yInPage,
                                            confidence: word.confidence || data.confidence || 90
                                        });
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // If blocks didn't work, try parsing the text directly
        if (lineNumbers.length === 0 && data.text) {
            console.log(`  [LineNum] Parsing text directly...`);
            const lines = data.text.split('\n').filter(l => l.trim());
            
            // Estimate line spacing based on content height and typical 25 lines
            const estimatedLineHeight = contentHeight / 25;
            
            let lineIdx = 0;
            for (const line of lines) {
                const match = line.trim().match(/^(\d{1,2})$/);
                if (match) {
                    const num = parseInt(match[1], 10);
                    if (num >= 1 && num <= 25) {
                        // Estimate Y position based on line index
                        const yEstimate = topMargin + (lineIdx * estimatedLineHeight) + (estimatedLineHeight / 2);
                        lineNumbers.push({
                            lineNumber: match[1],
                            y: yEstimate,
                            confidence: data.confidence || 80
                        });
                    }
                }
                lineIdx++;
            }
        }

        // Sort by Y position
        lineNumbers.sort((a, b) => a.y - b.y);

        // Clean up temporary file
        if (fs.existsSync(croppedPath)) {
            fs.unlinkSync(croppedPath);
        }

        console.log(`  [LineNum] Page ${pageNumber}: Found ${lineNumbers.length} line numbers`);
        if (lineNumbers.length > 0) {
            console.log(`  [LineNum] Numbers: ${lineNumbers.map(ln => ln.lineNumber).join(', ')}`);
        }

        return {
            pageNumber,
            lineNumbers,
            marginWidth,
            pageHeight: height
        };
    }

    /**
     * Alternative approach: Try multiple margin widths and find the best result
     */
    async extractLineNumbersAdaptive(
        imagePath: string,
        pageNumber: number
    ): Promise<LineNumberExtractionResult> {
        const marginWidths = [0.06, 0.08, 0.10, 0.12];
        let bestResult: LineNumberExtractionResult | null = null;
        let bestCount = 0;

        for (const margin of marginWidths) {
            const result = await this.extractLineNumbers(imagePath, pageNumber, margin);
            
            // Prefer results that have counts closer to expected (typically 20-25 lines)
            // with reasonable confidence
            const count = result.lineNumbers.length;
            const avgConfidence = count > 0 
                ? result.lineNumbers.reduce((sum, ln) => sum + ln.confidence, 0) / count 
                : 0;
            
            // Score based on proximity to ideal line count (25) and confidence
            const idealCount = 25;
            const countScore = Math.max(0, 1 - Math.abs(count - idealCount) / idealCount);
            const score = count * countScore * (avgConfidence / 100);
            
            if (score > bestCount || bestResult === null) {
                bestResult = result;
                bestCount = score;
            }
        }

        return bestResult!;
    }

    async terminate(): Promise<void> {
        if (this.worker) {
            await this.worker.terminate();
            this.worker = null;
            console.log('  ✓ Line Number Extractor terminated');
        }
    }
}


