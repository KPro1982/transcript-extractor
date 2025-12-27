# Database Schema Documentation
## Fact Atom Based Architecture - Contradiction Detection MVP

**Documented:** 2025-12-26
**Purpose:** Rollback reference for database structure restoration
**Architecture:** Fact Atom Based Architecture with claim extraction and contradiction detection

---

## Ephemeral Database Schema
**Database:** `depodigest_ephemeral` (or Railway auto-generated name)
**Purpose:** Transcript/document data that can be cleared without losing user data

### Tables

### `documents`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `filename` | character varying(255) | NO | | PDF filename |
| `file_hash` | character varying(64) | NO | | SHA256 hash (unique) |
| `s3_key` | character varying(500) | NO | | S3 storage key |
| `total_pages` | integer | NO | | Total pages in PDF |
| `case_name` | text | YES | | Case name |
| `case_number` | character varying(100) | YES | | Case number |
| `deposition_date` | character varying(50) | YES | | Deposition date |
| `attorneys` | text[] | YES | | Array of attorney names |
| `witness_name` | character varying(255) | YES | | Witness/deponent name |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |

**Primary Key:** `id`

**Indexes:**
- `idx_documents_file_hash`: ON documents(file_hash)

---

### `qa_items`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `document_id` | uuid | NO | | Foreign key to documents |
| `page_number` | integer | NO | | Page number (printed) |
| `line_number` | integer | NO | | Line number |
| `pdf_page_index` | integer | YES | | PDF page index (1-based) |
| `answer_end_page` | integer | YES | | End page for cross-page answers |
| `answer_end_line` | integer | YES | | End line for cross-page answers |
| `is_final` | boolean | YES | TRUE | Final Q&A vs interim/variable |
| `question` | text | NO | | Question text |
| `answer` | text | NO | | Answer text |
| `summary` | text | YES | | AI-generated summary |
| `topic` | character varying(255) | YES | | Topic category |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `document_id` → documents(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)

**Indexes:**
- `idx_qa_items_document_id`: ON qa_items(document_id)
- `idx_qa_items_is_final`: ON qa_items(document_id, is_final)

---

### `final_qa_items`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `document_id` | uuid | NO | | Foreign key to documents |
| `page_number` | integer | NO | | Page number (printed) |
| `line_number` | integer | NO | | Line number |
| `pdf_page_index` | integer | YES | | PDF page index (1-based) |
| `answer_end_page` | integer | YES | | End page for cross-page answers |
| `answer_end_line` | integer | YES | | End line for cross-page answers |
| `question` | text | NO | | Question text |
| `answer` | text | NO | | Answer text |
| `summary` | text | YES | '' | AI-generated summary |
| `topics` | text[] | YES | ARRAY['Other']::TEXT[] | Array of topic categories |
| `event_date` | character varying(50) | YES | | Extracted event date |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `document_id` → documents(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)

**Indexes:**
- `idx_final_qa_items_document_id`: ON final_qa_items(document_id)
- `idx_final_qa_items_page_line`: ON final_qa_items(document_id, page_number, line_number)

---

### `claims`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `document_id` | uuid | NO | | Foreign key to documents |
| `qa_item_id` | uuid | YES | | Foreign key to final_qa_items |
| `subject` | text | NO | | Subject of claim (who/what) |
| `predicate` | text | NO | | Predicate/action |
| `object` | text | YES | | Object of claim |
| `time` | character varying(255) | YES | | Temporal context |
| `location` | text | YES | | Location context |
| `polarity` | character varying(50) | YES | | positive/negative/uncertain |
| `certainty` | integer | YES | | 0-100 confidence level |
| `modality` | character varying(50) | YES | | certain/maybe/dont_recall |
| `scope` | jsonb | YES | | JSON with qualifications |
| `explicit_date` | character varying(255) | YES | | Explicitly stated date |
| `inferred_date` | character varying(255) | YES | | Inferred/relative date |
| `date_source` | character varying(50) | YES | | explicit/inferred/relative_to_anchor/none |
| `date_anchor` | character varying(255) | YES | | Reference point for relative dates |
| `page_number` | integer | NO | | Page number |
| `line_number` | integer | NO | | Line number |
| `answer_end_page` | integer | YES | | End page |
| `answer_end_line` | integer | YES | | End line |
| `raw_quote` | text | NO | | Original Q&A text |
| `normalized_subject` | text | YES | | Normalized subject for matching |
| `normalized_object` | text | YES | | Normalized object for matching |
| `event_id` | character varying(255) | YES | | Event cluster identifier |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `document_id` → documents(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)
- `qa_item_id` → final_qa_items(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)

