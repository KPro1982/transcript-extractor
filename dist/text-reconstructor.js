"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TextReconstructor = void 0;
class TextReconstructor {
    reconstructText(pages, options) {
        switch (options.format) {
            case 'json':
                return this.toJSON(pages);
            case 'md':
                return this.toMarkdown(pages, options);
            case 'txt':
            default:
                return this.toPlainText(pages, options);
        }
    }
    toPlainText(pages, options) {
        let output = '';
        for (const page of pages) {
            output += `${'='.repeat(80)}\n`;
            output += `PAGE ${page.pageNumber} (${page.dimensions.width.toFixed(0)} x ${page.dimensions.height.toFixed(0)}) - Confidence: ${page.confidence.toFixed(1)}%\n`;
            output += `${'='.repeat(80)}\n\n`;
            // Headers
            if (page.headers.length > 0) {
                output += '--- HEADERS ---\n';
                output += this.formatBlocks(page.headers, options);
                output += '\n';
            }
            // Line Numbers & Content
            if (page.lineNumbers.length > 0 || page.mainContent.length > 0) {
                output += '--- CONTENT ---\n';
                // Merge line numbers with content by proximity
                const merged = this.mergeLineNumbersWithContent(page.lineNumbers, page.mainContent);
                for (const item of merged) {
                    if (item.lineNumber) {
                        output += `${item.lineNumber.padStart(4)} | `;
                    }
                    else {
                        output += '     | ';
                    }
                    output += item.text;
                    if (options.includeConfidence && item.confidence !== undefined) {
                        output += ` [${item.confidence.toFixed(1)}%]`;
                    }
                    output += '\n';
                }
                output += '\n';
            }
            // Footers
            if (page.footers.length > 0) {
                output += '--- FOOTERS ---\n';
                output += this.formatBlocks(page.footers, options);
                output += '\n';
            }
        }
        return output;
    }
    toMarkdown(pages, options) {
        let output = '# PDF OCR Extraction\n\n';
        for (const page of pages) {
            output += `## Page ${page.pageNumber}\n\n`;
            if (options.includeConfidence) {
                output += `*Confidence: ${page.confidence.toFixed(1)}%*\n\n`;
            }
            if (page.headers.length > 0) {
                output += '### Headers\n\n';
                page.headers.forEach(h => {
                    output += `${h.text}  \n`;
                });
                output += '\n';
            }
            if (page.mainContent.length > 0) {
                output += '### Content\n\n';
                const merged = this.mergeLineNumbersWithContent(page.lineNumbers, page.mainContent);
                for (const item of merged) {
                    if (item.lineNumber) {
                        output += `**${item.lineNumber}** `;
                    }
                    output += `${item.text}  \n`;
                }
                output += '\n';
            }
            if (page.footers.length > 0) {
                output += '### Footers\n\n';
                page.footers.forEach(f => {
                    output += `${f.text}  \n`;
                });
                output += '\n';
            }
            output += '---\n\n';
        }
        return output;
    }
    toJSON(pages) {
        return JSON.stringify({ pages }, null, 2);
    }
    formatBlocks(blocks, options) {
        let output = '';
        for (const block of blocks) {
            if (options.includePositions) {
                output += `[${block.position.x.toFixed(0)}, ${block.position.y.toFixed(0)}] `;
            }
            output += block.text;
            if (options.includeConfidence) {
                output += ` [${block.confidence.toFixed(1)}%]`;
            }
            output += '\n';
        }
        return output;
    }
    /**
     * ROBUST mergeLineNumbersWithContent with CASCADING FALLBACKS
     * Belt and suspenders approach - tries multiple strategies
     */
    mergeLineNumbersWithContent(lineNumbers, content) {
        // Strategy 1: Position-based matching (original approach with better tolerance)
        let merged = this._mergeByPosition(lineNumbers, content);
        
        // Check if merge was successful (most lines should have content)
        const linesWithContent = merged.filter(m => m.lineNumber && m.text && m.text.trim().length > 0);
        const successRate = lineNumbers.length > 0 ? linesWithContent.length / lineNumbers.length : 0;
        
        if (successRate >= 0.7) {
            // Position-based matching worked well
            return merged;
        }
        
        // Strategy 2: Sequential matching (line numbers and content in order)
        console.log(`  [TextReconstructor] Position-based matching poor (${(successRate*100).toFixed(0)}%), trying sequential...`);
        merged = this._mergeBySequence(lineNumbers, content);
        
        const seqLinesWithContent = merged.filter(m => m.lineNumber && m.text && m.text.trim().length > 0);
        const seqSuccessRate = lineNumbers.length > 0 ? seqLinesWithContent.length / lineNumbers.length : 0;
        
        if (seqSuccessRate >= 0.7) {
            console.log(`  [TextReconstructor] Sequential matching succeeded (${(seqSuccessRate*100).toFixed(0)}%)`);
            return merged;
        }
        
        // Strategy 3: Nearest-neighbor matching (for misaligned Y positions)
        console.log(`  [TextReconstructor] Sequential matching poor (${(seqSuccessRate*100).toFixed(0)}%), trying nearest-neighbor...`);
        merged = this._mergeByNearestNeighbor(lineNumbers, content);
        
        const nnLinesWithContent = merged.filter(m => m.lineNumber && m.text && m.text.trim().length > 0);
        const nnSuccessRate = lineNumbers.length > 0 ? nnLinesWithContent.length / lineNumbers.length : 0;
        
        if (nnSuccessRate >= 0.5) {
            console.log(`  [TextReconstructor] Nearest-neighbor matching succeeded (${(nnSuccessRate*100).toFixed(0)}%)`);
            return merged;
        }
        
        // Strategy 4: Fallback - just use content directly without line number association
        console.log(`  [TextReconstructor] All position strategies failed, using direct content fallback`);
        return this._fallbackDirectContent(lineNumbers, content);
    }
    
