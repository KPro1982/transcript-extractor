/** Chat panel component for deposition Q&A */
'use client';

import React, { useState, useRef, useEffect } from 'react';
import { X, Send, Loader2, MessageSquarePlus } from 'lucide-react';
import { ChatMessage, Citation } from './ChatMessage';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  created_at: string;
}

interface ChatPanelProps {
  documentId: string;
  sessionId?: string;
  onCitationClick: (qaItemId: string, page: number, line: number) => void;
  isOpen: boolean;
  onClose: () => void;
}

export function ChatPanel({
  documentId,
  sessionId: initialSessionId,
  onCitationClick,
  isOpen,
  onClose
}: ChatPanelProps) {
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId || null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  
  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
  // Load or create session when opened
  useEffect(() => {
    if (isOpen && !sessionId) {
      createNewSession();
    } else if (isOpen && sessionId) {
      loadSession();
    }
  }, [isOpen, sessionId]);
  
  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    }
  }, [isOpen]);
  
  const createNewSession = async () => {
    setLoadingSession(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${apiUrl}/api/chat/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ document_id: documentId })
      });
      
      if (!response.ok) {
        throw new Error('Failed to create chat session');
      }
      
      const data = await response.json();
      setSessionId(data.session_id);
    } catch (error) {
      console.error('Failed to create session:', error);
      alert('Failed to start chat session');
    } finally {
      setLoadingSession(false);
    }
  };
  
  const loadSession = async () => {
    if (!sessionId) return;
    
    setLoadingSession(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${apiUrl}/api/chat/sessions/${sessionId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to load chat session');
      }
      
      const data = await response.json();
      setMessages(data.messages || []);
    } catch (error) {
      console.error('Failed to load session:', error);
    } finally {
      setLoadingSession(false);
    }
  };
  
  const sendMessage = async () => {
    if (!inputValue.trim() || !sessionId || isLoading) return;
    
    const messageText = inputValue.trim();
    setInputValue('');
    
    // Add user message immediately
    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: messageText,
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMessage]);
    
    setIsLoading(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${apiUrl}/api/chat/sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: messageText,
          stream: false
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to send message');
      }
      
      const data = await response.json();
      
      // Add assistant response
      const assistantMessage: Message = {
        id: data.message_id,
        role: 'assistant',
        content: data.content,
        citations: data.citations || [],
        created_at: data.created_at
      };
      setMessages(prev => [...prev, assistantMessage]);
      
    } catch (error) {
      console.error('Failed to send message:', error);
      alert('Failed to send message. Please try again.');
      // Remove the optimistic user message on error
      setMessages(prev => prev.filter(m => m.id !== userMessage.id));
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };
  
  if (!isOpen) return null;
  
  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 shadow-lg flex flex-col z-50">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center gap-2">
          <MessageSquarePlus className="w-5 h-5 text-blue-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Chat with Deposition
          </h2>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
      
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4">
        {loadingSession ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <MessageSquarePlus className="w-12 h-12 text-gray-300 dark:text-gray-700 mb-3" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
              Start a conversation
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Ask questions about this deposition. The AI will analyze the transcript and provide answers with citations.
            </p>
            <div className="mt-4 space-y-2 text-left w-full">
              <p className="text-xs font-medium text-gray-700 dark:text-gray-300">Try asking:</p>
              <button
                onClick={() => setInputValue("What did the witness say about the accident?")}
                className="block w-full text-left text-xs p-2 rounded bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                &ldquo;What did the witness say about the accident?&rdquo;
              </button>
              <button
                onClick={() => setInputValue("Did the witness contradict themselves?")}
                className="block w-full text-left text-xs p-2 rounded bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                &ldquo;Did the witness contradict themselves?&rdquo;
              </button>
            </div>
          </div>
        ) : (
          <div>
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                role={message.role}
                content={message.content}
                citations={message.citations}
                timestamp={new Date(message.created_at)}
                onCitationClick={onCitationClick}
              />
            ))}
            {isLoading && (
              <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400 mb-4">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">Analyzing deposition...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>
      
      {/* Input */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-800">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about this deposition..."
            className="flex-1 resize-none rounded-lg border border-gray-300 dark:border-gray-700 
                     bg-white dark:bg-gray-800 px-3 py-2 text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                     placeholder-gray-400 dark:placeholder-gray-500
                     text-gray-900 dark:text-gray-100"
            rows={3}
            disabled={!sessionId || isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={!inputValue.trim() || !sessionId || isLoading}
            className="self-end p-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 
                     disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}

