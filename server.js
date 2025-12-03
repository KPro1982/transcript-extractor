const http = require('http');
const fs = require('fs');
const path = require('path');

// Add Ghostscript to PATH if installed in standard location
const gsPath = 'C:\\Program Files\\gs\\gs10.02.1\\bin';
if (fs.existsSync(gsPath)) {
    process.env.PATH = gsPath + ';' + process.env.PATH;
    console.log('Added Ghostscript to PATH:', gsPath);
}

const { TextReconstructor } = require('./dist/text-reconstructor.js');

const PORT = 3000;
const UPLOAD_DIR = path.join(__dirname, 'temp', 'uploads');
const IMAGES_DIR = path.join(__dirname, 'temp', 'images');

// Ensure directories exist
[UPLOAD_DIR, IMAGES_DIR].forEach(dir => {
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
});

// Clean old images on startup
fs.readdirSync(IMAGES_DIR).forEach(file => {
    fs.unlinkSync(path.join(IMAGES_DIR, file));
});

/**
 * Detect page number from footer/header area text items (digital text)
 * Returns the printed page number if found, or null
 */
function detectPageNumber(textItems, width, height, pageNum, debug = false) {
    // Footer area: bottom 15% of page (expanded for legal transcripts)
    const footerY = height * 0.85;
    // Header area: top 10% of page  
    const headerY = height * 0.10;
    
    // Get text in footer area (y is inverted - larger y = lower on page)
    const footerItems = textItems.filter(item => item.y > footerY);
    // Get text in header area
    const headerItems = textItems.filter(item => item.y < headerY);
    
    if (debug && (footerItems.length > 0 || headerItems.length > 0)) {
        console.log(`    Page ${pageNum} footer/header text:`, 
            [...footerItems, ...headerItems].map(i => `"${i.text}" (y=${Math.round(i.y)})`).join(', '));
    }
    
    // Look for page numbers (standalone numbers, or "Page X" patterns)
    const candidates = [...footerItems, ...headerItems];
    
    for (const item of candidates) {
        const text = item.text.trim();
        
        // Match standalone number (1-999)
        if (/^[1-9]\d{0,2}$/.test(text)) {
            return parseInt(text, 10);
        }
        
        // Match "Page X" or "PAGE X" pattern
        const pageMatch = text.match(/page\s*(\d+)/i);
        if (pageMatch) {
            return parseInt(pageMatch[1], 10);
        }
        
        // Match "-X-" pattern (some legal docs use this)
        const dashMatch = text.match(/^-?\s*(\d+)\s*-?$/);
        if (dashMatch) {
            return parseInt(dashMatch[1], 10);
        }
    }
    
    return null;
}

/**
 * OCR the footer area of page 3 to detect the printed page number
 * Uses maximum quality settings for accurate number detection
 * Reads the bottom-left corner where legal transcript page numbers typically appear
 */
async function ocrFooterForPageNumber(imagePath) {
    const { createWorker, PSM, OEM } = require('tesseract.js');
    const sharp = require('sharp');
    
    console.log(`  [OCR] Reading footer from: ${path.basename(imagePath)}`);
    
    try {
        // Get image dimensions
        const metadata = await sharp(imagePath).metadata();
        const { width, height } = metadata;
        
        console.log(`  [OCR] Image dimensions: ${width}x${height}px`);
        
        // Extract bottom strip - ALL the way to the bottom edge, no cropping
        // Use bottom 5% of page height for the footer strip
        const footerHeight = Math.round(height * 0.05);
        const footerTop = height - footerHeight;
        
        // Focus on right half where page numbers are located
        const rightHalfStart = Math.round(width * 0.5);
        const rightHalfWidth = width - rightHalfStart;
        
        console.log(`  [OCR] Footer strip: y=${footerTop} to ${height} (bottom ${footerHeight}px), right half starting at x=${rightHalfStart}`);
        
        // Create cropped footer image - bottom RIGHT corner, all the way to the edge
        const footerBuffer = await sharp(imagePath)
            .extract({ 
                left: rightHalfStart, 
                top: footerTop, 
                width: rightHalfWidth, 
                height: footerHeight 
            })
            .sharpen({ sigma: 1.5 }) // Strong sharpening for small text
            .normalize() // Improve contrast
            .toBuffer();
        
        console.log(`  [OCR] Cropped footer: ${rightHalfWidth}x${footerHeight}px (bottom-right corner)`);
        
        // Initialize Tesseract with maximum quality settings
        const worker = await createWorker('eng');
        
        // Configure for maximum accuracy - single line of text expected
        await worker.setParameters({
            tessedit_pageseg_mode: PSM.SINGLE_LINE, // Treat as single line (page number)
            tessedit_ocr_engine_mode: OEM.LSTM_ONLY, // Best accuracy mode
            preserve_interword_spaces: '1',
        });
        
        // OCR footer
        console.log(`  [OCR] Scanning bottom-left footer for page number...`);
        const footerResult = await worker.recognize(footerBuffer);
        const footerText = footerResult.data.text.trim();
        console.log(`  [OCR] Footer text: "${footerText}" (confidence: ${footerResult.data.confidence?.toFixed(1)}%)`);
        
        await worker.terminate();
        
        // Extract page number from OCR result
        // Look for standalone numbers (most common format)
        const numberMatch = footerText.match(/\b([1-9]\d{0,2})\b/);
        if (numberMatch) {
            const pageNum = parseInt(numberMatch[1], 10);
            console.log(`  [OCR] ✓ Detected printed page number: ${pageNum}`);
            return pageNum;
        }
        
        // Look for "Page X" format
        const pageMatch = footerText.match(/page\s*(\d+)/i);
        if (pageMatch) {
            const pageNum = parseInt(pageMatch[1], 10);
            console.log(`  [OCR] ✓ Detected printed page number: ${pageNum}`);
            return pageNum;
        }
        
        // Try to find any number at all
        const anyNumber = footerText.match(/(\d+)/);
        if (anyNumber) {
            const num = parseInt(anyNumber[1], 10);
            if (num > 0 && num < 1000) {
                console.log(`  [OCR] ✓ Found number in footer: ${num}`);
                return num;
            }
        }
        
        console.log(`  [OCR] No page number found in footer`);
        return null;
        
    } catch (error) {
        console.log(`  [OCR] Error reading footer: ${error.message}`);
        return null;
    }
}

