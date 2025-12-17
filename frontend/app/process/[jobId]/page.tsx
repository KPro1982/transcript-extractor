'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useParams } from 'next/navigation'
import { Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { useJobProgress } from '@/hooks/useWebSocket'

export default function ProcessPage() {
  const router = useRouter()
  const params = useParams()
  const jobId = params?.jobId as string

  const { progress, isConnected, error } = useJobProgress(jobId)

  useEffect(() => {
    // Redirect to results when complete
    if (progress.status === 'completed') {
      setTimeout(() => {
        router.push(`/results/${jobId}`)
      }, 2000)
    }
  }, [progress.status, jobId, router])

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

            {/* Detailed Q&A Progress */}
            {progress.detailedProgress && (
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
                </div>
              </div>
            )}
          </div>

          {/* Status Info */}
          <div className="mt-8 pt-8 border-t border-gray-800">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-400">Connection Status</span>
              <span className={isConnected ? 'text-green-500' : 'text-gray-500'}>
                {isConnected ? '● Connected' : '○ Disconnected'}
              </span>
            </div>

            {error && (
              <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}
          </div>

          {/* Processing Steps */}
          <div className="mt-8 space-y-3">
            <ProcessingStep
              label="PDF Extraction"
              isActive={progress.progress >= 5 && progress.progress < 20}
              isComplete={progress.progress >= 20}
            />
            <ProcessingStep
              label="Q&A Parsing"
              isActive={progress.progress >= 20 && progress.progress < 25}
              isComplete={progress.progress >= 25}
            />
            <ProcessingStep
              label="AI Summarization"
              isActive={progress.progress >= 25 && progress.progress < 90}
              isComplete={progress.progress >= 90}
            />
            <ProcessingStep
              label="Saving Results"
              isActive={progress.progress >= 90 && progress.progress < 100}
              isComplete={progress.progress === 100}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function ProcessingStep({
  label,
  isActive,
  isComplete,
}: {
  label: string
  isActive: boolean
  isComplete: boolean
}) {
  return (
    <div className="flex items-center gap-3">
      <div
        className={`w-2 h-2 rounded-full ${
          isComplete
            ? 'bg-accent'
            : isActive
            ? 'bg-accent animate-pulse'
            : 'bg-gray-700'
        }`}
      />
      <span className={isComplete || isActive ? 'text-gray-300' : 'text-gray-600'}>
        {label}
      </span>
    </div>
  )
}

