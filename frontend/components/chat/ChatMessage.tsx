/** Chat message component with citations */
import React from 'react';
import { MessageCircle, User, Copy, Check } from 'lucide-react';

export interface Citation {
  qa_item_id: string;
  page: number;
  line: number;
  text_snippet: string;
}

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: Date;
  onCitationClick: (qaItemId: string, page: number, line: number) => void;
}

export function ChatMessage({
  role,
  content,
  citations,
  timestamp,
  onCitationClick
}: ChatMessageProps) {
  const [copied, setCopied] = React.useState(false);
  
  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  const formatTime = (date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    }).format(date);
  };
  
  const isUser = role === 'user';
  
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} mb-4`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
        isUser ? 'bg-blue-500' : 'bg-gray-600'
      }`}>
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <MessageCircle className="w-4 h-4 text-white" />
        )}
      </div>
      
      {/* Message content */}
      <div className={`flex-1 max-w-[80%] ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className={`rounded-lg px-4 py-2 ${
          isUser 
            ? 'bg-blue-500 text-white' 
            : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100'
        }`}>
          <div className="whitespace-pre-wrap break-words">{content}</div>
          
          {/* Citations */}
          {citations && citations.length > 0 && (
            <div className="mt-2 pt-2 border-t border-gray-300 dark:border-gray-600 flex flex-wrap gap-2">
              {citations.map((citation, idx) => (
                <button
                  key={idx}
                  onClick={() => onCitationClick(
                    citation.qa_item_id,
                    citation.page,
                    citation.line
                  )}
                  className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded
                           bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300
                           hover:bg-gray-50 dark:hover:bg-gray-600
                           border border-gray-300 dark:border-gray-600
                           transition-colors"
                  title={citation.text_snippet}
                >
                  <span className="font-medium">
                    Page {citation.page}, Line {citation.line}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
        
        {/* Timestamp and actions */}
        <div className={`flex items-center gap-2 mt-1 text-xs text-gray-500 ${
          isUser ? 'flex-row-reverse' : 'flex-row'
        }`}>
          <span>{formatTime(timestamp)}</span>
          
          {!isUser && (
            <button
              onClick={handleCopy}
              className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
              title="Copy message"
            >
              {copied ? (
                <Check className="w-3 h-3 text-green-500" />
              ) : (
                <Copy className="w-3 h-3" />
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

