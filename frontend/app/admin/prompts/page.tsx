'use client'

import { useRouter } from 'next/navigation'
import { ArrowLeft, Settings, Brain, TrendingUp } from 'lucide-react'
import ProtectedRoute from '@/components/ProtectedRoute'

export default function AdminPromptsPage() {
  const router = useRouter()

  return (
    <ProtectedRoute requireAdmin>
      <div className="min-h-screen bg-bg-base p-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-8 flex items-center gap-4">
            <button
              onClick={() => router.push('/admin')}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
            <div className="h-6 w-px bg-gray-700" />
            <div>
              <h1 className="text-3xl font-serif">Prompt Improvement Module</h1>
              <p className="text-gray-400 text-sm">Analyze feedback patterns and refine prompts</p>
            </div>
          </div>

          {/* Content */}
          <div className="bg-bg-card border border-gray-800 rounded-2xl p-12 text-center">
            <div className="max-w-2xl mx-auto">
              <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
                <Settings className="w-10 h-10 text-green-400" />
              </div>

              <h2 className="text-2xl font-semibold mb-4">Prompt Analysis Tools</h2>
              
              <div className="space-y-4 text-left">
                <div className="bg-bg-elevated rounded-xl p-6">
                  <div className="flex items-start gap-4">
                    <Brain className="w-6 h-6 text-purple-400 flex-shrink-0 mt-1" />
                    <div>
                      <h3 className="font-semibold mb-2">Review Learning Feedback</h3>
                      <p className="text-sm text-gray-400 mb-3">
                        Access user corrections through the &ldquo;Learning Feedback&rdquo; page. Compare AI-generated 
                        summaries with user corrections to identify patterns and improvement opportunities.
                      </p>
                      <button
                        onClick={() => router.push('/admin/feedback')}
                        className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-all text-sm"
                      >
                        Go to Feedback Review
                      </button>
                    </div>
                  </div>
                </div>

                <div className="bg-bg-elevated rounded-xl p-6">
                  <div className="flex items-start gap-4">
                    <TrendingUp className="w-6 h-6 text-blue-400 flex-shrink-0 mt-1" />
                    <div>
                      <h3 className="font-semibold mb-2">Prompt Iteration Process</h3>
                      <p className="text-sm text-gray-400 mb-3">
                        After reviewing feedback patterns:
                      </p>
                      <ol className="text-sm text-gray-400 space-y-2 list-decimal list-inside">
                        <li>Identify common issues in user corrections</li>
                        <li>Modify prompts in <code className="bg-bg-card px-2 py-1 rounded text-accent">backend/services/ai_providers/openai_provider.py</code></li>
                        <li>Test with sample documents</li>
                        <li>Mark feedback as &ldquo;Applied&rdquo; when integrated</li>
                        <li>Monitor new feedback for continued improvement</li>
                      </ol>
                    </div>
                  </div>
                </div>

                <div className="bg-bg-elevated rounded-xl p-6">
                  <div className="flex items-start gap-4">
                    <Settings className="w-6 h-6 text-green-400 flex-shrink-0 mt-1" />
                    <div>
                      <h3 className="font-semibold mb-2">Future Enhancements</h3>
                      <p className="text-sm text-gray-400">
                        This module can be expanded to include:
                      </p>
                      <ul className="text-sm text-gray-400 space-y-1 mt-2 list-disc list-inside">
                        <li>Automated pattern detection in feedback</li>
                        <li>A/B testing of prompt variations</li>
                        <li>AI-assisted prompt suggestions</li>
                        <li>Prompt version tracking and rollback</li>
                        <li>Performance metrics by prompt version</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  )
}

