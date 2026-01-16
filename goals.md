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
- [ ] Basic chunking with Chonkie (recipe-aware for cookbook)
- [ ] Supabase vector table setup
- [ ] Embedding generation
- [ ] Vector similarity search with **threshold filtering (>0.7)**
- [ ] LLM response generation with **grounded anti-hallucination prompt**
- [ ] Simple CLI or web interface
- [ ] Open original PDF to source page with highlighted text
- [ ] **"Not found" fallback** when no good matches exist

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

## 🚨 Critical Accuracy Improvements (20-30 min build)

### 1. Anti-Hallucination Guardrails

**Grounded Response Enforcement:**
```python
SYSTEM_PROMPT = """
You are a book assistant. You MUST follow these rules:

1. ONLY use information from the PROVIDED PASSAGES below
2. If the answer is NOT in the passages, say "I couldn't find this in the book"
3. ALWAYS cite the exact page number and chapter for every claim
4. NEVER invent quotes, scenes, or details not in the passages
5. If uncertain, say "Based on the passages, it appears..." rather than stating as fact

PASSAGES:
{retrieved_chunks}

Each passage is tagged with [Page X, Chapter Y]. Use these citations.
"""
```

**Validation Layer (Post-LLM Check):**
```python
def validate_response(llm_response, retrieved_chunks):
    """Check if LLM claims are grounded in source material"""
    # Extract any quotes from response
    quotes = extract_quotes(llm_response)
    
    # Verify each quote exists in chunks
    all_chunks_text = " ".join([c["content"] for c in retrieved_chunks])
    for quote in quotes:
        if quote.lower() not in all_chunks_text.lower():
            return flag_as_potentially_hallucinated(quote)
    
    return llm_response
```

**Confidence Scoring:**
```python
# Return similarity scores with results
results = supabase.rpc('match_documents', {
    'query_embedding': embedding,
    'match_threshold': 0.7,  # REJECT chunks below this
    'match_count': 5
}).execute()

# If best match is below 0.75, warn user
if results[0]['similarity'] < 0.75:
    prepend_warning = "⚠️ Low confidence match. Results may not be exact."
```

### 2. Chunking Accuracy (Chonkie Settings)

**For Novels - Preserve Scene Context:**
```python
from chonkie import SemanticChunker

novel_chunker = SemanticChunker(
    chunk_size=1024,           # Larger chunks = more context
    chunk_overlap=200,         # Overlap catches split sentences
    similarity_threshold=0.6,  # Keep semantically related content together
)
```

**For Cookbooks - Recipe-Aware Chunking:**
```python
# DON'T split recipes - use regex to find boundaries first
import re

def extract_recipes(text):
    # Split on recipe headers, keep each recipe as ONE chunk
    recipe_pattern = r'(?=\n[A-Z][A-Za-z\s]+\n(?:Serves|Prep|Ingredients))'
    recipes = re.split(recipe_pattern, text)
    return [r.strip() for r in recipes if len(r) > 100]
```

**Key Settings:**
| Parameter | Novel | Cookbook |
|-----------|-------|----------|
| chunk_size | 1024 | 2048 (full recipe) |
| overlap | 200 | 50 |
| split_on | paragraphs | recipe boundaries |

### 3. Embedding Accuracy Boost

**Query Expansion (Huge Accuracy Gain):**
```python
def expand_query(user_query, llm):
    """Generate multiple search queries for better recall"""
    prompt = f"""
    User question: "{user_query}"
    
    Generate 3 alternative search queries that would find relevant passages:
    1. Rephrase the question
    2. Use synonyms or related terms  
    3. Be more specific
    
    Return as JSON array.
    """
    alternatives = llm.generate(prompt)
    return [user_query] + alternatives  # Search with all 4

# Then search with each and merge results
all_results = []
for query in expand_query(user_query, llm):
    results = vector_search(query)
    all_results.extend(results)

# Dedupe and re-rank
final_results = dedupe_and_rerank(all_results)
```

**Example Expansion:**
- User: "encounters with Dumbledore"
- Expanded: ["encounters with Dumbledore", "Dumbledore speaking to", "Dumbledore appeared", "conversation with Albus"]

### 4. Retrieval Accuracy

**Hybrid Search (Vector + Keyword):**
```sql
-- Supabase function combining vector similarity + text match
CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(384),
    query_text text,
    match_count int
)
RETURNS TABLE (id uuid, content text, similarity float, keyword_rank float)
AS $$
    SELECT 
        id,
        content,
        1 - (embedding <=> query_embedding) as similarity,
        ts_rank(to_tsvector('english', content), plainto_tsquery('english', query_text)) as keyword_rank
    FROM document_chunks
    WHERE to_tsvector('english', content) @@ plainto_tsquery('english', query_text)
       OR 1 - (embedding <=> query_embedding) > 0.7
    ORDER BY (similarity * 0.7 + keyword_rank * 0.3) DESC
    LIMIT match_count;
$$ LANGUAGE sql;
```

**Metadata Filtering (Critical for Cookbooks):**
```python
# For "find me soup recipes" - filter FIRST, then vector search
def search_with_filters(query, filters=None):
    base_query = supabase.table('document_chunks').select('*')
    
    if filters:
        # e.g., filters = {"metadata->category": "soup"}
        for key, value in filters.items():
            base_query = base_query.eq(key, value)
    
    # Then apply vector similarity on filtered set
    return base_query.order('embedding <-> query_embedding').limit(5)
```

### 5. Quick Wins (Implement These First)

**A. Minimum Similarity Threshold:**
```python
SIMILARITY_THRESHOLD = 0.72  # Reject anything below this
results = [r for r in results if r['similarity'] > SIMILARITY_THRESHOLD]
```

**B. Force Citations in Output:**
```python
# Add to prompt
"Format your response as:
[Answer text] (Page X, Chapter Y)

If you cannot cite a specific page, do not include that information."
```

**C. "Not Found" Fallback:**
```python
if len(results) == 0 or results[0]['similarity'] < 0.65:
    return "I couldn't find information about this in the book. Try rephrasing your question."
```

**D. Chunk Deduplication:**
```python
# Avoid returning overlapping chunks
def dedupe_chunks(chunks):
    seen_pages = set()
    unique = []
    for chunk in chunks:
        page_key = (chunk['page_number'], chunk['chapter'])
        if page_key not in seen_pages:
            unique.append(chunk)
            seen_pages.add(page_key)
    return unique
```

### 6. 20-Minute Priority Order

1. **Set similarity threshold** (2 min) - Reject bad matches
2. **Grounded system prompt** (3 min) - Anti-hallucination
3. **Recipe-aware chunking** (5 min) - Don't split recipes
4. **Metadata filters for cookbook** (5 min) - Filter by category
5. **Query expansion** (5 min) - Multiple search terms

---

## Success Criteria

The demo succeeds if it can:

1. ✅ Ingest a Harry Potter book and answer: "Find chapters where someone encounters Dumbledore" with correct chapter citations

2. ✅ Ingest a cookbook and answer: "Find me two soup recipes" returning actual recipe names and brief descriptions

3. ✅ Handle follow-up questions about retrieved content

4. ✅ **Refuse to answer** when information isn't in the book (no hallucination)

5. ✅ **Cite exact page/chapter** for every claim made

6. ✅ **Open original PDF** to the correct page with highlighted source text

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
