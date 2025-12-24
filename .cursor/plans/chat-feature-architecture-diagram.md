# Chat-with-Depo Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Next.js)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Results Page (/results)                   │  │
│  │  ┌───────────────────┐  ┌──────────────────────────────┐   │  │
│  │  │   PDF Viewer      │  │     ChatPanel Component      │   │  │
│  │  │                   │  │  ┌────────────────────────┐  │   │  │
│  │  │  [Page Display]   │  │  │  ChatSessionList       │  │   │  │
│  │  │  [Highlighting]   │  │  │  ┌──────────────────┐  │  │   │  │
│  │  │                   │  │  │  │ Session 1        │  │  │   │  │
│  │  ├───────────────────┤  │  │  │ Session 2 (act.) │◄─┼──┼───┼── User selects
│  │  │  Summary Panel    │  │  │  └──────────────────┘  │  │   │  │
│  │  │                   │  │  └────────────────────────┘  │   │  │
│  │  │  [Q&A Summaries]  │  │                              │   │  │
│  │  │  [Event Dates]    │  │  ┌────────────────────────┐  │   │  │
│  │  │                   │  │  │   Message List         │  │   │  │
│  │  │                   │  │  │  ┌──────────────────┐  │  │   │  │
│  │  │                   │  │  │  │ User: Question   │  │  │   │  │
│  │  │                   │  │  │  └──────────────────┘  │  │   │  │
│  │  │                   │  │  │  ┌──────────────────┐  │  │   │  │
│  │  │                   │  │  │  │ AI: Answer       │  │  │   │  │
│  │  │                   │  │  │  │ [Page 5, Ln 12]◄─┼──┼───┼── Click citation
│  │  │                   │  │  │  └──────────────────┘  │  │   │  │
│  │  │                   │  │  └────────────────────────┘  │   │  │
│  │  │                   │  │                              │   │  │
│  │  │                   │  │  ┌────────────────────────┐  │   │  │
│  │  │                   │  │  │  [Type message...]     │  │   │  │
│  │  │                   │  │  │  [Send Button]         │  │   │  │
│  │  └───────────────────┘  │  └────────────────────────┘  │   │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                           │                      │                 │
│                           ▼                      ▼                 │
│                    onCitationClick()      sendMessage()            │
└───────────────────────────┼──────────────────────┼─────────────────┘
                            │                      │
                            │                      │ HTTP/REST
════════════════════════════╪══════════════════════╪═════════════════
                            │                      │
                            │                      ▼
