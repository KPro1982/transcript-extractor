'use client'

import { useState } from 'react'
import { Edit2, Save, X, Calendar, Scale, User, Users, FileText } from 'lucide-react'
import { updateCaseInfo } from '@/lib/api'

interface CaseInfo {
  case_name?: string | null
  case_number?: string | null
  deposition_date?: string | null
  attorneys?: string[] | null
  witness_name?: string | null
}

interface CaseInfoPanelProps {
  documentId: string
  caseInfo: CaseInfo
  onUpdate?: (updatedInfo: CaseInfo) => void
  editable?: boolean
  compact?: boolean
}

export default function CaseInfoPanel({
  documentId,
  caseInfo,
  onUpdate,
  editable = true,
  compact = false
}: CaseInfoPanelProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editedInfo, setEditedInfo] = useState<CaseInfo>(caseInfo)
  const [saving, setSaving] = useState(false)
  const [attorneysInput, setAttorneysInput] = useState(
    caseInfo.attorneys?.join(', ') || ''
  )

  const hasAnyInfo = 
    caseInfo.case_name || 
    caseInfo.case_number || 
    caseInfo.deposition_date || 
    (caseInfo.attorneys && caseInfo.attorneys.length > 0) || 
    caseInfo.witness_name

  const handleSave = async () => {
    try {
      setSaving(true)
      
      // Parse attorneys from comma-separated string
      const attorneys = attorneysInput
        .split(',')
        .map(a => a.trim())
        .filter(a => a.length > 0)
      
      // Convert null to undefined for API compatibility
      const updatedData = {
        case_name: editedInfo.case_name ?? undefined,
        case_number: editedInfo.case_number ?? undefined,
        deposition_date: editedInfo.deposition_date ?? undefined,
        witness_name: editedInfo.witness_name ?? undefined,
        attorneys: attorneys.length > 0 ? attorneys : undefined
      }
      
      const result = await updateCaseInfo(documentId, updatedData)
      
      if (onUpdate) {
        onUpdate(result)
      }
      
      setIsEditing(false)
    } catch (error) {
      console.error('Failed to update case info:', error)
      alert('Failed to save case information')
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setEditedInfo(caseInfo)
    setAttorneysInput(caseInfo.attorneys?.join(', ') || '')
    setIsEditing(false)
  }

  if (!hasAnyInfo && !isEditing) {
    return (
      <div className={`${compact ? 'p-4' : 'p-6'} bg-bg-card border border-gray-800 rounded-xl mb-6`}>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-400">Case Information</h3>
          {editable && (
            <button
              onClick={() => setIsEditing(true)}
              className="text-xs text-accent hover:text-accent-hover"
            >
              Add Manually
            </button>
          )}
        </div>
        <p className="text-xs text-gray-500">No case information detected</p>
      </div>
    )
  }

  return (
    <div className={`${compact ? 'p-4' : 'p-6'} bg-bg-card border border-gray-800 rounded-xl mb-6`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className={`${compact ? 'text-sm' : 'text-base'} font-semibold flex items-center gap-2`}>
          <Scale className="w-4 h-4 text-accent" />
          Case Information
        </h3>
        {editable && !isEditing && (
          <button
            onClick={() => setIsEditing(true)}
            className="p-1.5 hover:bg-gray-700 rounded transition-colors"
            title="Edit case information"
          >
            <Edit2 className="w-4 h-4" />
          </button>
        )}
        {isEditing && (
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-3 py-1 bg-accent hover:bg-accent-hover text-bg-base text-sm rounded transition-colors flex items-center gap-1"
            >
              <Save className="w-3 h-3" />
              {saving ? 'Saving...' : 'Save'}
            </button>
            <button
              onClick={handleCancel}
              disabled={saving}
              className="px-3 py-1 bg-gray-700 hover:bg-gray-600 text-sm rounded transition-colors flex items-center gap-1"
            >
              <X className="w-3 h-3" />
              Cancel
            </button>
          </div>
        )}
      </div>

      <div className={`space-y-3 ${compact ? 'text-sm' : ''}`}>
        {/* Case Name */}
        <div className="flex items-start gap-3">
          <FileText className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-xs text-gray-400 mb-1">Case Name</div>
            {isEditing ? (
              <input
                type="text"
                value={editedInfo.case_name || ''}
                onChange={(e) => setEditedInfo({ ...editedInfo, case_name: e.target.value })}
                placeholder="e.g., Smith v. Jones"
                className="w-full px-2 py-1 bg-bg-elevated border border-gray-700 rounded text-sm"
              />
            ) : (
              <div className="text-sm">{caseInfo.case_name || <span className="text-gray-500">Not provided</span>}</div>
            )}
          </div>
        </div>

        {/* Case Number */}
        <div className="flex items-start gap-3">
          <FileText className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-xs text-gray-400 mb-1">Case Number</div>
            {isEditing ? (
              <input
                type="text"
                value={editedInfo.case_number || ''}
                onChange={(e) => setEditedInfo({ ...editedInfo, case_number: e.target.value })}
                placeholder="e.g., 24CV001303"
                className="w-full px-2 py-1 bg-bg-elevated border border-gray-700 rounded text-sm"
              />
            ) : (
              <div className="text-sm">{caseInfo.case_number || <span className="text-gray-500">Not provided</span>}</div>
            )}
          </div>
        </div>

        {/* Deposition Date */}
        <div className="flex items-start gap-3">
          <Calendar className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-xs text-gray-400 mb-1">Deposition Date</div>
            {isEditing ? (
              <input
                type="text"
                value={editedInfo.deposition_date || ''}
                onChange={(e) => setEditedInfo({ ...editedInfo, deposition_date: e.target.value })}
                placeholder="e.g., September 18, 2025"
                className="w-full px-2 py-1 bg-bg-elevated border border-gray-700 rounded text-sm"
              />
            ) : (
              <div className="text-sm">{caseInfo.deposition_date || <span className="text-gray-500">Not provided</span>}</div>
            )}
          </div>
        </div>

        {/* Witness Name */}
        <div className="flex items-start gap-3">
          <User className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-xs text-gray-400 mb-1">Witness</div>
            {isEditing ? (
              <input
                type="text"
                value={editedInfo.witness_name || ''}
                onChange={(e) => setEditedInfo({ ...editedInfo, witness_name: e.target.value })}
                placeholder="e.g., Charlene Wilson Domingues"
                className="w-full px-2 py-1 bg-bg-elevated border border-gray-700 rounded text-sm"
              />
            ) : (
              <div className="text-sm">{caseInfo.witness_name || <span className="text-gray-500">Not provided</span>}</div>
            )}
          </div>
        </div>

        {/* Attorneys */}
        <div className="flex items-start gap-3">
          <Users className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-xs text-gray-400 mb-1">Attorneys</div>
            {isEditing ? (
              <input
                type="text"
                value={attorneysInput}
                onChange={(e) => setAttorneysInput(e.target.value)}
                placeholder="e.g., John Smith, Jane Doe (comma-separated)"
                className="w-full px-2 py-1 bg-bg-elevated border border-gray-700 rounded text-sm"
              />
            ) : (
              <div className="text-sm">
                {caseInfo.attorneys && caseInfo.attorneys.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {caseInfo.attorneys.map((attorney, idx) => (
                      <span key={idx} className="px-2 py-0.5 bg-bg-elevated rounded text-xs">
                        {attorney}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-gray-500">Not provided</span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {isEditing && (
        <div className="mt-4 pt-4 border-t border-gray-800">
          <p className="text-xs text-gray-500">
            Tip: Leave fields blank to remove information. Separate multiple attorneys with commas.
          </p>
        </div>
      )}
    </div>
  )
}

