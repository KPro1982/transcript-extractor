'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, Loader2, Settings } from 'lucide-react'
import { uploadDocument, startJob } from '@/lib/api'
import UserSettingsModal from '@/components/UserSettingsModal'
import UserMenu from '@/components/UserMenu'

export default function UploadPage() {
  const router = useRouter()
  const [isUploading, setIsUploading] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)

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

    try {
      // Upload document
      const uploadResult = await uploadDocument(file)
      const documentId = uploadResult.document_id

      // Start processing job
      const jobResult = await startJob(documentId)
      const jobId = jobResult.job_id

      // Redirect to processing page
      router.push(`/process/${jobId}`)
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

              <div className="flex gap-4">
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
                    <>Start Processing</>
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
    </div>
  )
}








