"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.OCREngine = void 0;
const tesseract_js_1 = require("tesseract.js");
class OCREngine {
    constructor(language = 'eng') {
        this.worker = null;
        this.language = language;
    }
    async initialize() {
        console.log('Initializing OCR engine...');
        this.worker = await (0, tesseract_js_1.createWorker)(this.language);
        // Configure Tesseract for best accuracy on printed documents
        await this.worker.setParameters({
            tessedit_pageseg_mode: tesseract_js_1.PSM.AUTO,
            tessedit_ocr_engine_mode: tesseract_js_1.OEM.LSTM_ONLY,
            preserve_interword_spaces: '1',
        });
        console.log('  ✓ OCR engine ready');
    }
    async processImage(imagePath, pageNumber) {
        if (!this.worker) {
            throw new Error('OCR worker not initialized. Call initialize() first.');
        }
        console.log(`  [OCR] Processing page ${pageNumber}...`);
        const startTime = Date.now();
        const { data } = await this.worker.recognize(imagePath);
        console.log(`  [OCR] Page ${pageNumber}: Tesseract completed...`);
        const lines = [];
        const words = [];
        
        // Try to extract words from blocks structure
        if (data.blocks && data.blocks.length > 0) {
            for (const block of data.blocks) {
                if (block.lines) {
                    for (const line of block.lines) {
                        if (line.words) {
                            for (const word of line.words) {
                                words.push({
                                    text: word.text,
                                    confidence: word.confidence || data.confidence || 90,
                                    bbox: {
                                        x: word.bbox.x0,
                                        y: word.bbox.y0,
                                        width: word.bbox.x1 - word.bbox.x0,
                                        height: word.bbox.y1 - word.bbox.y0
                                    }
                                });
                            }
                        }
                    }
                }
            }
            if (words.length > 0) {
                console.log(`  [OCR] Page ${pageNumber}: Extracted ${words.length} words from blocks structure`);
            }
        }
        
        // If still no words, parse text manually as fallback
        if (words.length === 0 && data.text && data.text.trim().length > 0) {
            console.log(`  [OCR] Page ${pageNumber}: Parsing text line-by-line (${data.text.length} chars)...`);
            const textLines = data.text.split('\n');
            const lineNumberPattern = /^([1-9]\d?)(\s|$)/; // Match 1-2 digit number at start of line
            let yPos = 0;
            for (const line of textLines) {
                const trimmedLine = line.trim();
                if (!trimmedLine) {
                    yPos += 20;
                    continue;
                }
                
                // Check if line starts with a line number
                const match = trimmedLine.match(lineNumberPattern);
                if (match) {
                    const lineNum = match[1];
                    // Add the line number as a word in the LEFT margin
                    words.push({
                        text: lineNum,
                        confidence: data.confidence || 90,
                        bbox: {
                            x: 10, // Far left position
                            y: yPos,
                            width: lineNum.length * 10,
                            height: 15
                        }
                    });
                    
                    // Add remaining text as content words (in main area)
                    const restOfLine = trimmedLine.substring(match[0].length).trim();
                    const contentWords = restOfLine.split(/\s+/).filter(w => w.length > 0);
                    let xPos = 200; // Content starts further right
                    for (const wordText of contentWords) {
                        words.push({
                            text: wordText,
                            confidence: data.confidence || 90,
                            bbox: {
                                x: xPos,
                                y: yPos,
                                width: wordText.length * 10,
                                height: 15
                            }
                        });
                        xPos += wordText.length * 10 + 10;
                    }
                } else {
                    // No line number - all words go in content area
                    const lineWords = trimmedLine.split(/\s+/).filter(w => w.length > 0);
                    let xPos = 200;
                    for (const wordText of lineWords) {
                        words.push({
                            text: wordText,
                            confidence: data.confidence || 90,
                            bbox: {
                                x: xPos,
                                y: yPos,
                                width: wordText.length * 10,
                                height: 15
                            }
                        });
                        xPos += wordText.length * 10 + 10;
                    }
                }
                
                yPos += 20;
            }
            console.log(`  [OCR] Page ${pageNumber}: Created ${words.length} words from text`);
        }
        // Process lines - check if data has lines property
        const dataLines = data.lines || [];
        for (const line of dataLines) {
            const lineBbox = {
                x: line.bbox.x0,
                y: line.bbox.y0,
                width: line.bbox.x1 - line.bbox.x0,
                height: line.bbox.y1 - line.bbox.y0,
            };
            const lineWords = [];
            // Process words in line
            const lineWordsList = line.words || [];
            for (const word of lineWordsList) {
                const wordBbox = {
                    x: word.bbox.x0,
                    y: word.bbox.y0,
                    width: word.bbox.x1 - word.bbox.x0,
                    height: word.bbox.y1 - word.bbox.y0,
                };
                const ocrWord = {
                    text: word.text,
                    confidence: word.confidence,
                    bbox: wordBbox,
                };
                lineWords.push(ocrWord);
                words.push(ocrWord);
            }
            lines.push({
                text: line.text,
                words: lineWords,
                bbox: lineBbox,
                confidence: line.confidence,
            });
        }
        // If no lines, try to extract words directly
        if (words.length === 0 && data.words) {
            const dataWords = data.words || [];
            for (const word of dataWords) {
                const wordBbox = {
                    x: word.bbox.x0,
                    y: word.bbox.y0,
                    width: word.bbox.x1 - word.bbox.x0,
                    height: word.bbox.y1 - word.bbox.y0,
                };
                words.push({
                    text: word.text,
                    confidence: word.confidence,
                    bbox: wordBbox,
                });
            }
        }
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        const confidence = data.confidence || 0;
        console.log(`  [OCR] Page ${pageNumber}: Found ${words.length} words in ${elapsed}s (confidence: ${confidence.toFixed(1)}%)`);
        return {
            pageNumber,
            width: data.width || 2550,
            height: data.height || 3300,
            lines,
            words,
            confidence: confidence,
        };
    }
    async terminate() {
        if (this.worker) {
            await this.worker.terminate();
            this.worker = null;
            console.log('  ✓ OCR engine terminated');
        }
    }
}
exports.OCREngine = OCREngine;
