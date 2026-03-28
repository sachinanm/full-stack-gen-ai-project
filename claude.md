# Nexus AI - Full Stack Agentic RAG Project

## High-Level Architecture
- **Backend Framework:** FastAPI (Python 3.11)
- **State Machine Engine:** LangGraph (ReAct Agent Architecture)
- **Primary LLM:** Google Gemini (`gemini-2.5-flash`)
- **Knowledge Base Database:** Local ChromaDB
- **Frontend UI:** Vanilla HTML/CSS/JS (SPA layout with custom glassmorphism styling)
- **Deployment:** Dockerized (ready for Railway or Hugging Face Spaces)

## Code Structuring
- `app/main.py`: Core FastAPI instantiation and static routing.
- `app/api/routes.py`: Endpoints (`/upload`, `/chat`, `/api/stats`, `/clear`).
- `app/services/rag_service.py`: Contains the `RAGEngine`, embedding logic, and the core LangGraph agent with its associated Tools (e.g., `search_documents`, `search_web`).
- `app/core/config.py`: Loads variables securely from `.env`.
- `static/`: Contains the frontend UI codebase (`index.html`, `css/style.css`, `js/script.js`).
- `data/`: Protected storage holding the live local `chroma_db` encodings and user `uploads`.

## Advanced Capabilities
- The backend relies on **Agentic Tool Calling** rather than raw query fetching. If the local document vector tools fail or lack data, the Agent will natively invoke Wikipedia Web Search APIs to find current information via a recursive state graph.
- The UI listens to custom Server-Sent Events (SSE) structured as JSON lines, dynamically parsing standard messages (`type: chunk`) and agentic processing logs (`type: thought`).
