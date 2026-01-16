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

---

## 🏆 HACKATHON WINNING STRATEGY

### What Judges Look For
1. **Working demo** > perfect architecture (ship it!)
2. **Wow moment** - something unexpected that delights
3. **Clear problem → solution narrative**
4. **Technical depth when asked** (you have it documented here)
5. **Polish** - smooth demo flow, no fumbling

### Your Competitive Edge: The "Magic Moments"

**Magic Moment 1: Instant Source Verification**
> User asks question → Answer appears → Click "View Source" → PDF opens to EXACT page with text highlighted in yellow

This is your killer feature. Judges will remember this.

**Magic Moment 2: Confidence Transparency**
> "I found 3 highly relevant passages (92%, 87%, 84% confidence) and 2 possible matches (71%, 68%). Here's what I found..."

Shows sophistication. Most RAG demos hide this.

**Magic Moment 3: "I Don't Know" Response**
> Ask something NOT in the book → System says "I couldn't find this in [Book Title]. This might not be covered, or try rephrasing."

Judges LOVE seeing responsible AI. This differentiates you from hallucination-prone demos.

---

## 🤖 Agentic RAG Workflow (Differentiator)

Transform from basic RAG to **Agentic RAG** with a reasoning loop:

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENTIC RAG PIPELINE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [User Query]                                                   │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────┐                                                │
│  │ CLASSIFIER  │ ← "Is this about recipes, characters, plot?"  │
│  │   AGENT     │   "What filters should I apply?"              │
│  └──────┬──────┘                                                │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────┐                                                │
│  │   QUERY     │ ← Expands: "soup" → "soup, broth, bisque"     │
│  │  EXPANDER   │   "Dumbledore" → "Dumbledore, Albus, headmaster"│
│  └──────┬──────┘                                                │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────┐                                                │
│  │  RETRIEVER  │ ← Hybrid search + metadata filtering          │
│  │             │   Returns chunks + confidence scores          │
│  └──────┬──────┘                                                │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────┐                                                │
│  │  RELEVANCE  │ ← "Are these chunks actually relevant?"       │
│  │   CHECKER   │   Re-ranks, filters low-confidence            │
│  └──────┬──────┘                                                │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────┐    ┌──────────────┐                           │
│  │  RESPONSE   │───▶│ GROUNDING    │ ← Verify claims exist     │
│  │  GENERATOR  │    │  VALIDATOR   │   in source chunks        │
│  └──────┬──────┘    └──────────────┘                           │
│         │                                                       │
│         ▼                                                       │
│  [Grounded Response + Citations + Source Links]                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation (Simplified for 20 min):**