**Constraints:**
- `claims_certainty_check` (CHECK): certainty >= 0 AND certainty <= 100

**Indexes:**
- `idx_claims_document`: ON claims(document_id)
- `idx_claims_qa_item`: ON claims(qa_item_id)
- `idx_claims_subject_predicate`: ON claims(document_id, subject, predicate)
- `idx_claims_event`: ON claims(document_id, event_id)
- `idx_claims_normalized_subject`: ON claims(document_id, normalized_subject)
- `idx_claims_explicit_date`: ON claims(document_id, explicit_date)
- `idx_claims_inferred_date`: ON claims(document_id, inferred_date)

---

### `claim_entities`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `claim_id` | uuid | NO | | Foreign key to claims |
| `entity_type` | character varying(50) | NO | | person/location/time/object |
| `entity_value` | text | NO | | Original entity value |
| `normalized_value` | text | YES | | Normalized value for matching |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `claim_id` → claims(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)

**Indexes:**
- `idx_claim_entities_claim`: ON claim_entities(claim_id)
- `idx_claim_entities_type`: ON claim_entities(entity_type)
- `idx_claim_entities_normalized`: ON claim_entities(normalized_value)

---

### `contradictions`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `document_id` | uuid | NO | | Foreign key to documents |
| `claim_a_id` | uuid | NO | | Foreign key to claims (first claim) |
| `claim_b_id` | uuid | NO | | Foreign key to claims (second claim) |
| `contradiction_type` | character varying(100) | NO | | direct_negation/mutually_exclusive/quantity_conflict/memory_drift/scope_mismatch |
| `severity` | integer | YES | | 0-100 severity score |
| `confidence` | integer | YES | | 0-100 confidence score |
| `explanation` | text | YES | | Explanation of contradiction |
| `requires_human_review` | boolean | YES | FALSE | Flag for manual review |
| `suggested_followups` | text[] | YES | | Array of impeachment questions |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `document_id` → documents(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)
- `claim_a_id` → claims(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)
- `claim_b_id` → claims(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)

**Constraints:**
- `contradictions_severity_check` (CHECK): severity >= 0 AND severity <= 100
- `contradictions_confidence_check` (CHECK): confidence >= 0 AND confidence <= 100

**Indexes:**
- `idx_contradictions_document`: ON contradictions(document_id)
- `idx_contradictions_severity`: ON contradictions(document_id, severity DESC)
- `idx_contradictions_type`: ON contradictions(document_id, contradiction_type)
- `idx_contradictions_claim_a`: ON contradictions(claim_a_id)
- `idx_contradictions_claim_b`: ON contradictions(claim_b_id)

---

### `summary_cache`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `content_hash` | character varying(64) | NO | | Primary key (SHA256 hash) |
| `summary` | text | NO | | Cached summary |
| `topic` | character varying(255) | YES | | Topic category |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |
| `last_accessed` | timestamp without time zone | YES | NOW() | Last access timestamp |

**Primary Key:** `content_hash`

**Indexes:**
- `idx_summary_cache_last_accessed`: ON summary_cache(last_accessed)

---

### `people_mentioned`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `document_id` | uuid | NO | | Foreign key to documents |
| `normalized_name` | character varying(255) | NO | | Normalized name for matching |
| `display_name` | character varying(255) | NO | | Display name |
| `role` | character varying(50) | YES | | Role (witness/attorney/etc) |
| `context` | text | YES | | Context of mention |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `document_id` → documents(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)

**Constraints:**
- `people_mentioned_document_id_normalized_name_key` (UNIQUE): (document_id, normalized_name)

**Indexes:**
- `idx_people_mentioned_document`: ON people_mentioned(document_id)
- `idx_people_mentioned_normalized`: ON people_mentioned(normalized_name)

---

### `qa_people`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `qa_item_id` | uuid | NO | | Foreign key to final_qa_items |
| `people_id` | uuid | NO | | Foreign key to people_mentioned |
| `mention_context` | text | YES | | Context of mention in Q&A |

**Primary Key:** (qa_item_id, people_id)