/**
 * Find the digital page where printed page 1 begins
 * Returns the 1-based digital page number, or 1 if not found
 */
function findFirstNumberedPage(pagesData) {
    // Look for the page that has printed page number "1"
    for (let i = 0; i < pagesData.length; i++) {
        if (pagesData[i].detectedPageNumber === 1) {
            console.log(`  → Detected: Printed page 1 is on digital page ${i + 1}`);
            return i + 1; // Return 1-based index
        }
    }
    
    // If page 1 not found, look for sequential page numbers to infer
    // E.g., if we find page 2 on digital page 4, then page 1 would be digital page 3
    for (let i = 0; i < pagesData.length; i++) {
        const detected = pagesData[i].detectedPageNumber;
        if (detected && detected > 0) {
            const inferredFirst = (i + 1) - (detected - 1);
            if (inferredFirst > 0) {
                console.log(`  → Inferred: Printed page 1 is on digital page ${inferredFirst} (from page ${detected} on digital ${i + 1})`);
                return inferredFirst;
            }
        }
    }
    
    // Default: assume first page is page 1
    console.log(`  → No page numbers detected, defaulting to digital page 1`);
    return 1;
}

/**
 * Extract text and images from PDF for side-by-side viewing
 */
async function extractPDFWithImages(pdfPath) {
    const { ExternalPDFToImageConverter } = require('./dist/pdf-to-image-external.js');
    const pdfjsLib = require('pdfjs-dist');
    
    if (pdfjsLib.GlobalWorkerOptions) {
        pdfjsLib.GlobalWorkerOptions.workerSrc = '';
    }

    // Get PDF info
    const pdfBuffer = fs.readFileSync(pdfPath);
    const pdfBytes = new Uint8Array(pdfBuffer);
    const loadingTask = pdfjsLib.getDocument({ data: pdfBytes, useWorkerFetch: false, isEvalSupported: false });
    const pdfDoc = await loadingTask.promise;
    const totalPages = pdfDoc.numPages;

    console.log(`\nProcessing ${totalPages} pages...`);

    // Convert PDF to images (use lower DPI for display)
    const imageConverter = new ExternalPDFToImageConverter({ dpi: 150, outputDir: IMAGES_DIR });
    const images = await imageConverter.convert(pdfPath);

    // Legal transcript settings
    const LINES_PER_PAGE = 25;
    const topMarginPercent = 0.10;
    const bottomMarginPercent = 0.10;

    const pages = [];
    const pagesWithDetection = []; // For page number detection

    console.log(`  Scanning for page numbers in headers/footers...`);

    for (let pageNum = 1; pageNum <= totalPages; pageNum++) {
        console.log(`  Processing page ${pageNum}/${totalPages}...`);

        // Get digital text
        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: 1.0 });
        const textContent = await page.getTextContent();
        
        const { width, height } = viewport;
        const textItems = [];
        
        for (const item of (textContent.items || [])) {
            const str = item.str || '';
            if (!str.trim()) continue;
            const transform = item.transform || [];
            textItems.push({
                text: str,
                x: transform[4] || 0,
                y: height - (transform[5] || 0),
                width: item.width || 0,
                height: item.height || 12,
            });
        }

        // Detect page number from header/footer (debug first 5 pages)
        const detectedPageNumber = detectPageNumber(textItems, width, height, pageNum, pageNum <= 5);
        if (detectedPageNumber) {
            console.log(`    → Found page number: ${detectedPageNumber}`);
        }
        pagesWithDetection.push({ pageNum, detectedPageNumber });

        // Find content bounds
        const contentItems = textItems.filter(item => item.x > width * 0.1);
        let minY = height, maxY = 0;
        for (const item of contentItems) {
            if (item.y < minY) minY = item.y;
            if (item.y > maxY) maxY = item.y;
        }

        if (contentItems.length === 0) {
            minY = height * topMarginPercent;
            maxY = height * (1 - bottomMarginPercent);
        }

        // Calculate line positions
        const contentSpan = maxY - minY;
        const lineHeight = contentSpan / (LINES_PER_PAGE - 1) || (height * 0.8 / LINES_PER_PAGE);

        // Generate line numbers with Y positions
        const lineNumbers = [];
        for (let num = 1; num <= LINES_PER_PAGE; num++) {
            const yPosition = minY + (num - 1) * lineHeight;
            lineNumbers.push({
                text: String(num),
                position: { x: 0, y: yPosition, width: 20, height: lineHeight },
                confidence: 100,
                type: 'line_number',
            });
        }

        // Categorize content
        const digitalLeftMargin = width * 0.10;
        const headerBound = minY - lineHeight;
        const footerBound = maxY + lineHeight;

        const mainContent = [];
        for (const item of textItems) {
            const centerY = item.y + (item.height || 0) / 2;
            const centerX = item.x + (item.width || 0) / 2;

            if (centerY >= headerBound && centerY <= footerBound && centerX >= digitalLeftMargin) {
                mainContent.push({
                    text: item.text,
                    position: { x: item.x, y: item.y, width: item.width, height: item.height },
                    confidence: 100,
                    type: 'content',
                });
            }
        }

        // Use TextReconstructor to merge line numbers with content
        const reconstructor = new TextReconstructor();
        const merged = reconstructor.mergeLineNumbersWithContent(lineNumbers, mainContent);

        // Get image URL
        const imageFile = images[pageNum - 1];
        const imageFileName = path.basename(imageFile.imagePath);

        pages.push({
            pageNumber: pageNum,
            imageUrl: `/images/${imageFileName}`,
            lines: merged.filter(m => m.lineNumber).map(m => ({
                lineNumber: m.lineNumber,
                text: m.text || ''
            })),
            unmatched: merged.filter(m => !m.lineNumber && m.text).map(m => m.text)
        });

        console.log(`  ✓ Page ${pageNum}: ${merged.filter(m => m.lineNumber && m.text).length} lines with content`);
    }

    // Always try OCR on page 3's footer to detect printed page number
    // (Digital text detection is unreliable for page numbers which are often in image layer)
    let firstNumberedPage = 1;
    
    if (totalPages >= 3) {
        console.log(`\n  Detecting page numbers via OCR on page 3 footer...`);
        const page3Image = images[2]; // 0-indexed, so page 3 is index 2
        if (page3Image && page3Image.imagePath) {
            const ocrPageNum = await ocrFooterForPageNumber(page3Image.imagePath);
            if (ocrPageNum !== null && ocrPageNum > 0 && ocrPageNum < 100) {
                // If page 3 shows printed page X, then page 1 starts at digital page (3 - X + 1)
                // e.g., if page 3 shows "1", firstNumberedPage = 3
                // if page 3 shows "2", firstNumberedPage = 2
                firstNumberedPage = 3 - ocrPageNum + 1;
                if (firstNumberedPage < 1) firstNumberedPage = 1;
                console.log(`  → Calculated: Printed page 1 is on digital page ${firstNumberedPage}`);
            } else {
                // Try page 5 as backup (in case page 3 has unusual content)
                if (totalPages >= 5) {
                    console.log(`  Trying page 5 as backup...`);
                    const page5Image = images[4];
                    if (page5Image && page5Image.imagePath) {
                        const ocrPageNum5 = await ocrFooterForPageNumber(page5Image.imagePath);
                        if (ocrPageNum5 !== null && ocrPageNum5 > 0 && ocrPageNum5 < 100) {
                            firstNumberedPage = 5 - ocrPageNum5 + 1;
                            if (firstNumberedPage < 1) firstNumberedPage = 1;
                            console.log(`  → Calculated from page 5: Printed page 1 is on digital page ${firstNumberedPage}`);
                        }
                    }
                }
            }
        }
    }

    return { pages, totalPages, firstNumberedPage };
}

