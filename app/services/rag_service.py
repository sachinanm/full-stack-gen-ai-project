import os
import json
import base64
from typing import AsyncGenerator

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma

from langchain_core.messages import HumanMessage, AIMessageChunk
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings

# Ensure directories exist
os.makedirs(settings.CHROMA_DB_DIR, exist_ok=True)
os.makedirs(settings.UPLOADS_DIR, exist_ok=True)


class RAGEngine:
    def __init__(self):
        # 1. Models
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            max_tokens=None,
            api_key=settings.GEMINI_API_KEY
        )
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=settings.GEMINI_API_KEY
        )
        
        # 2. Vector Store Setup
        self.vector_store = Chroma(
            persist_directory=settings.CHROMA_DB_DIR, 
            embedding_function=self.embeddings
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap=200
        )
        
        # 3. LangGraph Tools
        @tool
        def search_documents(query: str) -> str:
            """Searches the local knowledge base of uploaded user documents for relevant context. Always use this tool FIRST before searching the web."""
            if self.vector_store._collection.count() == 0:
                return "The document database is currently empty."
            retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})
            docs = retriever.invoke(query)
            if not docs:
                return "No relevant documents found in the database."
            return "\n\n".join([f"Source: {docs[i].metadata.get('source', '?')}\nContent: {docs[i].page_content}" for i in range(len(docs))])

        @tool
        def search_web(query: str) -> str:
            """Searches the live internet for up-to-date encyclopedic information. ONLY use this if 'search_documents' does not contain the answer, or if the user asks for concepts or current events."""
            import urllib.request, urllib.parse, json
            try:
                url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 NexusAI/1.0'})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode('utf-8'))
                results = data.get("query", {}).get("search", [])
                if not results:
                    return "No useful knowledge base results found."
                # Clean html tags from snippet
                import re
                return "\n\n".join([f"Title: {r.get('title')}\nSnippet: {re.sub('<[^<]+>', '', r.get('snippet', ''))}" for r in results[:3]])
            except Exception as e:
                return "Error: Could not search the web at this time."

        self.tools = [search_documents, search_web]
        
        # 4. Agent Architecture
        self.memory = MemorySaver()
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            checkpointer=self.memory,
            prompt="You are Nexus AI, a highly advanced agentic assistant. You must prioritize searching local documents using `search_documents` before falling back to `search_web`. Provide highly accurate answers. When you stream the final answer, be concise and helpful."
        )

    def ingest_document(self, file_path: str, filename: str) -> int:
        fn_lower = filename.lower()
        if fn_lower.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
            documents = loader.load()
        elif fn_lower.endswith(".txt"):
            loader = TextLoader(file_path, encoding='utf-8')
            documents = loader.load()
        elif fn_lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            with open(file_path, "rb") as image_file:
                image_bytes = image_file.read()
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                
            mime_type = "image/jpeg"
            if fn_lower.endswith(".png"): mime_type = "image/png"
            elif fn_lower.endswith(".webp"): mime_type = "image/webp"

            num_images = 1
            # We can't batch base64 elegantly if multiple pages, but assuming single image.
            msg = self.llm.invoke([
                HumanMessage(
                    content=[
                        {
                            "type": "text", 
                            "text": "Please completely and accurately transcribe all handwritten text, diagrams, and notes found in this image. Do not invent details. Simply output the transcription."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                        },
                    ]
                )
            ])
            documents = [Document(page_content=msg.content)]
        else:
            raise ValueError(f"Unsupported file type for {filename}")

        for doc in documents:
            doc.metadata["source"] = filename

        chunks = self.text_splitter.split_documents(documents)
        if chunks:
            self.vector_store.add_documents(chunks)
            return len(chunks)
        return 0

    async def query_stream(self, question: str, session_id: str) -> AsyncGenerator[str, None]:
        # Sources are harder to extract directly without a custom wrapper when using an agent,
        # but we can yield thoughts!
        
        config = {"configurable": {"thread_id": session_id}}
        
        # We will use stream_mode="messages" which yields (message_chunk, metadata)
        async for chunk, metadata in self.agent.astream(
            {"messages": [HumanMessage(content=question)]},
            config=config,
            stream_mode="messages"
        ):
            # A chunk can be from a tool, the human, or the AI.
            # We only care to stream the AI's thoughts and text.
            if isinstance(chunk, AIMessageChunk):
                # Is it a thought/tool call?
                if chunk.tool_call_chunks:
                    for tc in chunk.tool_call_chunks:
                        if "name" in tc and tc["name"]:
                            tool_name = tc.get("name", "UnknownTool")
                            yield f"data: {json.dumps({'type': 'thought', 'data': f'Using tool: {tool_name}...'})}\n\n"
                            
                # Is it the final text response?
                if chunk.content:
                    text_data = ""
                    if isinstance(chunk.content, list):
                        for item in chunk.content:
                            if isinstance(item, dict) and "text" in item:
                                text_data += item["text"]
                            else:
                                text_data += str(item)
                    else:
                        text_data = str(chunk.content)
                        
                    if text_data:
                        yield f"data: {json.dumps({'type': 'chunk', 'data': text_data})}\n\n"


    def get_db_stats(self):
        # Count total embeddings
        try:
            total_vectors = self.vector_store._collection.count()
        except:
            total_vectors = 0
            
        files = []
        if os.path.exists(settings.UPLOADS_DIR):
            for f in os.listdir(settings.UPLOADS_DIR):
                p = os.path.join(settings.UPLOADS_DIR, f)
                if os.path.isfile(p):
                    files.append({
                        "name": f,
                        "size": os.path.getsize(p),
                        "type": getattr(f.split('.')[-1], 'upper')() if '.' in f else 'UNKNOWN'
                    })
        return {"total_vectors": total_vectors, "files": files}

    def clear_database(self):
        self.vector_store.delete_collection()
        self.vector_store = Chroma(
            persist_directory=settings.CHROMA_DB_DIR, 
            embedding_function=self.embeddings
        )
        
        # In a real app we'd reset the LangGraph memory
        self.memory = MemorySaver()
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            checkpointer=self.memory
        )
        
        for filename in os.listdir(settings.UPLOADS_DIR):
            file_path = os.path.join(settings.UPLOADS_DIR, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                pass


# Singleton logic
rag_engine = None

def get_rag_engine() -> RAGEngine:
    global rag_engine
    if rag_engine is None:
        rag_engine = RAGEngine()
    return rag_engine
