'use client'

import { useState, useEffect } from 'react'
import { X, Settings, Save, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'

interface UserSettingsModalProps {
  isOpen: boolean
  onClose: () => void
}

interface PromptSettings {
  preset_options: Record<string, boolean>
  custom_instructions: string
}

const PRESET_OPTIONS = [
  {
    key: 'witness_last_name',
    label: 'Refer to witness by last name',
    description: 'Use only last names when referring to witnesses'
  },
  {
    key: 'exclude_colloquy',
    label: 'Exclude colloquy from summary',
    description: 'Skip non-substantive dialogue between attorneys'
  },
  {
    key: 'factual_only',
    label: 'Focus on factual testimony only',
    description: 'Emphasize facts over opinions and speculation'
  },
  {
    key: 'include_objections',
    label: 'Include objection context',
    description: 'Note objections and their outcomes in summaries'
  },
  {
    key: 'chronological_order',
    label: 'Maintain chronological order',
    description: 'Keep events in the order they were discussed'
  },
  {
    key: 'highlight_inconsistencies',
    label: 'Highlight inconsistencies',
    description: 'Note contradictions or changes in testimony'
  }
]

export default function UserSettingsModal({ isOpen, onClose }: UserSettingsModalProps) {
  const [settings, setSettings] = useState<PromptSettings>({
    preset_options: {},
    custom_instructions: ''
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [promptPreview, setPromptPreview] = useState<string>('')
  const [showPreview, setShowPreview] = useState(false)

  useEffect(() => {
    if (isOpen) {
      fetchSettings()
      fetchPromptPreview()
    }
  }, [isOpen])

  const fetchSettings = async () => {
    try {
      setLoading(true)
      const response = await api.get('/api/user-settings/prompts')
      setSettings({
        preset_options: response.data.preset_options || {},
        custom_instructions: response.data.custom_instructions || ''
      })
    } catch (error) {
      console.error('Failed to fetch settings:', error)
    } finally {
      setLoading(false)
    }
  }
  
  const fetchPromptPreview = async () => {
    try {
      const response = await api.get('/api/user-settings/prompt-preview')
      setPromptPreview(response.data.system_prompt || '')
    } catch (error) {
      console.error('Failed to fetch prompt preview:', error)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      await api.put('/api/user-settings/prompts', settings)
      // Refresh prompt preview after save
      await fetchPromptPreview()
      onClose()
    } catch (error) {
      console.error('Failed to save settings:', error)
      alert('Failed to save settings. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const toggleOption = (key: string) => {
    setSettings({
      ...settings,
      preset_options: {
        ...settings.preset_options,
        [key]: !settings.preset_options[key]
      }
    })
    // Refresh preview when settings change
    setTimeout(fetchPromptPreview, 100)
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70"
        onClick={() => !saving && onClose()}
      />

      {/* Modal */}
      <div className="relative bg-bg-card border border-gray-800 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center">
              <Settings className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold">Summary Settings</h2>
              <p className="text-sm text-gray-400">Customize how AI generates summaries</p>
            </div>
          </div>
          <button
            onClick={() => !saving && onClose()}
            className="p-2 hover:bg-bg-elevated rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex-1 flex items-center justify-center p-12">
            <Loader2 className="w-12 h-12 text-accent animate-spin" />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Preset Options */}
            <div>
              <h3 className="text-lg font-semibold mb-4">Quick Options</h3>
              <div className="space-y-3">
                {PRESET_OPTIONS.map((option) => (
                  <button
                    key={option.key}
                    onClick={() => toggleOption(option.key)}
                    className={`w-full text-left p-4 rounded-xl transition-all ${
                      settings.preset_options[option.key]
                        ? 'bg-accent/10 border-2 border-accent/50'
                        : 'bg-bg-elevated border border-gray-800 hover:border-accent/30'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1">
                        <p className="font-medium mb-1">{option.label}</p>
                        <p className="text-sm text-gray-400">{option.description}</p>
                      </div>
                      <div
                        className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                          settings.preset_options[option.key]
                            ? 'bg-accent border-accent'
                            : 'border-gray-600'
                        }`}
                      >
                        {settings.preset_options[option.key] && (
                          <svg className="w-3 h-3 text-bg-base" fill="currentColor" viewBox="0 0 20 20">
                            <path
                              fillRule="evenodd"
                              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                              clipRule="evenodd"
                            />
                          </svg>
                        )}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Custom Instructions */}
            <div>
              <h3 className="text-lg font-semibold mb-2">Custom Instructions</h3>
              <p className="text-sm text-gray-400 mb-4">
                Add any additional instructions or preferences for summary generation
              </p>
              <textarea
                value={settings.custom_instructions}
                onChange={(e) => {
                  setSettings({ ...settings, custom_instructions: e.target.value })
                  setTimeout(fetchPromptPreview, 100)
                }}
                placeholder="e.g., Always include timestamps, emphasize financial details, use formal language..."
                className="w-full px-4 py-3 bg-bg-elevated border border-gray-700 rounded-xl resize-none focus:outline-none focus:border-accent"
                rows={6}
              />
            </div>
            
            {/* Prompt Preview Section */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-semibold">Actual AI Prompt Being Used</h3>
                <button
                  onClick={() => setShowPreview(!showPreview)}
                  className="text-sm text-accent hover:underline"
                >
                  {showPreview ? 'Hide' : 'Show'} Prompt
                </button>
              </div>
              <p className="text-sm text-gray-400 mb-4">
                This is the actual system prompt sent to the AI, with your settings applied
              </p>
              {showPreview && promptPreview && (
                <div className="bg-bg-elevated border border-gray-700 rounded-xl p-4 max-h-96 overflow-y-auto">
                  <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono">
                    {promptPreview}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-800 flex justify-end gap-3">
          <button
            onClick={() => !saving && onClose()}
            className="px-6 py-3 bg-bg-elevated hover:bg-gray-800 text-gray-300 font-semibold rounded-xl transition-all"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-3 bg-accent hover:bg-accent-hover disabled:bg-gray-700 text-bg-base font-semibold rounded-xl transition-all flex items-center gap-2"
          >
            {saving ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Saving...</span>
              </>
            ) : (
              <>
                <Save className="w-5 h-5" />
                <span>Save Settings</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

