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
exports.ExternalPDFToImageConverter = void 0;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const child_process_1 = require("child_process");
const util_1 = require("util");
const execAsync = (0, util_1.promisify)(child_process_1.exec);
/**
 * PDF to Image converter using external tools (Ghostscript or poppler)
 * This provides MUCH better font rendering than canvas
 */
class ExternalPDFToImageConverter {
    constructor(options = {}) {
        this.options = {
            dpi: options.dpi || 300,
            format: options.format || 'png',
            outputDir: options.outputDir || './temp',
        };
    }
    async convert(pdfPath) {
        // Ensure output directory exists
        if (!fs.existsSync(this.options.outputDir)) {
            fs.mkdirSync(this.options.outputDir, { recursive: true });
        }
        // Try poppler first (pdftoppm), then ghostscript
        const converters = [
            { name: 'pdftoppm', cmd: this.buildPdftoppmCommand.bind(this) },
            { name: 'ghostscript', cmd: this.buildGhostscriptCommand.bind(this) },
            { name: 'magick', cmd: this.buildImageMagickCommand.bind(this) },
        ];
        for (const converter of converters) {
            if (await this.isAvailable(converter.name)) {
                console.log(`Using ${converter.name} for PDF conversion...`);
                return await converter.cmd(pdfPath);
            }
        }
        throw new Error('No PDF converter available. Please install one of:\n' +
            '  - poppler (pdftoppm): https://poppler.freedesktop.org/\n' +
            '  - Ghostscript (gs): https://www.ghostscript.com/\n' +
            '  - ImageMagick (magick): https://imagemagick.org/\n\n' +
            'Windows: Use chocolatey:\n' +
            '  choco install poppler\n' +
            '  choco install ghostscript\n' +
            '  choco install imagemagick');
    }
    async isAvailable(tool) {
        const commands = {
            pdftoppm: 'pdftoppm -v',
            ghostscript: process.platform === 'win32' ? 'gswin64c --version' : 'gs --version',
            magick: 'magick --version',
        };
        try {
            console.log(`  Testing ${tool}: ${commands[tool]}`);
            const result = await execAsync(commands[tool]);
            console.log(`  ✓ ${tool} available`);
            return true;
        }
        catch (error) {
            console.log(`  ✗ ${tool} not found: ${error.message}`);
            return false;
        }
    }
    async buildPdftoppmCommand(pdfPath) {
        const outputPrefix = path.join(this.options.outputDir, 'page');
        const format = this.options.format === 'png' ? '-png' : '-jpeg';
        // pdftoppm -png -r 300 input.pdf output-prefix
        const cmd = `pdftoppm ${format} -r ${this.options.dpi} "${pdfPath}" "${outputPrefix}"`;
        console.log(`Running: ${cmd}`);
        await execAsync(cmd);
        // List generated files
        return this.collectGeneratedImages(outputPrefix);
    }
    async buildGhostscriptCommand(pdfPath) {
        const results = [];
        // Get page count first
        const pageCount = await this.getPageCount(pdfPath);
        // Use gswin64c on Windows, gs on other platforms
        const gsCmd = process.platform === 'win32' ? 'gswin64c' : 'gs';
        for (let page = 1; page <= pageCount; page++) {
            const outputPath = path.join(this.options.outputDir, `page-${page}.${this.options.format}`);
            const device = this.options.format === 'png' ? 'png16m' : 'jpeg';
            // gswin64c -dNOPAUSE -dBATCH -sDEVICE=png16m -r300 -dFirstPage=1 -dLastPage=1 -sOutputFile=output.png input.pdf
            const cmd = `${gsCmd} -dNOPAUSE -dBATCH -sDEVICE=${device} -r${this.options.dpi} ` +
                `-dFirstPage=${page} -dLastPage=${page} -sOutputFile="${outputPath}" "${pdfPath}"`;
            await execAsync(cmd);
            results.push({
                pageNumber: page,
                imagePath: outputPath,
                width: Math.floor(8.5 * this.options.dpi),
                height: Math.floor(11 * this.options.dpi),
            });
            console.log(`  ✓ Page ${page}/${pageCount} converted`);
        }
        return results;
    }
    async buildImageMagickCommand(pdfPath) {
        const outputPattern = path.join(this.options.outputDir, `page-%d.${this.options.format}`);
        // magick -density 300 input.pdf output-%d.png
        const cmd = `magick -density ${this.options.dpi} "${pdfPath}" "${outputPattern}"`;
        console.log(`Running: ${cmd}`);
        await execAsync(cmd);
        return this.collectGeneratedImages(path.join(this.options.outputDir, 'page'));
    }
    collectGeneratedImages(prefix) {
        const dir = path.dirname(prefix);
        const baseName = path.basename(prefix);
        const files = fs.readdirSync(dir)
            .filter(f => f.startsWith(baseName))
            .sort();
        const results = [];
        files.forEach((file, idx) => {
            const fullPath = path.join(dir, file);
            results.push({
                pageNumber: idx + 1,
                imagePath: fullPath,
                width: Math.floor(8.5 * this.options.dpi),
                height: Math.floor(11 * this.options.dpi),
            });
        });
        return results;
    }
    async getPageCount(pdfPath) {
        // Use pdfjs-dist for page count
        const pdfjsLib = await Promise.resolve().then(() => __importStar(require('pdfjs-dist')));
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
        return pdfDoc.numPages;
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
exports.ExternalPDFToImageConverter = ExternalPDFToImageConverter;
