"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ContentAnalyzer = void 0;
class ContentAnalyzer {
    constructor(marginConfig = {
        leftMarginPercent: 0.12,
        rightMarginPercent: 0.88,
        topMarginPercent: 0.10,
        bottomMarginPercent: 0.90,
    }, lineNumberPattern = /^[1-9]\d?$/) {
        this.marginConfig = marginConfig;
        this.lineNumberPattern = lineNumberPattern;
    }
    analyze(ocrResult) {
        const { width, height, words } = ocrResult;
        const lineNumbers = [];
        const headers = [];
        const footers = [];
        const mainContent = [];
        // Calculate margin boundaries
        const leftMargin = width * this.marginConfig.leftMarginPercent;
        const rightMargin = width * this.marginConfig.rightMarginPercent;
        const topMargin = height * this.marginConfig.topMarginPercent;
        const bottomMargin = height * this.marginConfig.bottomMarginPercent;
        console.log(`  [ANALYZE] Page ${ocrResult.pageNumber}: Analyzing ${words.length} words (L=${this.marginConfig.leftMarginPercent * 100}%, T=${this.marginConfig.topMarginPercent * 100}%, B=${(1 - this.marginConfig.bottomMarginPercent) * 100}%)`);
        for (const word of words) {
            const { text, bbox, confidence } = word;
            const trimmedText = text.trim();
            if (!trimmedText)
                continue;
            const centerX = bbox.x + bbox.width / 2;
            const centerY = bbox.y + bbox.height / 2;
            const textBlock = {
                text: trimmedText,
                position: bbox,
                confidence,
                type: 'content',
            };
            // Categorize based on position and content
            if (centerY < topMargin) {
                // Header area
                textBlock.type = 'header';
                headers.push(textBlock);
            }
            else if (centerY > bottomMargin) {
                // Footer area
                textBlock.type = 'footer';
                footers.push(textBlock);
            }
            else if (centerX < leftMargin && this.lineNumberPattern.test(trimmedText)) {
                // Line number in left margin
                textBlock.type = 'line_number';
                lineNumbers.push(textBlock);
            }
            else if (centerX < leftMargin && /^\d+$/.test(trimmedText)) {
                // Number in left margin but doesn't match pattern (e.g., 3+ digits)
                console.log(`  [ANALYZE] Rejected line number "${trimmedText}" (too many digits, x=${centerX.toFixed(0)})`);
            }
            else if (centerX >= leftMargin && centerX <= rightMargin) {
                // Main content area
                textBlock.type = 'content';
                mainContent.push(textBlock);
            }
        }
        console.log(`  [ANALYZE] Page ${ocrResult.pageNumber}: Found ${lineNumbers.length} line numbers, ${headers.length} headers, ${footers.length} footers, ${mainContent.length} content words`);
        return {
            pageNumber: ocrResult.pageNumber,
            dimensions: { width, height },
            lineNumbers: this.sortByPosition(lineNumbers),
            headers: this.sortByPosition(headers),
            footers: this.sortByPosition(footers),
            mainContent: this.sortByPosition(mainContent),
            confidence: ocrResult.confidence,
        };
    }
    sortByPosition(blocks) {
        return blocks.sort((a, b) => {
            // Sort by Y position first (top to bottom)
            const yDiff = a.position.y - b.position.y;
            if (Math.abs(yDiff) > 5) {
                return yDiff;
            }
            // Then by X position (left to right)
            return a.position.x - b.position.x;
        });
    }
}
exports.ContentAnalyzer = ContentAnalyzer;
