'use client'

import { useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

export default function AuthCallbackPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { login } = useAuth()

  useEffect(() => {
    const handleCallback = async () => {
      const accessToken = searchParams?.get('access_token')
      const refreshToken = searchParams?.get('refresh_token')

      if (accessToken && refreshToken) {
        try {
          await login(accessToken, refreshToken)
          router.push('/')
        } catch (error) {
          console.error('Login error:', error)
          router.push('/login?error=authentication_failed')
        }
      } else {
        router.push('/login?error=authentication_failed')
      }
    }

    handleCallback()
  }, [searchParams, login, router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-base">
      <div className="text-center">
        <Loader2 className="w-12 h-12 text-accent animate-spin mx-auto mb-4" />
        <p className="text-gray-400">Completing sign in...</p>
      </div>
    </div>
  )
}

