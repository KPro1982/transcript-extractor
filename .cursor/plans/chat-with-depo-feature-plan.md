# Chat-with-Depo Feature Plan

## 📋 Overview
Add interactive chat capability allowing users to ask questions about depositions. The AI will analyze the entire deposition transcript, leveraging existing summaries and Q&A data to provide intelligent responses with citations.

## 🎯 Feature Requirements

### User Stories
1. **As a user**, I want to ask natural language questions about a deposition so I can quickly find relevant information.
2. **As a user**, I want the AI to cite specific page/line numbers so I can verify the source.
3. **As a user**, I want the AI to identify conflicting testimony so I can prepare cross-examination.
4. **As a user**, I want to find when breaks were taken or when witness refused to answer so I can understand deposition dynamics.
5. **As a user**, I want to see the chat history persist during my session so I can refer back to previous answers.

### AI Capabilities
The chat AI should be able to:
- ✅ Answer questions based on the entire deposition
- ✅ Leverage existing AI summaries for context
- ✅ Identify conflicting testimony from the witness
- ✅ Find instances where defending attorney instructed witness not to answer
- ✅ Locate breaks in testimony
- ✅ Identify when witness corrected their testimony
- ✅ Suggest areas for cross-examination at trial
- ✅ Provide citations with page/line numbers
- ✅ Click citations to jump to that Q&A in the PDF viewer

## 🏗️ Technical Architecture

### Database Schema (Persistent DB)

#### New Table: `chat_sessions`
```sql
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    document_id UUID NOT NULL, -- References ephemeral DB documents
    title VARCHAR(255) DEFAULT 'New Chat',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_chat_sessions_user ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_document ON chat_sessions(document_id);
```

#### New Table: `chat_messages`
```sql
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user' or 'assistant'
    content TEXT NOT NULL,
    citations JSONB, -- Array of {page, line, qa_item_id, text_snippet}
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_created ON chat_messages(session_id, created_at);
```

### Backend API Endpoints

#### Chat Session Management
```
POST   /api/chat/sessions
  Body: { document_id: UUID }
  Response: { session_id: UUID, title: string, created_at: string }

GET    /api/chat/sessions?document_id={id}
  Response: [{ session_id, title, created_at, message_count }]

GET    /api/chat/sessions/{session_id}
  Response: { session_id, document_id, title, messages: [...] }

DELETE /api/chat/sessions/{session_id}
  Response: { success: true }

PATCH  /api/chat/sessions/{session_id}
  Body: { title: string }
  Response: { success: true }
```

#### Chat Message Management
```
POST   /api/chat/sessions/{session_id}/messages
  Body: { 
    message: string,
    stream: boolean (optional, default false)
  }
  Response (non-streaming): { 
    message_id: UUID,
    content: string,
    citations: [{ page, line, qa_item_id, text }]
  }
  Response (streaming): SSE stream with chunks

GET    /api/chat/sessions/{session_id}/messages
  Response: [{ id, role, content, citations, created_at }]
```

### AI Service: RAG (Retrieval-Augmented Generation)

#### Components

**1. Document Context Builder**
```python
class DepositionContextBuilder:
    """Build comprehensive context from deposition data."""
    
    async def build_context(self, document_id: UUID) -> Dict:
        """
        Gather all deposition data:
        - Document metadata (case, witness, date, attorneys)
        - All Q&A pairs with summaries from final_qa_items
        - Full text when needed for specific questions
        """
        
        return {
            "metadata": {...},
            "qa_summaries": [...],  # All summaries + page/line refs
            "full_qa_text": [...],  # Optional: full Q&A text
        }
```

**2. Semantic Search Service**
```python
class SemanticSearchService:
    """Find relevant Q&A items using embeddings."""
    
    async def search_relevant_qa(
        self, 
        document_id: UUID, 
        query: str, 
        top_k: int = 20
    ) -> List[Dict]:
        """
        Two-stage retrieval:
        1. Use OpenAI embeddings to find semantically similar summaries
        2. Re-rank by relevance to query
        
        Returns: List of Q&A items with summaries and metadata
        """
```

**3. Chat Service**
```python
class ChatService:
    """Handle chat interactions with RAG."""
    
    async def generate_response(
        self,
        session_id: UUID,
        user_message: str,
        chat_history: List[Dict],
        stream: bool = False
    ) -> Dict:
        """
        1. Load document context (metadata)
        2. Semantic search for relevant Q&A items (top 20-30)
        3. Build prompt with:
           - System instructions (legal context, citation rules)
           - Relevant Q&A summaries
           - Chat history (last 5-10 messages)
           - User question
        4. Call OpenAI GPT-4 with function calling for citations
        5. Parse response and extract citations
        6. Save message to DB
        """
```

#### Special Query Handlers

**Conflict Detection**
```python
async def find_conflicting_testimony(document_id: UUID) -> List[Dict]:
    """
    1. Group Q&A items by topic/subject
    2. Use AI to compare statements within topics
    3. Identify contradictions
    4. Return with citations
    """
```

