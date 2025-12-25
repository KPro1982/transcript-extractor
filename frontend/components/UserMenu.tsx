'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { User, LogOut, Shield, Bell } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

export default function UserMenu() {
  const { user, logout } = useAuth()
  const router = useRouter()
  const [isOpen, setIsOpen] = useState(false)

  if (!user) return null

  const handleLogout = async () => {
    await logout()
  }

  const goToAdmin = () => {
    router.push('/admin')
    setIsOpen(false)
  }

  return (
    <div className="relative">
      {/* User Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 rounded-xl hover:bg-bg-elevated transition-colors"
      >
        {user.picture ? (
          <img
            src={user.picture}
            alt={user.name || user.email}
            className="w-8 h-8 rounded-full"
          />
        ) : (
          <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center">
            <User className="w-4 h-4 text-accent" />
          </div>
        )}
        <span className="text-sm hidden md:inline">{user.name || user.email}</span>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* Menu */}
          <div className="absolute right-0 mt-2 w-64 bg-bg-card border border-gray-800 rounded-xl shadow-xl z-20 overflow-hidden">
            {/* User Info */}
            <div className="px-4 py-3 border-b border-gray-800">
              <p className="text-sm font-medium">{user.name || 'User'}</p>
              <p className="text-xs text-gray-400 truncate">{user.email}</p>
              {user.is_admin && (
                <span className="inline-flex items-center gap-1 mt-2 px-2 py-1 bg-accent/10 border border-accent/30 rounded-full text-xs text-accent">
                  <Shield className="w-3 h-3" />
                  Admin
                </span>
              )}
            </div>

            {/* Menu Items */}
            <div className="py-2">
              {user.is_admin && (
                <button
                  onClick={goToAdmin}
                  className="w-full px-4 py-2 text-left text-sm hover:bg-bg-elevated transition-colors flex items-center gap-2"
                >
                  <Shield className="w-4 h-4" />
                  Admin Panel
                </button>
              )}

              <button
                onClick={handleLogout}
                className="w-full px-4 py-2 text-left text-sm hover:bg-bg-elevated transition-colors flex items-center gap-2 text-red-400"
              >
                <LogOut className="w-4 h-4" />
                Sign Out
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}