    /**
     * Strategy 1: Position-based matching with adaptive tolerance
     */
    _mergeByPosition(lineNumbers, content) {
        const merged = [];
        
        // Calculate line height from line numbers if available
        let lineHeight = 30; // Default
        if (lineNumbers.length >= 2) {
            const yDiffs = [];
            for (let i = 1; i < Math.min(lineNumbers.length, 10); i++) {
                yDiffs.push(Math.abs(lineNumbers[i].position.y - lineNumbers[i-1].position.y));
            }
            if (yDiffs.length > 0) {
                lineHeight = yDiffs.reduce((a, b) => a + b, 0) / yDiffs.length;
            }
        }
        
        // Use WIDER tolerance - 80% of line height (was 60%)
        const tolerance = lineHeight * 0.8;
        
        // For each line number, find content that falls within its range
        const usedContent = new Set();
        
        for (const lineNum of lineNumbers) {
            const lineY = lineNum.position.y;
            // Expand range more generously - center tolerance around the line
            const rangeTop = lineY - tolerance;
            const rangeBottom = lineY + tolerance;
            
            // Find all content blocks within this line's Y range
            const matchedBlocks = [];
            for (let i = 0; i < content.length; i++) {
                if (usedContent.has(i)) continue;
                
                const block = content[i];
                // Use multiple Y reference points
                const blockY = block.position.y;
                const blockCenterY = blockY + (block.position.height || 0) / 2;
                const blockBottomY = blockY + (block.position.height || 0);
                
                // Match if ANY part of the block is within range
                if ((blockY >= rangeTop && blockY <= rangeBottom) ||
                    (blockCenterY >= rangeTop && blockCenterY <= rangeBottom) ||
                    (blockBottomY >= rangeTop && blockBottomY <= rangeBottom)) {
                    matchedBlocks.push({ block, index: i });
                }
            }
            
            // Sort matched blocks by X position (left to right)
            matchedBlocks.sort((a, b) => a.block.position.x - b.block.position.x);
            
            // Mark these blocks as used
            matchedBlocks.forEach(m => usedContent.add(m.index));
            
            // Combine text from matched blocks
            const text = matchedBlocks.map(m => m.block.text).join(' ');
            const confidence = matchedBlocks.length > 0 
                ? Math.min(lineNum.confidence || 100, ...matchedBlocks.map(m => m.block.confidence || 100))
                : (lineNum.confidence || 100);
            
            merged.push({
                lineNumber: lineNum.text,
                text: text.trim(),
                confidence,
            });
        }
        
        // Add any remaining unmatched content at the end
        for (let i = 0; i < content.length; i++) {
            if (!usedContent.has(i)) {
                merged.push({
                    text: content[i].text,
                    confidence: content[i].confidence || 100,
                });
            }
        }
        
        return merged;
    }
    