**Instruction Not to Answer Detection**
```python
async def find_refusals_to_answer(document_id: UUID) -> List[Dict]:
    """
    Pattern matching + AI:
    - Search for "instruct" + "not to answer"
    - Check summaries for similar patterns
    - Return Q&A items with citations
    """
```

**Break Detection**
```python
async def find_breaks(document_id: UUID) -> List[Dict]:
    """
    Pattern matching:
    - Search for "break", "recess", "off the record"
    - Check Q&A answers for break indicators
    - Return with page/line citations
    """
```

**Correction Detection**
```python
async def find_corrections(document_id: UUID) -> List[Dict]:
    """
    Pattern matching:
    - Search for "correct", "clarify", "mistaken", "earlier"
    - Identify self-corrections in testimony
    - Return with citations
    """
```

**Cross-Examination Suggestions**
```python
async def suggest_cross_exam_areas(document_id: UUID) -> List[Dict]:
    """
    AI analysis:
    - Identify weak or evasive answers
    - Find inconsistencies
    - Highlight areas of uncertainty ("I don't recall")
    - Suggest impeachment opportunities
    """
```

### Frontend UI Design

#### Components

**1. ChatPanel Component**
```typescript
interface ChatPanelProps {
  documentId: string;
  onCitationClick: (qaItemId: string, page: number, line: number) => void;
}

// Features:
// - Collapsible sidebar or modal
// - Message list with user/assistant bubbles
// - Input field with send button
// - Citation links that jump to PDF location
// - Loading indicator during AI response
// - Streaming support for real-time responses
```

**2. ChatMessage Component**
```typescript
interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: Date;
}

// Features:
// - Formatted message display
// - Clickable citation chips
// - Copy button for assistant responses
```

**3. ChatSession List**
```typescript
// Show previous chat sessions for document
// Create new session
// Delete/rename sessions
```

#### UI Patterns

**Option A: Side Panel (Recommended)**
```
┌─────────────────────────────────────────────────────────┐
│  [← Back]  Deposition: John Doe           [Chat] [User] │
├──────────────────────────────┬──────────────────────────┤
│                              │  Chat History            │
│     PDF Viewer               │  ┌────────────────────┐ │
│                              │  │ User: Where did... │ │
│     [Page 1]                 │  └────────────────────┘ │
│                              │  ┌────────────────────┐ │
│                              │  │ AI: Based on pg 5  │ │
│     Q&A Summary Panel        │  │ [Page 5, Line 12]  │ │
│                              │  └────────────────────┘ │
│                              │  ┌────────────────────┐ │
│                              │  │ Ask a question...  │ │
│                              │  │ [Send]             │ │
│                              │  └────────────────────┘ │
└──────────────────────────────┴──────────────────────────┘
```

**Option B: Modal Overlay**
```
Chat opens as centered modal over PDF viewer
Can minimize to floating button
```

### AI Prompt Engineering

#### System Prompt
```
You are a legal assistant analyzing a deposition transcript. You have access to:
1. Complete Q&A pairs with AI-generated summaries
2. Document metadata (case info, witness, date)
3. Citation capabilities (page/line numbers)

Your role:
- Answer questions about the deposition accurately
- ALWAYS cite your sources with page and line numbers
- Identify patterns (conflicts, corrections, refusals)
- Suggest strategic insights for trial preparation
- Be concise but thorough

Citation format: [Page X, Line Y]
When citing, reference the Q&A item ID for clickable links.

The user may ask about:
- Specific facts or events
- Witness credibility issues
- Timeline of events
- Conflicting statements
- Areas for cross-examination
```

#### Function Calling Schema
```json
{
  "name": "cite_qa_item",
  "description": "Cite a specific Q&A from the deposition",
  "parameters": {
    "qa_item_id": "UUID of the Q&A item",
    "page": "Transcript page number",
    "line": "Line number",
    "text_snippet": "Brief quote from the Q&A"
  }
}
```

### Caching Strategy

**Embeddings Cache**
```python
# Store embeddings for all Q&A summaries in Redis
# Key: f"embeddings:{document_id}:{qa_item_id}"
# Value: Embedding vector (serialized)
# TTL: 7 days (regenerate if document changes)
```

**Context Cache**
```python
# Cache full document context in Redis
# Key: f"chat_context:{document_id}"
# Value: JSON with metadata + all Q&A summaries
# TTL: 24 hours
```

**Session Cache**
```python
# Cache active chat sessions in Redis
# Key: f"chat_session:{session_id}"
# Value: Recent messages (last 10)
# TTL: 1 hour (extend on each message)
```

## 🔄 Data Flow

### User Asks Question
1. Frontend sends POST to `/api/chat/sessions/{id}/messages`
2. Backend loads chat session from persistent DB
3. Load document context (metadata + Q&A summaries)
4. Perform semantic search on Q&A summaries (top 20 results)
5. Build AI prompt with:
   - System instructions
   - Relevant Q&A summaries
   - Recent chat history
   - User question
6. Call OpenAI GPT-4 with streaming
7. Parse citations from response
8. Save user message + assistant response to persistent DB
9. Return response with citations to frontend
10. Frontend displays message with clickable citation chips

