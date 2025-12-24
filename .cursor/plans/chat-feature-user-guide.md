# Chat with Deposition - User Guide

## 🎯 Overview

The "Chat with Deposition" feature allows you to ask natural language questions about your deposition transcripts. Our AI assistant analyzes the entire deposition and provides accurate answers with citations to specific page and line numbers.

---

## 🚀 Getting Started

### Accessing Chat

1. Upload and process your deposition as usual
2. Navigate to the Results page (PDF viewer + summaries)
3. Click the **"Chat"** button in the top navigation bar
4. A chat panel will open on the right side of your screen

### Starting a Conversation

1. Type your question in the input field at the bottom
2. Press **Enter** or click **Send**
3. The AI will analyze the deposition and respond with citations
4. Click any citation to jump to that location in the PDF

---

## 💬 What You Can Ask

### General Questions

Ask about facts, events, or testimony from the deposition:

**Examples:**
- "What did the witness say about the accident?"
- "Where did the collision occur?"
- "What was the witness doing at the time of the incident?"
- "Who was present at the meeting?"

### Timeline Questions

Get information about when events occurred:

**Examples:**
- "What happened in March 2020?"
- "Create a timeline of events leading to the accident"
- "When did the witness first notice the problem?"
- "What is the sequence of events described?"

### Credibility Analysis

Identify potential credibility issues:

**Examples:**
- "Did the witness contradict themselves?"
- "Where is the testimony inconsistent?"
- "What did the witness say they don't recall?"
- "Find evasive answers"

### Special Queries

Use specific commands for targeted analysis:

**Examples:**
- "When did the attorney instruct the witness not to answer?"
- "Find all breaks in testimony"
- "When did the witness correct their testimony?"
- "What are good areas for cross-examination?"

---

## 📍 Understanding Citations

### Citation Format

Citations appear as clickable chips: **[Page 5, Line 12]**

Each citation includes:
- **Page number**: The printed page number in the transcript
- **Line number**: The line number on that page
- **Text snippet**: A brief quote from the testimony

### Clicking Citations

1. Click any citation chip in the AI's response
2. The PDF viewer automatically scrolls to that page
3. The specific line is highlighted
4. The summary panel updates to show that Q&A pair

---

## 🔍 Advanced Features

### Conflict Detection

Ask: **"Did the witness give conflicting testimony?"**

The AI will:
- Compare statements throughout the deposition
- Identify contradictions
- Provide citations for each conflicting statement
- Explain the nature of the conflict

**Example Response:**
```
Yes, the witness gave conflicting testimony regarding the time of the incident.

On page 12, line 8, they stated: "The accident happened around 3 PM"
[Page 12, Line 8]

However, on page 45, line 15, they testified: "I believe it was closer to 5 PM"
[Page 45, Line 15]

This 2-hour discrepancy could be important for establishing timeline credibility.
```

---

### Refusal to Answer Detection

Ask: **"When did the attorney instruct the witness not to answer?"**

The AI will locate all instances where:
- Defense counsel objected
- Witness was instructed not to answer
- Questions were deemed outside scope

**Example Response:**
```
The defending attorney instructed the witness not to answer on 3 occasions:

1. Page 23, Line 5 - Question about confidential business information
[Page 23, Line 5]

2. Page 67, Line 12 - Question about attorney-client communications
[Page 67, Line 12]

3. Page 89, Line 3 - Question deemed outside the scope of discovery
[Page 89, Line 3]
```

---

### Break Detection

Ask: **"Find all breaks in testimony"**

Useful for:
- Understanding deposition timeline
- Identifying potential coaching opportunities
- Noting changes in testimony after breaks

**Example Response:**
```
There were 4 breaks during the deposition:

1. Page 15, Line 20 - Lunch break (12:00 PM - 1:00 PM)
2. Page 34, Line 8 - Short recess (15 minutes)
3. Page 58, Line 14 - Break requested by witness
4. Page 76, Line 2 - End of day (resumed next morning)
```

---

### Correction Detection

Ask: **"When did the witness correct their testimony?"**

Identifies where witness:
- Corrected previous statements
- Clarified earlier answers
- Changed their testimony

**Example Response:**
```
The witness made corrections on 2 occasions:

1. Page 28, Line 10 - Corrected the date from "June 5th" to "June 15th"
[Page 28, Line 10]

2. Page 52, Line 7 - Clarified that it was the "left lane" not "right lane"
[Page 52, Line 7]
```

---

### Cross-Examination Suggestions

Ask: **"What are good areas for cross-examination?"**

The AI analyzes:
- Weak or uncertain answers
- Evasive responses
- "I don't recall" statements
- Inconsistencies
- Lack of personal knowledge

**Example Response:**
```
Several areas offer opportunities for effective cross-examination:

1. MEMORY ISSUES (Pages 34-36)
The witness claimed "I don't recall" 8 times regarding key meetings in March.
[Page 34, Line 5] [Page 35, Line 12] [Page 36, Line 8]

2. INCONSISTENT TIMELINE (Pages 12 & 45)
Testified to different times for the same event (see conflict analysis above).

3. LACK OF PERSONAL KNOWLEDGE (Page 67)
Admitted they "heard from someone else" about critical incident details.
[Page 67, Line 15]

4. EVASIVE ON DAMAGES (Pages 78-80)
Repeatedly avoided direct answers about extent of injuries.
[Page 78, Line 3] [Page 79, Line 22]
```

---

## 💾 Chat Sessions

### Managing Sessions

Each document can have multiple chat sessions:

**Create New Session:**
- Click "New Chat" button
- Previous chat is saved automatically