┌───────────────────────────┼──────────────────────────────────────┐
│                           │      BACKEND (FastAPI)               │
├───────────────────────────┼──────────────────────────────────────┤
│                           │                                       │
│  ┌────────────────────────┴─────────────────────────────────┐   │
│  │                    API Endpoints                          │   │
│  │  POST   /api/chat/sessions                                │   │
│  │  GET    /api/chat/sessions?document_id=...                │   │
│  │  GET    /api/chat/sessions/{id}                           │   │
│  │  POST   /api/chat/sessions/{id}/messages   ◄──────────────┼───── User message
│  │  GET    /api/documents/{id}/qa-items        ◄─────────────┼───── Citation data
│  └───────────────────────┬──────────────────────────────────┘   │
│                          │                                       │
│                          ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  ChatService                              │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  generate_response(session_id, message)            │  │   │
│  │  │    1. Load session & history                       │  │   │
│  │  │    2. Get document context ──┐                     │  │   │
│  │  │    3. Semantic search       ──┼──┐                 │  │   │
│  │  │    4. Build AI prompt         │  │                 │  │   │
│  │  │    5. Call OpenAI GPT-4 ──────┼──┼──┐              │  │   │
│  │  │    6. Extract citations       │  │  │              │  │   │
│  │  │    7. Save to DB              │  │  │              │  │   │
│  │  └────────────────────────────────┼──┼──┼──────────────┘  │   │
│  └────────────────────────────────────┼──┼──┼──────────────────┘   │
│                                       │  │  │                  │
│           ┌───────────────────────────┘  │  │                  │
│           ▼                              │  │                  │
│  ┌──────────────────────────────────┐   │  │                  │
│  │  DepositionContextBuilder        │   │  │                  │
│  │  ┌────────────────────────────┐  │   │  │                  │
│  │  │ build_full_context()       │  │   │  │                  │
│  │  │  - Document metadata       │  │   │  │                  │
│  │  │  - All Q&A items           │  │   │  │                  │
│  │  │  - Summaries               │  │   │  │                  │
│  │  └────────────────────────────┘  │   │  │                  │
│  └──────────────┬───────────────────┘   │  │                  │
│                 │ Cache 24hr             │  │                  │
│                 ▼                        │  │                  │
│  ┌──────────────────────────────────┐   │  │                  │
│  │     Redis Cache                  │   │  │                  │
│  │  chat_context:{doc_id}           │   │  │                  │
│  └──────────────────────────────────┘   │  │                  │
│                                          │  │                  │
│              ┌───────────────────────────┘  │                  │
│              ▼                              │                  │
│  ┌──────────────────────────────────────┐  │                  │
│  │     SemanticSearchService            │  │                  │
│  │  ┌────────────────────────────────┐  │  │                  │
│  │  │ search_relevant_qa()           │  │  │                  │
│  │  │  1. Generate query embedding   │◄─┼──┼── OpenAI         │
│  │  │  2. Load doc embeddings        │  │  │   ada-002        │
│  │  │  3. Cosine similarity          │  │  │                  │
│  │  │  4. Return top 20 Q&As         │  │  │                  │
│  │  └────────────────────────────────┘  │  │                  │
│  └──────────────┬───────────────────────┘  │                  │
│                 │ Cache 7 days              │                  │
│                 ▼                           │                  │
│  ┌──────────────────────────────────┐      │                  │
│  │     Redis Cache                  │      │                  │
│  │  embeddings:{doc_id}:{qa_id}     │      │                  │
│  │  embeddings_matrix:{doc_id}      │      │                  │
│  └──────────────────────────────────┘      │                  │
│                                             │                  │
│                     ┌───────────────────────┘                  │
│                     ▼                                          │
│  ┌────────────────────────────────────────────────────────┐   │
│  │              OpenAI GPT-4 Integration                  │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │  System Prompt: "You are a legal assistant..."   │  │   │
│  │  │  Context: Document metadata + Top 20 Q&As        │  │   │
│  │  │  History: Last 10 messages                       │  │   │
│  │  │  User Query: "What did witness say about..."     │  │   │
│  │  │                                                   │  │   │
│  │  │  Function Calling: cite_qa_item(qa_id, pg, ln)   │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │         SpecialQueryHandlers (Optional)                │   │
│  │  - find_conflicting_testimony()                        │   │
│  │  - find_refusals_to_answer()                           │   │
│  │  - find_breaks()                                       │   │
│  │  - find_corrections()                                  │   │
│  │  - suggest_cross_examination()                         │   │
│  └────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
                            │
                            ▼
════════════════════════════════════════════════════════════════
                        DATABASES
════════════════════════════════════════════════════════════════

┌────────────────────────────┐     ┌─────────────────────────────┐
│  Persistent DB             │     │  Ephemeral DB               │
│  (User Data)               │     │  (Document Data)            │
├────────────────────────────┤     ├─────────────────────────────┤
│                            │     │                             │
│  ┌──────────────────────┐  │     │  ┌───────────────────────┐ │
│  │  chat_sessions       │  │     │  │  documents            │ │
│  │  - id                │  │     │  │  - id                 │ │
│  │  - user_id           │  │     │  │  - filename           │ │
│  │  - document_id ──────┼──┼─────┼─►│  - case_name          │ │
│  │  - title             │  │     │  │  - witness_name       │ │
│  │  - timestamps        │  │     │  │  - total_pages        │ │
│  └──────────────────────┘  │     │  └───────────────────────┘ │
│            │               │     │                             │
│            │               │     │  ┌───────────────────────┐ │
│            │               │     │  │  final_qa_items       │ │
│            ▼               │     │  │  - id ◄───────────────┼─┼─── Used for
│  ┌──────────────────────┐  │     │  │  - document_id        │ │     citations
│  │  chat_messages       │  │     │  │  - page_number        │ │
│  │  - id                │  │     │  │  - line_number        │ │
│  │  - session_id        │  │     │  │  - question           │ │
│  │  - role              │  │     │  │  - answer             │ │
│  │  - content           │  │     │  │  - summary  ◄─────────┼─┼─── Used for
│  │  - citations (JSONB) │  │     │  │  - topic              │ │     RAG search
│  │    [{qa_id, page,    │  │     │  │  - event_date         │ │
│  │      line, snippet}] │  │     │  └───────────────────────┘ │
│  │  - timestamp         │  │     │                             │
│  └──────────────────────┘  │     └─────────────────────────────┘
│                            │
│  ┌──────────────────────┐  │
│  │  users               │  │
│  │  - id                │  │
│  │  - email             │  │
│  │  - name              │  │
│  │  - is_admin          │  │
│  └──────────────────────┘  │
└────────────────────────────┘


════════════════════════════════════════════════════════════════
                    DATA FLOW DIAGRAM
════════════════════════════════════════════════════════════════

USER ASKS QUESTION:
───────────────────

1. User types question in ChatPanel
   │
   ▼
2. POST /api/chat/sessions/{id}/messages
   │
   ▼