### Citation Click
1. User clicks citation chip: `[Page 5, Line 12]`
2. Frontend calls `onCitationClick(qaItemId, 5, 12)`
3. Results page loads PDF to page 5
4. Highlights line 12
5. Updates summary panel to show that Q&A

## 📊 Performance Considerations

### Optimization Strategies
1. **Embeddings**: Generate once, cache in Redis (7-day TTL)
2. **Semantic Search**: Use FAISS or pgvector for fast similarity search
3. **Context Size**: Limit to top 20-30 most relevant Q&As (avoid token limits)
4. **Streaming**: Use SSE for real-time responses (better UX)
5. **Batch Embeddings**: Generate all embeddings after document processing completes

### Token Budget
- GPT-4 context limit: 128k tokens
- Typical deposition: 1000 Q&As × 100 tokens = 100k tokens
- Strategy: Use summaries (not full text) → ~50k tokens
- Top 20 Q&As with context: ~5-10k tokens ✅

## 🧪 Testing Strategy

### Unit Tests
- Semantic search accuracy
- Citation extraction from AI responses
- Context builder generates valid structure
- Special query handlers (conflicts, breaks, etc.)

### Integration Tests
- Chat session CRUD operations
- Message persistence
- Citation click navigation
- Streaming responses

### Manual Testing Scenarios
1. **General Questions**: "What did the witness say about the accident?"
2. **Conflict Detection**: "Did the witness contradict themselves?"
3. **Refusal Detection**: "When did they refuse to answer?"
4. **Timeline Questions**: "What happened in March 2020?"
5. **Cross-Exam**: "Where can I challenge this witness at trial?"

## 🚀 Implementation Phases

### Phase 1: Core Infrastructure (Days 1-2)
- [ ] Database schema (chat_sessions, chat_messages tables)
- [ ] Backend API endpoints (session + message CRUD)
- [ ] DepositionContextBuilder service
- [ ] Basic ChatService (no RAG yet)
- [ ] Simple frontend ChatPanel component

### Phase 2: RAG Implementation (Days 3-4)
- [ ] OpenAI embeddings integration
- [ ] SemanticSearchService with caching
- [ ] Enhanced ChatService with RAG
- [ ] Citation extraction and parsing
- [ ] Frontend citation rendering and click handling

### Phase 3: Special Features (Days 5-6)
- [ ] Conflict detection handler
- [ ] Refusal detection handler
- [ ] Break detection handler
- [ ] Correction detection handler
- [ ] Cross-examination suggestions

### Phase 4: Polish & Testing (Days 7-8)
- [ ] Streaming responses (SSE)
- [ ] Chat session management UI
- [ ] Error handling and edge cases
- [ ] Performance optimization
- [ ] Integration testing
- [ ] User acceptance testing

## 📝 Open Questions

1. **Embeddings Provider**: Use OpenAI embeddings or open-source (sentence-transformers)?
   - **Recommendation**: OpenAI (ada-002) for consistency with existing AI provider
   
2. **Vector Database**: FAISS (local) vs pgvector (PostgreSQL extension)?
   - **Recommendation**: Start with FAISS in Redis, migrate to pgvector later if needed
   
3. **Streaming**: Server-Sent Events (SSE) or WebSocket?
   - **Recommendation**: SSE (simpler, HTTP-based, already using WebSockets for progress)
   
4. **Session Persistence**: How long to keep chat sessions?
   - **Recommendation**: Keep indefinitely (user can delete), show last 10 per document
   
5. **Multi-Document Chat**: Support chatting with multiple depositions?
   - **Recommendation**: Phase 2 feature, start with single document

## 🔐 Security Considerations

- ✅ Chat sessions tied to user_id (prevent unauthorized access)
- ✅ Verify user has access to document before loading chat
- ✅ Rate limiting on chat messages (prevent abuse)
- ✅ Sanitize user input before sending to AI
- ✅ No PII in chat logs (GDPR compliance)

## 💰 Cost Estimates

### Per Chat Interaction
- Embeddings: $0.0001 per 1k tokens × 20 Q&As = $0.002
- GPT-4 response: $0.03 per 1k tokens × 2k tokens = $0.06
- **Total per message**: ~$0.06

### Monthly Usage (1000 messages)
- 1000 messages × $0.06 = $60/month

### Optimization
- Cache embeddings → Reduce to ~$0.03 per message
- Use GPT-3.5 for simple queries → Reduce to ~$0.01 per message

## ✅ Success Metrics

- [ ] Users can ask questions and receive accurate answers
- [ ] Citations are correct and clickable
- [ ] Response time < 5 seconds per message
- [ ] Special features (conflicts, breaks) work correctly
- [ ] No security vulnerabilities
- [ ] Cost per message < $0.05

---

## Next Steps

**Before Implementation:**
1. Review plan with stakeholder
2. Confirm UI/UX approach (side panel vs modal)
3. Decide on embeddings provider
4. Set up development environment

**Ready to Build?**
Switch to Agent Mode and start with Phase 1.

