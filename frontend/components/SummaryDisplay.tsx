'use client'

import { ChevronUp, ChevronDown, MessageSquare } from 'lucide-react'

interface QAItem {
  id: string
  page_number: number
  line_number: number
  end_page: number
  end_line: number
  question: string
  answer: string
  summary: string
  topic: string
}

interface SummaryDisplayProps {
  item: QAItem | null
  currentIndex: number
  totalItems: number
  onPrevious: () => void
  onNext: () => void
}

/**
 * Format citation based on page and line ranges.
 * Same page: [page:startLine-endLine] → [5:12-19]
 * Cross-page: [startPage:startLine-endPage:endLine] → [5:19-6:4]
 */
function formatCitation(item: QAItem): string {
  const { page_number, line_number, end_page, end_line } = item
  
  if (page_number === end_page) {
    // Same page
    return `[${page_number}:${line_number}-${end_line}]`
  } else {
    // Cross-page
    return `[${page_number}:${line_number}-${end_page}:${end_line}]`
  }
}

/**
 * Summary display component for reading mode.
 * Shows the current Q&A summary with citation and navigation controls.
 */
export default function SummaryDisplay({
  item,
  currentIndex,
  totalItems,
  onPrevious,
  onNext
}: SummaryDisplayProps) {
  if (!item) {
    return (
      <div className="flex flex-col h-full bg-bg-card rounded-xl overflow-hidden">
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center text-gray-500">
            <MessageSquare className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No Q&A items available</p>
          </div>
        </div>
      </div>
    )
  }

  const citation = formatCitation(item)
  const isFirstItem = currentIndex === 0
  const isLastItem = currentIndex === totalItems - 1

  return (
    <div className="flex flex-col h-full bg-bg-card rounded-xl overflow-hidden">
      {/* Navigation Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-bg-elevated border-b border-gray-800">
        <div className="flex items-center gap-4">
          <button
            onClick={onPrevious}
            disabled={isFirstItem}
            className="p-2 rounded-lg hover:bg-bg-card disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Previous (↑)"
          >
            <ChevronUp className="w-5 h-5" />
          </button>
          <button
            onClick={onNext}
            disabled={isLastItem}
            className="p-2 rounded-lg hover:bg-bg-card disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Next (↓)"
          >
            <ChevronDown className="w-5 h-5" />
          </button>
        </div>
        
        <div className="text-sm font-mono text-gray-400">
          <span className="text-white font-semibold">{currentIndex + 1}</span> of {totalItems}
        </div>
        
        {/* Topic Badge */}
        <div className="px-3 py-1 bg-accent/10 border border-accent/30 rounded-full text-xs text-accent font-medium">
          {item.topic || 'Uncategorized'}
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-auto p-6">
        {/* Question */}
        <div className="mb-6">
          <div className="flex items-start gap-3">
            <span className="text-accent font-bold text-lg flex-shrink-0">Q:</span>
            <p className="text-gray-200 text-lg leading-relaxed">{item.question}</p>
          </div>
        </div>

        {/* Answer */}
        <div className="mb-8">
          <div className="flex items-start gap-3">
            <span className="text-gray-400 font-bold text-lg flex-shrink-0">A:</span>
            <p className="text-gray-400 leading-relaxed">{item.answer}</p>
          </div>
        </div>

        {/* Summary Card */}
        <div className="bg-gradient-to-br from-accent/5 to-accent/10 border border-accent/20 rounded-xl p-6">
          {/* Citation Badge at Top */}
          <div className="flex justify-between items-center mb-4">
            <div className="text-xs text-accent font-semibold uppercase tracking-wider">
              AI Summary
            </div>
            <span className="font-mono text-xs text-accent/80 bg-accent/10 px-3 py-1.5 rounded-lg border border-accent/20">
              {citation}
            </span>
          </div>
          
          {item.summary ? (
            <p className="text-gray-100 text-lg leading-relaxed">
              {item.summary}
            </p>
          ) : (
            <p className="text-gray-400 text-sm italic">
              No summary available for this Q&A pair.
            </p>
          )}
        </div>
      </div>

      {/* Keyboard Hints Footer */}
      <div className="px-6 py-3 bg-bg-elevated border-t border-gray-800">
        <div className="flex items-center justify-center gap-6 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 bg-bg-card border border-gray-700 rounded text-gray-400">↑</kbd>
            <span>Previous</span>
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 bg-bg-card border border-gray-700 rounded text-gray-400">↓</kbd>
            <span>Next</span>
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 bg-bg-card border border-gray-700 rounded text-gray-400">Home</kbd>
            <span>First</span>
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 bg-bg-card border border-gray-700 rounded text-gray-400">End</kbd>
            <span>Last</span>
          </span>
        </div>
      </div>
    </div>
  )
}

