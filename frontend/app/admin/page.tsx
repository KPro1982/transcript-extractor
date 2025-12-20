'use client'

import { useRouter } from 'next/navigation'
import { Shield, MessageSquare, Brain, Settings, Users, BarChart3 } from 'lucide-react'
import ProtectedRoute from '@/components/ProtectedRoute'

export default function AdminDashboard() {
  const router = useRouter()

  const cards = [
    {
      title: 'Bug Reports & Chats',
      description: 'View and respond to user bug reports and feature requests',
      icon: MessageSquare,
      href: '/admin/chats',
      color: 'text-blue-400'
    },
    {
      title: 'Learning Feedback',
      description: 'Review user corrections to improve AI summaries',
      icon: Brain,
      href: '/admin/feedback',
      color: 'text-purple-400'
    },
    {
      title: 'Prompt Improvement',
      description: 'Analyze feedback patterns and refine prompts',
      icon: Settings,
      href: '/admin/prompts',
      color: 'text-green-400'
    }
  ]

  return (
    <ProtectedRoute requireAdmin>
      <div className="min-h-screen bg-bg-base p-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <Shield className="w-8 h-8 text-accent" />
              <h1 className="text-4xl font-serif">Admin Panel</h1>
            </div>
            <p className="text-gray-400">Manage bug reports, feedback, and system improvements</p>
          </div>

          {/* Admin Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {cards.map((card) => (
              <button
                key={card.href}
                onClick={() => router.push(card.href)}
                className="bg-bg-card border border-gray-800 rounded-2xl p-6 hover:border-accent/50 transition-all text-left group"
              >
                <card.icon className={`w-12 h-12 ${card.color} mb-4 group-hover:scale-110 transition-transform`} />
                <h2 className="text-xl font-semibold mb-2">{card.title}</h2>
                <p className="text-gray-400 text-sm">{card.description}</p>
              </button>
            ))}
          </div>

          {/* Quick Stats */}
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-bg-card border border-gray-800 rounded-xl p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Open Bug Reports</p>
                  <p className="text-3xl font-bold mt-1">0</p>
                </div>
                <MessageSquare className="w-8 h-8 text-blue-400 opacity-50" />
              </div>
            </div>

            <div className="bg-bg-card border border-gray-800 rounded-xl p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Pending Feedback</p>
                  <p className="text-3xl font-bold mt-1">0</p>
                </div>
                <Brain className="w-8 h-8 text-purple-400 opacity-50" />
              </div>
            </div>

            <div className="bg-bg-card border border-gray-800 rounded-xl p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Total Users</p>
                  <p className="text-3xl font-bold mt-1">1</p>
                </div>
                <Users className="w-8 h-8 text-green-400 opacity-50" />
              </div>
            </div>
          </div>

          {/* Back to App */}
          <div className="mt-8">
            <button
              onClick={() => router.push('/')}
              className="px-6 py-3 bg-bg-elevated hover:bg-gray-800 text-gray-300 font-semibold rounded-xl transition-all"
            >
              Back to Application
            </button>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  )
}

