'use client'

import { useEffect, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { LogIn, Loader2, AlertCircle } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

function LoginContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, loading } = useAuth()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Check for error in URL
    const errorParam = searchParams?.get('error')
    if (errorParam === 'authentication_failed') {
      setError('Authentication failed. Please try again.')
    }

    // Redirect if already logged in
    if (!loading && user) {
      router.push('/')
    }
  }, [user, loading, router, searchParams])

  const handleGoogleLogin = () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    window.location.href = `${apiUrl}/api/auth/google/login`
  }
  
  const handleBypassAdmin = async () => {
    try {
      setError(null)
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      console.log('Fetching admin bypass from:', `${apiUrl}/api/auth/dev/bypass-admin`)
      const response = await fetch(`${apiUrl}/api/auth/dev/bypass-admin`)
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('Bypass admin error:', errorText)
        setError(`Failed to bypass login: ${errorText}`)
        return
      }
      
      const data = await response.json()
      console.log('Bypass admin response:', data)
      
      if (data.access_token && data.refresh_token) {
        // Store tokens
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
        
        // Force reload to trigger auth context
        window.location.href = '/'
      } else {
        setError('Failed to bypass login - no tokens received')
      }
    } catch (err: any) {
      console.error('Bypass admin login error:', err)
      setError(`Failed to bypass login: ${err.message}`)
    }
  }
  
  const handleBypassUser = async () => {
    try {
      setError(null)
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      console.log('Fetching user bypass from:', `${apiUrl}/api/auth/dev/bypass-user`)
      const response = await fetch(`${apiUrl}/api/auth/dev/bypass-user`)
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('Bypass user error:', errorText)
        setError(`Failed to bypass login: ${errorText}`)
        return
      }
      
      const data = await response.json()
      console.log('Bypass user response:', data)
      
      if (data.access_token && data.refresh_token) {
        // Store tokens
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
        
        // Force reload to trigger auth context
        window.location.href = '/'
      } else {
        setError('Failed to bypass login - no tokens received')
      }
    } catch (err: any) {
      console.error('Bypass user login error:', err)
      setError(`Failed to bypass login: ${err.message}`)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg-base">
        <Loader2 className="w-12 h-12 text-accent animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-base p-8">
      <div className="max-w-md w-full">
        <div className="bg-bg-card border border-gray-800 rounded-2xl p-8">
          {/* Logo/Title */}
          <div className="text-center mb-8">
            <h1 className="text-4xl font-serif mb-2">DepoDigest</h1>
            <p className="text-gray-400">AI-powered deposition summarization</p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Google Sign In Button */}
          <button
            onClick={handleGoogleLogin}
            className="w-full px-6 py-4 bg-white hover:bg-gray-100 text-gray-900 font-semibold rounded-xl transition-all flex items-center justify-center gap-3 shadow-lg mb-6"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            <span>Sign in with Google</span>
          </button>
          
          {/* Development Bypass Buttons */}
          <div className="mt-6 pt-6 border-t border-gray-800">
            <p className="text-xs text-gray-500 mb-3 text-center">Development Bypass</p>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={handleBypassAdmin}
                className="px-4 py-3 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-400 font-semibold rounded-xl transition-all text-sm"
              >
                Admin
              </button>
              <button
                onClick={handleBypassUser}
                className="px-4 py-3 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-400 font-semibold rounded-xl transition-all text-sm"
              >
                User
              </button>
            </div>
            <p className="text-xs text-gray-600 mt-2 text-center">
              Skip OAuth for testing
            </p>
          </div>

          {/* Info */}
          <p className="text-center text-sm text-gray-500 mt-6">
            Sign in to access your deposition summaries and settings
          </p>
        </div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-bg-base">
        <Loader2 className="w-12 h-12 text-accent animate-spin" />
      </div>
    }>
      <LoginContent />
    </Suspense>
  )
}