**Foreign Keys:**
- `qa_item_id` → final_qa_items(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)
- `people_id` → people_mentioned(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)

**Indexes:**
- `idx_qa_people_qa`: ON qa_people(qa_item_id)
- `idx_qa_people_person`: ON qa_people(people_id)

---

### `processing_jobs`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `document_id` | uuid | NO | | Foreign key to documents |
| `status` | character varying(50) | NO | | Job status |
| `progress` | integer | YES | 0 | Progress percentage |
| `error_message` | text | YES | | Error message if failed |
| `started_at` | timestamp without time zone | YES | | Start timestamp |
| `completed_at` | timestamp without time zone | YES | | Completion timestamp |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |
| `num_chunks` | integer | YES | 1 | Number of chunks for parallel processing |
| `is_chunked` | boolean | YES | FALSE | Whether job is chunked |

**Primary Key:** `id`

**Foreign Keys:**
- `document_id` → documents(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)

**Indexes:**
- `idx_processing_jobs_document_id`: ON processing_jobs(document_id)
- `idx_processing_jobs_status`: ON processing_jobs(status)

---

### `chunk_jobs`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `parent_job_id` | uuid | NO | | Foreign key to processing_jobs |
| `document_id` | uuid | NO | | Foreign key to documents |
| `chunk_index` | integer | NO | | Chunk index (0-based) |
| `worker_id` | integer | YES | | Worker ID (0, 1, or 2) |
| `first_page` | integer | NO | | First page of chunk |
| `last_page` | integer | YES | | Last page of chunk |
| `status` | character varying(50) | NO | | Chunk status |
| `progress` | integer | YES | 0 | Progress percentage |
| `error_message` | text | YES | | Error message if failed |
| `items_processed` | integer | YES | 0 | Number of items processed |
| `retry_count` | integer | YES | 0 | Retry count |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |
| `started_at` | timestamp without time zone | YES | | Start timestamp |
| `completed_at` | timestamp without time zone | YES | | Completion timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `parent_job_id` → processing_jobs(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)
- `document_id` → documents(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)

**Constraints:**
- `chunk_jobs_parent_job_id_chunk_index_key` (UNIQUE): (parent_job_id, chunk_index)

**Indexes:**
- `idx_chunk_jobs_parent`: ON chunk_jobs(parent_job_id)
- `idx_chunk_jobs_status`: ON chunk_jobs(status)
- `idx_chunk_jobs_document`: ON chunk_jobs(document_id)

---

## Persistent Database Schema
**Database:** `depodigest_persistent` (or Railway auto-generated name)
**Purpose:** User data, authentication, settings, feedback (NEVER cleared)

### Tables

### `users`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `email` | character varying(255) | NO | | Email (unique) |
| `name` | character varying(255) | YES | | Full name |
| `picture` | text | YES | | Profile picture URL |
| `is_admin` | boolean | YES | FALSE | Admin flag |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |
| `updated_at` | timestamp without time zone | YES | NOW() | Update timestamp |

**Primary Key:** `id`

**Constraints:**
- `users_email_key` (UNIQUE): (email)

**Indexes:**
- `idx_users_email`: ON users(email)

---

### `sessions`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `user_id` | uuid | NO | | Foreign key to users |
| `refresh_token` | text | NO | | JWT refresh token |
| `expires_at` | timestamp without time zone | NO | | Expiration timestamp |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `user_id` → users(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)

**Indexes:**
- `idx_sessions_user_id`: ON sessions(user_id)
- `idx_sessions_refresh_token`: ON sessions(refresh_token)
- `idx_sessions_expires_at`: ON sessions(expires_at)

---

### `bug_reports`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `user_id` | uuid | YES | | Foreign key to users |
| `title` | character varying(255) | NO | | Report title |
| `description` | text | NO | | Report description |
| `status` | character varying(50) | YES | 'open' | Status (open/closed/resolved) |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |
| `updated_at` | timestamp without time zone | YES | NOW() | Update timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `user_id` → users(id) (ON UPDATE NO ACTION, ON DELETE SET NULL)

**Indexes:**
- `idx_bug_reports_user_id`: ON bug_reports(user_id)
- `idx_bug_reports_status`: ON bug_reports(status)

---

