'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft, Brain, Check, X, Clock, ChevronRight } from 'lucide-react'
import ProtectedRoute from '@/components/ProtectedRoute'
import { api } from '@/lib/api'

interface LearningFeedback {
  id: string
  user_name: string
  user_email: string
  question: string
  answer: string
  ai_summary: string
  user_summary: string
  notes?: string
  document_filename?: string
  page_citation?: string
  status: string
  created_at: string
}

export default function AdminFeedbackPage() {
  const router = useRouter()
  const [feedback, setFeedback] = useState<LearningFeedback[]>([])
  const [selectedFeedback, setSelectedFeedback] = useState<LearningFeedback | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('pending')

  useEffect(() => {
    fetchFeedback()
  }, [filter])

  const fetchFeedback = async () => {
    try {
      setLoading(true)
      const response = await api.get('/api/learning-feedback', {
        params: { status: filter }
      })
      setFeedback(response.data)
      if (response.data.length > 0 && !selectedFeedback) {
        setSelectedFeedback(response.data[0])
      }
    } catch (error) {
      console.error('Failed to fetch learning feedback:', error)
    } finally {
      setLoading(false)
    }
  }

  const updateStatus = async (feedbackId: string, newStatus: string) => {
    try {
      await api.patch(`/api/learning-feedback/${feedbackId}/status`, { status: newStatus }, {
        params: { status: newStatus }
      })
      await fetchFeedback()
      setSelectedFeedback(null)
    } catch (error) {
      console.error('Failed to update status:', error)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-400" />
      case 'reviewed':
        return <Check className="w-4 h-4 text-blue-400" />
      case 'applied':
        return <Check className="w-4 h-4 text-green-400" />
      case 'rejected':
        return <X className="w-4 h-4 text-red-400" />
      default:
        return null
    }
  }

  return (
    <ProtectedRoute requireAdmin>
      <div className="h-screen flex flex-col bg-bg-base">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 bg-bg-card border-b border-gray-800">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/admin')}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
            <div className="h-6 w-px bg-gray-700" />
            <div>
              <h1 className="text-xl font-semibold">Learning Feedback Review</h1>
              <p className="text-sm text-gray-400">Review user corrections to improve AI</p>
            </div>
          </div>

          {/* Filters */}
          <div className="flex gap-2">
            {['pending', 'reviewed', 'applied', 'rejected'].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 rounded-lg transition-colors capitalize text-sm ${
                  filter === f
                    ? 'bg-accent text-bg-base'
                    : 'bg-bg-elevated text-gray-400 hover:text-white'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Sidebar - Feedback List */}
          <div className="w-96 border-r border-gray-800 overflow-y-auto bg-bg-elevated">
            {loading ? (
              <div className="p-8 text-center text-gray-400">Loading...</div>
            ) : feedback.length === 0 ? (
              <div className="p-8 text-center text-gray-400">
                <Brain className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No feedback found</p>
              </div>
            ) : (
              <div className="p-4 space-y-2">
                {feedback.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setSelectedFeedback(item)}
                    className={`w-full text-left p-4 rounded-xl transition-all ${
                      selectedFeedback?.id === item.id
                        ? 'bg-accent/10 border-2 border-accent/50'
                        : 'bg-bg-card border border-gray-800 hover:border-accent/30'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(item.status)}
                        <span className="text-xs font-medium capitalize">{item.status}</span>
                      </div>
                      <ChevronRight className="w-4 h-4 text-gray-500" />
                    </div>
                    <p className="text-sm font-medium mb-1 line-clamp-2">
                      {item.question.substring(0, 80)}...
                    </p>
                    <p className="text-xs text-gray-500">
                      {item.user_name} • {new Date(item.created_at).toLocaleDateString()}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Right Panel - Feedback Detail */}
          <div className="flex-1 overflow-y-auto">
            {selectedFeedback ? (
              <div className="p-8 max-w-5xl mx-auto space-y-6">
                {/* User Info */}
                <div className="bg-bg-card border border-gray-800 rounded-xl p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-400">Submitted by</p>
                      <p className="font-medium">{selectedFeedback.user_name} ({selectedFeedback.user_email})</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-gray-400">Date</p>
                      <p className="text-sm">{new Date(selectedFeedback.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                  {selectedFeedback.page_citation && (
                    <p className="text-xs text-gray-500 mt-2">
                      Citation: {selectedFeedback.page_citation}
                    </p>
                  )}
                </div>

                {/* Q&A */}
                <div className="bg-bg-card border border-gray-800 rounded-xl p-6">
                  <h3 className="text-sm font-semibold text-gray-400 mb-3">Question & Answer</h3>
                  <div className="space-y-3">
                    <div>
                      <span className="text-xs text-gray-500">Q:</span>
                      <p className="text-sm text-gray-300 mt-1">{selectedFeedback.question}</p>
                    </div>
                    <div className="h-px bg-gray-800" />
                    <div>
                      <span className="text-xs text-gray-500">A:</span>
                      <p className="text-sm text-gray-300 mt-1">{selectedFeedback.answer}</p>
                    </div>
                  </div>
                </div>

                {/* Side by Side Comparison */}
                <div className="grid grid-cols-2 gap-6">
                  {/* AI Summary */}
                  <div className="bg-bg-card border border-gray-800 rounded-xl p-6">
                    <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                      <span className="text-red-400">AI Generated Summary</span>
                    </h3>
                    <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">
                      {selectedFeedback.ai_summary}
                    </p>
                  </div>

                  {/* User Correction */}
                  <div className="bg-accent/10 border border-accent/30 rounded-xl p-6">
                    <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                      <span className="text-green-400">User Corrected Summary</span>
                    </h3>
                    <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">
                      {selectedFeedback.user_summary}
                    </p>
                  </div>
                </div>

                {/* Notes */}
                {selectedFeedback.notes && (
                  <div className="bg-bg-card border border-gray-800 rounded-xl p-6">
                    <h3 className="text-sm font-semibold text-gray-400 mb-3">User Notes</h3>
                    <p className="text-sm text-gray-300 whitespace-pre-wrap">{selectedFeedback.notes}</p>
                  </div>
                )}

                {/* Actions */}
                {selectedFeedback.status === 'pending' && (
                  <div className="flex gap-4">
                    <button
                      onClick={() => updateStatus(selectedFeedback.id, 'applied')}
                      className="flex-1 px-6 py-3 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-xl transition-all flex items-center justify-center gap-2"
                    >
                      <Check className="w-5 h-5" />
                      <span>Mark as Applied</span>
                    </button>
                    <button
                      onClick={() => updateStatus(selectedFeedback.id, 'reviewed')}
                      className="flex-1 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl transition-all flex items-center justify-center gap-2"
                    >
                      <Check className="w-5 h-5" />
                      <span>Mark as Reviewed</span>
                    </button>
                    <button
                      onClick={() => updateStatus(selectedFeedback.id, 'rejected')}
                      className="flex-1 px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-xl transition-all flex items-center justify-center gap-2"
                    >
                      <X className="w-5 h-5" />
                      <span>Reject</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">
                <div className="text-center">
                  <Brain className="w-16 h-16 mx-auto mb-4 opacity-30" />
                  <p>Select feedback to review</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </ProtectedRoute>
  )
}

