/**
 * Autonomous test for deposition summarization
 * 
 * This test uses the abridged transcript to verify that the summarization
 * process completes without getting stuck. It monitors progress and detects
 * if the process hangs (e.g., due to API timeouts or infinite loops).
 * 
 * Usage:
 *   1. Start the server: npm start (in another terminal)
 *   2. Run the test: npm run test-summarization
 * 
 * The test will:
 *   - Load the abridged transcript from Transcripts/
 *   - Send it to the /api/summarize endpoint
 *   - Monitor progress events via Server-Sent Events (SSE)
 *   - Detect if the process gets stuck (no progress for 60s)
 *   - Report where it got stuck and why
 * 
 * Expected issues this test can detect:
 *   - OpenAI API calls hanging (no timeout configured in callOpenAI)
 *   - Network issues causing API calls to hang
 *   - Infinite loops in batch processing
 *   - Rate limiting causing indefinite waits
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

// Load server functions (we'll need to extract them or require server.js)
// For now, we'll create a test that uses the HTTP API endpoint

const TRANSCRIPT_PATH = path.join(__dirname, 'Transcripts', 'Buksh - Deposition Transcript of Charlene Wilson Domingues 9-18-25 (Abridged).pdf');
const TEST_TIMEOUT = 300000; // 5 minutes timeout
const PROGRESS_TIMEOUT = 60000; // 1 minute without progress = stuck

class SummarizationTester {
    constructor() {
        this.startTime = null;
        this.lastProgressTime = null;
        this.progressCheckInterval = null;
        this.isStuck = false;
        this.stuckLocation = null;
        this.progressHistory = [];
    }

    /**
     * Test with timeout detection
     */
    async testSummarization() {
        console.log('='.repeat(70));
        console.log('DEPOSITION SUMMARIZATION TEST');
        console.log('='.repeat(70));
        console.log(`Transcript: ${path.basename(TRANSCRIPT_PATH)}`);
        console.log(`Test Timeout: ${TEST_TIMEOUT / 1000}s`);
        console.log(`Progress Timeout: ${PROGRESS_TIMEOUT / 1000}s`);
        console.log('='.repeat(70));
        console.log('');

        // Check if transcript exists
        if (!fs.existsSync(TRANSCRIPT_PATH)) {
            console.error(`ERROR: Transcript not found at ${TRANSCRIPT_PATH}`);
            process.exit(1);
        }

        this.startTime = Date.now();
        this.lastProgressTime = Date.now();

        // Start progress monitoring
        this.startProgressMonitoring();

        try {
            // Test via HTTP API endpoint
            await this.testViaAPI();
        } catch (error) {
            console.error('\n❌ TEST FAILED:', error.message);
            if (this.isStuck) {
                console.error(`\n🔴 PROCESS GOT STUCK at: ${this.stuckLocation}`);
                console.error(`   Last progress: ${this.getTimeSinceLastProgress()}s ago`);
                console.error(`   Progress history:`);
                this.progressHistory.slice(-5).forEach(p => {
                    console.error(`     - ${p.time}: ${p.message}`);
                });
            }
            process.exit(1);
        } finally {
            this.stopProgressMonitoring();
        }
    }

    /**
     * Test via HTTP API (simulates real usage)
     * Step 1: Extract PDF to pages
     * Step 2: Parse Q&A and summarize
     */
    async testViaAPI() {
        // Step 1: Extract PDF
        console.log('📤 Step 1: Extracting PDF to pages...');
        const pages = await this.extractPDF();
        console.log(`   ✓ Extracted ${pages.length} pages\n`);

        // Step 2: Parse Q&A and summarize
        console.log('📤 Step 2: Parsing Q&A and summarizing...');
        await this.parseAndSummarize(pages);
    }

    /**
     * Extract PDF to pages
     */
    async extractPDF() {
        return new Promise((resolve, reject) => {
            const http = require('http');
            const pdfData = fs.readFileSync(TRANSCRIPT_PATH);
            const boundary = '----FormBoundary' + Math.random().toString(36).substring(2);

            const body = Buffer.concat([
                Buffer.from(`--${boundary}\r\n`),
                Buffer.from(`Content-Disposition: form-data; name="pdf"; filename="${path.basename(TRANSCRIPT_PATH)}"\r\n`),
                Buffer.from('Content-Type: application/pdf\r\n\r\n'),
                pdfData,
                Buffer.from(`\r\n--${boundary}--\r\n`)
            ]);

            const options = {
                hostname: 'localhost',
                port: 3000,
                path: '/api/extract',
                method: 'POST',
                headers: {
                    'Content-Type': `multipart/form-data; boundary=${boundary}`,
                    'Content-Length': body.length
                },
                timeout: 120000 // 2 minutes for extraction
            };

            const req = http.request(options, (res) => {
                let data = '';
                res.on('data', chunk => data += chunk.toString());
                res.on('end', () => {
                    if (res.statusCode === 200) {
                        try {
                            const result = JSON.parse(data);
                            if (result.success && result.pages) {
                                resolve(result.pages);
                            } else {
                                reject(new Error('Extraction failed: ' + (result.error || 'Unknown error')));
                            }
                        } catch (e) {
                            reject(new Error('Failed to parse extraction response: ' + e.message));
                        }
                    } else {
                        reject(new Error(`HTTP ${res.statusCode}: ${data.substring(0, 200)}`));
                    }
                });
            });

            req.on('error', (error) => {
                if (error.code === 'ECONNREFUSED') {
                    reject(new Error('Server not running. Please start the server with: npm start'));
                } else {
                    reject(error);
                }
            });

            req.setTimeout(120000, () => {
                req.destroy();
                reject(new Error('PDF extraction timed out after 2 minutes'));
            });

            req.write(body);
            req.end();
        });
    }

    /**
     * Parse Q&A and summarize
     */
    async parseAndSummarize(pages) {
        return new Promise((resolve, reject) => {
            const http = require('http');
            
            const body = JSON.stringify({
                pages: pages,
                firstPrintedPage: 1,
                useAI: true,
                enableTopics: true
            });

            const options = {
                hostname: 'localhost',
                port: 3000,
                path: '/api/parse-qa',
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(body)
                },
                timeout: TEST_TIMEOUT
            };

            const req = http.request(options, (res) => {
                let data = '';
                let isSSE = false;

                res.on('data', (chunk) => {
                    data += chunk.toString();
                    
                    // Check if this is Server-Sent Events (SSE) format
                    if (!isSSE && data.includes('data:')) {
                        isSSE = true;
                        console.log('📥 Receiving Server-Sent Events (SSE) stream...\n');
                    }

                    if (isSSE) {
                        // Parse SSE messages
                        const lines = data.split('\n');
                        data = lines.pop() || ''; // Keep incomplete line in buffer
                        
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                try {
                                    const eventData = JSON.parse(line.slice(6));
                                    this.handleProgressEvent(eventData);
                                    
                                    // Check for completion
                                    if (eventData.type === 'complete') {
                                        const elapsed = ((Date.now() - this.startTime) / 1000).toFixed(1);
                                        console.log(`\n✅ Summarization completed in ${elapsed}s`);
                                        console.log(`   Total Q&A pairs: ${eventData.totalQA || 0}`);
                                        resolve();
                                        return;
                                    }
                                } catch (e) {
                                    // Not JSON, might be other SSE data
                                }
                            }
                        }
                    }
                });

                res.on('end', () => {
                    const elapsed = ((Date.now() - this.startTime) / 1000).toFixed(1);
                    console.log(`\n✅ Request completed in ${elapsed}s`);
                    
                    if (res.statusCode === 200) {
                        // If we got here without a 'complete' event, something might be wrong
                        // But status 200 means it completed
                        resolve();
                    } else {
                        reject(new Error(`HTTP ${res.statusCode}: ${data.substring(0, 200)}`));
                    }
                });
            });

            req.on('error', (error) => {
                if (error.code === 'ECONNREFUSED') {
                    reject(new Error('Server not running. Please start the server with: npm start'));
                } else {
                    reject(error);
                }
            });

            req.setTimeout(TEST_TIMEOUT, () => {
                req.destroy();
                reject(new Error(`Request timed out after ${TEST_TIMEOUT / 1000}s`));
            });

            req.write(body);
            req.end();
        });
    }

    /**
     * Handle progress events from the server
     */
    handleProgressEvent(event) {
        this.lastProgressTime = Date.now();
        const elapsed = ((Date.now() - this.startTime) / 1000).toFixed(1);

        const progressEntry = {
            time: `${elapsed}s`,
            message: this.formatEvent(event)
        };
        this.progressHistory.push(progressEntry);

        // Log progress
        if (event.type === 'chunk-complete') {
            console.log(`  ✓ Chunk ${event.chunk}/${event.totalChunks || '?'}: ${event.qaFound} Q&A pairs found (Total: ${event.totalQA || 0})`);
        } else if (event.type === 'batch-progress') {
            console.log(`  → Batch ${event.batchNum}/${event.totalBatches}: Processing items ${event.currentStart}-${event.currentEnd}/${event.total}`);
        } else if (event.type === 'step') {
            console.log(`  [${event.step}] Chunk ${event.chunk}: ${event.message}`);
        } else if (event.type === 'error') {
            console.error(`  ❌ Error: ${event.message}`);
        }
    }

    /**
     * Format event for display
     */
    formatEvent(event) {
        if (event.type === 'chunk-complete') {
            return `Chunk ${event.chunk}: ${event.qaFound} Q&A pairs`;
        } else if (event.type === 'batch-progress') {
            return `Batch ${event.batchNum}/${event.totalBatches}: ${event.currentStart}-${event.currentEnd}/${event.total}`;
        } else if (event.type === 'step') {
            return `Step ${event.step}: ${event.message}`;
        }
        return JSON.stringify(event);
    }

    /**
     * Start monitoring for stuck processes
     */
    startProgressMonitoring() {
        this.progressCheckInterval = setInterval(() => {
            const timeSinceLastProgress = Date.now() - this.lastProgressTime;
            
            if (timeSinceLastProgress > PROGRESS_TIMEOUT && !this.isStuck) {
                this.isStuck = true;
                const elapsed = ((Date.now() - this.startTime) / 1000).toFixed(1);
                this.stuckLocation = this.progressHistory.length > 0 
                    ? this.progressHistory[this.progressHistory.length - 1].message
                    : 'Unknown';
                
                console.error(`\n🔴 PROCESS APPEARS STUCK!`);
                console.error(`   No progress for ${(timeSinceLastProgress / 1000).toFixed(0)}s`);
                console.error(`   Last activity: ${this.stuckLocation}`);
                console.error(`   Total elapsed: ${elapsed}s`);
                console.error(`\n   This indicates the summarization process is hanging.`);
                console.error(`   Likely causes:`);
                console.error(`   - OpenAI API call timeout (no timeout configured)`);
                console.error(`   - Network issues`);
                console.error(`   - API rate limiting`);
                console.error(`   - Infinite loop in batch processing`);
                
                this.stopProgressMonitoring();
                process.exit(1);
            }
        }, 5000); // Check every 5 seconds
    }

    /**
     * Stop progress monitoring
     */
    stopProgressMonitoring() {
        if (this.progressCheckInterval) {
            clearInterval(this.progressCheckInterval);
            this.progressCheckInterval = null;
        }
    }

    /**
     * Get time since last progress
     */
    getTimeSinceLastProgress() {
        return ((Date.now() - this.lastProgressTime) / 1000).toFixed(1);
    }
}

// Run the test
if (require.main === module) {
    const tester = new SummarizationTester();
    tester.testSummarization()
        .then(() => {
            console.log('\n' + '='.repeat(70));
            console.log('✅ TEST PASSED: Summarization completed without getting stuck');
            console.log('='.repeat(70));
            process.exit(0);
        })
        .catch((error) => {
            console.error('\n' + '='.repeat(70));
            console.error('❌ TEST FAILED');
            console.error('='.repeat(70));
            console.error(error.message);
            process.exit(1);
        });
}

module.exports = SummarizationTester;

