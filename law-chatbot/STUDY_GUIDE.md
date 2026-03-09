# 📚 **Law Chatbot (LexBot) Study Guide**

## **What is LexBot?**
LexBot is an AI-powered legal assistant that answers questions about Indian laws using **RAG (Retrieval-Augmented Generation)**. It searches a vector database of law documents, retrieves relevant sections, and uses Groq's LLM (Llama 3.3) to explain legal concepts in simple language with proper citations.

**Key Features:**
- Ask legal questions in natural language
- Get answers with exact section/article citations
- Chat history with session management
- Upload custom PDF legal documents
- Scrape laws from online sources

---

## **🎯 Recommended Study Order**

### **PHASE 1: Foundation Layer (Start Here)**

#### **1. [backend/config.py](backend/config.py)**
**What it does:** Centralized configuration using environment variables

**Simple explanation:**
- Uses `pydantic-settings` to load from `.env` file
- **Key settings:**
  - `groq_api_key`: Your AI model access key
  - `qdrant_url`: Vector database URL (stores law embeddings)
  - `mongo_uri`: MongoDB for users, sessions, messages
  - `embedding_model`: Local model that converts text → numbers
  - `chunk_size`: How to split long documents (1000 chars)
  - `retrieval_top_k`: How many relevant chunks to retrieve (6)

**Key insight:** `@lru_cache` makes `get_settings()` a singleton (created once, reused everywhere)

---

#### **2. [backend/deps.py](backend/deps.py)**
**What it does:** Lazy initialization of expensive resources

**Simple explanation:**
Creates and caches connections to external services:
- **`get_llm_client()`**: Groq API client for AI responses
- **`get_qdrant_client()`**: Vector database (auto-creates collection if missing)
- **`get_mongo_client()` / `get_db()`**: MongoDB for chat data
- **`get_embeddings()`**: HuggingFace sentence-transformers model (runs **locally**, no API needed)
- **`get_vector_store()`**: LangChain wrapper around Qdrant

**Why lazy?**
- Import modules without Docker running
- Connect only when actually needed (saves startup time)

**Auto-bootstrap:**
- Creates `law_documents` Qdrant collection automatically (384-dim cosine vectors)

---

#### **3. [backend/main.py](backend/main.py)**
**What it does:** FastAPI application entry point

**Simple explanation:**
- Creates the FastAPI app
- Adds CORS middleware (lets Next.js frontend call the API)
- **Startup event:** Connects to Qdrant, MongoDB, Embeddings — prints ✓/✗ status
- **Registers routes:**
  - `/api/auth` → login/signup
  - `/api/chat` → ask questions, manage sessions
  - `/api/documents` → upload/list/delete PDFs
  - `/api/scraper` → fetch laws from URLs
- Health check at `/` → returns `{status: "ok"}`

**Entry point:** Run with `python -m backend.main`

---

### **PHASE 2: Data Models (Understanding the Structure)**

#### **4. [backend/schemas/chat.py](backend/schemas/chat.py)**
**What it does:** Defines the shape of chat data

**Simple explanation:**

**ChatRequest** (what user sends):
```python
{
  "question": "What are my rights if arrested?",
  "session_id": "uuid-or-null"  # null = start new chat
}
```

**ChatResponse** (what AI returns):
```python
{
  "answer": "Plain English explanation...",
  "citations": [
    {
      "section": "Section 41A",
      "act": "Criminal Procedure Code, 1973",
      "chapter": "Chapter V",
      "page": 25,
      "source": "CrPC.pdf",
      "relevance_score": 0.89
    }
  ],
  "confidence": 0.92,
  "disclaimer": "Not legal advice...",
  "related_questions": ["Can I refuse to answer?", "What is bail?"],
  "session_id": "abc-123"
}
```

**Key insight:** Structured responses ensure frontend can display citations nicely

---

#### **5. [backend/schemas/document.py](backend/schemas/document.py)**
**What it does:** Document metadata structure

**Simple explanation:**
Defines how uploaded PDFs are tracked:
- `doc_id`: Unique identifier
- `title`: Human-readable name
- `act_name`: Optional law name (for filtering)
- `source_type`: "pdf" or "scraped"
- `status`: "processing", "complete", "failed"
- `uploaded_at`: Timestamp

---

#### **6. [backend/schemas/auth.py](backend/schemas/auth.py)**
**What it does:** User authentication schemas

**Simple explanation:**
- **SignupRequest**: `{email, password, name}`
- **LoginRequest**: `{email, password}`
- **AuthResponse**: `{token, user: {id, email, name}}`

---

