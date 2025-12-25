'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useParams } from 'next/navigation'
import { Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react'
import { useJobProgress } from '@/hooks/useWebSocket'
import { useIsAdmin } from '@/hooks/useIsAdmin'
import { api } from '@/lib/api'
import CompletionModal from '@/components/CompletionModal'

export default function ProcessPage() {
  const router = useRouter()
  const params = useParams()
  const jobId = params?.jobId as string
  const isAdmin = useIsAdmin()

  const { progress, isConnected, error } = useJobProgress(jobId)
  const [avgTimePerPage, setAvgTimePerPage] = useState(1.5) // Default 1.5s per page
  const [estimatedCompletion, setEstimatedCompletion] = useState<string | null>(null)
  const [countdown, setCountdown] = useState<string>('')
  const [showCompletionModal, setShowCompletionModal] = useState(false)
  const [documentId, setDocumentId] = useState<string | null>(null)

  // Fetch average processing time on mount
  useEffect(() => {
    const fetchAvgTime = async () => {
      try {
        const response = await api.get('/api/jobs/metrics/avg-time')
        setAvgTimePerPage(response.data.avg_time_per_page_seconds || 1.5)
      } catch (error) {
        console.error('Failed to fetch avg time:', error)
      }
    }
    fetchAvgTime()
  }, [])

  // Calculate estimated completion time and countdown
  useEffect(() => {
    if (progress.detailedProgress && avgTimePerPage > 0) {
      const { current, total } = progress.detailedProgress
      const remaining = total - current
      const estimatedSeconds = remaining * avgTimePerPage
      
      if (estimatedSeconds > 0 && remaining > 0) {
        const completionTime = new Date(Date.now() + estimatedSeconds * 1000)
        setEstimatedCompletion(completionTime.toLocaleTimeString())
      } else {
        setEstimatedCompletion(null)
      }
    }
  }, [progress.detailedProgress, avgTimePerPage])

  // Update countdown every second - count down continuously
  useEffect(() => {
    if (!progress.detailedProgress || progress.status === 'completed') {
      setCountdown('')
      return
    }

    // Store the initial calculation and start time
    let initialRemaining = 0
    let startTime = Date.now()
    
    const calculateInitial = () => {
      const { current, total } = progress.detailedProgress!
      const remaining = total - current
      initialRemaining = remaining * avgTimePerPage
      startTime = Date.now()
    }
    
    calculateInitial()

    const updateCountdown = () => {
      // Calculate elapsed time since start
      const elapsedSeconds = (Date.now() - startTime) / 1000
      
      // Subtract elapsed time from initial estimate
      const estimatedSeconds = Math.max(0, initialRemaining - elapsedSeconds)
      
      if (estimatedSeconds > 0) {
        const minutes = Math.floor(estimatedSeconds / 60)
        const seconds = Math.floor(estimatedSeconds % 60)
        setCountdown(`${minutes}:${seconds.toString().padStart(2, '0')}`)
      } else {
        setCountdown('0:00')
      }
    }

    updateCountdown()
    // Update every 100ms for smooth countdown
    const interval = setInterval(updateCountdown, 100)
    
    return () => clearInterval(interval)
  }, [progress.detailedProgress, avgTimePerPage, progress.status])

  useEffect(() => {
    // Show modal when complete instead of auto-redirecting
    if (progress.status === 'completed') {
      // Extract document_id from progress result if available
      const docId = (progress as any).document_id || (progress as any).result?.document_id
      if (docId) {
        setDocumentId(docId)
      }
      setShowCompletionModal(true)
    }
  }, [progress.status])

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="max-w-2xl w-full">
        <div className="bg-bg-card border border-gray-800 rounded-2xl p-12">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-accent/20 to-accent/10 rounded-2xl mb-6">
              {progress.status === 'completed' ? (
                <CheckCircle2 className="w-10 h-10 text-accent" />
              ) : progress.status === 'failed' ? (
                <XCircle className="w-10 h-10 text-red-500" />
              ) : (
                <Loader2 className="w-10 h-10 text-accent animate-spin" />
              )}
            </div>

            <h1 className="text-3xl font-serif mb-2">
              {progress.status === 'completed'
                ? 'Processing Complete!'
                : progress.status === 'failed'
                ? 'Processing Failed'
                : 'Processing Document'}
            </h1>

            <p className="text-gray-400">
              {progress.message || 'Please wait while we process your deposition...'}
            </p>
          </div>

          {/* Progress Bar */}
          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">Progress</span>
              <span className="font-mono text-accent">{progress.progress}%</span>
            </div>

            <div className="h-3 bg-bg-elevated rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-accent to-accent-hover transition-all duration-500 ease-out"
                style={{ width: `${progress.progress}%` }}
              />
            </div>

            {/* Detailed Q&A Progress - Only show for admins */}
            {isAdmin && progress.detailedProgress && (
              <div className="mt-4 pt-4 border-t border-gray-800">
                <div className="text-center space-y-2">
                  <div className="text-2xl font-mono font-bold text-accent">
                    {progress.detailedProgress.current.toLocaleString()} / {progress.detailedProgress.total.toLocaleString()}
                  </div>
                  <div className="text-sm text-gray-400">
                    Q&A pairs processed
                  </div>
                  <div className="text-xs text-gray-500">
                    {progress.detailedProgress.percentage.toFixed(1)}% of items complete
                  </div>
                  
                  {/* Estimated Completion Time */}
                  {estimatedCompletion && progress.status !== 'completed' && (
                    <div className="mt-3 flex items-center justify-center gap-3 text-sm">
                      <div className="flex items-center gap-2 text-gray-400">
                        <Clock className="w-4 h-4" />
                        <span>
                          Est. completion: <span className="text-accent font-mono">{estimatedCompletion}</span>
                        </span>
                      </div>
                      {countdown && (
                        <div className="flex items-center gap-2 text-gray-500">
                          <span>•</span>
                          <span className="font-mono text-accent">{countdown}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Status Info - Only show connection status for admins */}
          {isAdmin && (
            <div className="mt-8 pt-8 border-t border-gray-800">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">Connection Status</span>
                <span className={isConnected ? 'text-green-500' : 'text-gray-500'}>
                  {isConnected ? '● Connected' : '○ Disconnected'}
                </span>
              </div>
            </div>
          )}

          {error && (
            <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}
        </div>
      </div>

      {/* Completion Modal */}
      {showCompletionModal && documentId && (
        <CompletionModal
          jobId={jobId}
          documentId={documentId}
          onClose={() => setShowCompletionModal(false)}
        />
      )}
    </div>
  )
}