3. ChatService.generate_response()
   │
   ├─► DepositionContextBuilder.build_full_context()
   │   │
   │   ├─► Check Redis cache: chat_context:{doc_id}
   │   │   │
   │   │   └─► If miss: Query ephemeral DB (documents + final_qa_items)
   │   │       │
   │   │       └─► Cache in Redis (24hr TTL)
   │   │
   │   └─► Return: {metadata, qa_items[]}
   │
   ├─► SemanticSearchService.search_relevant_qa()
   │   │
   │   ├─► Generate query embedding (OpenAI ada-002)
   │   │
   │   ├─► Get document embeddings from Redis
   │   │   │
   │   │   └─► If miss: Generate all embeddings (summaries)
   │   │       │
   │   │       └─► Cache in Redis (7-day TTL)
   │   │
   │   ├─► Compute cosine similarity (FAISS)
   │   │
   │   └─► Return: Top 20 most relevant Q&A items
   │
   ├─► Build AI prompt:
   │   │ - System instructions (legal assistant role)
   │   │ - Document metadata (case, witness, date)
   │   │ - Top 20 relevant Q&As (question, answer, summary)
   │   │ - Chat history (last 10 messages)
   │   │ - User question
   │   │
   │   ▼
   ├─► Call OpenAI GPT-4 with function calling
   │   │ - Model: gpt-4
   │   │ - Function: cite_qa_item(qa_id, page, line, snippet)
   │   │ - Max tokens: 1000
   │   │ - Temperature: 0.3 (more deterministic)
   │   │
   │   ▼
   ├─► Parse response
   │   │ - Extract content
   │   │ - Extract function calls → citations
   │   │ - Validate citations (qa_item_id exists)
   │   │
   │   ▼
   ├─► Save to persistent DB
   │   │ - User message → chat_messages
   │   │ - AI response → chat_messages (with citations JSONB)
   │   │ - Update session.updated_at
   │   │
   │   ▼
   └─► Return response to frontend
       │ - message_id
       │ - content
       │ - citations: [{qa_item_id, page, line, text_snippet}]
       │
       ▼
4. Frontend displays message
   │
   ▼
5. User clicks citation: [Page 5, Line 12]
   │
   ▼
6. onCitationClick(qa_item_id, 5, 12)
   │
   ├─► PDF Viewer: Scroll to page 5
   │
   ├─► Highlight line 12
   │
   └─► Summary Panel: Load Q&A item details


CITATION CLICK FLOW:
────────────────────

[Page 5, Line 12] ─── onClick ───┐
                                  │
                                  ▼
                      onCitationClick(qa_id, page, line)
                                  │
                                  ├─► Get Q&A item from final_qa_items
                                  │   │
                                  │   └─► GET /api/documents/{doc_id}/qa-items
                                  │       (filter by qa_id)
                                  │
                                  ├─► PDF Viewer Component:
                                  │   │ - Navigate to page
                                  │   │ - Highlight line
                                  │
                                  └─► Summary Panel Component:
                                      │ - Display question
                                      │ - Display answer
                                      │ - Display summary
                                      │ - Display event_date


════════════════════════════════════════════════════════════════
                    CACHING STRATEGY
════════════════════════════════════════════════════════════════

Redis Keys:
───────────

1. chat_context:{document_id}
   - Value: JSON {metadata, qa_items[]}
   - TTL: 24 hours
   - Purpose: Avoid reloading document data on each message

2. embeddings:{document_id}:{qa_item_id}
   - Value: Float array [1536 dimensions]
   - TTL: 7 days
   - Purpose: Avoid regenerating embeddings

3. embeddings_matrix:{document_id}
   - Value: Serialized numpy array (N x 1536)
   - TTL: 7 days
   - Purpose: Fast similarity search

4. chat_session:{session_id}
   - Value: JSON {session_info, recent_messages[]}
   - TTL: 1 hour (extend on each access)
   - Purpose: Reduce DB queries for active sessions


Cache Invalidation:
───────────────────