### **PHASE 3: Core Services (Business Logic)**

#### **7. [backend/services/vector_service.py](backend/services/vector_service.py)**
**What it does:** Search and manage law chunks in Qdrant

**Simple explanation:**

**Key function: `search_laws(query, k=6, act_name=None)`**
- Converts your question to a vector (embedding)
- Finds top-k most similar law chunks in Qdrant
- Optionally filters by `act_name` (e.g., only search IPC)
- Returns list of LangChain `Document` objects with metadata

**Example:**
```python
query = "What is murder?"
docs = search_laws(query, k=6)
# Returns: [
#   Document(page_content="Section 302. Murder...", 
#            metadata={act_name: "IPC", relevance_score: 0.91})
# ]
```

**Other functions:**
- `add_documents()`: Batch insert chunks
- `delete_document()`: Remove all chunks for a doc_id
- `collection_info()`: Get stats (total vectors, etc.)

**Why vector search?**
- **Semantic**: Finds concepts, not just keywords
- Example: "killing someone" matches "Section 302 Murder" even without exact words

---

#### **8. [backend/services/ingestion_service.py](backend/services/ingestion_service.py)**
**What it does:** PDF → Vector Database pipeline

**Simple explanation:**

**5-step process:**
1. **Load PDF**: Uses `PyPDFLoader` to extract text page-by-page
2. **Enrich metadata**: Adds `doc_id`, `title`, `act_name`, `page` number
3. **Split into chunks**: `RecursiveCharacterTextSplitter` (1000 chars, 200 overlap)
4. **Generate embeddings**: Convert text → 384-dim vectors
5. **Store in Qdrant**: Upsert to `law_documents` collection

**Two entry points:**
- `ingest_pdf(file_path, metadata)`: For local files (used by seed script)
- `ingest_uploaded_file(upload_file, title, act_name)`: For FastAPI uploads (saves to temp file first)

**MongoDB tracking:**
- Sets status to "processing" before ingestion
- Updates to "complete" or "failed" after

