"""FastAPI backend: answers questions and serves source PDFs for the chat UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from providers import EmbeddingProviderName, LLMProviderName
from pydantic import BaseModel
from qa import answer_question_structured

ROOT = Path(__file__).resolve().parents[2]
FILES_DIR = ROOT / "files"
CACHE_PATH = FILES_DIR / "embeddings_cache.json"
WEB_DIR = ROOT / "web"

app = FastAPI(title="Citation-Aware RAG")


class AskRequest(BaseModel):
    question: str


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    """Answer a question; response includes citations with page/bbox info."""
    return answer_question_structured(
        request.question,
        cache_path=CACHE_PATH,
        embedding_provider_name=EmbeddingProviderName.MONGO_VOYAGE,
        llm_provider_name=LLMProviderName.GROQ,
    )


@app.get("/documents")
def list_documents() -> list[str]:
    """Return the filenames of every PDF available in files/, for the UI to pick from."""
    return sorted(p.name for p in FILES_DIR.glob("*.pdf"))


@app.get("/pdf/{document_id}")
def get_pdf(document_id: str) -> FileResponse:
    """Serve a source PDF by its document_id (the original filename)."""
    safe_name = Path(document_id).name  # strip any path components, block traversal
    pdf_path = FILES_DIR / safe_name
    if pdf_path.suffix.lower() != ".pdf" or not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf")



# Mounted last so /ask and /pdf/{document_id} are matched before this catch-all.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