**Switch Sessions:**
- Click "Chat History" dropdown
- Select previous session to resume

**Rename Session:**
- Click edit icon next to session title
- Give it a descriptive name (e.g., "Timeline Questions")

**Delete Session:**
- Click delete icon
- Confirm deletion

### Session Persistence

- Chat sessions are saved permanently
- Access past conversations anytime
- Sessions tied to specific documents

---

## 🎨 UI Tips

### Side Panel Layout

```
┌─────────────────────────────────────────┐
│  [← Back]  Deposition: John Doe   Chat │
├──────────────────────┬──────────────────┤
│                      │  💬 Chat Panel   │
│   PDF Viewer         │                  │
│                      │  User: What...   │
│   [Page 5]           │                  │
│                      │  AI: Based on... │
│   Summary Panel      │  [Page 5:12]     │
│                      │                  │
│                      │  [Type here...]  │
└──────────────────────┴──────────────────┘
```

**Benefits:**
- View PDF and chat simultaneously
- Citations jump to PDF location
- Seamless workflow

### Keyboard Shortcuts

- **Enter**: Send message
- **Shift + Enter**: New line in message
- **Esc**: Close chat panel
- **Ctrl/Cmd + K**: Open chat (from anywhere in app)

---

## ⚡ Best Practices

### Writing Effective Questions

**✅ Good Questions:**
- Specific and clear
- Focused on one topic
- Use proper context

Examples:
- "What did the witness say about the speed of the vehicle?"
- "Summarize testimony about events on March 15, 2020"

**❌ Avoid:**
- Too broad or vague
- Multiple unrelated questions
- Requests outside the deposition content

Examples:
- "Tell me everything" (too broad)
- "What happened and who was there and when?" (multiple questions)

### Using Citations Effectively

1. **Verify Citations**: Always click citations to verify context
2. **Note Multiple Sources**: AI may cite several locations for one fact
3. **Check Full Context**: Read surrounding Q&A for complete picture
4. **Copy Citations**: Use citations in your legal briefs or notes

### Iterative Questioning

Build on previous answers:

```
You: "What did witness say about brakes?"
AI: "Witness testified brakes were checked in March..."

You: "Were they checked again after that?"
AI: "Yes, on page 67 witness mentions second check..."

You: "What were the results of that check?"
AI: "The second inspection revealed..."
```

---

## 🔒 Privacy & Security

### Data Protection

- All chats are private to your account
- No one else can see your questions or chat history
- Chats deleted when session is deleted

### AI Processing

- Your questions are processed by OpenAI GPT-4
- Deposition content is sent securely for analysis
- No data is retained by OpenAI after processing
- Compliant with legal confidentiality requirements

---

## 💰 Cost Information

### Usage Costs

Each chat message costs approximately:
- **$0.03 - $0.06** per message
- Caching reduces costs for repeated queries
- Costs included in your subscription

### Cost Optimization Tips

1. **Ask Specific Questions**: Focused queries use fewer tokens
2. **Use Special Commands**: Pre-built queries are optimized
3. **Review Summaries First**: May answer question without chat

---

## 🐛 Troubleshooting

### Common Issues

**Chat not loading**
- Refresh the page
- Check internet connection
- Ensure document processing completed

**Citations not working**
- PDF must be fully loaded
- Try clicking citation again
- Refresh page if persistent

**Slow responses**
- First query takes longer (loads context)
- Subsequent queries are faster (cached)
- Complex analysis queries take more time

**AI doesn't understand question**
- Rephrase more specifically
- Provide more context
- Break into smaller questions

### Getting Help

Contact support if:
- Chat feature not working after refresh
- Citations consistently incorrect
- AI responses seem inaccurate
- Technical errors persist

---

## 📊 Example Workflows

### Trial Preparation Workflow

1. **Initial Review**: "Summarize the witness's main testimony"
2. **Identify Weaknesses**: "Find all instances of 'I don't recall'"
3. **Check Consistency**: "Did the witness contradict themselves?"
4. **Cross-Exam Prep**: "What are good areas for cross-examination?"
5. **Document Review**: Click all citations to review source material

### Discovery Review Workflow

1. **Timeline**: "Create a timeline of events"
2. **Key Facts**: "What does witness say about [specific issue]?"
3. **Corroboration**: "Who else was present at these events?"
4. **Gaps**: "What topics did witness refuse to answer about?"

### Settlement Evaluation Workflow

1. **Damages**: "What did witness say about injuries/damages?"
2. **Liability**: "What admissions did witness make?"
3. **Weaknesses**: "Where is the testimony inconsistent?"
4. **Strategy**: "What are the strongest and weakest points?"

---

## 🎓 Tips from Legal Experts

### Maximizing Chat Value

1. **Start Broad, Then Narrow**: Begin with overview questions, drill down to specifics
2. **Cross-Reference Citations**: Use citations to build deposition index
3. **Save Important Exchanges**: Copy/paste key Q&A into notes
4. **Combine with Manual Review**: AI supplements, doesn't replace, careful reading
5. **Use for Deposition Prep**: Prepare questions for future depositions

### Common Use Cases

- **Impeachment**: Find prior inconsistent statements
- **Timeline Creation**: Build chronological narrative
- **Issue Spotting**: Identify areas needing follow-up discovery
- **Witness Prep**: Prepare your witnesses for similar questioning
- **Brief Writing**: Quickly locate supporting testimony

---

**Questions or Feedback?**

Contact support: support@depodigest.com

Or use the in-app feedback button to report issues or suggest improvements.

