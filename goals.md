# Hackathon RAG Demo: Book Intelligence System

## Overview
A demonstration RAG system that ingests books (cookbooks, novels) and answers natural language questions about their contents using semantic search and LLM-powered responses.

---

## Target Demo Queries

**Harry Potter (Novel):**
- "Can you please find chapters where a person has an encounter with Dumbledore?"
- "Which scenes involve the Forbidden Forest?"
- "Find moments where Harry uses a spell for the first time"

**Cookbook:**
- "Please find me two recipes that are soups"
- "What recipes can I make with chicken and under 30 minutes?"
- "Find vegetarian main dishes"

---

## System Architecture

### 1. Document Ingestion Pipeline

```
[Raw Book File] → [Text Extraction] → [Preprocessing] → [Chunking] → [Embedding] → [Vector DB]
```

**Supported Input Formats:**
- PDF
- EPUB
- Plain text (.txt)
- (Stretch) MOBI, DOCX

**Text Extraction:**
- PDF: `pypdf` or `pdfplumber`
- EPUB: `ebooklib`
- Handle encoding issues, strip artifacts

### 2. Preprocessing & Metadata Extraction

**For Novels:**
- Chapter detection (regex patterns for "Chapter X", "CHAPTER ONE", etc.)
- Scene/section boundaries
- Character mention tagging (optional but valuable)

**For Cookbooks:**
- Recipe boundary detection
- Extract structured fields:
  - Recipe name
  - Ingredients list
  - Cooking time
  - Serving size
  - Category/tags (soup, dessert, vegetarian, etc.)
  - Difficulty level

**Universal Metadata:**
- Source document name
- Page number / location
- Character offsets (start/end position for highlighting)
- Section/chapter identifier
- Chunk sequence number

### 3. Chunking Strategy (Chonkie)

**Chunking Approach:**
- Use semantic chunking to preserve meaning
- Respect natural boundaries (paragraphs, recipe blocks, chapters)
- Target chunk size: 512-1024 tokens (tunable)
- Overlap: 50-100 tokens for context continuity

**Chonkie Configuration:**
```python
from chonkie import SemanticChunker

chunker = SemanticChunker(
    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    chunk_size=512,
    similarity_threshold=0.5
)
```

**Alternative Chunkers to Consider:**
- `TokenChunker` for simpler use cases
- `SentenceChunker` for dialogue-heavy content
- `RecursiveChunker` for nested structures

### 4. Vector Database (Supabase)

**Schema Design:**

```sql
-- Main chunks table
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding VECTOR(384),  -- Dimension depends on embedding model
    
    -- Document metadata
    document_id UUID REFERENCES documents(id),
    document_name TEXT,
    document_type TEXT,  -- 'novel', 'cookbook'
    
    -- Location metadata
    chapter_number INTEGER,
    chapter_title TEXT,
    page_number INTEGER,
    chunk_index INTEGER,
    
    -- Content-specific metadata (JSONB for flexibility)
    metadata JSONB,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Parent documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    type TEXT,
    total_chunks INTEGER,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- Enable vector similarity search
CREATE INDEX ON document_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

**Metadata JSONB Examples:**

Novel:
```json
{
    "characters_mentioned": ["Dumbledore", "Harry", "Hagrid"],
    "location": "Hogwarts",
    "scene_type": "dialogue"
}
```

Cookbook:
```json
{
    "recipe_name": "Tomato Basil Soup",
    "category": "soup",
    "cuisine": "Italian",
    "cook_time_minutes": 45,
    "difficulty": "easy",
    "dietary": ["vegetarian", "vegan"],
    "main_ingredients": ["tomatoes", "basil", "onion"]
}
```

### 5. Embedding Generation

**Recommended Models:**
- `sentence-transformers/all-MiniLM-L6-v2` (384 dim, fast, good baseline)
- `text-embedding-3-small` (OpenAI, 1536 dim, higher quality)
- `nomic-embed-text` (768 dim, good open-source option)

**Implementation:**
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
embedding = model.encode(chunk_text)
```

### 6. Query Pipeline

```
[User Query] → [Query Embedding] → [Vector Search] → [Context Assembly] → [LLM] → [Response]
```

**Query Processing Steps:**

1. **Query Understanding**
   - Detect query type (search, summarize, compare)
   - Extract filters (chapter, recipe type, etc.)
   
2. **Hybrid Search** (recommended)
   - Vector similarity search (semantic)
   - Keyword/metadata filtering (exact matches)
   - Combine scores for ranking

3. **Context Assembly**
   - Retrieve top-k chunks (k=5-10)
   - Include surrounding context if needed
   - Format with metadata for LLM

4. **LLM Response Generation**
   - System prompt with task context
   - Retrieved chunks as context
   - Generate natural language answer with citations

### 7. LLM Integration

