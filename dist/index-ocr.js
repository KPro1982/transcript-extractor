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
const ocr_extractor_1 = require("./ocr-extractor");
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
async function main() {
    const args = process.argv.slice(2);
    if (args.length === 0) {
        console.log('\n╔════════════════════════════════════════════════════════════╗');
        console.log('║              OCR-Based PDF Text Extractor                 ║');
        console.log('╚════════════════════════════════════════════════════════════╝\n');
        console.log('Usage: npm run ocr <pdf-file> [options]\n');
        console.log('Options:');
        console.log('  --format <txt|json|md>  Output format (default: txt)');
        console.log('  --dpi <number>          DPI for image conversion (default: 300)');
        console.log('  --output <path>         Output file path');
        console.log('  --no-confidence         Hide confidence scores');
        console.log('  --positions             Include position data\n');
        console.log('Examples:');
        console.log('  npm run ocr document.pdf');
        console.log('  npm run ocr document.pdf --format md --dpi 600');
        console.log('  npm run ocr "Transcripts/Deposition example.pdf" --format txt\n');
        process.exit(1);
    }
    const pdfPath = path.resolve(args[0]);
    if (!fs.existsSync(pdfPath)) {
        console.error(`\n✗ Error: PDF file not found: ${pdfPath}\n`);
        process.exit(1);
    }
    // Parse options
    const format = getArg(args, '--format', 'txt');
    const dpi = parseInt(getArg(args, '--dpi', '300'), 10);
    const hasConfidence = !args.includes('--no-confidence');
    const hasPositions = args.includes('--positions');
    const defaultOutput = pdfPath.replace(/\.pdf$/i, `_ocr.${format}`);
    const outputPath = getArg(args, '--output', defaultOutput);
    console.log('\n╔════════════════════════════════════════════════════════════╗');
    console.log('║              OCR-Based PDF Text Extractor                 ║');
    console.log('╚════════════════════════════════════════════════════════════╝');
    console.log(`\nInput:       ${pdfPath}`);
    console.log(`Output:      ${outputPath}`);
    console.log(`Format:      ${format}`);
    console.log(`DPI:         ${dpi}`);
    console.log(`Confidence:  ${hasConfidence ? 'Yes' : 'No'}`);
    console.log(`Positions:   ${hasPositions ? 'Yes' : 'No'}`);
    try {
        const extractor = new ocr_extractor_1.OCRExtractor({ dpi });
        await extractor.extractAndSave(pdfPath, outputPath, {
            format,
            includePositions: hasPositions,
            includeConfidence: hasConfidence,
        });
        console.log('\n╔════════════════════════════════════════════════════════════╗');
        console.log('║                  ✓ Extraction Complete!                   ║');
        console.log('╚════════════════════════════════════════════════════════════╝\n');
    }
    catch (error) {
        console.error('\n╔════════════════════════════════════════════════════════════╗');
        console.error('║                  ✗ Extraction Failed!                     ║');
        console.error('╚════════════════════════════════════════════════════════════╝');
        console.error('\nError:', error);
        console.error('');
        process.exit(1);
    }
}
function getArg(args, flag, defaultValue) {
    const index = args.indexOf(flag);
    if (index !== -1 && index + 1 < args.length) {
        return args[index + 1];
    }
    return defaultValue;
}
if (require.main === module) {
    main();
}
