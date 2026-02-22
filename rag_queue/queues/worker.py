
from dotenv import load_dotenv
import os

from openai import OpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore


load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)


#vector embedding (using free HuggingFace embeddings) of user input
embeddings = HuggingFaceEmbeddings(
    model_name='sentence-transformers/all-MiniLM-L6-v2'
)

vector_db = QdrantVectorStore.from_existing_collection(
    embedding=embeddings,
    url="http://localhost:6333",
    collection_name="nodejs_docs"
)

def process_query(user_query: str) -> str:
    print("Searching chunks for relevant information...   ",user_query)
    search_results = vector_db.similarity_search(query=user_query, k=5)

    # Build context from search results
    context = "\n\n".join([
        f"Page Content: {result.page_content}\n"
        f"Page Number: {result.metadata.get('page_label', 'N/A')}\n"
        f"Source: {result.metadata.get('source', 'Unknown')}"
        for result in search_results
    ])

    SYSTEM_PROMPT = f"""
    You are a knowledgeable AI Assistant specialized in answering questions about Node.js documentation.

    Your role:
    - Answer user queries accurately based ONLY on the provided context from the PDF documentation
    - Always cite the page number when referencing information
    - If the context doesn't contain enough information to answer the question, clearly state that
    - Guide users to the specific page numbers where they can find more detailed information

    Guidelines:
    1. Be concise but thorough in your explanations
    2. Use code examples from the context when relevant
    3. If multiple pages discuss the topic, mention all relevant page numbers
    4. Never make up information that isn't in the provided context

    Context from Node.js Documentation:
    {context}
    """

    
    response = client.chat.completions.create(
        model="gemini-3-flash-preview",
        messages=[
            {   "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_query
            }
        ]
    )

    return response.choices[0].message.content
