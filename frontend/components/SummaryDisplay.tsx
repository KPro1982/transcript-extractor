'use client'

import { useState } from 'react'
import { ChevronUp, ChevronDown, MessageSquare, Brain, Edit2, Save, X } from 'lucide-react'
import LearningFeedbackModal from './LearningFeedbackModal'
import { api } from '@/lib/api'

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
  event_date?: string
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
  const [isEditing, setIsEditing] = useState(false)
  const [editedSummary, setEditedSummary] = useState('')
  const [editedDate, setEditedDate] = useState('')
  const [saving, setSaving] = useState(false)

  const handleStartEdit = () => {
    setEditedSummary(item?.summary || '')
    setEditedDate(item?.event_date || '')
    setIsEditing(true)
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    setEditedSummary('')
    setEditedDate('')
  }

  const handleSave = async () => {
    if (!item) return
    
    try {
      setSaving(true)
      await api.patch(`/api/documents/qa-items/${item.id}`, {
        summary: editedSummary,
        event_date: editedDate || null
      })
      
      // Update local state
      item.summary = editedSummary
      item.event_date = editedDate
      
      setIsEditing(false)
    } catch (error) {
      console.error('Failed to save summary:', error)
      alert('Failed to save changes. Please try again.')
    } finally {
      setSaving(false)
    }
  }

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
          {item.summary || isEditing ? (
            <div className="space-y-4">
              {isEditing ? (
                // Edit Mode
                <div className="space-y-4">
                  {/* Editable Summary */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-300 mb-2">
                      Summary
                    </label>
                    <textarea
                      value={editedSummary}
                      onChange={(e) => setEditedSummary(e.target.value)}
                      className="w-full min-h-[200px] px-4 py-3 bg-bg-elevated border border-gray-700 rounded-xl text-gray-100 text-lg leading-relaxed focus:outline-none focus:border-accent/50 focus:ring-2 focus:ring-accent/20 resize-y"
                      placeholder="Enter summary..."
                    />
                  </div>

                  {/* Editable Event Date */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-300 mb-2">
                      Event Date (Optional)
                      <span className="ml-2 text-xs text-gray-500 font-normal">
                        Format: yyyy-mm-dd, yyyy-mm, yyyy, or flexible like &quot;2020 mid-year&quot;
                      </span>
                    </label>
                    <input
                      type="text"
                      value={editedDate}
                      onChange={(e) => setEditedDate(e.target.value)}
                      className="w-full px-4 py-2 bg-bg-elevated border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:border-accent/50 focus:ring-2 focus:ring-accent/20"
                      placeholder="e.g., 2020-04, 2020, 2020 mid-year"
                    />
                  </div>

                  {/* Edit Actions */}
                  <div className="flex gap-3 pt-2">
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent/80 text-black font-semibold rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Save className="w-4 h-4" />
                      {saving ? 'Saving...' : 'Save Changes'}
                    </button>
                    <button
                      onClick={handleCancelEdit}
                      disabled={saving}
                      className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-100 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <X className="w-4 h-4" />
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                // View Mode
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-4">
                    <p className="text-gray-100 text-xl leading-relaxed flex-1">
                      {item.summary}
                    </p>
                    <div className="flex gap-2">
                      {/* Edit Button */}
                      <button
                        onClick={handleStartEdit}
                        className="flex-shrink-0 p-2 rounded-lg bg-blue-500/10 border border-blue-500/30 hover:bg-blue-500/20 transition-colors group"
                        title="Edit summary and date"
                      >
                        <Edit2 className="w-5 h-5 text-blue-400 group-hover:scale-110 transition-transform" />
                      </button>
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
                  
                  {/* Display Event Date if present */}
                  {item.event_date && (
                    <div className="flex items-center gap-2 text-sm text-gray-400">
                      <span className="font-semibold">Event Date:</span>
                      <span className="px-2 py-1 bg-blue-500/10 border border-blue-500/30 rounded text-blue-400">
                        {item.event_date}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex items-center justify-center">
              <div className="text-center text-gray-500">
                <MessageSquare className="w-16 h-16 mx-auto mb-4 opacity-30" />
                <p className="text-lg">Summary not available</p>
                <p className="text-sm mt-2 text-gray-600">
                  This Q&A pair was not summarized by AI.
                </p>
                <button
                  onClick={handleStartEdit}
                  className="mt-4 flex items-center gap-2 mx-auto px-4 py-2 bg-accent/20 hover:bg-accent/30 text-accent rounded-lg transition-colors"
                >
                  <Edit2 className="w-4 h-4" />
                  Add Summary
                </button>
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
