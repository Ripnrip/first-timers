import sys
import os
import warnings
from pathlib import Path
from typing import List, Dict
import json
import pypdf
import re
from sentence_transformers import SentenceTransformer
import psycopg2
from dotenv import load_dotenv

# Suppress Streamlit ScriptRunContext warnings when running outside Streamlit
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_PROJECT_ID = os.getenv('SUPABASE_PROJECT_ID')
SUPABASE_DB_PASSWORD = os.getenv('SUPABASE_DB_PASSWORD')
SUPABASE_DB_URL = f"postgresql://postgres.kvwylswcjlqkmompogty:{SUPABASE_DB_PASSWORD}@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 512

def extract_text_from_pdf(pdf_path: str) -> List[Dict]:
    """Extract text from PDF with page information"""
    chunks = []

    with open(pdf_path, 'rb') as file:
        pdf_reader = pypdf.PdfReader(file)

        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()

            if text:
                chunks.append({
                    'text': text,
                    'page_number': page_num + 1
                })

    return chunks

def create_semantic_chunks(text_chunks: List[Dict], doc_name: str, doc_type: str) -> List[Dict]:
    """Create semantic chunks from text"""
    # Initialize embedding model
    model = SentenceTransformer(EMBEDDING_MODEL)

    all_chunks = []
    chunk_index = 0

    for chunk in text_chunks:
        text = chunk['text']
        page_num = chunk['page_number']

        # Simple chunking: split into paragraphs
        paragraphs = re.split(r'\n\s*\n', text)

        for para in paragraphs:
            para = para.strip()
            if len(para) < 50:  # Skip very short paragraphs
                continue

            # Create embedding
            embedding = model.encode(para).tolist()

            # Create chunk data
            chunk_data = {
                'content': para,
                'embedding': embedding,
                'document_name': doc_name,
                'document_type': doc_type,
                'page_number': page_num,
                'chunk_index': chunk_index,
                'metadata': {}
            }

            all_chunks.append(chunk_data)
            chunk_index += 1

    return all_chunks

def setup_database():
    """Setup database tables"""
    conn = psycopg2.connect(SUPABASE_DB_URL)
    cur = conn.cursor()

    # Enable pgvector
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        print("✓ pgvector extension enabled")
    except:
        conn.rollback()

    # Create documents table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            type TEXT,
            total_chunks INTEGER,
            uploaded_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # Create document chunks table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            content TEXT NOT NULL,
            embedding VECTOR(384),
            document_id UUID REFERENCES documents(id),
            document_name TEXT,
            document_type TEXT,
            page_number INTEGER,
            chunk_index INTEGER,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # Create index for vector search
    cur.execute("""
        CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
        ON document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✓ Database tables created")

def insert_document(name: str, doc_type: str, total_chunks: int) -> str:
    """Insert document record"""
    conn = psycopg2.connect(SUPABASE_DB_URL)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO documents (name, type, total_chunks)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (name, doc_type, total_chunks))

    doc_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return doc_id

def insert_chunks(chunks: List[Dict], doc_id: str):
    """Insert chunks into database"""
    conn = psycopg2.connect(SUPABASE_DB_URL)
    cur = conn.cursor()

    # Prepare data for insertion
    chunk_data = []
    for chunk in chunks:
        chunk_data.append((
            chunk['content'],
            chunk['embedding'],
            doc_id,
            chunk['document_name'],
            chunk['document_type'],
            chunk['page_number'],
            chunk['chunk_index'],
            json.dumps(chunk['metadata'])
        ))

    # Insert in batches
    batch_size = 100
    for i in range(0, len(chunk_data), batch_size):
        batch = chunk_data[i:i+batch_size]
        cur.executemany("""
            INSERT INTO document_chunks
            (content, embedding, document_id, document_name, document_type, page_number, chunk_index, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, batch)
        conn.commit()
        print(f"  Inserted batch {i//batch_size + 1}/{(len(chunk_data)-1)//batch_size + 1}")

    cur.close()
    conn.close()

def process_pdf(pdf_path: str, doc_type: str):
    """Process a single PDF"""
    print(f"\n📖 Processing {pdf_path}...")

    # Extract text
    print("  Step 1: Extracting text...")
    text_chunks = extract_text_from_pdf(pdf_path)
    print(f"    Extracted {len(text_chunks)} pages")

    # Create semantic chunks
    print("  Step 2: Creating semantic chunks...")
    doc_name = Path(pdf_path).stem
    semantic_chunks = create_semantic_chunks(text_chunks, doc_name, doc_type)
    print(f"    Created {len(semantic_chunks)} semantic chunks")

    # Insert document
    print("  Step 3: Storing document...")
    doc_id = insert_document(doc_name, doc_type, len(semantic_chunks))

    # Add document ID to chunks
    for chunk in semantic_chunks:
        chunk['document_id'] = doc_id

    # Insert chunks
    print("  Step 4: Storing chunks...")
    insert_chunks(semantic_chunks, doc_id)

    print(f"  ✅ Successfully ingested {doc_name}")
    return doc_id

def main():
    # Setup database
    print("🔧 Setting up database...")
    setup_database()

    # Process inputs directory
    inputs_dir = Path(__file__).parent / "inputs"
    print(f"\n📁 Processing directory: {inputs_dir}")

    # Process each PDF
    for pdf_file in inputs_dir.glob("*.pdf"):
        # Determine type
        if 'cook' in pdf_file.stem.lower() or 'matcha' in pdf_file.stem.lower():
            doc_type = "cookbook"
        else:
            doc_type = "novel"

        try:
            process_pdf(str(pdf_file), doc_type)
        except Exception as e:
            print(f"  ❌ Error processing {pdf_file}: {str(e)}")

    print("\n🎉 Ingestion complete!")

if __name__ == "__main__":
    main()