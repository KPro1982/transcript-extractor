'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { ArrowLeft, Send, Loader2, Image as ImageIcon } from 'lucide-react'
import ProtectedRoute from '@/components/ProtectedRoute'
import { api } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'

interface ChatMessage {
  id: string
  sender_name: string
  sender_picture?: string
  message: string
  screenshot_url?: string
  is_admin_message: boolean
  created_at: string
}

interface BugReportDetail {
  id: string
  user_name: string
  user_email: string
  title: string
  type: string
  status: string
  messages: ChatMessage[]
}

export default function BugReportChatPage() {
  const router = useRouter()
  const params = useParams()
  const { user } = useAuth()
  const reportId = params?.reportId as string

  const [report, setReport] = useState<BugReportDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [status, setStatus] = useState('')

  useEffect(() => {
    if (reportId) {
      fetchReport()
    }
  }, [reportId])

  const fetchReport = async () => {
    try {
      const response = await api.get(`/api/bug-reports/${reportId}`)
      setReport(response.data)
      setStatus(response.data.status)
    } catch (error) {
      console.error('Failed to fetch bug report:', error)
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = async () => {
    if (!message.trim() || sending) return

    try {
      setSending(true)
      await api.post(`/api/bug-reports/${reportId}/messages`, {
        bug_report_id: reportId,
        message: message.trim()
      })
      setMessage('')
      await fetchReport()
    } catch (error) {
      console.error('Failed to send message:', error)
    } finally {
      setSending(false)
    }
  }

  const updateStatus = async (newStatus: string) => {
    try {
      await api.patch(`/api/bug-reports/${reportId}/status`, { status: newStatus }, {
        params: { status: newStatus }
      })
      setStatus(newStatus)
      await fetchReport()
    } catch (error) {
      console.error('Failed to update status:', error)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg-base">
        <Loader2 className="w-12 h-12 text-accent animate-spin" />
      </div>
    )
  }

  if (!report) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg-base">
        <p className="text-gray-400">Bug report not found</p>
      </div>
    )
  }

  return (
    <ProtectedRoute requireAdmin>
      <div className="h-screen flex flex-col bg-bg-base">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 bg-bg-card border-b border-gray-800">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/admin/chats')}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
            <div className="h-6 w-px bg-gray-700" />
            <div>
              <h1 className="text-xl font-semibold">{report.title}</h1>
              <p className="text-sm text-gray-400">
                {report.user_name} ({report.user_email})
              </p>
            </div>
          </div>

          {/* Status Selector */}
          {user?.is_admin && (
            <select
              value={status}
              onChange={(e) => updateStatus(e.target.value)}
              className="px-4 py-2 bg-bg-elevated border border-gray-700 rounded-lg text-sm"
            >
              <option value="open">Open</option>
              <option value="in_progress">In Progress</option>
              <option value="resolved">Resolved</option>
              <option value="closed">Closed</option>
            </select>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {report.messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.is_admin_message ? 'flex-row-reverse' : ''}`}
            >
              {/* Avatar */}
              {msg.sender_picture ? (
                <img
                  src={msg.sender_picture}
                  alt={msg.sender_name}
                  className="w-8 h-8 rounded-full flex-shrink-0"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0">
                  <span className="text-xs text-accent">{msg.sender_name[0]}</span>
                </div>
              )}

              {/* Message Content */}
              <div className={`flex-1 max-w-2xl ${msg.is_admin_message ? 'items-end' : ''}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium">{msg.sender_name}</span>
                  <span className="text-xs text-gray-500">
                    {new Date(msg.created_at).toLocaleString()}
                  </span>
                </div>
                <div
                  className={`p-4 rounded-xl ${
                    msg.is_admin_message
                      ? 'bg-accent/10 border border-accent/30'
                      : 'bg-bg-card border border-gray-800'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{msg.message}</p>
                  {msg.screenshot_url && (
                    <img
                      src={msg.screenshot_url}
                      alt="Screenshot"
                      className="mt-3 rounded-lg max-w-full"
                    />
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Input */}
        <div className="p-6 bg-bg-card border-t border-gray-800">
          <div className="flex gap-4">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendMessage()
                }
              }}
              placeholder="Type your message..."
              className="flex-1 px-4 py-3 bg-bg-elevated border border-gray-700 rounded-xl resize-none focus:outline-none focus:border-accent"
              rows={3}
            />
            <button
              onClick={sendMessage}
              disabled={!message.trim() || sending}
              className="px-6 py-3 bg-accent hover:bg-accent-hover disabled:bg-gray-700 text-bg-base font-semibold rounded-xl transition-all flex items-center gap-2"
            >
              {sending ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  <Send className="w-5 h-5" />
                  <span>Send</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  )
}