const server = http.createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
    }

    const url = new URL(req.url, `http://localhost:${PORT}`);

    // Serve page images
    if (req.method === 'GET' && url.pathname.startsWith('/images/')) {
        const imageName = url.pathname.replace('/images/', '');
        const imagePath = path.join(IMAGES_DIR, imageName);
        
        if (fs.existsSync(imagePath)) {
            const ext = path.extname(imagePath).toLowerCase();
            const mimeTypes = { '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg' };
            res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'image/png' });
            fs.createReadStream(imagePath).pipe(res);
            return;
        } else {
            res.writeHead(404);
            res.end('Image not found');
            return;
        }
    }

    // Single extraction endpoint
    if (req.method === 'POST' && url.pathname === '/api/extract') {
        const chunks = [];
        req.on('data', chunk => chunks.push(chunk));
        req.on('end', async () => {
            try {
                const buffer = Buffer.concat(chunks);
                const boundary = req.headers['content-type'].split('boundary=')[1];
                const parts = parseMultipart(buffer, boundary);
                
                const filePart = parts.find(p => p.filename);
                if (!filePart) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'No PDF file uploaded' }));
                    return;
                }

                const tempPath = path.join(UPLOAD_DIR, `upload_${Date.now()}.pdf`);
                fs.writeFileSync(tempPath, filePart.data);

                console.log(`\n${'='.repeat(50)}`);
                console.log(`Processing: ${filePart.filename}`);
                console.log(`${'='.repeat(50)}`);

                const result = await extractPDFWithImages(tempPath);

                // Clean up uploaded file
                fs.unlinkSync(tempPath);

                console.log(`\n✓ Extraction complete: ${result.totalPages} pages\n`);

                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({
                    success: true,
                    filename: filePart.filename,
                    pages: result.pages,
                    totalPages: result.totalPages,
                    firstNumberedPage: result.firstNumberedPage
                }));

            } catch (error) {
                console.error('Extraction error:', error);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Failed to extract: ' + error.message }));
            }
        });
        return;
    }

    // Serve static files
    let filePath = path.join(__dirname, 'public', url.pathname === '/' ? 'index.html' : url.pathname);
    const extname = String(path.extname(filePath)).toLowerCase();
    const mimeTypes = {
        '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
        '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpg',
        '.gif': 'image/gif', '.svg': 'image/svg+xml', '.pdf': 'application/pdf'
    };
    
    fs.readFile(filePath, (error, content) => {
        if (error) {
            res.writeHead(error.code === 'ENOENT' ? 404 : 500, { 'Content-Type': 'text/html' });
            res.end(error.code === 'ENOENT' ? '<h1>404 - Not Found</h1>' : 'Server Error');
        } else {
            res.writeHead(200, { 'Content-Type': mimeTypes[extname] || 'application/octet-stream' });
            res.end(content);
        }
    });
});

