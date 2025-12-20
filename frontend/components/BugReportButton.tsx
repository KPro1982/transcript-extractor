'use client'

import { useState } from 'react'
import { MessageSquare, X, Send, Loader2, Image as ImageIcon } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { api } from '@/lib/api'

export default function BugReportButton() {
  const { user } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [message, setMessage] = useState('')
  const [type, setType] = useState<'bug' | 'feature'>('bug')
  const [sending, setSending] = useState(false)
  const [success, setSuccess] = useState(false)

  if (!user) return null

  const handleSubmit = async () => {
    if (!title.trim() || !message.trim() || sending) return

    try {
      setSending(true)
      await api.post('/api/bug-reports', {
        title: title.trim(),
        message: message.trim(),
        type
      })
      
      setSuccess(true)
      setTimeout(() => {
        setIsOpen(false)
        setTitle('')
        setMessage('')
        setType('bug')
        setSuccess(false)
      }, 2000)
    } catch (error) {
      console.error('Failed to submit bug report:', error)
      alert('Failed to submit bug report. Please try again.')
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      {/* Floating Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 w-14 h-14 bg-accent hover:bg-accent-hover text-bg-base rounded-full shadow-lg flex items-center justify-center transition-all z-50 hover:scale-110"
          title="Report Bug or Request Feature"
        >
          <MessageSquare className="w-6 h-6" />
        </button>
      )}

      {/* Modal */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-end justify-end p-6">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => !sending && setIsOpen(false)}
          />

          {/* Modal Content */}
          <div className="relative bg-bg-card border border-gray-800 rounded-2xl shadow-2xl w-full max-w-md">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <h2 className="text-xl font-semibold">Report Issue</h2>
              <button
                onClick={() => !sending && setIsOpen(false)}
                className="p-2 hover:bg-bg-elevated rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Form */}
            {success ? (
              <div className="px-6 py-12 text-center">
                <div className="w-16 h-16 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
                  <MessageSquare className="w-8 h-8 text-green-400" />
                </div>
                <h3 className="text-lg font-semibold mb-2">Thank you!</h3>
                <p className="text-gray-400 text-sm">
                  Your report has been submitted. We'll get back to you soon.
                </p>
              </div>
            ) : (
              <div className="px-6 py-4 space-y-4">
                {/* Type Selector */}
                <div className="flex gap-2">
                  <button
                    onClick={() => setType('bug')}
                    className={`flex-1 px-4 py-2 rounded-lg transition-colors ${
                      type === 'bug'
                        ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                        : 'bg-bg-elevated text-gray-400 hover:text-white'
                    }`}
                  >
                    Bug Report
                  </button>
                  <button
                    onClick={() => setType('feature')}
                    className={`flex-1 px-4 py-2 rounded-lg transition-colors ${
                      type === 'feature'
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        : 'bg-bg-elevated text-gray-400 hover:text-white'
                    }`}
                  >
                    Feature Request
                  </button>
                </div>

                {/* Title */}
                <div>
                  <label className="block text-sm font-medium mb-2">Title</label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Brief description of the issue"
                    className="w-full px-4 py-2 bg-bg-elevated border border-gray-700 rounded-lg focus:outline-none focus:border-accent"
                    maxLength={100}
                  />
                </div>

                {/* Message */}
                <div>
                  <label className="block text-sm font-medium mb-2">Description</label>
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Provide details about the issue or feature request..."
                    className="w-full px-4 py-2 bg-bg-elevated border border-gray-700 rounded-lg resize-none focus:outline-none focus:border-accent"
                    rows={5}
                  />
                </div>

                {/* Submit Button */}
                <button
                  onClick={handleSubmit}
                  disabled={!title.trim() || !message.trim() || sending}
                  className="w-full px-6 py-3 bg-accent hover:bg-accent-hover disabled:bg-gray-700 text-bg-base font-semibold rounded-xl transition-all flex items-center justify-center gap-2"
                >
                  {sending ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Submitting...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-5 h-5" />
                      <span>Submit Report</span>
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}

