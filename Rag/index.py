from dotenv import load_dotenv

from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore

#langchain is a framework for building applications with LLMs. It provides tools for document loading, text splitting, embedding generation, and vector store management.
#In this code snippet, we are using langchain to load a PDF document, split it into chunks, generate embeddings for the chunks using a HuggingFace model, and store the embeddings in a Qdrant vector store.


load_dotenv()
file_path = Path(__file__).parent / "nodejs.pdf"

#load this file in python program
loader = PyPDFLoader(file_path)
docs = loader.load()
#print(docs[12])

#split the document into chunks
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
chunks = text_splitter.split_documents(docs)
print(f"Split into {len(chunks)} chunks.")

#vector embedding (using free HuggingFace embeddings)
embeddings = HuggingFaceEmbeddings(
    model_name='sentence-transformers/all-MiniLM-L6-v2'
)

vector_store = QdrantVectorStore.from_documents(
    documents=chunks,
    embedding=embeddings,
    url="http://localhost:6333",
    collection_name="nodejs_docs"
)

print("Vector store created and data inserted.")