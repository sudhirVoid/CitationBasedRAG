# Citation-Aware RAG — Learning Project

This repository follows the guidance in AGENT.md and is intentionally built as a mentor-driven learning project for understanding retrieval-augmented generation from first principles.

## Learning principle

The AI acts as a guide, not as the implementer. The goal is for the developer to understand each concept before moving to the next layer of the system.

## Current focus

We are beginning with Phase 1: understanding PDFs and their structure in PyMuPDF.

## Run locally

From the repository root:

```powershell
cd "c:\Users\bhandars\source\repos\PracticeProjects\CitationBasedRAG"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you are using a different shell, the equivalent activation command is:

```bash
source .venv/bin/activate
```

After activation, confirm the environment is ready:

```powershell
python -c "import fitz, numpy, pytest; print('environment ready')"
```

## Run the app (chat + PDF viewer)

One FastAPI process serves both the API and the static frontend together —
there's no separate frontend server to start.

From Git Bash (or WSL), from the repository root:

```bash
bash run.sh
```

This stops any process already using port 8000, then starts the server at
[http://127.0.0.1:8000](http://127.0.0.1:8000). Ask a question in the chat
panel, then click any `[1]`, `[2]`... citation to jump to and highlight the
exact source location in the PDF panel.

## First task

Open the implementation in `src/citation_rag/pdf_inspector.py` and complete TASK 01 there.

The task is intentionally left as a guided TODO so the learning flow remains explicit and reviewable.

## Project structure

```text
CitationBasedRAG/
├── AGENT.MD
├── README.md
├── requirements.txt
├── .venv/
├── src/
│   └── citation_rag/
│       ├── __init__.py
│       └── pdf_inspector.py
└── tests/
```
