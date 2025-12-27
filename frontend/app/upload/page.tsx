'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, Loader2, Settings, FileCheck, AlertTriangle } from 'lucide-react'
import { uploadDocument, startJob, getQATestLog } from '@/lib/api'
import UserSettingsModal from '@/components/UserSettingsModal'
import UserMenu from '@/components/UserMenu'

export default function UploadPage() {
  const router = useRouter()
  const [isUploading, setIsUploading] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [uploadedDocumentId, setUploadedDocumentId] = useState<string | null>(null)
  const [qaTestResult, setQaTestResult] = useState<{
    passed: boolean
    pairsFound: number
    logFile: string | null
    errors?: string[]
  } | null>(null)
  const [showLogModal, setShowLogModal] = useState(false)
  const [logContent, setLogContent] = useState<string>('')
  const [loadingLog, setLoadingLog] = useState(false)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
    },
    maxFiles: 1,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        setFile(acceptedFiles[0])
      }
    },
  })

  const handleUpload = async () => {
    if (!file) return

    setIsUploading(true)
    setQaTestResult(null) // Reset previous test results
    setUploadedDocumentId(null)

    try {
      // Upload document
      const uploadResult = await uploadDocument(file)
      const documentId = uploadResult.document_id
      
      // Store document ID for later use
      setUploadedDocumentId(documentId)
      
      // Store Q/A test results if available
      if (uploadResult.qa_test_passed !== undefined) {
        setQaTestResult({
          passed: uploadResult.qa_test_passed,
          pairsFound: uploadResult.qa_test_pairs_found || 0,
          logFile: uploadResult.qa_test_log_file || null,
          errors: uploadResult.qa_test_errors || []
        })
      }

      // Don't redirect automatically - let user review Q/A test results first
      setIsUploading(false)
    } catch (error: any) {
      console.error('Upload failed:', error)
      
      // Extract error message from API response
      let errorMessage = 'Upload failed. Please try again.'
      
      if (error?.response?.data?.detail) {
        errorMessage = `Upload failed: ${error.response.data.detail}`
      } else if (error?.response?.data?.message) {
        errorMessage = `Upload failed: ${error.response.data.message}`
      } else if (error?.message) {
        errorMessage = `Upload failed: ${error.message}`
      } else if (error?.response?.status === 0 || error?.code === 'ERR_NETWORK') {
        errorMessage = 'Upload failed: Cannot connect to server. Please check your connection and try again.'
      } else if (error?.response?.status === 500) {
        errorMessage = 'Upload failed: Server error. Please check Railway logs and try again.'
      } else if (error?.response?.status === 413) {
        errorMessage = 'Upload failed: File too large. Please try a smaller file.'
      }
      
      alert(errorMessage)
      setIsUploading(false)
    }
  }
  
  const handleStartProcessing = () => {
    if (uploadedDocumentId) {
      router.push(`/select-pages/${uploadedDocumentId}`)
    }
  }
  
  const handleViewLog = async () => {
    if (!qaTestResult?.logFile) return
    
    setLoadingLog(true)
    setShowLogModal(true)
    
    try {
      const content = await getQATestLog(qaTestResult.logFile)
      setLogContent(content)
    } catch (error) {
      console.error('Failed to load log:', error)
      setLogContent('Error loading log file. The file may have been cleaned up.')
    } finally {
      setLoadingLog(false)
    }
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-serif mb-2">Upload Deposition</h1>
            <p className="text-gray-400">Select a PDF transcript to begin AI-powered summarization</p>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Settings Gear Icon */}
            <button
              onClick={() => setSettingsOpen(true)}
              className="p-3 bg-bg-card border border-gray-800 hover:border-accent/50 rounded-xl transition-all group"
              title="Summary Settings"
            >
              <Settings className="w-6 h-6 text-gray-400 group-hover:text-accent group-hover:rotate-90 transition-all" />
            </button>

            {/* User Menu */}
            <UserMenu />
          </div>
        </div>

        <div className="bg-bg-card border border-gray-800 rounded-2xl p-8">
          {!file ? (
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all ${
                isDragActive
                  ? 'border-accent bg-accent/5'
                  : 'border-gray-700 hover:border-accent/50'
              }`}
            >
              <input {...getInputProps()} />
              <Upload className="w-16 h-16 mx-auto mb-4 text-gray-500" />
              <p className="text-lg mb-2">
                {isDragActive ? 'Drop your PDF here' : 'Drag & drop your PDF here'}
              </p>
              <p className="text-sm text-gray-500">or click to browse files</p>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="flex items-center gap-4 p-4 bg-bg-elevated rounded-xl">
                <FileText className="w-8 h-8 text-accent flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{file.name}</p>
                  <p className="text-sm text-gray-500">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
                {!isUploading && (
                  <button
                    onClick={() => setFile(null)}
                    className="text-sm text-gray-400 hover:text-white"
                  >
                    Remove
                  </button>
                )}
              </div>

              {/* Q/A Test Results */}
              {qaTestResult && (
                <div className={`p-4 rounded-xl border ${
                  qaTestResult.passed 
                    ? 'bg-green-500/10 border-green-500/30' 
                    : 'bg-yellow-500/10 border-yellow-500/30'
                }`}>
                  <div className="flex items-start gap-3">
                    {qaTestResult.passed ? (
                      <FileCheck className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                    ) : (
                      <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                    )}
                    <div className="flex-1">
                      <p className={`font-medium mb-1 ${
                        qaTestResult.passed ? 'text-green-400' : 'text-yellow-400'
                      }`}>
                        {qaTestResult.passed 
                          ? '✓ Q/A Extraction Test Passed' 
                          : '⚠ Q/A Extraction Test Warning'}
                      </p>
                      <p className="text-sm text-gray-300 mb-2">
                        {qaTestResult.passed 
                          ? `Found ${qaTestResult.pairsFound} Q/A pairs in examination section.`
                          : 'No Q/A pairs found. Check log for details.'}
                      </p>
                      {qaTestResult.logFile && (
                        <button
                          onClick={handleViewLog}
                          className="text-sm text-accent hover:text-accent-hover underline"
                        >
                          View Test Log
                        </button>
                      )}
                      {qaTestResult.errors && qaTestResult.errors.length > 0 && (
                        <div className="mt-2 text-sm text-gray-400">
                          {qaTestResult.errors.map((err, idx) => (
                            <p key={idx}>• {err}</p>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              <div className="flex gap-4">
                {!uploadedDocumentId ? (
                  // Initial upload button
                  <>
                    <button
                      onClick={handleUpload}
                      disabled={isUploading}
                      className="flex-1 px-6 py-3 bg-accent hover:bg-accent-hover disabled:bg-gray-700 text-bg-base font-semibold rounded-xl transition-all flex items-center justify-center gap-2"
                    >
                      {isUploading ? (
                        <>
                          <Loader2 className="w-5 h-5 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        <>Upload & Analyze</>
                      )}
                    </button>

                    {!isUploading && (
                      <button
                        onClick={() => router.push('/')}
                        className="px-6 py-3 bg-bg-elevated hover:bg-gray-800 text-gray-300 font-semibold rounded-xl transition-all"
                      >
                        Cancel
                      </button>
                    )}
                  </>
                ) : (
                  // After upload complete - show Start Processing button
                  <>
                    <button
                      onClick={handleStartProcessing}
                      className="flex-1 px-6 py-3 bg-accent hover:bg-accent-hover text-bg-base font-semibold rounded-xl transition-all"
                    >
                      Start Processing
                    </button>
                    <button
                      onClick={() => {
                        setFile(null)
                        setUploadedDocumentId(null)
                        setQaTestResult(null)
                      }}
                      className="px-6 py-3 bg-bg-elevated hover:bg-gray-800 text-gray-300 font-semibold rounded-xl transition-all"
                    >
                      Cancel
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="mt-8 grid grid-cols-3 gap-6">
          <div className="bg-bg-card border border-gray-800 rounded-xl p-6">
            <div className="text-3xl font-bold text-accent mb-2">~3s</div>
            <div className="text-sm text-gray-400">PDF Extraction</div>
          </div>
          <div className="bg-bg-card border border-gray-800 rounded-xl p-6">
            <div className="text-3xl font-bold text-accent mb-2">~30s</div>
            <div className="text-sm text-gray-400">AI Summarization</div>
          </div>
          <div className="bg-bg-card border border-gray-800 rounded-xl p-6">
            <div className="text-3xl font-bold text-accent mb-2">6.4x</div>
            <div className="text-sm text-gray-400">Speed Improvement</div>
          </div>
        </div>
      </div>

      {/* User Settings Modal */}
      <UserSettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
      
      {/* Q/A Test Log Modal */}
      {showLogModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-bg-card border border-gray-800 rounded-2xl max-w-4xl w-full max-h-[80vh] flex flex-col">
            {/* Header */}
            <div className="p-6 border-b border-gray-800 flex items-center justify-between">
              <h2 className="text-2xl font-semibold">Q/A Extraction Test Log</h2>
              <button
                onClick={() => setShowLogModal(false)}
                className="text-gray-400 hover:text-white text-2xl leading-none"
              >
                ×
              </button>
            </div>
            
            {/* Content */}
            <div className="p-6 overflow-auto flex-1">
              {loadingLog ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-accent" />
                </div>
              ) : (
                <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono bg-bg-elevated p-4 rounded-lg">
                  {logContent}
                </pre>
              )}
            </div>
            
            {/* Footer */}
            <div className="p-6 border-t border-gray-800 flex justify-end">
              <button
                onClick={() => setShowLogModal(false)}
                className="px-6 py-2 bg-accent hover:bg-accent-hover text-bg-base font-semibold rounded-lg transition-all"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}