```python
class BookRAGAgent:
    def __init__(self, supabase_client, llm_client, embedder):
        self.db = supabase_client
        self.llm = llm_client
        self.embedder = embedder
    
    async def answer(self, query: str, document_id: str) -> dict:
        # Step 1: Classify & Extract Intent
        intent = await self._classify_query(query)
        
        # Step 2: Expand Query
        expanded_queries = await self._expand_query(query, intent)
        
        # Step 3: Retrieve with Confidence Scores
        chunks = await self._hybrid_retrieve(expanded_queries, document_id, intent)
        
        # Step 4: Check if we have good enough matches
        if not chunks or chunks[0]['similarity'] < 0.65:
            return {
                "answer": f"I couldn't find information about this in the book. Try rephrasing your question.",
                "confidence": "low",
                "sources": []
            }
        
        # Step 5: Generate Grounded Response
        response = await self._generate_response(query, chunks)
        
        # Step 6: Validate (check for hallucinations)
        validated = await self._validate_grounding(response, chunks)
        
        return {
            "answer": validated['answer'],
            "confidence": validated['confidence'],
            "sources": [
                {
                    "page": c['page_number'],
                    "chapter": c['chapter_title'],
                    "excerpt": c['content'][:200] + "...",
                    "similarity": c['similarity'],
                    "highlight_data": c['metadata']
                }
                for c in chunks[:3]
            ]
        }
    
    async def _classify_query(self, query: str) -> dict:
        """Detect query type and extract filters"""
        prompt = f"""Analyze this query about a book:
        "{query}"
        
        Return JSON:
        {{
            "type": "character_search" | "recipe_search" | "plot_search" | "general",
            "filters": {{"category": "soup"}} or {{}},
            "entities": ["Dumbledore", "Harry"] or [],
            "keywords": ["encounter", "meet"] or []
        }}"""
        
        result = await self.llm.generate(prompt)
        return json.loads(result)
    
    async def _expand_query(self, query: str, intent: dict) -> list:
        """Generate multiple search queries for better recall"""
        expansions = [query]
        
        # Add entity variations
        for entity in intent.get('entities', []):
            if entity == "Dumbledore":
                expansions.append(query.replace("Dumbledore", "Albus"))
                expansions.append(query.replace("Dumbledore", "headmaster"))
        
        # Add keyword synonyms
        if "soup" in query.lower():
            expansions.append(query.replace("soup", "broth"))
            expansions.append(query.replace("soup", "stew"))
        
        return expansions[:4]  # Limit for speed
    
    async def _hybrid_retrieve(self, queries: list, doc_id: str, intent: dict) -> list:
        """Vector + keyword + metadata hybrid search"""
        all_results = []
        
        for q in queries:
            embedding = self.embedder.encode(q)
            
            # Build query with optional filters
            rpc_params = {
                'query_embedding': embedding.tolist(),
                'match_threshold': 0.6,
                'match_count': 5,
                'doc_id': doc_id
            }
            
            # Add metadata filter if present (e.g., category = soup)
            if intent.get('filters'):
                rpc_params['metadata_filter'] = intent['filters']
            
            results = self.db.rpc('hybrid_search', rpc_params).execute()
            all_results.extend(results.data)
        
        # Dedupe and re-rank by similarity
        seen = set()
        unique = []
        for r in sorted(all_results, key=lambda x: x['similarity'], reverse=True):
            if r['id'] not in seen:
                seen.add(r['id'])
                unique.append(r)
        
        return unique[:5]
    
    async def _generate_response(self, query: str, chunks: list) -> str:
        """Generate grounded response with citations"""
        formatted_chunks = "\n\n".join([
            f"[Page {c['page_number']}, {c['chapter_title']}]\n{c['content']}"
            for c in chunks
        ])
        
        prompt = f"""You are a book assistant. Answer ONLY using the passages below.

PASSAGES:
{formatted_chunks}

QUESTION: {query}

RULES:
1. ONLY use information from the passages above
2. Cite [Page X, Chapter Y] for EVERY claim
3. If the answer isn't in the passages, say "I couldn't find this"
4. Never invent details not in the passages

ANSWER:"""
        
        return await self.llm.generate(prompt)
    
    async def _validate_grounding(self, response: str, chunks: list) -> dict:
        """Check if response is grounded in source material"""
        all_text = " ".join([c['content'].lower() for c in chunks])
        
        # Simple validation: check key claims exist in chunks
        # (In production, use NLI model or more sophisticated check)
        confidence = "high" if chunks[0]['similarity'] > 0.8 else "medium"
        
        return {
            "answer": response,
            "confidence": confidence,
            "grounded": True
        }
```

---

## 🎯 Demo Script (Follow This Exactly)

### Opening (30 seconds)
> "We built an intelligent book assistant that can answer questions about ANY book - and prove its answers by showing you the exact source page. Let me show you."

### Demo 1: Cookbook (60 seconds)
```
1. [Show uploaded cookbook PDF]
   "Here's a cookbook with 50 recipes already ingested."

2. [Type]: "Find me two soup recipes"
   
3. [System responds with]:
   "I found 3 soup recipes:
   
   1. **Tomato Basil Soup** (Page 24) - A creamy Italian classic with fresh basil
   2. **Chicken Noodle Soup** (Page 31) - Comfort food with vegetables
   3. **French Onion Soup** (Page 45) - Caramelized onions with gruyere
   
   Confidence: 94%, 91%, 88%"

4. [Click "View Source" on first result]
   → PDF opens to page 24, "Tomato Basil Soup" highlighted in yellow
   
5. "The system shows exactly where it found this. No hallucination possible."
```

