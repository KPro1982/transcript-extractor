'use client'

import React, { createContext, useContext, useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'

interface User {
  id: string
  email: string
  name?: string
  picture?: string
  is_admin: boolean
}

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (accessToken: string, refreshToken: string) => Promise<void>
  logout: () => Promise<void>
  refreshAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  // Check if user is authenticated on mount
  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const accessToken = localStorage.getItem('access_token')
      if (!accessToken) {
        setLoading(false)
        return
      }

      // Set auth header
      api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`

      // Fetch current user
      const response = await api.get('/api/auth/me')
      setUser(response.data)
    } catch (error) {
      console.error('Auth check failed:', error)
      // Try to refresh token
      await refreshAuth()
    } finally {
      setLoading(false)
    }
  }

  const login = async (accessToken: string, refreshToken: string) => {
    // Store tokens
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('refresh_token', refreshToken)

    // Set auth header
    api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`

    // Fetch user info
    const response = await api.get('/api/auth/me')
    setUser(response.data)
  }

  const logout = async () => {
    try {
      await api.post('/api/auth/logout')
    } catch (error) {
      console.error('Logout error:', error)
    }

    // Clear tokens and user
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    delete api.defaults.headers.common['Authorization']
    setUser(null)

    // Redirect to login
    router.push('/login')
  }

  const refreshAuth = async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        throw new Error('No refresh token')
      }

      const response = await api.post('/api/auth/refresh', { refresh_token: refreshToken })
      const { access_token, refresh_token: newRefreshToken } = response.data

      // Update tokens
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('refresh_token', newRefreshToken)
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`

      // Update user
      setUser(response.data.user)
    } catch (error) {
      console.error('Token refresh failed:', error)
      // Clear tokens and redirect to login
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      delete api.defaults.headers.common['Authorization']
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