**Prompt Template:**
```
You are a helpful assistant answering questions about books.

DOCUMENT TYPE: {document_type}
DOCUMENT NAME: {document_name}

RELEVANT PASSAGES:
{formatted_chunks_with_metadata}

USER QUESTION: {query}

Instructions:
- Answer based ONLY on the provided passages
- Cite specific chapters/recipes/page numbers
- If information is not in the passages, say so
- For recipes, include key details (ingredients, time)
- For novels, include chapter context
```

**Model Options:**
- Claude (recommended for quality)
- GPT-4 / GPT-3.5
- Local: Llama 3, Mistral

---

## Components Checklist

### Must Have (MVP)
- [ ] Text extraction from PDF/TXT
- [ ] Basic chunking with Chonkie
- [ ] Supabase vector table setup
- [ ] Embedding generation
- [ ] Vector similarity search
- [ ] LLM response generation
- [ ] Simple CLI or web interface
- [ ] Open original PDF to source page with highlighted text

### Should Have
- [ ] Chapter/recipe metadata extraction
- [ ] Hybrid search (vector + keyword)
- [ ] Source citations in responses
- [ ] Multiple document support
- [ ] Query type detection

### Nice to Have
- [ ] EPUB support
- [ ] Character/entity extraction for novels
- [ ] Ingredient parsing for cookbooks
- [ ] Conversation memory
- [ ] Re-ranking with cross-encoder
- [ ] Streaming responses

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Chunking | Chonkie |
| Vector DB | Supabase (pgvector) |
| Embeddings | sentence-transformers / OpenAI |
| LLM | Claude API / OpenAI |
| Backend | Python (FastAPI or Flask) |
| Frontend | Streamlit (quick demo) or React |
| File Parsing | pypdf, ebooklib |
| PDF Viewer | pdf.js (web) or PyMuPDF (highlighting) |

---

## PDF Navigation & Highlighting

**Implementation Approach:**

1. **Store position data during ingestion:**
   ```python
   # When chunking, capture page + character positions
   chunk_metadata = {
       "page_number": 42,
       "start_char": 1250,
       "end_char": 1890,
       "bounding_boxes": [...]  # Optional: pixel coordinates
   }
   ```

2. **Navigation options:**
   - **Web (pdf.js):** Open PDF to page, use text search or annotations to highlight
   - **Desktop:** Generate URL with page anchor: `file.pdf#page=42`
   - **PyMuPDF:** Programmatically add highlight annotations to PDF

3. **Highlighting methods:**
   - Text layer highlight via pdf.js `textLayer` API
   - Add annotation overlays at stored bounding boxes
   - Generate a new PDF with highlights baked in (PyMuPDF)

**Quick Demo Option:**
```python
import fitz  # PyMuPDF

def highlight_and_open(pdf_path, page_num, search_text):
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]
    text_instances = page.search_for(search_text)
    for inst in text_instances:
        page.add_highlight_annot(inst)
    highlighted_path = "highlighted_output.pdf"
    doc.save(highlighted_path)
    return highlighted_path
```

---

## Demo Flow

1. **Upload** → User uploads a book (PDF/TXT)
2. **Process** → System extracts, chunks, embeds, stores
3. **Query** → User asks natural language question
4. **Retrieve** → Vector search finds relevant chunks
5. **Generate** → LLM synthesizes answer with citations
6. **Display** → Show answer + source passages
7. **Navigate** → User clicks result to open original page with text highlighted

---

## Key Considerations

### What Could Go Wrong
- **Poor chunk boundaries**: Recipe split mid-ingredients, chapter context lost
- **Metadata extraction failures**: Regex misses chapter formats
- **Embedding quality**: Generic embeddings miss domain nuance
- **Context window limits**: Too many chunks overflow LLM context

### Mitigations
- Test chunking on actual book samples early
- Build flexible metadata extractors with fallbacks
- Consider domain-specific or fine-tuned embeddings
- Implement smart context selection/summarization

---

## Success Criteria

The demo succeeds if it can:

1. ✅ Ingest a Harry Potter book and answer: "Find chapters where someone encounters Dumbledore" with correct chapter citations

2. ✅ Ingest a cookbook and answer: "Find me two soup recipes" returning actual recipe names and brief descriptions

3. ✅ Handle follow-up questions about retrieved content

---

## Sample Code Structure

```
hackathon-rag/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI/Streamlit entry
│   ├── ingest.py            # Document processing pipeline
│   ├── chunker.py           # Chonkie configuration
│   ├── embeddings.py        # Embedding generation
│   ├── database.py          # Supabase client
│   ├── search.py            # Query + retrieval logic
│   ├── llm.py               # LLM integration
│   ├── prompts.py           # Prompt templates
│   └── pdf_viewer.py        # Page navigation + highlighting
├── extractors/
│   ├── novel.py             # Novel-specific metadata
│   └── cookbook.py          # Recipe extraction
├── config.py
├── requirements.txt
└── README.md
```

---

## Notes

- Start with a small test file (single chapter, 5 recipes) before full book
- Log everything during hackathon for debugging
- Have fallback prompts if structured extraction fails
- Pre-chunk a book beforehand if ingestion is slow for demo