function parseMultipart(buffer, boundary) {
    const parts = [];
    const boundaryBuffer = Buffer.from('--' + boundary);
    let start = buffer.indexOf(boundaryBuffer) + boundaryBuffer.length;
    
    while (start < buffer.length) {
        let end = buffer.indexOf(boundaryBuffer, start);
        if (end === -1) break;
        
        const partData = buffer.slice(start, end);
        const headerEnd = partData.indexOf('\r\n\r\n');
        if (headerEnd === -1) { start = end + boundaryBuffer.length; continue; }
        
        const headers = partData.slice(0, headerEnd).toString();
        const body = partData.slice(headerEnd + 4, -2);
        
        parts.push({
            name: (headers.match(/name="([^"]+)"/) || [])[1],
            filename: (headers.match(/filename="([^"]+)"/) || [])[1],
            data: body
        });
        
        start = end + boundaryBuffer.length;
        if (buffer.slice(end + boundaryBuffer.length, end + boundaryBuffer.length + 2).toString() === '--') break;
    }
    return parts;
}

server.listen(PORT, () => {
    console.log(`\n${'='.repeat(50)}`);
    console.log('  PDF Reader Server Running');
    console.log(`${'='.repeat(50)}`);
    console.log(`\n  Server: http://localhost:${PORT}/`);
    console.log(`\n  Features:`);
    console.log('    - Side-by-side PDF + text view');
    console.log('    - Line numbers 1-25 per page');
    console.log('    - Page navigation');
    console.log(`\n${'='.repeat(50)}\n`);

    // Open in default browser
    const { exec } = require('child_process');
    const url = `http://localhost:${PORT}/`;
    
    // Windows
    exec(`start ${url}`);
});