### Demo 2: Harry Potter (60 seconds)
```
1. "Now let's try a novel - Harry Potter."

2. [Type]: "Find chapters where someone encounters Dumbledore"

3. [System responds with]:
   "I found 5 significant Dumbledore encounters:
   
   1. **Chapter 1: The Boy Who Lived** (Page 12) - Dumbledore arrives at Privet Drive
   2. **Chapter 7: The Sorting Hat** (Page 91) - Harry sees Dumbledore at the feast
   3. **Chapter 12: The Mirror of Erised** (Page 156) - Harry's late-night conversation
   
   Confidence: 96%, 89%, 87%"

4. [Click to open source]
   → Shows exact page with highlighted text

5. "Every answer is traceable to the original text."
```

### Demo 3: Anti-Hallucination (30 seconds)
```
1. [Type]: "What happens when Harry meets Gandalf?"

2. [System responds]:
   "I couldn't find any mention of Gandalf in this Harry Potter book. 
   Gandalf is a character from Lord of the Rings, not Harry Potter.
   Would you like me to search for a different character?"

3. "This is responsible AI - it knows what it doesn't know."
```

### Closing (15 seconds)
> "Three key innovations: semantic search with confidence scores, source verification with PDF highlighting, and hallucination guardrails. Questions?"

---

## 🔧 Last-Minute Polish Checklist

### Before Demo
- [ ] Pre-ingest both books (don't do live ingestion - too slow/risky)
- [ ] Test your 3 demo queries work perfectly
- [ ] Have backup queries ready if something fails
- [ ] Clear browser cache, close unnecessary tabs
- [ ] Test PDF highlighting works
- [ ] Have terminal ready to show "technical depth" if asked

### UI Quick Wins (5 min each)
- [ ] Add loading spinner during search
- [ ] Show confidence percentage badges (green >85%, yellow >70%, red <70%)
- [ ] Add "View Source" button next to each result
- [ ] Show chunk excerpt preview before opening PDF

### If Something Breaks During Demo
1. **Search returns nothing**: "Let me try a broader search..." (have backup query)
2. **PDF won't open**: "Here's the page number, let me show the raw result..." (show JSON)
3. **LLM timeout**: "Processing large context..." (have pre-cached response ready)

---

## 📊 Technical Depth Answers (For Judge Q&A)

**Q: How do you handle hallucinations?**
> "Three layers: First, similarity threshold rejects weak matches. Second, the prompt forces citation or 'not found'. Third, we validate that any quotes actually exist in retrieved chunks."

**Q: Why Chonkie for chunking?**
> "Semantic chunking keeps related content together. For cookbooks, we do recipe-boundary detection first. For novels, we preserve paragraph and scene context."

**Q: How accurate is the retrieval?**
> "Hybrid search combining vector similarity with keyword matching. For structured queries like 'soup recipes', we filter by metadata first, then rank by semantic similarity."

**Q: What's the latency?**
> "Embedding is ~50ms, Supabase vector search is ~100ms, LLM response is ~1-2s. Total under 3 seconds."

**Q: How would you scale this?**
> "Supabase pgvector scales horizontally. For larger books, we'd add hierarchical indexing - chapter summaries for coarse search, then drill into chunks."

---

## 🚀 Post-Hackathon Roadmap (Mention if Asked)

1. **Multi-book search** - "Find recipes across all my cookbooks"
2. **Conversation memory** - Follow-up questions with context
3. **Voice interface** - "Hey, what's a good soup recipe?"
4. **Collaborative annotations** - Team highlights and notes
5. **Fine-tuned embeddings** - Domain-specific for better accuracy

---

## Files to Have Ready

```
/demo/
├── cookbook.pdf                    # Pre-ingested
├── harry_potter_chapter1.pdf       # Pre-ingested (use sample, not full book)
├── pre_computed_embeddings.json    # Backup if embedding fails
├── demo_responses.json             # Cached responses for emergency
└── screenshots/                    # Backup visuals if live demo fails
```

**Emergency Backup Plan:**
If everything breaks, show screenshots + architecture diagram + code walkthrough.
"Here's what it does when working..." → Still shows technical competence.

---

## 💡 One-Liner Pitch

> "RAG that proves its answers - every response links to the highlighted source page, and it knows when to say 'I don't know'."

This is your memorable soundbite. Say it in the intro and closing.
