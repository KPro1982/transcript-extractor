'use client'

import { useRouter } from 'next/navigation'
import { FileText, BarChart3, CheckCircle } from 'lucide-react'

interface CompletionModalProps {
  jobId: string
  documentId: string
  onClose: () => void
}

export default function CompletionModal({ jobId, documentId, onClose }: CompletionModalProps) {
  const router = useRouter()

  return (
    <div 
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div 
        className="bg-bg-card border border-accent/30 rounded-2xl p-8 max-w-2xl w-full shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-green-500/20 to-accent/20 rounded-full mb-4">
            <CheckCircle className="w-12 h-12 text-green-500" />
          </div>
          <h2 className="text-3xl font-serif font-bold mb-2">Processing Complete!</h2>
          <p className="text-gray-400">
            Your deposition has been processed successfully. Choose how you'd like to proceed:
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button
            onClick={() => router.push(`/results/${jobId}`)}
            className="flex flex-col items-center gap-3 p-6 bg-bg-elevated hover:bg-bg-elevated/80 border border-gray-800 hover:border-gray-700 rounded-xl transition-all group"
          >
            <FileText className="w-10 h-10 text-gray-400 group-hover:text-white transition-colors" />
            <div className="text-center">
              <h3 className="text-lg font-semibold mb-1">Reading Mode</h3>
              <p className="text-sm text-gray-400">Review Q&A with PDF viewer</p>
            </div>
          </button>

          <button
            onClick={() => router.push(`/reports/${documentId}`)}
            className="flex flex-col items-center gap-3 p-6 bg-accent/10 hover:bg-accent/20 border border-accent/30 hover:border-accent/50 rounded-xl transition-all group"
          >
            <BarChart3 className="w-10 h-10 text-accent group-hover:text-accent-hover transition-colors" />
            <div className="text-center">
              <h3 className="text-lg font-semibold mb-1">View Reports</h3>
              <p className="text-sm text-gray-400">Narrative summaries & analysis</p>
            </div>
          </button>
        </div>

        <div className="mt-6 text-center">
          <button
            onClick={onClose}
            className="text-sm text-gray-500 hover:text-gray-300 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

