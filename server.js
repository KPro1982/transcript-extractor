const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

// Add Ghostscript to PATH if installed in standard location
const gsPath = 'C:\\Program Files\\gs\\gs10.02.1\\bin';
if (fs.existsSync(gsPath)) {
    process.env.PATH = gsPath + ';' + process.env.PATH;
    console.log('Added Ghostscript to PATH:', gsPath);
}

const { TextReconstructor } = require('./dist/text-reconstructor.js');

// OpenAI API configuration
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || process.env.VITE_OPENAI_API_KEY;
if (!OPENAI_API_KEY) {
    console.warn('Warning: OPENAI_API_KEY not found. AI summarization will fall back to rule-based summaries.');
}

/**
 * Call OpenAI API for summarization
 */
async function callOpenAI(messages, options = {}) {
    if (!OPENAI_API_KEY) {
        throw new Error('OpenAI API key not configured');
    }

    const payload = JSON.stringify({
        model: options.model || 'gpt-4o-mini',
        messages: messages,
        temperature: options.temperature || 0.3,
        max_tokens: options.max_tokens || 500
    });

    return new Promise((resolve, reject) => {
        const req = https.request({
            hostname: 'api.openai.com',
            path: '/v1/chat/completions',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${OPENAI_API_KEY}`,
                'Content-Length': Buffer.byteLength(payload)
            }
        }, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const parsed = JSON.parse(data);
                    if (parsed.error) {
                        reject(new Error(parsed.error.message || 'OpenAI API error'));
                    } else {
                        resolve(parsed.choices[0].message.content);
                    }
                } catch (e) {
                    reject(new Error('Failed to parse OpenAI response'));
                }
            });
        });

        req.on('error', reject);
        req.write(payload);
        req.end();
    });
}

/**
 * Generate AI-powered summary for a Q&A pair
 */
async function generateAISummary(question, answer, colloquy = '') {
    const systemPrompt = `You are a legal assistant summarizing deposition testimony. 
Your task is to convert a question-answer exchange into a single, clear, factual statement about what the witness testified.

Rules:
- Write in third person ("The witness..." or "Witness testified that...")
- Be concise but capture the key information
- Use past tense for events, present tense for ongoing facts
- Include specific names, dates, numbers when mentioned
- If the answer is unclear or the witness doesn't know, reflect that
- Keep summaries to 1-2 sentences maximum
- Do not include objections or colloquy in the summary unless it affected the answer`;

    const userPrompt = colloquy 
        ? `Q: ${question}\n\n${colloquy ? `[Colloquy: ${colloquy}]\n\n` : ''}A: ${answer}`
        : `Q: ${question}\n\nA: ${answer}`;

    try {
        const summary = await callOpenAI([
            { role: 'system', content: systemPrompt },
            { role: 'user', content: userPrompt }
        ]);
        return summary.trim();
    } catch (error) {
        console.error('AI summarization failed:', error.message);
        // Fall back to rule-based summary
        return generateSummary(question, answer);
    }
}

/**
 * Generate AI summary for merged Q&A pairs (with topic classification)
 */
async function generateMergedAISummary(qaSequence) {
    if (!qaSequence || qaSequence.length === 0) {
        return { summary: '', topic: 'Uncategorized' };
    }

    const systemPrompt = `You are a legal assistant summarizing deposition testimony.
You are given multiple related question-answer exchanges that have been grouped together because they form a coherent topic or line of questioning.

Your task is to:
1. Synthesize these exchanges into a unified summary
2. Classify the overall topic

Common topics: Admonitions, Background, Work History, Complaints, Harassment, Discrimination, Performance, Policies, Timeline, Witnesses, Documents, Medical, Damages

Summary requirements:
- Captures the key testimony from all Q&A pairs
- Presents the information in a logical, flowing narrative
- Uses third person ("The witness testified..." or "According to the witness...")
- Remains factual and objective
- Is 2-4 sentences maximum, depending on complexity

Respond in JSON format: {"summary": "...", "topic": "..."}`;

    let userPrompt = 'Summarize the following related Q&A exchanges:\n\n';
    qaSequence.forEach((qa, idx) => {
        userPrompt += `--- Exchange ${idx + 1} ---\n`;
        userPrompt += `Q: ${qa.question}\n`;
        if (qa.colloquy) {
            userPrompt += `[Colloquy: ${qa.colloquy}]\n`;
        }
        userPrompt += `A: ${qa.answer}\n\n`;
    });

    try {
        const response = await callOpenAI([
            { role: 'system', content: systemPrompt },
            { role: 'user', content: userPrompt }
        ], { max_tokens: 300 });
        
        // Parse JSON response
        const parsed = JSON.parse(response.trim());
        return {
            summary: parsed.summary || '',
            topic: parsed.topic || 'Uncategorized'
        };
    } catch (error) {
        console.error('AI merged summarization failed:', error.message);
        // Fall back to combining individual summaries
        return {
            summary: qaSequence.map(qa => qa.summary || '').filter(Boolean).join(' '),
            topic: qaSequence[0]?.topic || 'Uncategorized'
        };
    }
}

/**
 * Batch summarize multiple Q&A pairs using AI
 * Limited to AI_SUMMARY_LIMIT items to save costs - remainder use rule-based summaries
 */
const AI_SUMMARY_LIMIT = 20; // Limit AI summarization to 15-25 Q/As to save money

async function batchSummarizeQA(qaItems, batchSize = 5) {
    if (!OPENAI_API_KEY) {
        console.log('No API key - using rule-based summaries');
        return qaItems.map(qa => ({
            ...qa,
            summary: generateSummary(qa.question, qa.answer),
            topic: 'Uncategorized'
        }));
    }

    // Split items: AI summarize first AI_SUMMARY_LIMIT, rule-based for the rest
    const aiItems = qaItems.slice(0, AI_SUMMARY_LIMIT);
    const ruleBasedItems = qaItems.slice(AI_SUMMARY_LIMIT);

    console.log(`Generating AI summaries for ${aiItems.length} Q&A pairs (limit: ${AI_SUMMARY_LIMIT})...`);
    if (ruleBasedItems.length > 0) {
        console.log(`Using rule-based summaries for remaining ${ruleBasedItems.length} pairs to save costs`);
    }

    const results = [];
    
    // Process AI items in batches
    for (let i = 0; i < aiItems.length; i += batchSize) {
        const batch = aiItems.slice(i, i + batchSize);
        const promises = batch.map(async (qa) => {
            try {
                const summary = await generateAISummary(qa.question, qa.answer, qa.colloquy);
                return { ...qa, summary, aiSummarized: true };
            } catch (error) {
                console.error(`Failed to summarize Q&A ${i}: ${error.message}`);
                return { ...qa, summary: generateSummary(qa.question, qa.answer), aiSummarized: false };
            }
        });
        
        const batchResults = await Promise.all(promises);
        results.push(...batchResults);
        
        // Progress update
        console.log(`  Summarized ${Math.min(i + batchSize, aiItems.length)}/${aiItems.length} pairs`);
        
        // Small delay between batches to avoid rate limiting
        if (i + batchSize < aiItems.length) {
            await new Promise(r => setTimeout(r, 200));
        }
    }
    
    // Add rule-based items
    for (const qa of ruleBasedItems) {
        results.push({
            ...qa,
            summary: generateSummary(qa.question, qa.answer),
            aiSummarized: false
        });
    }
    
    return results;
}

/**
 * Classify topic, extract people, and detect dates for Q&A pairs using AI
 * Common deposition topics: admonitions, background, work history, complaints, 
 * harassment, discrimination, performance, policies
 */
async function classifyTopicsAndExtractMetadata(qaItems) {
    if (!OPENAI_API_KEY || qaItems.length === 0) {
        return qaItems.map(qa => ({ 
            ...qa, 
            topic: 'Uncategorized',
            peopleMentioned: [],
            hasDates: false
        }));
    }

    const systemPrompt = `You are a legal assistant analyzing deposition testimony.
Your task is to analyze each Q&A exchange and provide:
1. Topic classification (broad category)
2. People mentioned (names of individuals referenced)
3. Whether EXPLICIT dates are mentioned (true/false)

Common deposition topics include:
- Admonitions: Instructions given at the start of a deposition
- Background: Personal background, education, biographical information
- Work History: Employment history, job duties, positions held
- Complaints: Filed complaints, grievances, issues raised
- Harassment: Harassment allegations, incidents, complaints
- Discrimination: Discrimination claims, protected class issues
- Performance: Job performance, evaluations, reviews
- Policies: Company policies, procedures, handbooks
- Timeline: Dates, chronology of events
- Witnesses: Other people involved, who witnessed events
- Documents: Document identification, exhibits
- Medical: Health issues, injuries, medical treatment
- Damages: Financial harm, emotional distress, losses

For people mentioned:
- Extract full names when available (e.g., "John Smith")
- Include role/title if mentioned (e.g., {"name": "John Smith", "role": "Supervisor"})
- Do NOT include the witness themselves unless they refer to themselves by name
- Do NOT include attorneys or court reporter

For hasDates - ONLY set to true if an EXPLICIT, SPECIFIC date is mentioned:
- TRUE examples: "January 15, 2020", "on 3/15/2019", "March 2020"
- FALSE examples: "last year", "a few months ago", "in 2019" (year alone is not enough)
- FALSE by default - only true if a clear date can be extracted for chronological ordering

Respond in JSON format:
{"topic": "...", "peopleMentioned": [{"name": "...", "role": "..."}], "hasDates": true/false}`;

    console.log(`Analyzing ${Math.min(qaItems.length, AI_SUMMARY_LIMIT)} Q&A pairs for topics, people, and dates...`);
    
    // Only analyze the first AI_SUMMARY_LIMIT items to save costs
    const itemsToAnalyze = qaItems.slice(0, AI_SUMMARY_LIMIT);
    const remainingItems = qaItems.slice(AI_SUMMARY_LIMIT);
    
    const results = [];
    
    for (let i = 0; i < itemsToAnalyze.length; i++) {
        const qa = itemsToAnalyze[i];
        try {
            const userPrompt = `Q: ${qa.question}\nA: ${qa.answer}`;
            const response = await callOpenAI([
                { role: 'system', content: systemPrompt },
                { role: 'user', content: userPrompt }
            ], { max_tokens: 200 });
            
            const parsed = JSON.parse(response.trim());
            results.push({ 
                ...qa, 
                topic: parsed.topic || 'Uncategorized',
                peopleMentioned: parsed.peopleMentioned || [],
                hasDates: parsed.hasDates || false
            });
        } catch (error) {
            console.error(`Failed to analyze Q&A ${i}: ${error.message}`);
            results.push({ 
                ...qa, 
                topic: 'Uncategorized',
                peopleMentioned: [],
                hasDates: detectDatesInText(qa.question + ' ' + qa.answer)
            });
        }
        
        // Progress update every 10 items
        if ((i + 1) % 10 === 0) {
            console.log(`  Analyzed ${i + 1}/${itemsToAnalyze.length} items`);
        }
        
        // Small delay to avoid rate limiting
        if (i < itemsToAnalyze.length - 1) {
            await new Promise(r => setTimeout(r, 100));
        }
    }
    
    // Add remaining items with basic metadata
    for (const qa of remainingItems) {
        results.push({ 
            ...qa, 
            topic: 'Uncategorized',
            peopleMentioned: [],
            hasDates: detectDatesInText(qa.question + ' ' + qa.answer)
        });
    }
    
    return results;
}

// Simple date detection for non-AI processed items
function detectDatesInText(text) {
    // Only detect EXPLICIT dates (month + day, or full dates)
    // Do NOT match standalone years - those are too vague for chronological ordering
    const datePatterns = [
        /\b\d{1,2}\/\d{1,2}\/\d{2,4}\b/,                    // 1/15/2020 or 01/15/20
        /\b\d{4}-\d{2}-\d{2}\b/,                            // 2020-01-15
        /\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b/i,  // January 15, 2020
        /\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[.\s]+\d{1,2},?\s+\d{4}\b/i,  // Jan. 15, 2020
        /\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b/i,  // 15 January 2020
        /\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(st|nd|rd|th)?,?\s+\d{4}\b/i,  // January 15th, 2020
    ];
    
    return datePatterns.some(pattern => pattern.test(text));
}

/**
 * Reevaluate topics when user adds a new custom topic
 */
async function reevaluateTopicsWithNewTopic(qaItems, newTopic, existingTopics) {
    if (!OPENAI_API_KEY || qaItems.length === 0) {
        return { updates: qaItems.map(() => ({ newTopic: null })) };
    }

    const systemPrompt = `You are a legal assistant analyzing deposition testimony.
A user has added a new topic category: "${newTopic}"

Your task is to review each Q&A exchange and determine if this new topic is a better fit than the current topic.

Existing topics: ${existingTopics.join(', ')}

For each Q&A, respond with:
- The new topic if "${newTopic}" is a better fit
- null if the current topic is better

Be conservative - only change topics if the new topic is clearly more appropriate.

Respond in JSON format: {"shouldChange": true/false, "newTopic": "..." or null}`;

    console.log(`Reevaluating ${Math.min(qaItems.length, AI_SUMMARY_LIMIT)} Q&A items with new topic "${newTopic}"...`);
    
    const itemsToEvaluate = qaItems.slice(0, AI_SUMMARY_LIMIT);
    const updates = [];
    
    for (let i = 0; i < itemsToEvaluate.length; i++) {
        const qa = itemsToEvaluate[i];
        try {
            const userPrompt = `Current topic: ${qa.currentTopic}\n\nQ: ${qa.question}\nA: ${qa.answer}`;
            const response = await callOpenAI([
                { role: 'system', content: systemPrompt },
                { role: 'user', content: userPrompt }
            ], { max_tokens: 100 });
            
            const parsed = JSON.parse(response.trim());
            updates.push({ 
                newTopic: parsed.shouldChange ? newTopic : null 
            });
        } catch (error) {
            updates.push({ newTopic: null });
        }
        
        // Small delay to avoid rate limiting
        if (i < itemsToEvaluate.length - 1) {
            await new Promise(r => setTimeout(r, 50));
        }
    }
    
    // Add null updates for remaining items
    for (let i = itemsToEvaluate.length; i < qaItems.length; i++) {
        updates.push({ newTopic: null });
    }
    
    return { updates };
}

/**
 * Generate AI summary AND topic for a single Q&A (used for merged entries)
 */
async function generateAISummaryWithTopic(question, answer, colloquy = '') {
    const systemPrompt = `You are a legal assistant summarizing deposition testimony. 
Your task is to:
1. Convert a question-answer exchange into a single, clear, factual statement
2. Classify the topic into a broad category

Common topics: Admonitions, Background, Work History, Complaints, Harassment, Discrimination, Performance, Policies, Timeline, Witnesses, Documents, Medical, Damages

Rules for summary:
- Write in third person ("The witness..." or "Witness testified that...")
- Be concise but capture the key information
- Keep summaries to 1-2 sentences maximum

Respond in JSON format: {"summary": "...", "topic": "..."}`;

    const userPrompt = colloquy 
        ? `Q: ${question}\n\n${colloquy ? `[Colloquy: ${colloquy}]\n\n` : ''}A: ${answer}`
        : `Q: ${question}\n\nA: ${answer}`;

    try {
        const response = await callOpenAI([
            { role: 'system', content: systemPrompt },
            { role: 'user', content: userPrompt }
        ], { max_tokens: 200 });
        
        // Parse JSON response
        const parsed = JSON.parse(response.trim());
        return {
            summary: parsed.summary || '',
            topic: parsed.topic || 'Uncategorized'
        };
    } catch (error) {
        console.error('AI summarization with topic failed:', error.message);
        return {
            summary: generateSummary(question, answer),
            topic: 'Uncategorized'
        };
    }
}

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
 * Parse Q/A pairs from examination content
 * Each Q/A object contains:
 * - question: text snippet
 * - questionLocation: page:startLine-endLine
 * - answer: text snippet
 * - answerLocation: page:startLine-endLine
 * - colloquy: text snippet (objections, etc.)
 * - colloquyLocation: page:startLine-endLine
 */
function parseExamination(pages, firstPrintedPage) {
    const qaItems = [];
    
    // Flatten all lines with page/line info
    const allLines = [];
    for (let i = 0; i < pages.length; i++) {
        const printedPage = (i + 1) - firstPrintedPage + 1;
        const page = pages[i];
        const lines = page.lines || [];
        
        for (const line of lines) {
            allLines.push({
                text: line.text || '',
                lineNumber: line.lineNumber,
                pageIndex: i,
                printedPage: printedPage
            });
        }
    }
    
    // Find examination start
    let examStart = -1;
    for (let i = 0; i < allLines.length; i++) {
        const text = allLines[i].text.trim();
        // Look for "EXAMINATION" header or "BY MR./MS. X:"
        if (text.match(/^EXAMINATION$/i) || 
            text.match(/^BY\s+M[RS]\.\s+\w+:$/i) ||
            text.match(/EXAMINATION\s*$/i)) {
            examStart = i;
            break;
        }
    }
    
    if (examStart === -1) {
        // Try to find first Q. or QUESTION if no EXAMINATION header
        // Handle patterns with middle dots like "· · ·Q.·"
        for (let i = 0; i < allLines.length; i++) {
            const lineText = allLines[i].text;
            if (lineText.match(/[·\s]*Q\.[·\s]/i) || 
                lineText.match(/^\s*Q\.\s+/i) || 
                lineText.match(/^\s*QUESTION[:\s]/i)) {
                examStart = i;
                break;
            }
        }
    }
    
    if (examStart === -1) {
        console.log('Could not find examination section');
        return qaItems;
    }
    
    console.log(`Found examination starting at line ${examStart}`);
    
    // Parse Q/A pairs
    let currentQ = null;
    let currentA = null;
    let currentColloquy = null;
    let state = 'searching'; // searching, in_question, in_colloquy, in_answer
    
    for (let i = examStart; i < allLines.length; i++) {
        const line = allLines[i];
        const text = line.text;
        const trimmed = text.trim();
        
        // Skip empty lines
        if (!trimmed) continue;
        
        // Check if this is a Question line (Q. or QUESTION or Question:)
        // Handle patterns like "· · ·Q.·" with middle dots
        const isQuestion = trimmed.match(/^Q\.\s*/i) || 
                          text.match(/^\s+Q\.\s*/i) ||
                          trimmed.match(/^[·\s]*Q\.[·\s]/i) ||
                          trimmed.match(/^QUESTION[:\s]/i) ||
                          trimmed.match(/^Question[:\s]/i);
        // Check if this is an Answer line (A. or ANSWER or Answer:)
        // Handle patterns like "· · ·A.·" with middle dots
        const isAnswer = trimmed.match(/^A\.\s*/i) || 
                        text.match(/^\s+A\.\s*/i) ||
                        trimmed.match(/^[·\s]*A\.[·\s]/i) ||
                        trimmed.match(/^ANSWER[:\s]/i) ||
                        trimmed.match(/^Answer[:\s]/i);
        // Check if this is THE WITNESS: (answer after objection)
        const isWitnessAnswer = trimmed.match(/^[·\s]*THE\s+WITNESS:[·\s]*/i) ||
                               trimmed.match(/^THE\s+WITNESS:/i);
        // Check if this is colloquy (attorney speaking, objection, etc.)
        // But NOT "THE WITNESS:" which is an answer
        const isColloquy = (trimmed.match(/^M[RS]\.\s+\w+:/i) || 
                          trimmed.match(/^THE\s+(REPORTER|COURT):/i) ||
                          trimmed.match(/^\(.*\)$/) || // Parenthetical notes
                          trimmed.match(/^[·\s]*M[RS]\.\s+\w+:/i) ||
                          trimmed.match(/^BY\s+M[RS]\.\s+\w+:$/i)) && // Return to questioning
                          !isWitnessAnswer;
        
        // Check for end of examination (certificate, signature pages)
        if (trimmed.match(/^CERTIFICATE OF REPORTER/i) ||
            trimmed.match(/^PENALTY OF PERJURY/i) ||
            trimmed.match(/^CHANGES AND SIGNATURE/i)) {
            // Save current Q/A if complete
            if (currentQ && currentA) {
                qaItems.push({
                    question: currentQ.text,
                    questionLocation: formatLocation(currentQ),
                    answer: currentA.text,
                    answerLocation: formatLocation(currentA),
                    location: formatFullLocation(currentQ, currentA),
                    colloquy: currentColloquy ? currentColloquy.text : '',
                    colloquyLocation: currentColloquy ? formatLocation(currentColloquy) : '',
                    summary: generateSummary(currentQ.text, currentA.text)
                });
            }
            break;
        }
        
        if (isQuestion) {
            // Save previous Q/A if complete
            if (currentQ && currentA) {
                qaItems.push({
                    question: currentQ.text,
                    questionLocation: formatLocation(currentQ),
                    answer: currentA.text,
                    answerLocation: formatLocation(currentA),
                    location: formatFullLocation(currentQ, currentA),
                    colloquy: currentColloquy ? currentColloquy.text : '',
                    colloquyLocation: currentColloquy ? formatLocation(currentColloquy) : '',
                    summary: generateSummary(currentQ.text, currentA.text)
                });
            }
            
            // Start new question
            currentQ = {
                text: cleanQAText(text),
                startPage: line.printedPage,
                startLine: line.lineNumber,
                endPage: line.printedPage,
                endLine: line.lineNumber
            };
            currentA = null;
            currentColloquy = null;
            state = 'in_question';
            
        } else if (isAnswer || isWitnessAnswer) {
            if (currentQ) {
                // Start answer - handle both A. and THE WITNESS:
                const answerText = isWitnessAnswer 
                    ? cleanWitnessText(text)
                    : cleanQAText(text);
                    
                if (!currentA) {
                    // Start new answer
                    currentA = {
                        text: answerText,
                        startPage: line.printedPage,
                        startLine: line.lineNumber,
                        endPage: line.printedPage,
                        endLine: line.lineNumber
                    };
                } else {
                    // Continue existing answer (another THE WITNESS: line)
                    currentA.text += ' ' + answerText;
                    currentA.endPage = line.printedPage;
                    currentA.endLine = line.lineNumber;
                }
                state = 'in_answer';
            }
            
        } else if (isColloquy) {
            if (state === 'in_question' || state === 'in_colloquy') {
                // Colloquy between question and answer (objection, etc.)
                if (!currentColloquy) {
                    currentColloquy = {
                        text: cleanColloquyText(trimmed),
                        startPage: line.printedPage,
                        startLine: line.lineNumber,
                        endPage: line.printedPage,
                        endLine: line.lineNumber
                    };
                } else {
                    currentColloquy.text += ' ' + cleanColloquyText(trimmed);
                    currentColloquy.endPage = line.printedPage;
                    currentColloquy.endLine = line.lineNumber;
                }
                state = 'in_colloquy';
            } else if (state === 'in_answer') {
                // In answer state, colloquy might indicate end of this Q/A
                // or continuation - we'll treat it as end and let next Q pick it up
            }
            
        } else {
            // Continuation of current element
            if (state === 'in_question' && currentQ) {
                currentQ.text += ' ' + trimmed;
                currentQ.endPage = line.printedPage;
                currentQ.endLine = line.lineNumber;
            } else if (state === 'in_answer' && currentA) {
                currentA.text += ' ' + trimmed;
                currentA.endPage = line.printedPage;
                currentA.endLine = line.lineNumber;
            } else if (state === 'in_colloquy' && currentColloquy) {
                currentColloquy.text += ' ' + trimmed;
                currentColloquy.endPage = line.printedPage;
                currentColloquy.endLine = line.lineNumber;
            }
        }
    }
    
    // Don't forget the last Q/A pair
    if (currentQ && currentA) {
        qaItems.push({
            question: currentQ.text,
            questionLocation: formatLocation(currentQ),
            answer: currentA.text,
            answerLocation: formatLocation(currentA),
            location: formatFullLocation(currentQ, currentA),
            colloquy: currentColloquy ? currentColloquy.text : '',
            colloquyLocation: currentColloquy ? formatLocation(currentColloquy) : '',
            summary: generateSummary(currentQ.text, currentA.text)
        });
    }
    
    console.log(`Parsed ${qaItems.length} Q/A pairs`);
    return qaItems;
}

function cleanQAText(text) {
    // Remove Q./A./QUESTION/ANSWER prefix and clean up middle dots/spacing
    // Handle patterns like "· · ·Q.· text" or "· · ·A.· text"
    return text
        .replace(/^[·\s]*Q\.[·\s]*/i, '')
        .replace(/^[·\s]*A\.[·\s]*/i, '')
        .replace(/^\s*QUESTION[:\s]*/i, '')
        .replace(/^\s*ANSWER[:\s]*/i, '')
        .replace(/·/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function cleanWitnessText(text) {
    // Remove "THE WITNESS:" prefix and clean up
    return text
        .replace(/^[·\s]*THE\s+WITNESS:[·\s]*/i, '')
        .replace(/·/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function cleanColloquyText(text) {
    // Clean up colloquy text (keep the speaker label for context)
    return text
        .replace(/·/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

/**
 * Generate a summary statement from a Q&A pair
 * Converts question-answer format into a single affirmative statement
 */
function generateSummary(question, answer) {
    if (!question || !answer) return '';
    
    // Clean up input
    let q = question.trim().replace(/\?$/, '').trim();
    let a = answer.trim().replace(/\.$/, '').trim();
    
    // Normalize answer for checking
    const aLower = a.toLowerCase();
    
    // Check for yes/no type answers
    const isYes = /^(yes|yeah|yep|correct|that's correct|that is correct|right|affirmative|i do|i did|i have|i was|i am|i can|it is|it was|they are|they were|there is|there are|uh-huh)\.?$/i.test(aLower);
    const isNo = /^(no|nope|nah|incorrect|that's incorrect|negative|i don't|i didn't|i haven't|i wasn't|i'm not|i cannot|it isn't|it wasn't|they aren't|they weren't|there isn't|there aren't|uh-uh|not that i)\.?$/i.test(aLower);
    
    if (isYes) {
        return convertQuestionToAffirmative(q);
    }
    
    if (isNo) {
        return convertQuestionToNegative(q);
    }
    
    // For substantive answers, create combined statement
    return createSubstantiveSummary(q, a);
}

function convertQuestionToAffirmative(q) {
    const qLower = q.toLowerCase();
    
    // "Have you had your deposition taken" -> "The witness has been deposed before"
    if (qLower.match(/have you (had your|ever had your|ever given a) deposition/)) {
        return 'The witness has been deposed before.';
    }
    
    // "Have you ever..." -> "The witness has..."
    if (qLower.match(/^have you (ever )?/)) {
        const rest = q.replace(/^have you (ever )?/i, '');
        return 'The witness has ' + rest + '.';
    }
    
    // "Had you ever..." -> "The witness had..."
    if (qLower.match(/^had you (ever )?/)) {
        const rest = q.replace(/^had you (ever )?/i, '');
        return 'The witness had ' + rest + '.';
    }
    
    // "Did you..." -> "The witness [past tense action]"
    if (qLower.match(/^did you\s+/)) {
        const action = q.replace(/^did you\s+/i, '');
        return 'The witness ' + action + '.';
    }
    
    // "Were you..." -> "The witness was..."
    if (qLower.match(/^were you\s+/)) {
        const state = q.replace(/^were you\s+/i, '');
        return 'The witness was ' + state + '.';
    }
    
    // "Are you..." -> "The witness is..."
    if (qLower.match(/^are you\s+/)) {
        const state = q.replace(/^are you\s+/i, '');
        return 'The witness is ' + state + '.';
    }
    
    // "Do you..." -> "The witness does..."
    if (qLower.match(/^do you\s+/)) {
        const action = q.replace(/^do you\s+/i, '');
        return 'The witness ' + conjugateVerb(action) + '.';
    }
    
    // "Can you..." -> "The witness can..."
    if (qLower.match(/^can you\s+/)) {
        const action = q.replace(/^can you\s+/i, '');
        return 'The witness can ' + action + '.';
    }
    
    // "Would you..." -> "The witness would..."
    if (qLower.match(/^would you\s+/)) {
        const action = q.replace(/^would you\s+/i, '');
        return 'The witness would ' + action + '.';
    }
    
    // "Is it true/correct that..." -> statement
    if (qLower.match(/^is it (true|correct|fair to say) that\s+/)) {
        const statement = q.replace(/^is it (true|correct|fair to say) that\s+/i, '');
        return capitalizeFirst(statement) + '.';
    }
    
    // "Is that..." / "Is this..." -> "That/This is..."
    if (qLower.match(/^is (that|this)\s+/)) {
        const rest = q.replace(/^is (that|this)\s+/i, '');
        return capitalizeFirst(q.match(/^is (that|this)/i)[1]) + ' is ' + rest + '.';
    }
    
    // Default: affirm
    return 'The witness confirmed this.';
}

function convertQuestionToNegative(q) {
    const qLower = q.toLowerCase();
    
    // "Have you ever..." -> "The witness has never..."
    if (qLower.match(/^have you (ever )?/)) {
        const rest = q.replace(/^have you (ever )?/i, '');
        return 'The witness has not ' + rest + '.';
    }
    
    // "Did you..." -> "The witness did not..."
    if (qLower.match(/^did you\s+/)) {
        const action = q.replace(/^did you\s+/i, '');
        return 'The witness did not ' + action + '.';
    }
    
    // "Were you..." -> "The witness was not..."
    if (qLower.match(/^were you\s+/)) {
        const state = q.replace(/^were you\s+/i, '');
        return 'The witness was not ' + state + '.';
    }
    
    // "Are you..." -> "The witness is not..."
    if (qLower.match(/^are you\s+/)) {
        const state = q.replace(/^are you\s+/i, '');
        return 'The witness is not ' + state + '.';
    }
    
    // "Do you..." -> "The witness does not..."
    if (qLower.match(/^do you\s+/)) {
        const action = q.replace(/^do you\s+/i, '');
        return 'The witness does not ' + action + '.';
    }
    
    // Default: deny
    return 'The witness denied this.';
}

function createSubstantiveSummary(q, a) {
    const qLower = q.toLowerCase();
    
    // "What is/was your [X]" -> "The witness's [X] is/was [answer]"
    const whatIsYourMatch = qLower.match(/^what (is|was|are|were) your\s+(.+)/);
    if (whatIsYourMatch) {
        const verb = whatIsYourMatch[1];
        const subject = whatIsYourMatch[2];
        return `The witness's ${subject} ${verb} ${a}.`;
    }
    
    // "What is/was your [X] in [time]" -> preserve time context
    const whatIsYourTimeMatch = qLower.match(/^what (is|was|are|were) your\s+(.+?)\s+in\s+(\d{4}|\w+)/);
    if (whatIsYourTimeMatch) {
        const verb = whatIsYourTimeMatch[1];
        const subject = whatIsYourTimeMatch[2];
        const time = whatIsYourTimeMatch[3];
        return `The witness's ${subject} in ${time} ${verb} ${a}.`;
    }
    
    // "What is/was the [X]" -> "The [X] is/was [answer]"
    const whatIsTheMatch = qLower.match(/^what (is|was|are|were) the\s+(.+)/);
    if (whatIsTheMatch) {
        const verb = whatIsTheMatch[1];
        const subject = whatIsTheMatch[2];
        return `The ${subject} ${verb} ${a}.`;
    }
    
    // "What [X] do/did you [verb]" -> "The witness [verb]s/[verb]ed [answer]"
    if (qLower.match(/^what\s+.+\s+do you\s+/)) {
        return `The witness's answer: ${a}.`;
    }
    
    // "Where do/did you [verb]" -> "The witness [verb]s/[verb]ed at [answer]"
    if (qLower.match(/^where (do|did|does) you\s+(live|work|reside)/)) {
        const verb = qLower.match(/(live|work|reside)/)[1];
        const tense = qLower.includes('did') ? 'ed' : 's';
        return `The witness ${verb}${tense === 'ed' ? 'd' : 's'} at ${a}.`;
    }
    
    // "How many..." -> "[Answer] [rest of question context]"
    if (qLower.match(/^how many\s+/)) {
        return `${a}.`;
    }
    
    // "How long..." -> "The duration was [answer]"
    if (qLower.match(/^how long\s+/)) {
        return `The duration was ${a}.`;
    }
    
    // "Who is/was..." -> "[Answer] is/was [context]"
    if (qLower.match(/^who (is|was|are|were)\s+/)) {
        return `${a}.`;
    }
    
    // "When did..." -> "[Event] occurred [answer]"
    if (qLower.match(/^when (did|do|does|was|were)\s+/)) {
        return `This occurred ${a}.`;
    }
    
    // "Can you state and spell your name" -> "The witness's name is [answer]"
    if (qLower.match(/state.*(and|&)?\s*spell.*name/)) {
        // Extract just the name from answers like "John Smith, J-O-H-N S-M-I-T-H"
        const nameOnly = a.split(/[,\-–—]/)[0].trim();
        return `The witness's name is ${nameOnly}.`;
    }
    
    // "Can you state your name" -> "The witness's name is [answer]"
    if (qLower.match(/state\s+(your\s+)?(full\s+)?name/)) {
        const nameOnly = a.split(/[,\-–—]/)[0].trim();
        return `The witness's name is ${nameOnly}.`;
    }
    
    // Default: create statement from answer with context
    return `${a}.`;
}

function conjugateVerb(phrase) {
    const words = phrase.split(' ');
    if (words.length > 0) {
        const verb = words[0].toLowerCase();
        const irregulars = {
            'have': 'has',
            'do': 'does',
            'go': 'goes',
            'be': 'is',
            'know': 'knows',
            'understand': 'understands',
            'remember': 'remembers',
            'recall': 'recalls',
            'believe': 'believes',
            'think': 'thinks',
            'agree': 'agrees'
        };
        if (irregulars[verb]) {
            words[0] = irregulars[verb];
        } else if (verb.match(/(s|sh|ch|x|z|o)$/)) {
            words[0] = verb + 'es';
        } else if (verb.match(/[^aeiou]y$/)) {
            words[0] = verb.slice(0, -1) + 'ies';
        } else {
            words[0] = verb + 's';
        }
    }
    return words.join(' ');
}

function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function formatLocation(item) {
    if (item.startPage === item.endPage) {
        if (item.startLine === item.endLine) {
            return `${item.startPage}:${item.startLine}`;
        }
        return `${item.startPage}:${item.startLine}-${item.endLine}`;
    }
    return `${item.startPage}:${item.startLine}-${item.endPage}:${item.endLine}`;
}

/**
 * Format the full location spanning from question start to answer end
 */
function formatFullLocation(question, answer) {
    if (!question || !answer) {
        return question ? formatLocation(question) : (answer ? formatLocation(answer) : '');
    }
    
    const startPage = question.startPage;
    const startLine = question.startLine;
    const endPage = answer.endPage;
    const endLine = answer.endLine;
    
    if (startPage === endPage) {
        if (startLine === endLine) {
            return `${startPage}:${startLine}`;
        }
        return `${startPage}:${startLine}-${endLine}`;
    }
    return `${startPage}:${startLine}-${endPage}:${endLine}`;
}

/**
 * Extract text and images from PDF for side-by-side viewing
 * Uses DIGITAL extraction first, with OCR fallback only for pages without text
 */
async function extractPDFWithImages(pdfPath) {
    const { ExternalPDFToImageConverter } = require('./dist/pdf-to-image-external.js');
    const { OCREngine } = require('./dist/ocr-engine.js');
    const pdfjsLib = require('pdfjs-dist');
    
    if (pdfjsLib.GlobalWorkerOptions) {
        pdfjsLib.GlobalWorkerOptions.workerSrc = '';
    }

    console.log(`\n${'='.repeat(60)}`);
    console.log('SMART PDF Extraction (Digital First, OCR Fallback)');
    console.log(`${'='.repeat(60)}`);

    // Get PDF info
    const pdfBuffer = fs.readFileSync(pdfPath);
    const pdfBytes = new Uint8Array(pdfBuffer);
    const loadingTask = pdfjsLib.getDocument({ data: pdfBytes, useWorkerFetch: false, isEvalSupported: false });
    const pdfDoc = await loadingTask.promise;
    const totalPages = pdfDoc.numPages;

    // Legal transcript settings
    const LINES_PER_PAGE = 25;
    const topMarginPercent = 0.10;
    const bottomMarginPercent = 0.10;
    const MIN_TEXT_ITEMS_THRESHOLD = 10; // Minimum items to consider digital extraction successful

    // Step 1: Try digital extraction for all pages first
    console.log(`\n[1/3] Attempting digital text extraction for ${totalPages} pages...`);
    
    const digitalPages = [];
    const pagesNeedingOCR = [];
    
    for (let pageNum = 1; pageNum <= totalPages; pageNum++) {
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

        // Check if this page has meaningful text
        const meaningfulItems = textItems.filter(item => /[a-zA-Z0-9]/.test(item.text.trim()));
        const hasEnoughText = meaningfulItems.length >= MIN_TEXT_ITEMS_THRESHOLD;
        
        digitalPages.push({
            pageNum,
            width,
            height,
            textItems,
            hasEnoughText
        });

        if (!hasEnoughText) {
            pagesNeedingOCR.push(pageNum);
            console.log(`  ⚠ Page ${pageNum}: ${textItems.length} items (needs OCR)`);
        } else {
            console.log(`  ✓ Page ${pageNum}: ${textItems.length} items (digital OK)`);
        }
    }

    // Step 2: Only convert to images and OCR if needed
    let images = null;
    let ocrEngine = null;
    let ocrResults = new Map();

    if (pagesNeedingOCR.length > 0) {
        console.log(`\n[2/3] OCR fallback for ${pagesNeedingOCR.length} pages: ${pagesNeedingOCR.join(', ')}`);
        
        // Convert PDF to images
        console.log('  Converting PDF to images...');
        const imageConverter = new ExternalPDFToImageConverter({ dpi: 150, outputDir: IMAGES_DIR });
        images = await imageConverter.convert(pdfPath);
        
        // Initialize OCR engine
        console.log('  Initializing OCR engine...');
        ocrEngine = new OCREngine('eng');
        await ocrEngine.initialize();
        
        // OCR only the pages that need it
        for (const pageNum of pagesNeedingOCR) {
            const pageImage = images.find(img => img.pageNumber === pageNum);
            if (pageImage) {
                console.log(`  Processing page ${pageNum} with OCR...`);
                const ocrResult = await ocrEngine.processImage(pageImage.imagePath, pageNum);
                ocrResults.set(pageNum, ocrResult);
            }
        }
        
        // Cleanup OCR engine
        await ocrEngine.terminate();
    } else {
        console.log(`\n[2/3] Skipping OCR - all pages have digital text!`);
        
        // Still need images for display
        console.log('  Converting PDF to images for display...');
        const imageConverter = new ExternalPDFToImageConverter({ dpi: 150, outputDir: IMAGES_DIR });
        images = await imageConverter.convert(pdfPath);
    }

    // Step 3: Build final results
    console.log(`\n[3/3] Building final results...`);
    const pages = [];

    for (let i = 0; i < digitalPages.length; i++) {
        const digitalPage = digitalPages[i];
        const pageNum = digitalPage.pageNum;
        const { width, height } = digitalPage;
        
        let textItems;
        let extractionMethod;
        
        if (ocrResults.has(pageNum)) {
            // Use OCR results for this page
            const ocrResult = ocrResults.get(pageNum);
            textItems = ocrResult.words.map(word => ({
                text: word.text,
                x: word.bbox.x,
                y: word.bbox.y,
                width: word.bbox.width,
                height: word.bbox.height,
            }));
            extractionMethod = 'ocr';
            console.log(`  Page ${pageNum}: Using OCR (${textItems.length} words)`);
        } else {
            // Use digital extraction
            textItems = digitalPage.textItems;
            extractionMethod = 'digital';
            console.log(`  Page ${pageNum}: Using digital (${textItems.length} items)`);
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
                    confidence: extractionMethod === 'digital' ? 100 : 90,
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
            unmatched: merged.filter(m => !m.lineNumber && m.text).map(m => m.text),
            extractionMethod
        });
    }

    const digitalCount = pages.filter(p => p.extractionMethod === 'digital').length;
    const ocrCount = pages.filter(p => p.extractionMethod === 'ocr').length;
    
    console.log(`\n${'='.repeat(60)}`);
    console.log(`✓ Smart Extraction Complete - ${totalPages} pages processed`);
    console.log(`  Digital: ${digitalCount} pages | OCR fallback: ${ocrCount} pages`);
    console.log(`${'='.repeat(60)}\n`);

    return { pages, totalPages };
}

const server = http.createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');

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

    // Parse Q/A endpoint - with AI summarization, topic classification, people extraction, and date detection
    if (req.method === 'POST' && url.pathname === '/api/parse-qa') {
        const chunks = [];
        req.on('data', chunk => chunks.push(chunk));
        req.on('end', async () => {
            try {
                const body = JSON.parse(Buffer.concat(chunks).toString());
                const { pages, firstPrintedPage, useAI = true } = body;
                
                console.log(`\nParsing Q/A with first printed page = ${firstPrintedPage}`);
                let qaItems = parseExamination(pages, firstPrintedPage);
                
                // Use AI summarization if enabled and API key is available
                if (useAI && OPENAI_API_KEY && qaItems.length > 0) {
                    console.log(`Using AI for summarization (limited to first ${AI_SUMMARY_LIMIT} items)...`);
                    qaItems = await batchSummarizeQA(qaItems);
                    
                    // Classify topics, extract people, detect dates
                    console.log('Analyzing topics, people, and dates...');
                    qaItems = await classifyTopicsAndExtractMetadata(qaItems);
                } else if (!OPENAI_API_KEY) {
                    console.log('No OpenAI API key - using rule-based summaries');
                    qaItems = qaItems.map(qa => ({ 
                        ...qa, 
                        topic: 'Uncategorized',
                        peopleMentioned: [],
                        hasDates: detectDatesInText(qa.question + ' ' + qa.answer)
                    }));
                }
                
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({
                    success: true,
                    qaItems: qaItems,
                    totalQA: qaItems.length,
                    aiSummaries: !!(useAI && OPENAI_API_KEY),
                    aiSummaryLimit: AI_SUMMARY_LIMIT
                }));
            } catch (error) {
                console.error('Parse error:', error);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Failed to parse: ' + error.message }));
            }
        });
        return;
    }

    // Summarize merged Q&A pairs endpoint (returns summary and topic)
    if (req.method === 'POST' && url.pathname === '/api/summarize-merged') {
        const chunks = [];
        req.on('data', chunk => chunks.push(chunk));
        req.on('end', async () => {
            try {
                const body = JSON.parse(Buffer.concat(chunks).toString());
                const { qaSequence } = body;
                
                if (!qaSequence || !Array.isArray(qaSequence) || qaSequence.length === 0) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'Invalid qaSequence provided' }));
                    return;
                }
                
                console.log(`Generating merged summary for ${qaSequence.length} Q&A pairs...`);
                const result = await generateMergedAISummary(qaSequence);
                
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({
                    success: true,
                    summary: result.summary,
                    topic: result.topic
                }));
            } catch (error) {
                console.error('Summarize error:', error);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Failed to summarize: ' + error.message }));
            }
        });
        return;
    }

    // Reevaluate topics with new custom topic
    if (req.method === 'POST' && url.pathname === '/api/reevaluate-topics') {
        const chunks = [];
        req.on('data', chunk => chunks.push(chunk));
        req.on('end', async () => {
            try {
                const body = JSON.parse(Buffer.concat(chunks).toString());
                const { qaItems, newTopic, existingTopics } = body;
                
                if (!qaItems || !newTopic) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'qaItems and newTopic are required' }));
                    return;
                }
                
                console.log(`Reevaluating topics with new topic "${newTopic}"...`);
                const result = await reevaluateTopicsWithNewTopic(qaItems, newTopic, existingTopics || []);
                
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({
                    success: true,
                    updates: result.updates
                }));
            } catch (error) {
                console.error('Topic reevaluation error:', error);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Failed to reevaluate: ' + error.message }));
            }
        });
        return;
    }

    // Single Q&A summarization endpoint
    if (req.method === 'POST' && url.pathname === '/api/summarize') {
        const chunks = [];
        req.on('data', chunk => chunks.push(chunk));
        req.on('end', async () => {
            try {
                const body = JSON.parse(Buffer.concat(chunks).toString());
                const { question, answer, colloquy } = body;
                
                if (!question || !answer) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'Question and answer are required' }));
                    return;
                }
                
                const summary = await generateAISummary(question, answer, colloquy);
                
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({
                    success: true,
                    summary: summary
                }));
            } catch (error) {
                console.error('Summarize error:', error);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Failed to summarize: ' + error.message }));
            }
        });
        return;
    }

    // PDF extraction endpoint
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
    console.log('  DepoDigest - Deposition Summarization Tool');
    console.log(`${'='.repeat(50)}`);
    console.log(`\n  Server: http://localhost:${PORT}/`);
    console.log(`\n  Features:`);
    console.log('    - Upload deposition PDFs');
    console.log('    - Confirm first printed page number');
    console.log('    - Parse Q/A examination section');
    console.log('    - Navigate through Q/A pairs');
    console.log(`\n${'='.repeat(50)}\n`);

    // Open in default browser
    const { exec } = require('child_process');
    const url = `http://localhost:${PORT}/`;
    
    // Windows
    exec(`start ${url}`);
});
