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
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
/**
 * Diagnostic tool to analyze PDF structure and find line numbers
 */
async function analyzePDF(pdfPath) {
    console.log('\n╔════════════════════════════════════════════════════════════╗');
    console.log('║              PDF Structure Diagnostic Tool                ║');
    console.log('╚════════════════════════════════════════════════════════════╝\n');
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
    console.log(`PDF: ${path.basename(pdfPath)}`);
    console.log(`Pages: ${pdfDoc.numPages}\n`);
    // Analyze first few pages
    for (let pageNum = 5; pageNum <= Math.min(7, pdfDoc.numPages); pageNum++) {
        console.log(`\n${'='.repeat(60)}`);
        console.log(`PAGE ${pageNum} ANALYSIS`);
        console.log(`${'='.repeat(60)}\n`);
        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: 1.0 });
        const textContent = await page.getTextContent();
        console.log(`Page dimensions: ${viewport.width.toFixed(1)} x ${viewport.height.toFixed(1)}\n`);
        // Analyze text positions
        const items = textContent.items || [];
        // Group items by X position
        const leftMarginItems = [];
        const mainContentItems = [];
        const leftMarginBoundary = viewport.width * 0.15; // 15% for wider check
        for (const item of items) {
            const str = item.str || '';
            if (!str.trim())
                continue;
            const transform = item.transform || [];
            const x = transform[4] || 0;
            const y = viewport.height - (transform[5] || 0);
            const itemData = {
                text: str,
                x: x.toFixed(1),
                y: y.toFixed(1),
            };
            if (x < leftMarginBoundary) {
                leftMarginItems.push(itemData);
            }
            else {
                mainContentItems.push(itemData);
            }
        }
        // Display left margin items
        console.log(`LEFT MARGIN (X < ${leftMarginBoundary.toFixed(1)}):`);
        console.log(`Found ${leftMarginItems.length} items\n`);
        if (leftMarginItems.length > 0) {
            leftMarginItems.slice(0, 20).forEach((item, idx) => {
                const isNumeric = /^\d+\.?\s*$/.test(item.text);
                const marker = isNumeric ? ' 🔢' : '';
                console.log(`  [${item.x}, ${item.y}] "${item.text}"${marker}`);
            });
            if (leftMarginItems.length > 20) {
                console.log(`  ... and ${leftMarginItems.length - 20} more`);
            }
        }
        else {
            console.log('  (none found in digital text)');
        }
        // Check for numeric patterns
        const numericItems = leftMarginItems.filter(item => /^\d+\.?\s*$/.test(item.text));
        if (numericItems.length > 0) {
            console.log(`\n✓ Found ${numericItems.length} potential line numbers in digital text!`);
        }
        else {
            console.log(`\n⚠️  No numeric items found in left margin of digital text`);
            console.log(`   This suggests line numbers may be:`);
            console.log(`   1. Image-based (need OCR)`);
            console.log(`   2. Outside the 15% boundary`);
            console.log(`   3. Not present on this page`);
        }
        // Display first few main content items for reference
        console.log(`\n\nMAIN CONTENT (X >= ${leftMarginBoundary.toFixed(1)}):`);
        console.log(`Found ${mainContentItems.length} items\n`);
        mainContentItems.slice(0, 10).forEach(item => {
            console.log(`  [${item.x}, ${item.y}] "${item.text}"`);
        });
        if (mainContentItems.length > 10) {
            console.log(`  ... and ${mainContentItems.length - 10} more`);
        }
    }
    console.log('\n\n' + '='.repeat(60));
    console.log('SUMMARY');
    console.log('='.repeat(60) + '\n');
    console.log('Next steps:');
    console.log('- If line numbers found in digital text → Use original extractor');
    console.log('- If no line numbers in digital text → Line numbers are images');
    console.log('  → Need to adjust OCR or check if line numbers exist at all');
}
async function main() {
    const args = process.argv.slice(2);
    if (args.length === 0) {
        console.log('Usage: npm run diagnostic <pdf-file>');
        console.log('Example: npm run diagnostic "Transcripts/Deposition example.pdf"');
        process.exit(1);
    }
    const pdfPath = path.resolve(args[0]);
    if (!fs.existsSync(pdfPath)) {
        console.error(`Error: PDF file not found: ${pdfPath}`);
        process.exit(1);
    }
    await analyzePDF(pdfPath);
}
if (require.main === module) {
    main();
}