**Why chunking?**
- LLMs have token limits (can't process 200-page PDFs)
- Smaller chunks = more precise retrieval

---

#### **9. [backend/services/chat_service.py](backend/services/chat_service.py)**
**What it does:** The heart of the RAG system

**Simple explanation:**

**Full ask() flow (6 steps):**

1. **Create/validate session**
   - If no `session_id`, create new one
   - Auto-generate title from first question

2. **Retrieve relevant chunks**
   - Call `search_laws(question, k=6)`
   - Build context string with citations

3. **Load conversation history**
   - Fetch last 10 messages from MongoDB
   - Gives LLM memory of the conversation

4. **Build prompt**
   - System prompt: "You are LexBot... reply in JSON format"
   - History: Previous Q&A turns
   - User message: `CONTEXT: [retrieved chunks]\nQUESTION: [user question]`

5. **Call Groq LLM**
   - Model: `llama-3.3-70b-versatile`
   - Temperature: 0.2 (more focused, less creative)
   - Max tokens: 2048

6. **Parse JSON response**
   - Extract `answer`, `citations`, `confidence`, `related_questions`
   - Fallback if JSON parsing fails
   - Save Q&A to MongoDB

**System prompt magic:**
- Instructs LLM to cite sections
- Explain in plain language
- Return structured JSON (not prose)
- Always add disclaimer

---

#### **10. [backend/services/memory_service.py](backend/services/memory_service.py)**
**What it does:** Chat session and message persistence

**Simple explanation:**

**Session functions:**
- `create_session(user_id, title)`: New chat with UUID
- `list_sessions(user_id)`: All chats, newest first
- `delete_session(session_id, user_id)`: Remove session + all messages
- `auto_title_session(session_id, first_question)`: Smart naming (truncates long questions)

**Message functions:**
- `save_message(session_id, role, content, citations)`: Store user/assistant turns
- `get_history(session_id, limit=10)`: Load conversation context

**MongoDB collections:**
- `chat_sessions`: `{_id, user_id, title, created_at, message_count}`
- `messages`: `{session_id, role, content, citations, timestamp}`

**Why separate collections?**
- Fast session list queries (don't load all messages)
- Can delete old messages while keeping session metadata

---

#### **11. [backend/services/auth_service.py](backend/services/auth_service.py)**
**What it does:** User authentication with JWT

**Simple explanation:**

**Key functions:**
- `signup(email, password, name)`: Hash password (bcrypt), save to MongoDB
- `login(email, password)`: Verify password hash, return JWT token
- `get_current_user(token)`: Decode JWT → return user dict

**JWT structure:**
```python
{
  "sub": "user_id_here",
  "exp": 1234567890  # expires in 24h
}
```

**Security:**
- Passwords hashed with `bcrypt` (one-way, salted)
- Token signed with `jwt_secret` (set in `.env`)
- 24-hour token expiry

---

#### **12. [backend/services/scraper_service.py](backend/services/scraper_service.py)**
**What it does:** Fetch laws from public URLs

**Simple explanation:**
- Takes a URL (e.g., Wikipedia article on IPC)
- Uses `BeautifulSoup` to extract text
- Cleans HTML, extracts paragraphs
- Splits into chunks and stores in Qdrant

**Fallback strategy:**
- Try Wikipedia API first (less blocking)
- Fall back to direct scraping if API fails
- Handle rate limits gracefully

---

### **PHASE 4: API Routes (HTTP Endpoints)**

#### **13. [backend/routes/auth.py](backend/routes/auth.py)**
**What it does:** User authentication endpoints

**Endpoints:**
- `POST /api/auth/signup` → Create new user
- `POST /api/auth/login` → Get JWT token
- `GET /api/auth/me` → Get current user (requires token)

**Auth header format:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

#### **14. [backend/routes/chat.py](backend/routes/chat.py)**
**What it does:** Main chat interface

**Endpoints:**
- `POST /api/chat` → Ask a legal question (requires auth)
- `GET /api/chat/sessions` → List all user's chats
- `GET /api/chat/sessions/{id}` → Get full chat history
- `DELETE /api/chat/sessions/{id}` → Delete a chat
- `POST /api/chat/sessions` → Create empty session

**Example request:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Section 420 IPC?"}'
```

---

#### **15. [backend/routes/documents.py](backend/routes/documents.py)**
**What it does:** Document management

**Endpoints:**
- `POST /api/documents/upload` → Upload PDF (multipart/form-data)
- `GET /api/documents` → List all uploaded docs
- `DELETE /api/documents/{id}` → Delete doc and all chunks
- `GET /api/documents/stats` → Qdrant collection info

**Upload example:**
```python
# Frontend
const formData = new FormData()
formData.append('file', pdfFile)
formData.append('title', 'IPC 1860')
formData.append('act_name', 'Indian Penal Code')
```

**Delete cascade:**
- Removes MongoDB document record
- Removes all Qdrant chunks (by `doc_id` filter)

---

#### **16. [backend/routes/scraper.py](backend/routes/scraper.py)**
**What it does:** Scrape laws from URLs

**Endpoint:**
- `POST /api/scraper/scrape` → Fetch and ingest URL content

**Example:**
```json
{
  "url": "https://en.wikipedia.org/wiki/Indian_Penal_Code",
  "title": "IPC Overview",
  "act_name": "Indian Penal Code"
}
```

---

### **PHASE 5: Seed Script (Pre-populate Knowledge Base)**

#### **17. [scripts/seed_laws.py](scripts/seed_laws.py)**
**What it does:** Load 7 Indian laws into Qdrant on first run

**Simple explanation:**

**Seeded laws:**
1. Indian Penal Code (IPC), 1860
2. Criminal Procedure Code (CrPC), 1973
3. Indian Constitution
4. Right to Information Act, 2005
5. Consumer Protection Act, 2019
6. IT Act, 2000
7. Domestic Violence Act + Motor Vehicles Act

**Strategy:**
1. Try Wikipedia API fetch (more content)
2. Fallback to hardcoded sections (always works offline)
3. Create LangChain Documents with metadata
4. Chunk with RecursiveCharacterTextSplitter
5. Store in Qdrant + MongoDB

**Stable IDs:**
- Uses `uuid.uuid5(namespace, act_name)` for deterministic doc IDs
- Prevents duplicate ObjectId serialization issues
- Idempotent (can run multiple times safely)

**Run it:**
```bash
cd law-chatbot
python -m scripts.seed_laws
```

---

### **PHASE 6: Frontend (Next.js 14)**

#### **18. [frontend/lib/auth.tsx](frontend/lib/auth.tsx)**
**What it does:** React Context for authentication

**Simple explanation:**
- Stores user + token in React state
- Persists token to `localStorage` (survives page refresh)
- Provides `useAuth()` hook to all components
- Auto-fetches user on mount if token exists

**Usage:**
```tsx
const { user, login, logout } = useAuth()
if (user) {
  // Logged in
}
```

---

#### **19. [frontend/lib/api.ts](frontend/lib/api.ts)**
**What it does:** TypeScript API client

**Simple explanation:**
- Typed functions for all backend endpoints
- Automatically adds `Authorization: Bearer TOKEN` header
- Base URL: `process.env.NEXT_PUBLIC_API_URL` (defaults to localhost:8000)

**Example:**
```typescript
import { chatAPI } from '@/lib/api'

const response = await chatAPI.ask({
  question: "What is bail?",
  session_id: null
})
// response: ChatResponse type with answer, citations, etc.
```

---

#### **20. Frontend Pages**

**[frontend/app/page.tsx](frontend/app/page.tsx)** → Landing page

**[frontend/app/login/page.tsx](frontend/app/login/page.tsx)** → Login form

**[frontend/app/signup/page.tsx](frontend/app/signup/page.tsx)** → Signup form

**[frontend/app/chat/page.tsx](frontend/app/chat/page.tsx)** → Main chat interface
- Session sidebar (left)
- Message history (center)
- Input box (bottom)
- Citation cards (expandable)
- Related questions (clickable chips)

**[frontend/app/documents/page.tsx](frontend/app/documents/page.tsx)** → Document management
- Upload PDFs
- Enter URLs to scrape
- View uploaded docs
- Delete functionality

---

#### **21. Frontend Components**

**ChatMessage.tsx** → Single message bubble
- Different styling for user (blue, right) vs assistant (gray, left)
- Expandable citations
- Confidence badge (0-100%)
- Related questions chips

**CitationCard.tsx** → Legal citation display
- Section + Act name
- Chapter, page, source
- Relevance score progress bar
- Click to expand/collapse

**SessionSidebar.tsx** → Chat history sidebar
- List of sessions with titles
- Click to switch
- Delete button
- "New Chat" action

**DocumentUploader.tsx** → PDF upload UI
- Drag & drop zone
- Tab switcher (Upload PDF / Enter URL)
- Status indicators (idle/loading/success/error)
- Auto-fill title from filename

**Navbar.tsx** → Top navigation
- Logo, nav links
- User menu (profile, logout)
- Conditional rendering (logged in/out)

---

## **🔧 How It All Works Together**

### **Scenario: User Asks "What is Section 302 IPC?"**

1. **Frontend** sends `POST /api/chat`
   ```json
   {
     "question": "What is Section 302 IPC?",
     "session_id": null
   }
   ```

2. **Auth middleware** validates JWT token

3. **Chat route** calls `chat_service.ask()`

4. **Chat service**:
   - Creates new session (since `session_id` is null)
   - Calls `vector_service.search_laws("What is Section 302 IPC?", k=6)`

5. **Vector service**:
   - Converts question to 384-dim embedding
   - Searches Qdrant for top 6 similar chunks
   - Returns chunks with metadata (act_name, section, page)

6. **Chat service** (continued):
   - Builds context string from retrieved chunks
   - Loads conversation history (empty for new session)
   - Builds prompt: System + History + Context + User Question
   - Calls Groq API with Llama 3.3 model

7. **Groq LLM** generates JSON response:
   ```json
   {
     "answer": "Section 302 of the IPC deals with punishment for murder...",
     "citations": [{"section": "Section 302", "act": "IPC"}],
     "confidence": 0.95,
     "related_questions": ["What is culpable homicide?", "Death penalty laws?"]
   }
   ```

8. **Chat service**:
   - Parses JSON
   - Saves user + assistant messages to MongoDB
   - Returns structured response

9. **Frontend**:
   - Displays answer in ChatMessage component
   - Shows citation cards (expandable)
   - Renders related question chips
   - Updates session in sidebar

---

## **💡 Key Technologies Explained Simply**

| Technology | What It Does | Why We Use It |
|------------|-------------|---------------|
| **FastAPI** | Python web framework | Auto-generates docs, fast async |
| **Qdrant** | Vector database | Semantic search (meaning, not keywords) |
| **MongoDB** | Document database | Store users, sessions, messages |
| **Groq** | LLM API provider | Fast inference (Llama 3.3 70B) |
| **LangChain** | LLM framework | PDF loading, chunking, embeddings |
| **Sentence-Transformers** | Embedding model | Runs locally (no API cost) |
| **Next.js 14** | React framework | App Router, server components |
| **PyPDFLoader** | PDF parser | Extract text from legal documents |
| **bcrypt** | Password hashing | Secure one-way encryption |
| **JWT** | Token standard | Stateless authentication |

---

## **🎓 Study Tips**

1. **Start with the flow:** Read `chat_service.ask()` line by line — it ties everything together
2. **Understand RAG:** `search_laws() → build prompt → call LLM → return` is the core pattern
3. **Test with curl:** Call endpoints directly to see responses
   ```bash
   curl http://localhost:8000/api/chat/sessions \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```
4. **Add print statements:** See what's retrieved from Qdrant
5. **Run seed script:** Populate with real data before testing chat
6. **Inspect Qdrant:** Visit http://localhost:6333/dashboard to see vectors
7. **Check MongoDB:** Use MongoDB Compass to explore stored data

---

## **Common Questions**

**Q: What is RAG?**  
A: Retrieval-Augmented Generation = Search relevant docs + Send to LLM + Get grounded answer. Prevents hallucinations (LLM making up laws).

**Q: Why embeddings?**  
A: Convert text to numbers for similarity search. "murder" and "killing" have similar embeddings even with different words.

**Q: Why chunk documents?**  
A: LLMs can't read 1000-page PDFs. Chunks let us retrieve only relevant sections.

**Q: What if Qdrant is empty?**  
A: `search_laws()` returns `[]`, LLM gets "No context found" → replies "I don't have relevant documents to answer this."

**Q: Can I use this for other domains?**  
A: Yes! Replace law PDFs with medical textbooks, history docs, etc. The RAG pattern is universal.

**Q: Why Groq over OpenAI?**  
A: Groq is free (30 req/min), very fast inference, and works with Llama (open-source model).

---

## **📊 Project Structure Summary**

```
law-chatbot/
├── backend/
│   ├── config.py          ⚙️  Settings (API keys, DB URLs)
│   ├── deps.py            🔌 Lazy singletons (LLM, Qdrant, MongoDB)
│   ├── main.py            🚀 FastAPI app entry point
│   ├── schemas/           📋 Pydantic models (data shapes)
│   ├── services/          💼 Business logic
│   │   ├── chat_service.py       ❤️  RAG pipeline (core)
│   │   ├── vector_service.py     🔍 Qdrant search wrapper
│   │   ├── ingestion_service.py  📄 PDF → chunks → Qdrant
│   │   ├── memory_service.py     💾 Session/message CRUD
│   │   ├── auth_service.py       🔐 JWT auth
│   │   └── scraper_service.py    🌐 URL → text
│   └── routes/            🛣️  HTTP endpoints
├── frontend/              🎨 Next.js UI
│   ├── lib/
│   │   ├── auth.tsx       👤 React Context + useAuth()
│   │   └── api.ts         📡 Typed API client
│   ├── app/               📄 Pages (App Router)
│   └── components/        🧩 Reusable UI
├── scripts/
│   └── seed_laws.py       🌱 Pre-populate Qdrant
├── docker-compose.yml     🐳 Qdrant + MongoDB + Redis
├── requirements.txt       📦 Python deps
└── .env                   🔑 API keys + config
```

---

## **🚀 Quick Start Study Path**

**Day 1: Understand RAG Flow**
1. Read `backend/services/chat_service.py` (the `ask()` function)
2. Read `backend/services/vector_service.py` (`search_laws()`)
3. Trace: Question → Embeddings → Qdrant → LLM → Answer

**Day 2: Data Pipeline**
1. Read `backend/services/ingestion_service.py`
2. Read `scripts/seed_laws.py`
3. Understand: PDF → Pages → Chunks → Embeddings → Qdrant

**Day 3: API Layer**
1. Read `backend/main.py`
2. Read `backend/routes/chat.py`
3. Test endpoints with curl/Postman

**Day 4: Frontend**
1. Read `frontend/lib/api.ts`
2. Read `frontend/app/chat/page.tsx`
3. See how UI calls backend and renders responses

---

**Pro tip:** Start backend, run seed script, open frontend, and **trace a single question** through all layers using `print()` statements and browser DevTools. This is the fastest way to understand the full flow!

---

## **🛠️ Setup Instructions**

### **Prerequisites**
- Python 3.9+
- Node.js 18+
- Docker & Docker Compose

### **Backend Setup**
```bash
cd law-chatbot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start infrastructure
docker-compose up -d

# Seed the database
python -m scripts.seed_laws

# Run backend
python -m backend.main
```

### **Frontend Setup**
```bash
cd law-chatbot/frontend
npm install
npm run dev
```

### **Environment Variables**
Copy `.env.example` to `.env` and fill in:
```env
GROQ_API_KEY=your_key_here
MONGO_URI=mongodb://localhost:27017
QDRANT_URL=http://localhost:6333
JWT_SECRET=your_secret_here
```

---

## **📝 License**
This project is for educational purposes. Not intended for production use without proper legal review.

---

**Happy Learning! 🚀**