- Document context: Invalidate if document reprocessed
- Embeddings: Invalidate if Q&A items updated
- Session cache: Auto-expire after 1 hour of inactivity
- Always fetch latest messages from DB (don't rely on cache)


════════════════════════════════════════════════════════════════
                 SPECIAL FEATURES FLOW
════════════════════════════════════════════════════════════════

CONFLICT DETECTION:
───────────────────

User: "Did the witness contradict themselves?"
  │
  ▼
ChatService detects intent: conflict_detection
  │
  ▼
SpecialQueryHandlers.find_conflicting_testimony()
  │
  ├─► Load all Q&A items grouped by topic
  │
  ├─► For each topic group:
  │   │ - Send to GPT-4: "Identify contradictions"
  │   │ - Parse conflicts with citations
  │   │
  │   ▼
  └─► Return structured response:
      {
        "conflicts": [
          {
            "topic": "Time of incident",
            "statements": [
              {"page": 12, "line": 8, "text": "3 PM"},
              {"page": 45, "line": 15, "text": "5 PM"}
            ],
            "explanation": "2-hour discrepancy"
          }
        ]
      }


REFUSAL DETECTION:
──────────────────

User: "When did attorney instruct witness not to answer?"
  │
  ▼
SpecialQueryHandlers.find_refusals_to_answer()
  │
  ├─► Pattern search in answers:
  │   │ - "instruct" + "not to answer"
  │   │ - "object to the form"
  │   │ - "refuse"
  │   │
  │   ▼
  └─► Return Q&A items with citations


════════════════════════════════════════════════════════════════
```

## Technology Stack

### Frontend
- **Framework**: Next.js 14 (React 18)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State**: React Context + useState
- **HTTP**: fetch API
- **Icons**: lucide-react

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Language**: Python with type hints
- **AI**: OpenAI GPT-4 + ada-002 embeddings
- **Vector Search**: FAISS (numpy-based)
- **Caching**: Redis
- **Database**: PostgreSQL (asyncpg)

### Infrastructure
- **Deployment**: Railway
- **Cache**: Redis (managed)
- **Databases**: 2 PostgreSQL instances (ephemeral + persistent)
- **Monitoring**: Railway logs + OpenAI usage dashboard

## Key Design Decisions

### 1. RAG Architecture
**Why**: Enables accurate responses grounded in source material
**How**: Semantic search → Top 20 Q&As → GPT-4 with context

### 2. Separate Persistent DB
**Why**: Chat history must survive document clearing
**How**: chat_sessions and chat_messages in persistent DB

### 3. OpenAI Embeddings
**Why**: Consistency with existing AI provider, good accuracy
**How**: ada-002 (1536 dimensions), cached 7 days

### 4. FAISS for Vector Search
**Why**: Fast, simple, no additional infrastructure
**How**: In-memory numpy arrays cached in Redis

### 5. Function Calling for Citations
**Why**: Structured citation extraction, clickable links
**How**: GPT-4 function: cite_qa_item(qa_id, page, line, snippet)

### 6. Side Panel UI
**Why**: View PDF and chat simultaneously
**How**: Resizable panel, clickable citations

### 7. Caching Strategy
**Why**: Reduce costs, improve performance
**How**: 3-tier cache (embeddings 7d, context 24h, session 1h)

## Performance Optimizations

1. **Embeddings**: Generate once, cache 7 days
2. **Context**: Cache document context 24 hours
3. **Semantic Search**: Top 20 only (not full transcript)
4. **Token Limit**: Use summaries instead of full Q&A text
5. **Batch Embeddings**: Generate all at once after processing
6. **Connection Pooling**: asyncpg pools for DB queries
7. **Redis Pipelining**: Batch cache operations

## Security Measures

1. **Authentication**: JWT tokens for all endpoints
2. **Authorization**: Verify user owns session before access
3. **Input Sanitization**: Clean user input before AI processing
4. **Citation Validation**: Verify qa_item_id exists
5. **Rate Limiting**: 30 messages/minute per user
6. **SQL Injection**: Parameterized queries only
7. **No PII Logging**: Sanitize logs

## Cost Analysis

### Per Message (Without Caching)
- Query embedding: $0.0001 × 0.5k tokens = $0.00005
- Doc embeddings: $0.0001 × 50k tokens = $0.005 (one-time)
- GPT-4 input: $0.03 × 5k tokens = $0.15
- GPT-4 output: $0.06 × 0.5k tokens = $0.03
- **Total**: ~$0.18

### Per Message (With Caching)
- Query embedding: $0.00005
- Doc embeddings: $0 (cached)
- GPT-4 input: $0.03 (top 20 Q&As only)
- GPT-4 output: $0.03
- **Total**: ~$0.06

### Monthly (1000 messages, cached)
- 1000 × $0.06 = $60/month
- If 70% cached: ~$40/month

## Deployment Architecture

```
Railway:
├─ Backend Service (FastAPI)
│  ├─ /api/chat/* endpoints
│  ├─ ChatService + RAG
│  └─ Connects to: Persistent DB, Ephemeral DB, Redis
│
├─ Worker-0, Worker-1, Worker-2 (Document Processing)
│  └─ No changes needed
│
├─ Frontend Service (Next.js)
│  └─ Chat UI components
│
├─ PostgreSQL (Persistent)
│  └─ chat_sessions, chat_messages, users
│
├─ PostgreSQL (Ephemeral)
│  └─ documents, final_qa_items
│
└─ Redis
   └─ Embeddings, context, session cache
```

