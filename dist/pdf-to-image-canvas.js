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
exports.PDFToImageConverter = void 0;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const canvas_1 = require("canvas");
class PDFToImageConverter {
    constructor(options = {}) {
        this.options = {
            dpi: options.dpi || 300,
            format: options.format || 'png',
            outputDir: options.outputDir || './temp',
            preserveMargins: options.preserveMargins ?? true,
        };
    }
    async convert(pdfPath) {
        // Ensure output directory exists
        if (!fs.existsSync(this.options.outputDir)) {
            fs.mkdirSync(this.options.outputDir, { recursive: true });
        }
        // Use pdfjs-dist to render pages
        const pdfjsLib = await Promise.resolve().then(() => __importStar(require('pdfjs-dist')));
        // Set worker (Node.js environment)
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
        const results = [];
        const scale = this.options.dpi / 72; // 72 DPI is the default PDF resolution
        console.log(`Converting ${pdfDoc.numPages} pages to images...`);
        for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
            try {
                const page = await pdfDoc.getPage(pageNum);
                const viewport = page.getViewport({ scale });
                // Create canvas
                const canvas = (0, canvas_1.createCanvas)(viewport.width, viewport.height);
                const context = canvas.getContext('2d');
                // Render PDF page to canvas
                const renderContext = {
                    canvasContext: context,
                    viewport: viewport,
                };
                await page.render(renderContext).promise;
                // Save canvas to file
                const outputFileName = `page-${pageNum}.${this.options.format}`;
                const outputPath = path.join(this.options.outputDir, outputFileName);
                let buffer;
                if (this.options.format === 'png') {
                    buffer = canvas.toBuffer('image/png');
                }
                else {
                    buffer = canvas.toBuffer('image/jpeg');
                }
                fs.writeFileSync(outputPath, buffer);
                results.push({
                    pageNumber: pageNum,
                    imagePath: outputPath,
                    width: viewport.width,
                    height: viewport.height,
                });
                console.log(`  ✓ Page ${pageNum}/${pdfDoc.numPages} converted`);
            }
            catch (error) {
                console.error(`  ✗ Failed to convert page ${pageNum}:`, error);
                throw error;
            }
        }
        return results;
    }
    cleanup(pages) {
        console.log('Cleaning up temporary image files...');
        pages.forEach(page => {
            if (fs.existsSync(page.imagePath)) {
                fs.unlinkSync(page.imagePath);
            }
        });
    }
}
exports.PDFToImageConverter = PDFToImageConverter;
