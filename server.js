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

    return { pages, totalPages };
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
                    totalPages: result.totalPages
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
});