### `chat_messages`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `bug_report_id` | uuid | YES | | Foreign key to bug_reports |
| `user_id` | uuid | YES | | Foreign key to users |
| `message` | text | NO | | Message text |
| `is_admin` | boolean | YES | FALSE | Admin message flag |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `bug_report_id` → bug_reports(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)
- `user_id` → users(id) (ON UPDATE NO ACTION, ON DELETE SET NULL)

**Indexes:**
- `idx_chat_messages_bug_report`: ON chat_messages(bug_report_id)
- `idx_chat_messages_user_id`: ON chat_messages(user_id)

---

### `learning_feedback`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `user_id` | uuid | YES | | Foreign key to users |
| `document_id` | uuid | YES | | Document UUID (not FK) |
| `qa_item_id` | uuid | YES | | Q&A item UUID (not FK) |
| `original_summary` | text | NO | | Original AI summary |
| `corrected_summary` | text | NO | | User-corrected summary |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `user_id` → users(id) (ON UPDATE NO ACTION, ON DELETE SET NULL)

**Indexes:**
- `idx_learning_feedback_user_id`: ON learning_feedback(user_id)
- `idx_learning_feedback_document_id`: ON learning_feedback(document_id)

---

### `user_prompt_settings`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `user_id` | uuid | NO | | Foreign key to users |
| `preset_options` | jsonb | YES | | JSON with toggle options |
| `custom_instructions` | text | YES | | Custom prompt instructions |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |
| `updated_at` | timestamp without time zone | YES | NOW() | Update timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `user_id` → users(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)

**Constraints:**
- `user_prompt_settings_user_id_key` (UNIQUE): (user_id)

**Indexes:**
- `idx_user_prompt_settings_user_id`: ON user_prompt_settings(user_id)

---

### `notifications`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `user_id` | uuid | NO | | Foreign key to users |
| `title` | character varying(255) | NO | | Notification title |
| `message` | text | NO | | Notification message |
| `type` | character varying(50) | YES | 'info' | Notification type |
| `read` | boolean | YES | FALSE | Read flag |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |

**Primary Key:** `id`

**Foreign Keys:**
- `user_id` → users(id) (ON UPDATE NO ACTION, ON DELETE CASCADE)

**Indexes:**
- `idx_notifications_user_id`: ON notifications(user_id)
- `idx_notifications_read`: ON notifications(user_id, read)

---

### `processing_metrics`
**Type:** BASE TABLE

**Columns:**

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `total_pages` | integer | NO | | Total pages processed |
| `total_processing_time_seconds` | numeric | NO | | Processing time |
| `avg_time_per_page` | numeric | NO | | Average time per page |
| `created_at` | timestamp without time zone | YES | NOW() | Creation timestamp |

**Primary Key:** `id`

---

## Restoration Instructions

To restore the database structure to this state:

1. **Connect to Railway databases** using Railway CLI or dashboard
2. **Run the SQL CREATE statements** from `backend/services/db_service.py`:
   - Ephemeral database: `init_db()` function (lines 103-570)
   - Persistent database: `init_persistent_db()` function (lines 572-764)
3. **Verify indexes** are created correctly
4. **Check constraints** match documented structure

### Quick Restore Commands

```bash
# Connect to ephemeral database
railway connect --service depodigest-ephemeral

# Connect to persistent database  
railway connect --service depodigest-persistent

# Run schema initialization
# (The db_service.py init functions will create all tables)
```

### Key Schema Features

**Fact Atom Based Architecture:**
- `claims` table: Atomic facts extracted from Q&A pairs
- `claim_entities` table: Entity tracking for coreference resolution
- `contradictions` table: Detected contradictions between claims

**Date Provenance:**
- `explicit_date`: Dates explicitly stated in testimony
- `inferred_date`: Dates inferred from context
- `date_source`: How date was determined (explicit/inferred/relative_to_anchor/none)
- `date_anchor`: Reference point for relative dates

**Multi-Transcript Ready:**
- Schema designed for future cross-document contradiction detection
- Normalized entity fields enable matching across transcripts
- Event clustering supports cross-document event matching

---

## Notes

- This schema represents the **Fact Atom Based Architecture** state
- Includes new tables: `claims`, `claim_entities`, `contradictions`
- Date provenance fields enable temporal reasoning
- Designed for future multi-transcript contradiction detection
- All foreign keys use CASCADE delete for data cleanup
- Indexes optimized for contradiction detection queries


