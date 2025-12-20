'use client'

import { useState } from 'react'
import { X, Send, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'

interface LearningFeedbackModalProps {
  isOpen: boolean
  onClose: () => void
  qaData: {
    question: string
    answer: string
    aiSummary: string
    documentFilename?: string
    pageCitation?: string
  }
}

export default function LearningFeedbackModal({
  isOpen,
  onClose,
  qaData
}: LearningFeedbackModalProps) {
  const [userSummary, setUserSummary] = useState(qaData.aiSummary)
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)

  if (!isOpen) return null

  const handleSubmit = async () => {
    if (!userSummary.trim() || submitting) return

    try {
      setSubmitting(true)
      await api.post('/api/learning-feedback', {
        question: qaData.question,
        answer: qaData.answer,
        ai_summary: qaData.aiSummary,
        user_summary: userSummary.trim(),
        notes: notes.trim() || null,
        document_filename: qaData.documentFilename,
        page_citation: qaData.pageCitation
      })

      setSuccess(true)
      setTimeout(() => {
        onClose()
        setSuccess(false)
        setUserSummary(qaData.aiSummary)
        setNotes('')
      }, 2000)
    } catch (error) {
      console.error('Failed to submit feedback:', error)
      alert('Failed to submit feedback. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70"
        onClick={() => !submitting && onClose()}
      />

      {/* Modal */}
      <div className="relative bg-bg-card border border-gray-800 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center">
              <svg
                className="w-5 h-5 text-purple-400"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 2C9.5 2 7 3.5 6 6C5.5 7 5 8.5 5 10C5 12 5.5 14 7 15.5C8 16.5 9 17 10 17.5C10.5 17.7 11 18 11 18.5V20C11 21 12 22 13 22C14 22 15 21 15 20V18.5C15 18 15.5 17.7 16 17.5C17 17 18 16.5 19 15.5C20.5 14 21 12 21 10C21 8.5 20.5 7 20 6C19 3.5 16.5 2 14 2" />
                <path d="M9 8H11" opacity="0.6" />
                <path d="M13 8H15" opacity="0.6" />
                <path d="M10 11H14" opacity="0.6" />
                <path d="M9 14H15" opacity="0.6" />
                <circle cx="9.5" cy="8" r="0.5" fill="currentColor" />
                <circle cx="14.5" cy="8" r="0.5" fill="currentColor" />
                <circle cx="12" cy="11" r="0.5" fill="currentColor" />
              </svg>
            </div>
            <div>
              <h2 className="text-xl font-semibold">Learning Feedback</h2>
              <p className="text-sm text-gray-400">Help improve AI summaries</p>
            </div>
          </div>
          <button
            onClick={() => !submitting && onClose()}
            className="p-2 hover:bg-bg-elevated rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        {success ? (
          <div className="flex-1 flex items-center justify-center p-12">
            <div className="text-center">
              <div className="w-16 h-16 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg
                  className="w-8 h-8 text-green-400"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 2C9.5 2 7 3.5 6 6C5.5 7 5 8.5 5 10C5 12 5.5 14 7 15.5C8 16.5 9 17 10 17.5C10.5 17.7 11 18 11 18.5V20C11 21 12 22 13 22C14 22 15 21 15 20V18.5C15 18 15.5 17.7 16 17.5C17 17 18 16.5 19 15.5C20.5 14 21 12 21 10C21 8.5 20.5 7 20 6C19 3.5 16.5 2 14 2" />
                  <path d="M9 8H11" opacity="0.6" />
                  <path d="M13 8H15" opacity="0.6" />
                  <path d="M10 11H14" opacity="0.6" />
                  <path d="M9 14H15" opacity="0.6" />
                  <circle cx="9.5" cy="8" r="0.5" fill="currentColor" />
                  <circle cx="14.5" cy="8" r="0.5" fill="currentColor" />
                  <circle cx="12" cy="11" r="0.5" fill="currentColor" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Thank you!</h3>
              <p className="text-gray-400">
                Your feedback will help us improve our AI summaries.
              </p>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Q&A Display (Read-only) */}
            <div className="bg-bg-elevated rounded-xl p-4 border border-gray-800">
              <h3 className="text-sm font-semibold text-gray-400 mb-2">Question & Answer</h3>
              <div className="space-y-2">
                <div>
                  <span className="text-xs text-gray-500">Q:</span>
                  <p className="text-sm text-gray-300 mt-1">{qaData.question}</p>
                </div>
                <div className="h-px bg-gray-800 my-2" />
                <div>
                  <span className="text-xs text-gray-500">A:</span>
                  <p className="text-sm text-gray-300 mt-1">{qaData.answer}</p>
                </div>
              </div>
            </div>

            {/* AI Summary (Read-only) */}
            <div>
              <label className="block text-sm font-semibold mb-2">
                AI Generated Summary
              </label>
              <div className="bg-bg-elevated rounded-xl p-4 border border-gray-800">
                <p className="text-sm text-gray-300 whitespace-pre-wrap">{qaData.aiSummary}</p>
              </div>
            </div>

            {/* User Corrected Summary (Editable) */}
            <div>
              <label className="block text-sm font-semibold mb-2">
                Your Corrected Summary <span className="text-red-400">*</span>
              </label>
              <textarea
                value={userSummary}
                onChange={(e) => setUserSummary(e.target.value)}
                placeholder="Edit the summary to show how it should be..."
                className="w-full px-4 py-3 bg-bg-elevated border border-gray-700 rounded-xl resize-none focus:outline-none focus:border-accent"
                rows={6}
              />
              <p className="text-xs text-gray-500 mt-1">
                Edit the AI summary above to show us how it should have been written.
              </p>
            </div>

            {/* Notes */}
            <div>
              <label className="block text-sm font-semibold mb-2">
                Notes (Optional)
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Explain what was wrong with the AI summary or provide additional context..."
                className="w-full px-4 py-3 bg-bg-elevated border border-gray-700 rounded-xl resize-none focus:outline-none focus:border-accent"
                rows={4}
              />
            </div>
          </div>
        )}

        {/* Footer */}
        {!success && (
          <div className="px-6 py-4 border-t border-gray-800 flex justify-end gap-3">
            <button
              onClick={() => !submitting && onClose()}
              className="px-6 py-3 bg-bg-elevated hover:bg-gray-800 text-gray-300 font-semibold rounded-xl transition-all"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={!userSummary.trim() || submitting}
              className="px-6 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 text-white font-semibold rounded-xl transition-all flex items-center gap-2"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Submitting...</span>
                </>
              ) : (
                <>
                  <Send className="w-5 h-5" />
                  <span>Submit Feedback</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

