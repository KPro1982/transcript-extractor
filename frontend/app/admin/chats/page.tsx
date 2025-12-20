'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft, MessageSquare, AlertCircle, CheckCircle, Clock, X } from 'lucide-react'
import ProtectedRoute from '@/components/ProtectedRoute'
import { api } from '@/lib/api'

interface BugReport {
  id: string
  user_name: string
  user_email: string
  title: string
  type: string
  status: string
  created_at: string
  updated_at: string
  unread_count: number
  last_message?: string
}

export default function AdminChatsPage() {
  const router = useRouter()
  const [reports, setReports] = useState<BugReport[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')

  const fetchReports = useCallback(async () => {
    try {
      setLoading(true)
      const statusFilter = filter === 'all' ? undefined : filter
      const response = await api.get('/api/bug-reports', {
        params: statusFilter ? { status: statusFilter } : {}
      })
      setReports(response.data)
    } catch (error) {
      console.error('Failed to fetch bug reports:', error)
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    fetchReports()
  }, [filter, fetchReports])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'open':
        return <AlertCircle className="w-4 h-4 text-yellow-400" />
      case 'in_progress':
        return <Clock className="w-4 h-4 text-blue-400" />
      case 'resolved':
        return <CheckCircle className="w-4 h-4 text-green-400" />
      case 'closed':
        return <X className="w-4 h-4 text-gray-400" />
      default:
        return <MessageSquare className="w-4 h-4" />
    }
  }

  const getTypeColor = (type: string) => {
    return type === 'bug' ? 'text-red-400' : 'text-blue-400'
  }

  return (
    <ProtectedRoute requireAdmin>
      <div className="min-h-screen bg-bg-base p-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-8 flex items-center justify-between">
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
                <h1 className="text-3xl font-serif">Bug Reports & Chats</h1>
                <p className="text-gray-400 text-sm">View and respond to user feedback</p>
              </div>
            </div>
          </div>

          {/* Filters */}
          <div className="mb-6 flex gap-2">
            {['all', 'open', 'in_progress', 'resolved', 'closed'].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 rounded-lg transition-colors capitalize ${
                  filter === f
                    ? 'bg-accent text-bg-base'
                    : 'bg-bg-card text-gray-400 hover:text-white'
                }`}
              >
                {f.replace('_', ' ')}
              </button>
            ))}
          </div>

          {/* Reports List */}
          {loading ? (
            <div className="text-center py-12 text-gray-400">Loading...</div>
          ) : reports.length === 0 ? (
            <div className="bg-bg-card border border-gray-800 rounded-xl p-12 text-center">
              <MessageSquare className="w-16 h-16 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No bug reports found</p>
            </div>
          ) : (
            <div className="space-y-4">
              {reports.map((report) => (
                <button
                  key={report.id}
                  onClick={() => router.push(`/admin/chats/${report.id}`)}
                  className="w-full bg-bg-card border border-gray-800 rounded-xl p-6 hover:border-accent/50 transition-all text-left"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        {getStatusIcon(report.status)}
                        <h3 className="text-lg font-semibold">{report.title}</h3>
                        <span className={`text-xs px-2 py-1 rounded-full ${getTypeColor(report.type)}`}>
                          {report.type}
                        </span>
                        {report.unread_count > 0 && (
                          <span className="bg-accent text-bg-base text-xs px-2 py-1 rounded-full font-semibold">
                            {report.unread_count} new
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-400 mb-2">
                        From: {report.user_name} ({report.user_email})
                      </p>
                      {report.last_message && (
                        <p className="text-sm text-gray-500 truncate">{report.last_message}</p>
                      )}
                    </div>
                    <div className="text-right text-sm text-gray-500">
                      <p>{new Date(report.updated_at).toLocaleDateString()}</p>
                      <p className="text-xs">{new Date(report.updated_at).toLocaleTimeString()}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </ProtectedRoute>
  )
}

