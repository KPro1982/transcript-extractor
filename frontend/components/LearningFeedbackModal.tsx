'use client'

import { useState } from 'react'
import { X, Send, Loader2, BrainCircuit } from 'lucide-react'
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
              <BrainCircuit className="w-5 h-5 text-purple-400" />
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
                <BrainCircuit className="w-8 h-8 text-green-400" />
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

