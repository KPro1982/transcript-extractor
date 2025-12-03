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
exports.extractTextFromPDF = extractTextFromPDF;
exports.formatExtractedText = formatExtractedText;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
async function extractTextFromPDF(pdfPath) {
    try {
        // Use pdfjs-dist directly (which pdf-ts depends on) to get positioning information
        // pdf-ts uses pdfjs-dist under the hood, so we'll use it directly for better control
        const pdfjsLib = await Promise.resolve().then(() => __importStar(require('pdfjs-dist')));
        // Set up the worker for pdfjs-dist (Node.js environment)
        // For Node.js, we can disable the worker or use a file path
        try {
            // Try to resolve the worker file
            const workerPath = require.resolve('pdfjs-dist/build/pdf.worker.mjs');
            pdfjsLib.GlobalWorkerOptions.workerSrc = workerPath;
        }
        catch (e) {
            // If worker file not found, disable worker (Node.js can work without it)
            pdfjsLib.GlobalWorkerOptions.workerSrc = '';
        }
        const pdfBytes = fs.readFileSync(pdfPath);
        // Load the PDF document
        const loadingTask = pdfjsLib.getDocument({ data: pdfBytes });
        const pdfDoc = await loadingTask.promise;
        const results = [];
        // Process each page
        for (let pageIndex = 1; pageIndex <= pdfDoc.numPages; pageIndex++) {
            const page = await pdfDoc.getPage(pageIndex);
            const viewport = page.getViewport({ scale: 1.0 });
            const { width, height } = viewport;
            // Get text content with positioning
            const textContent = await page.getTextContent();
            const textItems = [];
            // Process each text item
            // Handle different possible text content structures
            let items = [];
            if (textContent.items && Array.isArray(textContent.items)) {
                items = textContent.items;
            }
            else if (Array.isArray(textContent)) {
                items = textContent;
            }
            else if (textContent && typeof textContent === 'object') {
                // Try to extract items from various possible structures
                items = textContent.textItems || textContent.text || [];
            }
            items.forEach((item) => {
                const str = item.str || item.text || item.content || '';
                if (!str || !str.trim())
                    return;
                // Extract position from transform matrix
                // Transform matrix: [a, b, c, d, e, f]
                // e = x translation, f = y translation
                let x = 0;
                let y = 0;
                let fontSize = item.fontSize || item.size || 12;
                if (item.transform && Array.isArray(item.transform) && item.transform.length >= 6) {
                    x = item.transform[4] || 0;
                    // PDF coordinates start from bottom-left, convert to top-left
                    y = height - (item.transform[5] || 0);
                }
                else if (item.x !== undefined && item.y !== undefined) {
                    x = item.x;
                    // Convert coordinate system if needed
                    y = item.y > height / 2 ? height - item.y : item.y;
                }
                else if (item.left !== undefined && item.top !== undefined) {
                    x = item.left;
                    y = height - item.top;
                }
                // Calculate text dimensions if available
                let textWidth = item.width || 0;
                let textHeight = item.height || fontSize;
                if (item.transform && item.transform.length >= 4) {
                    // Use transform matrix to estimate dimensions
                    const scaleX = Math.sqrt((item.transform[0] || 1) * (item.transform[0] || 1) +
                        (item.transform[1] || 0) * (item.transform[1] || 0));
                    const scaleY = Math.sqrt((item.transform[2] || 0) * (item.transform[2] || 0) +
                        (item.transform[3] || 1) * (item.transform[3] || 1));
                    if (scaleX > 0)
                        textWidth = (str.length * fontSize * 0.6) * scaleX;
                    if (scaleY > 0)
                        textHeight = fontSize * scaleY;
                }
                else if (item.width === undefined) {
                    // Estimate width based on character count and font size
                    textWidth = str.length * fontSize * 0.6;
                }
                textItems.push({
                    str,
                    x,
                    y,
                    width: textWidth,
                    height: textHeight,
                    fontSize
                });
            });
            // Define margin boundaries (adjustable percentages)
            // These can be tuned based on your PDF layout
            const leftMarginThreshold = width * 0.08; // 8% of page width for line numbers
            const rightMarginThreshold = width * 0.92; // 92% for right margin
            const topMarginThreshold = height * 0.12; // 12% from top for headers
            const bottomMarginThreshold = height * 0.88; // 88% from top (12% from bottom) for footers
            // Categorize text items
            const lineNumbers = [];
            const headers = [];
            const footers = [];
            const mainContent = [];
            textItems.forEach(item => {
                // Check if it's a line number (left margin, typically numeric)
                // Also check for line numbers that might have trailing spaces or dots
                const trimmedStr = item.str.trim();
                const isNumeric = /^\d+[\.\)]?\s*$/.test(trimmedStr) || /^\d+$/.test(trimmedStr);
                const isInLeftMargin = item.x < leftMarginThreshold;
                // Check if it's in header area (top margin)
                const isInHeader = item.y < topMarginThreshold;
                // Check if it's in footer area (bottom margin)
                const isInFooter = item.y > bottomMarginThreshold;
                // Prioritize categorization: headers/footers first, then line numbers, then main content
                if (isInHeader) {
                    headers.push(item);
                }
                else if (isInFooter) {
                    footers.push(item);
                }
                else if (isInLeftMargin && isNumeric) {
                    lineNumbers.push(item);
                }
                else {
                    mainContent.push(item);
                }
            });
            // Sort items by position for better readability
            const sortByPosition = (a, b) => {
                // Primary sort by Y (top to bottom), secondary by X (left to right)
                if (Math.abs(a.y - b.y) > 5) {
                    return a.y - b.y;
                }
                return a.x - b.x;
            };
            lineNumbers.sort(sortByPosition);
            headers.sort(sortByPosition);
            footers.sort(sortByPosition);
            mainContent.sort(sortByPosition);
            textItems.sort(sortByPosition);
            results.push({
                pageNumber: pageIndex + 1,
                width,
                height,
                lineNumbers,
                headers,
                footers,
                mainContent,
                allText: textItems
            });
        }
        return results;
    }
    catch (error) {
        console.error('Error extracting text from PDF:', error);
        throw error;
    }
}
function formatExtractedText(pages) {
    let output = '';
    pages.forEach(page => {
        output += `\n${'='.repeat(80)}\n`;
        output += `PAGE ${page.pageNumber} (${page.width.toFixed(0)} x ${page.height.toFixed(0)})\n`;
        output += `${'='.repeat(80)}\n\n`;
        // Headers
        if (page.headers.length > 0) {
            output += '--- HEADERS ---\n';
            page.headers.forEach(item => {
                output += `  [${item.x.toFixed(1)}, ${item.y.toFixed(1)}] ${item.str}\n`;
            });
            output += '\n';
        }
        // Line Numbers
        if (page.lineNumbers.length > 0) {
            output += '--- LINE NUMBERS ---\n';
            page.lineNumbers.forEach(item => {
                output += `  [${item.x.toFixed(1)}, ${item.y.toFixed(1)}] ${item.str}\n`;
            });
            output += '\n';
        }
        // Main Content
        if (page.mainContent.length > 0) {
            output += '--- MAIN CONTENT ---\n';
            page.mainContent.forEach(item => {
                output += `  [${item.x.toFixed(1)}, ${item.y.toFixed(1)}] ${item.str}\n`;
            });
            output += '\n';
        }
        // Footers
        if (page.footers.length > 0) {
            output += '--- FOOTERS ---\n';
            page.footers.forEach(item => {
                output += `  [${item.x.toFixed(1)}, ${item.y.toFixed(1)}] ${item.str}\n`;
            });
            output += '\n';
        }
        // All Text (complete extraction)
        output += '--- ALL TEXT (COMPLETE) ---\n';
        page.allText.forEach(item => {
            output += `  [${item.x.toFixed(1)}, ${item.y.toFixed(1)}] ${item.str}\n`;
        });
        output += '\n';
    });
    return output;
}
// Main execution
async function main() {
    const args = process.argv.slice(2);
    if (args.length === 0) {
        console.error('Usage: npm start <path-to-pdf-file>');
        console.error('Example: npm start document.pdf');
        process.exit(1);
    }
    const pdfPath = path.resolve(args[0]);
    if (!fs.existsSync(pdfPath)) {
        console.error(`Error: PDF file not found: ${pdfPath}`);
        process.exit(1);
    }
    console.log(`Extracting text from: ${pdfPath}\n`);
    try {
        const pages = await extractTextFromPDF(pdfPath);
        const formattedText = formatExtractedText(pages);
        console.log(formattedText);
        // Also save to file
        const outputPath = pdfPath.replace(/\.pdf$/i, '_extracted.txt');
        fs.writeFileSync(outputPath, formattedText, 'utf-8');
        console.log(`\nExtracted text saved to: ${outputPath}`);
    }
    catch (error) {
        console.error('Failed to extract text:', error);
        process.exit(1);
    }
}
// Run if executed directly
if (require.main === module) {
    main();
}
