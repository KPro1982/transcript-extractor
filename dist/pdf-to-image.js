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
const pdf2pic_1 = require("pdf2pic");
const fs = __importStar(require("fs"));
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
        const converter = (0, pdf2pic_1.fromPath)(pdfPath, {
            density: this.options.dpi,
            format: this.options.format,
            width: Math.floor(8.5 * this.options.dpi), // Letter size
            height: Math.floor(11 * this.options.dpi),
            savePath: this.options.outputDir,
            preserveAspectRatio: true,
        });
        const results = [];
        const pdfInfo = await this.getPDFInfo(pdfPath);
        console.log(`Converting ${pdfInfo.pages} pages to images...`);
        for (let page = 1; page <= pdfInfo.pages; page++) {
            try {
                const result = await converter(page, { responseType: 'image' });
                // Extract path from result - could be result.path, result.name, or result itself
                const imagePath = result.path || result.name || result.toString();
                results.push({
                    pageNumber: page,
                    imagePath: imagePath,
                    width: result.width || 2550, // 8.5" at 300 DPI
                    height: result.height || 3300, // 11" at 300 DPI
                });
                console.log(`  ✓ Page ${page}/${pdfInfo.pages} converted`);
            }
            catch (error) {
                console.error(`  ✗ Failed to convert page ${page}:`, error);
                throw error;
            }
        }
        return results;
    }
    async getPDFInfo(pdfPath) {
        // Use pdfjs-dist to get page count
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
        // Convert Buffer to Uint8Array for pdfjs-dist
        const pdfBytes = new Uint8Array(pdfBuffer);
        const loadingTask = pdfjsLib.getDocument({ data: pdfBytes });
        const pdfDoc = await loadingTask.promise;
        return { pages: pdfDoc.numPages };
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
