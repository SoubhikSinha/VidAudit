# VidAudit

### _Multi-modal brand-compliance auditing for YouTube ads, powered by Azure Video Indexer, Azure AI Search (RAG) and LangGraph_

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Workflow-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![Azure](https://img.shields.io/badge/Azure-Video%20Indexer%20%7C%20OpenAI%20%7C%20AI%20Search-0078D4?logo=microsoftazure)](https://azure.microsoft.com/)
[![uv](https://img.shields.io/badge/packaged%20with-uv-6E56CF)](https://docs.astral.sh/uv/)

Give VidAudit a YouTube URL. It transcribes the video, reads the on-screen text, checks both against your regulatory rule documents, and returns a **PASS/FAIL verdict with the specific violations**.

## 📑 Table of Contents

- [📸 Demo](#-demo)
- [📖 Overview](#-overview)
- [⚡ Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [🛠 Tech Stack](#-tech-stack)
- [⚙️ Setup Instructions](#️-setup-instructions)
- [🚀 Usage](#-usage)
- [📊 Load Test Results](#-load-test-results)
- [📂 Project Structure](#-project-structure)

## 📸 Demo

<!-- Add screenshots to a DemoPics/ folder and link them here, e.g.:
![Swagger UI](DemoPics/swagger.png)
![Application Map](DemoPics/app-insights-map.png)
![LangSmith trace](DemoPics/langsmith-trace.png)
-->

_Swagger UI (`/docs`), Application Insights Application Map and a LangSmith trace go here._

## 📖 Overview

Manually reviewing video ads against brand and platform policy (claims, disclosures, ad specs) is slow and inconsistent. VidAudit automates the first pass:

1. **Video → text:** downloads the video and uses **Azure Video Indexer** to extract the speech transcript and on-screen text (OCR).
2. **Rules retrieval (RAG):** embeds the content and pulls the most relevant clauses from your compliance PDFs, stored in **Azure AI Search**.
3. **Audit:** an **Azure OpenAI** model compares content against the retrieved rules and returns structured JSON: status, violations (category, severity, description) and a summary report.

The two stages are a two-node **LangGraph** workflow (`indexer → auditor`) exposed through a **FastAPI** endpoint, and instrumented with **Azure Application Insights** and **LangSmith**.

## ⚡ Features

- 🎥 **Multi-modal extraction**: transcript + OCR from video via Azure Video Indexer.
- 📚 **Grounded audits**: the LLM only judges against rules retrieved from your own documents.
- 🧩 **Structured output**: `PASS`/`FAIL`, violations with severity, written report.
- ⏱️ **Per-stage timings** returned on every response (`download`, `upload`, `vi_wait`, `rag`, `llm`).
- 🚦 **Concurrency-safe**: per-request temp files, async graph execution, semaphore cap (`MAX_CONCURRENT_AUDITS`).
- 🔁 **Resilient**: request timeouts, backoff on Video Indexer 429/5xx, indexing max-wait, OpenAI retries.
- 🔭 **Observability**: Application Insights (Application Map, dependency traces) + LangSmith LLM traces.
- 🧪 **Load-test harness** included (`backend/loadtest/`).

## 🏗️ Architecture

```
   YouTube URL
        │
        ▼
 ┌──────────────┐   POST /audit
 │   FastAPI    │──────────────────────────────┐
 └──────┬───────┘                              │
        │ ainvoke                              │ telemetry
        ▼                                      ▼
 ┌─────────────────────────────┐      ┌──────────────────┐
 │ LangGraph                   │      │ App Insights     │
 │                             │      │ LangSmith        │
 │  [1] Indexer node           │      └──────────────────┘
 │      yt-dlp download        │
 │      → Azure Video Indexer  │  (transcript + OCR)
 │                             │
 │  [2] Auditor node           │
 │      embed → Azure AI Search│  (top-3 rule chunks)
 │      → Azure OpenAI (JSON)  │
 └──────────────┬──────────────┘
                ▼
     status · violations · report · timings
```

## 🛠 Tech Stack

| Layer | Tools |
|---|---|
| Orchestration | LangGraph, LangChain |
| LLM / Embeddings | Azure OpenAI (chat + `text-embedding-3-small`) |
| Retrieval | Azure AI Search (vector store) |
| Video understanding | Azure Video Indexer (transcript, OCR) |
| Ingestion | yt-dlp, pypdf |
| API | FastAPI, Uvicorn |
| Observability | Azure Monitor / Application Insights (OpenTelemetry), LangSmith |
| Packaging | uv, Python 3.12+ |

## ⚙️ Setup Instructions

### Prerequisites

- **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)**
- An **Azure subscription** with: Azure OpenAI (chat + embedding deployments), Azure AI Search, Azure Video Indexer (ARM-based account), Application Insights, and an App Registration (for `DefaultAzureCredential`)
- A **[LangSmith](https://smith.langchain.com/)** API key (optional, for LLM tracing)

### Install

```bash
git clone https://github.com/SoubhikSinha/VidAudit.git
cd VidAudit/ComplianceQAPipeline

curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv isn't installed
uv sync
```

### Configure environment

```bash
cp .env.example .env
```

Fill in the values (all names are in `.env.example`): Azure OpenAI, AI Search, Video Indexer, Application Insights, LangSmith, and Azure AD credentials.

> Optional tuning: `MAX_CONCURRENT_AUDITS` (default `5`), `VI_MAX_WAIT_SECONDS` (default `1200`).

### Index the rule documents

Loads the PDFs in `backend/data/` into Azure AI Search (run once):

```bash
uv run python backend/scripts/index_documents.py
```

## 🚀 Usage

Start the server (from `ComplianceQAPipeline/`):

```bash
uv run uvicorn backend.src.api.server:app
```

- Swagger UI → http://127.0.0.1:8000/docs
- Health check → `GET /health`

**Audit a video**

```bash
curl -X POST http://127.0.0.1:8000/audit \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://youtu.be/dT7S75eYhcQ"}'
```

**Response shape**

```json
{
  "session_id": "ce6c43bb-c71a-4f16-a377-8b493502fee2",
  "video_id": "vid_ce6c43bb",
  "status": "FAIL",
  "final_report": "Summary of findings...",
  "compliance_results": [
    {"category": "Claim Validation", "severity": "CRITICAL", "description": "..."}
  ],
  "timings": {"download": 1.8, "upload": 2.7, "vi_wait": 62.0, "rag": 0.5, "llm": 4.0},
  "errors": []
}
```

`status` is `PASS`, `FAIL` (compliance verdict), or `NO_TRANSCRIPT` (nothing to audit, e.g. music-only ad). Pipeline problems are reported in `errors` and can still return HTTP 200, so check `status`/`errors`, not only the HTTP code.

**Observability:** open Application Insights → _Application Map_ to see FastAPI's calls to each Azure service; LangSmith shows the LLM/retrieval traces.

**Load test**

```bash
uv run python backend/loadtest/build_urls.py 300                      # collect short ad URLs
uv run python backend/loadtest/run.py --count 50 --concurrency 5      # fire requests → results.csv
uv run python backend/loadtest/report.py backend/loadtest/results.csv 5 <wall_clock_s>
```

## 📊 Load Test Results

> **Preliminary:** 30 real YouTube ads (15–90s), run against Azure services with a single uvicorn worker. Small sample; larger tiers are planned.

| | Concurrency 3 | Concurrency 5 |
|---|---|---|
| Requests | 15 | 15 |
| Infrastructure errors | 0 | 0 |
| Audits with verdict | 14 | 11 |
| `NO_TRANSCRIPT` (no speech) | 1 | 4 |
| Latency p50 / p95 | 44.5s / 131s | 73s / 100s |
| Throughput | ~140 audits/hr | ~183 audits/hr |

**Where time goes:** Video Indexer processing is ~85% of end-to-end latency (p50 ≈ 62s at concurrency 1). Download, upload, retrieval and LLM together take ≈ 10s.

**Issues found and fixed during testing:** shared temp-file collision under concurrency, blocking graph call serializing the server, unbounded Video Indexer polling, empty-transcript videos reported as compliance FAILs, and a misspelled App Insights env var that silently disabled telemetry.

## 📂 Project Structure

```
VidAudit/
├── README.md
└── ComplianceQAPipeline/
    ├── main.py                       # CLI: audit a single video
    ├── pyproject.toml / uv.lock
    ├── .env.example                  # variable names only
    └── backend/
        ├── data/                     # Compliance PDFs (rule knowledge base)
        ├── scripts/
        │   └── index_documents.py    # PDFs → Azure AI Search
        ├── loadtest/                 # build_urls.py · run.py · report.py
        └── src/
            ├── api/
            │   ├── server.py         # FastAPI app (/audit, /health)
            │   └── telemetry.py      # Azure Monitor / OpenTelemetry setup
            ├── graph/
            │   ├── workflow.py       # LangGraph: indexer → auditor
            │   ├── nodes.py          # Indexer & Auditor nodes
            │   └── state.py          # Shared graph state
            └── services/
                └── video_indexer.py  # yt-dlp + Azure Video Indexer client
```
