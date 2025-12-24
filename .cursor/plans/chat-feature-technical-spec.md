# Chat-with-Depo Technical Specification

## 1. Database Schema Changes

### Persistent Database (depodigest_persistent)

```sql
-- Chat Sessions Table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id UUID NOT NULL,  -- References ephemeral DB documents table
    title VARCHAR(255) DEFAULT 'New Chat',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chat_sessions_user ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_document ON chat_sessions(document_id);
CREATE INDEX idx_chat_sessions_updated ON chat_sessions(user_id, updated_at DESC);

-- Chat Messages Table
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    citations JSONB,  -- [{qa_item_id, page, line, text_snippet}]
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_created ON chat_messages(session_id, created_at ASC);

-- Add check constraint for role
ALTER TABLE chat_messages ADD CONSTRAINT check_role 
    CHECK (role IN ('user', 'assistant'));
```

## 2. Backend API Specification

### 2.1 Chat Session Endpoints

#### POST /api/chat/sessions
Create a new chat session for a document.

**Request:**
```json
{
  "document_id": "uuid"
}
```

**Response (201):**
```json
{
  "session_id": "uuid",
  "document_id": "uuid",
  "title": "New Chat",
  "created_at": "2024-12-24T10:00:00Z",
  "updated_at": "2024-12-24T10:00:00Z"
}
```

**Errors:**
- 400: Invalid document_id
- 401: Unauthorized
- 404: Document not found or user doesn't have access

---

#### GET /api/chat/sessions?document_id={uuid}
Get all chat sessions for a document (for current user).

**Query Params:**
- `document_id` (required): UUID of document

**Response (200):**
```json
{
  "sessions": [
    {
      "session_id": "uuid",
      "title": "Questions about timeline",
      "created_at": "2024-12-24T10:00:00Z",
      "updated_at": "2024-12-24T10:30:00Z",
      "message_count": 12
    }
  ]
}
```

---

#### GET /api/chat/sessions/{session_id}
Get a specific chat session with all messages.

**Response (200):**
```json
{
  "session_id": "uuid",
  "document_id": "uuid",
  "title": "Questions about timeline",
  "created_at": "2024-12-24T10:00:00Z",
  "updated_at": "2024-12-24T10:30:00Z",
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "What did the witness say about the accident?",
      "created_at": "2024-12-24T10:00:00Z"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "Based on the testimony, the witness stated...",
      "citations": [
        {
          "qa_item_id": "uuid",
          "page": 5,
          "line": 12,
          "text_snippet": "I saw the car run the red light"
        }
      ],
      "created_at": "2024-12-24T10:00:15Z"
    }
  ]
}
```

