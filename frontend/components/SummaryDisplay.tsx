'use client'

import { useState } from 'react'
import { ChevronUp, ChevronDown, MessageSquare, Brain } from 'lucide-react'
import LearningFeedbackModal from './LearningFeedbackModal'

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
    return `${page_number}:${line_number}-${end_line}`
  } else {
    // Cross-page
    return `${page_number}:${line_number}-${end_page}:${end_line}`
  }
}

/**
 * Summary display component for reading mode.
 * Shows ONLY the summary with citation - no Q&A display.
 */
export default function SummaryDisplay({
  item,
  currentIndex,
  totalItems,
  onPrevious,
  onNext
}: SummaryDisplayProps) {
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false)

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
          {item.topic || 'Other'}
        </div>
      </div>

      {/* Summary Content Area - Full Width */}
      <div className="flex-1 overflow-auto p-6 flex flex-col">
        {/* Summary Text - Takes up most of the space */}
        <div className="flex-1">
          {item.summary ? (
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-4">
                <p className="text-gray-100 text-xl leading-relaxed flex-1">
                  {item.summary}
                </p>
                {/* Brain Icon Button */}
                <button
                  onClick={() => setFeedbackModalOpen(true)}
                  className="flex-shrink-0 p-2 rounded-lg bg-purple-500/10 border border-purple-500/30 hover:bg-purple-500/20 transition-colors group"
                  title="Provide learning feedback"
                >
                  <Brain className="w-5 h-5 text-purple-400 group-hover:scale-110 transition-transform" />
                </button>
              </div>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center">
              <div className="text-center text-gray-500">
                <MessageSquare className="w-16 h-16 mx-auto mb-4 opacity-30" />
                <p className="text-lg">Summary not available</p>
                <p className="text-sm mt-2 text-gray-600">
                  This Q&A pair was not summarized by AI.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Citation at Bottom - Full Width */}
        <div className="mt-6 pt-4 border-t border-gray-800">
          <div className="font-mono text-sm text-accent bg-accent/10 px-4 py-2 rounded-lg text-center">
            {citation}
          </div>
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

      {/* Learning Feedback Modal */}
      <LearningFeedbackModal
        isOpen={feedbackModalOpen}
        onClose={() => setFeedbackModalOpen(false)}
        qaData={{
          question: item.question,
          answer: item.answer,
          aiSummary: item.summary || '',
          pageCitation: citation
        }}
      />
    </div>
  )
}