    /**
     * Strategy 2: Sequential matching - assumes line numbers and content appear in order
     */
    _mergeBySequence(lineNumbers, content) {
        const merged = [];
        
        // Sort both arrays by Y position
        const sortedLineNums = [...lineNumbers].sort((a, b) => a.position.y - b.position.y);
        const sortedContent = [...content].sort((a, b) => a.position.y - b.position.y);
        
        // Simple sequential assignment - each line number gets the next content item
        const usedContent = new Set();
        
        for (let i = 0; i < sortedLineNums.length; i++) {
            const lineNum = sortedLineNums[i];
            
            // Find the closest unused content item
            let bestMatch = null;
            let bestDistance = Infinity;
            let bestIndex = -1;
            
            for (let j = 0; j < sortedContent.length; j++) {
                if (usedContent.has(j)) continue;
                
                const dist = Math.abs(sortedContent[j].position.y - lineNum.position.y);
                if (dist < bestDistance) {
                    bestDistance = dist;
                    bestMatch = sortedContent[j];
                    bestIndex = j;
                }
            }
            
            if (bestMatch && bestIndex !== -1) {
                usedContent.add(bestIndex);
                merged.push({
                    lineNumber: lineNum.text,
                    text: bestMatch.text.trim(),
                    confidence: Math.min(lineNum.confidence || 100, bestMatch.confidence || 100),
                });
            } else {
                merged.push({
                    lineNumber: lineNum.text,
                    text: '',
                    confidence: lineNum.confidence || 100,
                });
            }
        }
        
        // Add remaining unmatched content
        for (let i = 0; i < sortedContent.length; i++) {
            if (!usedContent.has(i)) {
                merged.push({
                    text: sortedContent[i].text,
                    confidence: sortedContent[i].confidence || 100,
                });
            }
        }
        
        return merged;
    }
    
    /**
     * Strategy 3: Nearest-neighbor matching with greedy assignment
     */
    _mergeByNearestNeighbor(lineNumbers, content) {
        const merged = [];
        const usedContent = new Set();
        
        // Sort line numbers by Y
        const sortedLineNums = [...lineNumbers].sort((a, b) => a.position.y - b.position.y);
        
        for (const lineNum of sortedLineNums) {
            // Find ALL content items within a reasonable vertical range
            const lineY = lineNum.position.y;
            const candidates = [];
            
            for (let i = 0; i < content.length; i++) {
                if (usedContent.has(i)) continue;
                
                const contentY = content[i].position.y;
                const distance = Math.abs(contentY - lineY);
                
                // Accept anything within 50 units (generous)
                if (distance < 50) {
                    candidates.push({ index: i, content: content[i], distance });
                }
            }
            
            // Sort by distance, take the closest
            candidates.sort((a, b) => a.distance - b.distance);
            
            if (candidates.length > 0) {
                const best = candidates[0];
                usedContent.add(best.index);
                
                merged.push({
                    lineNumber: lineNum.text,
                    text: best.content.text.trim(),
                    confidence: Math.min(lineNum.confidence || 100, best.content.confidence || 100),
                });
            } else {
                merged.push({
                    lineNumber: lineNum.text,
                    text: '',
                    confidence: lineNum.confidence || 100,
                });
            }
        }
        
        // Add remaining content
        for (let i = 0; i < content.length; i++) {
            if (!usedContent.has(i)) {
                merged.push({
                    text: content[i].text,
                    confidence: content[i].confidence || 100,
                });
            }
        }
        
        return merged;
    }
    
    /**
     * Strategy 4: Fallback - assign synthetic line numbers to content
     */
    _fallbackDirectContent(lineNumbers, content) {
        const merged = [];
        
        // Sort content by Y position
        const sortedContent = [...content].sort((a, b) => a.position.y - b.position.y);
        
        // If we have line numbers, try to use their count as a guide
        const expectedLines = lineNumbers.length > 0 ? lineNumbers.length : sortedContent.length;
        
        for (let i = 0; i < sortedContent.length; i++) {
            const lineNumber = i < lineNumbers.length ? lineNumbers[i].text : String(i + 1);
            
            merged.push({
                lineNumber: lineNumber,
                text: sortedContent[i].text.trim(),
                confidence: sortedContent[i].confidence || 100,
            });
        }
        
        return merged;
    }
}
exports.TextReconstructor = TextReconstructor;