**Errors:**
- 401: Unauthorized
- 403: Forbidden (not user's session)
- 404: Session not found

---

#### PATCH /api/chat/sessions/{session_id}
Update chat session metadata (title).

**Request:**
```json
{
  "title": "Timeline questions"
}
```

**Response (200):**
```json
{
  "session_id": "uuid",
  "title": "Timeline questions",
  "updated_at": "2024-12-24T10:35:00Z"
}
```

---

#### DELETE /api/chat/sessions/{session_id}
Delete a chat session and all its messages.

**Response (204):** No content

**Errors:**
- 401: Unauthorized
- 403: Forbidden
- 404: Not found

---

### 2.2 Chat Message Endpoints

#### POST /api/chat/sessions/{session_id}/messages
Send a message and get AI response.

**Request:**
```json
{
  "message": "What did the witness say about the accident?",
  "stream": false
}
```

**Response (200) - Non-streaming:**
```json
{
  "message_id": "uuid",
  "role": "assistant",
  "content": "Based on the testimony on page 5, the witness stated that...",
  "citations": [
    {
      "qa_item_id": "uuid",
      "page": 5,
      "line": 12,
      "text_snippet": "I saw the car run the red light"
    }
  ],
  "created_at": "2024-12-24T10:00:15Z"
}
```

**Response - Streaming (SSE):**
```
event: message
data: {"type": "start", "message_id": "uuid"}

event: message
data: {"type": "content", "delta": "Based on"}

event: message
data: {"type": "content", "delta": " the testimony"}

event: message
data: {"type": "citation", "citation": {...}}

event: message
data: {"type": "end"}
```

**Errors:**
- 400: Invalid message
- 401: Unauthorized
- 403: Forbidden
- 404: Session not found
- 429: Rate limit exceeded
- 500: AI service error

---

#### GET /api/chat/sessions/{session_id}/messages
Get all messages for a session (alternative to getting with session).

**Response (200):**
```json
{
  "messages": [...]
}
```

---

## 3. Backend Services

### 3.1 DepositionContextBuilder

**File:** `backend/services/deposition_context_builder.py`

```python
class DepositionContextBuilder:
    """Build comprehensive context from deposition data."""
    
    async def build_full_context(self, document_id: UUID) -> Dict:
        """
        Build complete context including metadata and all Q&A items.
        
        Returns:
        {
            "metadata": {
                "document_id": str,
                "filename": str,
                "case_name": str,
                "witness_name": str,
                "deposition_date": str,
                "total_pages": int
            },
            "qa_items": [
                {
                    "qa_item_id": str,
                    "page": int,
                    "line": int,
                    "question": str,
                    "answer": str,
                    "summary": str,
                    "topic": str,
                    "event_date": str
                }
            ]
        }
        """
        
    async def get_cached_context(self, document_id: UUID) -> Optional[Dict]:
        """Get context from Redis cache (24hr TTL)."""
        
    async def cache_context(self, document_id: UUID, context: Dict):
        """Store context in Redis with 24hr TTL."""
```

---

### 3.2 SemanticSearchService

**File:** `backend/services/semantic_search_service.py`

```python
class SemanticSearchService:
    """Semantic search using embeddings for Q&A retrieval."""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        self.dimension = 1536  # OpenAI ada-002 embedding dimension
        
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI ada-002."""
        
    async def get_or_generate_embeddings(
        self, 
        document_id: UUID
    ) -> Tuple[List[str], np.ndarray]:
        """
        Get embeddings for all Q&A summaries in document.
        Uses cache if available, generates and caches otherwise.
        
        Returns: (qa_item_ids, embeddings_matrix)
        """
        
    async def search_relevant_qa(
        self, 
        document_id: UUID, 
        query: str, 
        top_k: int = 20
    ) -> List[Dict]:
        """
        Find most relevant Q&A items using semantic search.
        
        Steps:
        1. Generate query embedding
        2. Load/generate document Q&A embeddings
        3. Compute cosine similarity
        4. Return top_k most similar items with full context
        """
        
    async def cache_embeddings(
        self,
        document_id: UUID,
        embeddings: Dict[str, List[float]]
    ):
        """Cache embeddings in Redis (7-day TTL)."""
```

---

### 3.3 ChatService

**File:** `backend/services/chat_service.py`

```python
class ChatService:
    """Handle chat interactions with RAG."""
    
    def __init__(self):
        self.context_builder = DepositionContextBuilder()
        self.semantic_search = SemanticSearchService()
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        
    async def generate_response(
        self,
        session_id: UUID,
        user_message: str,
        stream: bool = False
    ) -> Dict:
        """
        Generate AI response using RAG.
        
        Steps:
        1. Load chat session and document_id
        2. Load recent chat history (last 10 messages)
        3. Get document metadata
        4. Semantic search for relevant Q&A items (top 20)
        5. Build prompt with system instructions + context + history
        6. Call OpenAI GPT-4 with function calling for citations
        7. Parse response and extract citations
        8. Save messages to database
        9. Return response
        """
        
    async def _build_system_prompt(self) -> str:
        """Build system prompt for legal assistant."""
        
    async def _build_context_prompt(
        self,
        metadata: Dict,
        relevant_qas: List[Dict]
    ) -> str:
        """Build context section with metadata and relevant Q&As."""
        
    async def _extract_citations(
        self,
        response_text: str,
        function_calls: List[Dict]
    ) -> List[Dict]:
        """Extract and validate citations from AI response."""
        
    async def generate_stream_response(
        self,
        session_id: UUID,
        user_message: str
    ) -> AsyncGenerator[Dict, None]:
        """Stream response using SSE."""
```

---

### 3.4 Special Query Handlers

**File:** `backend/services/special_query_handlers.py`

```python
class SpecialQueryHandlers:
    """Handlers for specific legal analysis queries."""
    
    async def find_conflicting_testimony(
        self,
        document_id: UUID
    ) -> Dict:
        """
        Find instances where witness gave conflicting statements.
        
        Algorithm:
        1. Group Q&A items by topic
        2. For each topic, ask AI to identify contradictions
        3. Return conflicts with citations
        """
        
    async def find_refusals_to_answer(
        self,
        document_id: UUID
    ) -> Dict:
        """
        Find instances where attorney instructed witness not to answer.
        
        Pattern matching:
        - "instruct" + "not to answer"
        - "object to the form"
        - "refuse to answer"
        """
        
    async def find_breaks(
        self,
        document_id: UUID
    ) -> Dict:
        """
        Find breaks in testimony.
        
        Pattern matching:
        - "break"
        - "recess"
        - "off the record"
        - "lunch"
        """
        
    async def find_corrections(
        self,
        document_id: UUID
    ) -> Dict:
        """
        Find instances where witness corrected testimony.
        
        Pattern matching:
        - "correct"
        - "clarify"
        - "mistaken"
        - "earlier I said"
        """
        
    async def suggest_cross_examination(
        self,
        document_id: UUID
    ) -> Dict:
        """
        AI analysis to suggest cross-examination areas.
        
        Analyzes:
        - Evasive answers
        - "I don't recall" responses
        - Inconsistencies
        - Weak explanations
        """
```

---

## 4. Frontend Components

### 4.1 ChatPanel Component

**File:** `frontend/components/chat/ChatPanel.tsx`

```typescript
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
  // State: messages, loading, session
  // Load or create session
  // Load message history
  // Handle message submission
  // Handle streaming responses
  // Render chat UI
}
```

---

### 4.2 ChatMessage Component

**File:** `frontend/components/chat/ChatMessage.tsx`

```typescript
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
  // Render message bubble
  // Render citations as clickable chips
  // Format timestamp
  // Copy button for assistant messages
}
```

---

### 4.3 ChatSessionList Component

**File:** `frontend/components/chat/ChatSessionList.tsx`

```typescript
interface ChatSessionListProps {
  documentId: string;
  currentSessionId?: string;
  onSessionSelect: (sessionId: string) => void;
  onNewSession: () => void;
}

export function ChatSessionList({
  documentId,
  currentSessionId,
  onSessionSelect,
  onNewSession
}: ChatSessionListProps) {
  // Load sessions for document
  // Render session list
  // Handle session selection
  // Handle new session creation
  // Handle session deletion
}
```

---

## 5. AI Prompt Templates

### System Prompt

```
You are an expert legal assistant analyzing a deposition transcript. You have access to:

1. Complete Q&A pairs from the deposition with AI-generated summaries
2. Document metadata (case information, witness name, deposition date)
3. The ability to cite specific locations in the transcript

Your responsibilities:
- Answer questions about the deposition accurately and thoroughly
- ALWAYS provide citations with page and line numbers for your statements
- Identify patterns such as conflicts, corrections, and refusals to answer
- Provide strategic insights for trial preparation
- Be precise, concise, and professional

Citation Rules:
- Format citations as [Page X, Line Y]
- When referencing testimony, include a brief quote
- Use the cite_qa_item function to create clickable citations
- Cite multiple sources when applicable

The user may ask about:
- Specific facts, events, or testimony
- Timeline of events
- Witness credibility and inconsistencies
- Areas for potential cross-examination
- Legal strategy and preparation

Remember: Accuracy is paramount. If you're unsure, say so and explain why.
```

### Context Prompt Template

```
DOCUMENT INFORMATION:
- Case: {{case_name}}
- Witness: {{witness_name}}
- Date: {{deposition_date}}
- Total Pages: {{total_pages}}

RELEVANT Q&A ITEMS (Based on semantic search):

{% for qa in relevant_qas %}
[Q&A #{{loop.index}} - Page {{qa.page}}, Line {{qa.line}}]
Topic: {{qa.topic}}
{% if qa.event_date %}Date Reference: {{qa.event_date}}{% endif %}
Summary: {{qa.summary}}

Question: {{qa.question}}
Answer: {{qa.answer}}

---
{% endfor %}

CHAT HISTORY:
{% for msg in chat_history %}
{{msg.role}}: {{msg.content}}
{% endfor %}

USER QUESTION: {{user_question}}
```

### Function Calling Schema

```json
{
  "name": "cite_qa_item",
  "description": "Cite a specific Q&A item from the deposition to support your answer",
  "parameters": {
    "type": "object",
    "properties": {
      "qa_item_id": {
        "type": "string",
        "description": "UUID of the Q&A item being cited"
      },
      "page": {
        "type": "integer",
        "description": "Transcript page number"
      },
      "line": {
        "type": "integer",
        "description": "Line number on the page"
      },
      "text_snippet": {
        "type": "string",
        "description": "Brief relevant quote from the Q&A (20-50 words)"
      }
    },
    "required": ["qa_item_id", "page", "line", "text_snippet"]
  }
}
```

---

## 6. Caching Strategy

### Redis Cache Keys

```python
# Embeddings cache (7-day TTL)
f"embeddings:{document_id}:{qa_item_id}" → List[float]

# Document context cache (24-hour TTL)
f"chat_context:{document_id}" → JSON

# Session cache (1-hour TTL, extend on access)
f"chat_session:{session_id}" → JSON

# Embeddings matrix cache (7-day TTL)
f"embeddings_matrix:{document_id}" → Serialized numpy array
```

---

## 7. Error Handling

### Backend Error Responses

```python
class ChatError(Exception):
    """Base exception for chat errors."""
    pass

class SessionNotFoundError(ChatError):
    """Session does not exist."""
    pass

class UnauthorizedSessionError(ChatError):
    """User doesn't own this session."""
    pass

class DocumentNotFoundError(ChatError):
    """Document doesn't exist or user lacks access."""
    pass

class AIServiceError(ChatError):
    """OpenAI API error."""
    pass

class RateLimitError(ChatError):
    """Rate limit exceeded."""
    pass
```

### Frontend Error Handling

- Display user-friendly error messages
- Retry logic for transient failures
- Fallback to non-streaming if streaming fails
- Clear error states on new message

---

## 8. Testing Requirements

### Unit Tests

```python
# backend/tests/test_chat_service.py
- test_generate_response()
- test_extract_citations()
- test_build_context_prompt()

# backend/tests/test_semantic_search.py
- test_generate_embeddings()
- test_search_relevant_qa()
- test_cache_embeddings()

# backend/tests/test_special_handlers.py
- test_find_conflicting_testimony()
- test_find_refusals_to_answer()
- test_find_breaks()
```

### Integration Tests

```python
# backend/tests/integration/test_chat_api.py
- test_create_session()
- test_send_message()
- test_get_session_with_messages()
- test_citation_click_navigation()
- test_streaming_response()
```

---

## 9. Deployment Checklist

- [ ] Add chat_sessions and chat_messages tables to persistent DB
- [ ] Deploy backend API changes to Railway
- [ ] Deploy frontend changes to Railway
- [ ] Set OpenAI API key in Railway environment
- [ ] Test chat functionality in production
- [ ] Monitor logs for errors
- [ ] Test rate limiting
- [ ] Verify cost tracking

---

## 10. Performance Targets

- Message response time: < 5 seconds (non-streaming)
- Embeddings generation: < 30 seconds per document
- Semantic search: < 500ms
- Context loading: < 1 second
- Streaming first token: < 2 seconds

---

## 11. Security Checklist

- [ ] All chat endpoints require authentication
- [ ] Verify user owns session before access
- [ ] Verify user has access to document
- [ ] Rate limiting: 30 messages per minute per user
- [ ] Sanitize user input before AI processing
- [ ] No PII in logs
- [ ] Citations validated before returning
- [ ] SQL injection prevention (parameterized queries)

