# DisasterRelief AI

**An evidence-grounded disaster relief assistant powered by Retrieval-Augmented Generation (RAG).**

DisasterRelief AI is a project designed to help users find relevant information from disaster-management and government documents. It combines document retrieval with a locally run Large Language Model (LLM) to generate contextual responses grounded in retrieved source material.

The project also includes a model evaluation workflow for comparing code-oriented language models and analyzing retrieval quality, response quality, and other RAG pipeline characteristics.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Knowledge Base](#knowledge-base)
- [Model Evaluation](#model-evaluation)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Limitations](#limitations)
- [Future Improvements](#future-improvements)

## Overview

During a disaster, people may need to locate relevant guidance across multiple documents quickly. Finding the right information manually can be time-consuming.

DisasterRelief AI explores how RAG can make this information easier to access by retrieving relevant document passages before generating an answer.

Instead of relying exclusively on a model's pretrained knowledge, the system uses a retrieval pipeline to provide relevant context for response generation.

**Important:** This project is an informational assistant and should not replace official emergency instructions, emergency services, or professional guidance.

## Key Features

- **Document-grounded question answering:** Retrieves relevant information from the disaster-management knowledge base.
- **RAG pipeline:** Combines document ingestion, embeddings, retrieval, and LLM-based response generation.
- **Web interface:** Provides a React-based frontend for interacting with the application.
- **Backend API:** Uses FastAPI to handle application requests and backend processing.
- **Local LLM integration:** Uses Ollama to run supported language models locally.
- **Vector search:** Uses ChromaDB as part of the retrieval workflow.
- **Model evaluation:** Includes scripts, datasets, reports, dashboards, and results for analyzing model and RAG performance.

## System Architecture

The application follows a retrieval-augmented generation workflow.

1. **Knowledge sources:** Disaster-management documents provide the source material.
2. **Document ingestion:** Documents are processed and prepared for retrieval.
3. **Embedding generation:** Text is converted into vector representations.
4. **Vector storage and retrieval:** ChromaDB supports storing and retrieving relevant document chunks.
5. **Context construction:** Retrieved passages are supplied as context for response generation.
6. **Answer generation:** The configured language model generates a contextual response.
7. **Frontend interaction:** The React interface allows users to interact with the backend.

### Architecture Flow

```text
Disaster Management Documents
             |
             v
     Document Ingestion
             |
             v
      Text Embeddings
             |
             v
      ChromaDB Storage
             |
             v
       User Question
             |
             v
    Relevant Retrieval
             |
             v
     Context + Question
             |
             v
      Ollama / LLM
             |
             v
    Generated Response
             |
             v
       React Frontend
```

The diagram represents the intended RAG workflow. Exact implementation details may vary by component and configuration.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend logic and evaluation scripts |
| FastAPI | Backend API framework |
| React | Frontend interface |
| JavaScript | Frontend functionality and dashboard components |
| Ollama | Local language model execution |
| ChromaDB | Vector storage and retrieval |
| Embeddings | Representing text for semantic retrieval |
| Docker | Containerization support |
| CSV, JSON, Markdown, Excel | Evaluation datasets, results, and reports |

## Knowledge Base

The `knowledge_base/` directory contains disaster-management reference material organized by topic.

Current categories include:

- **Common:** General disaster-management and response-related resources.
- **Cyclone:** Cyclone-related guidance.
- **Earthquake:** Earthquake-related guidance.
- **Flood:** Flood-related guidance.

A `sources.json` file provides additional source information.

The quality of the retrieved information depends on the documents indexed, retrieval configuration, and relevance of the retrieved passages.

## Model Evaluation

The project includes a Week 4 evaluation workflow for comparing multiple code-oriented language models and investigating RAG behavior.

### Models Evaluated

The evaluation results include:

- Code Llama
- DeepSeek-Coder 6.7B
- Qwen2.5-Coder 7B

### Evaluation Dataset

The evaluation dataset contains 28 questions across seven categories:

- Explanation
- Code Retrieval
- Dependency Understanding
- Bug Analysis
- Code Generation
- Refactoring
- RAG

### Evaluation Components

The `week4_evaluation/` directory includes:

- Dataset creation and evaluation scripts.
- Model evaluation results and scoring outputs.
- Retrieval and response-quality analysis.
- Resource metric reports.
- Repository-level evaluation.
- Evaluation dashboards and technical reports.

These artifacts support analysis of model behavior and RAG pipeline performance. Specific performance conclusions should be drawn from the corresponding evaluation reports rather than assumed from the model names.

## Project Structure

```text
DisasterRelief-AI/
├── backend/
│   ├── ingestion/
│   │   └── ingest.py
│   ├── rag/
│   │   ├── embeddings.py
│   │   ├── rag_comparison.py
│   │   ├── rag_service.py
│   │   └── retrieval.py
│   ├── services/
│   │   ├── embedding_service.py
│   │   ├── llm_service.py
│   │   ├── orchestration_service.py
│   │   └── retrieval_service.py
│   └── main.py
├── frontend/
│   ├── public/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── knowledge_base/
│   ├── common/
│   ├── cyclone/
│   ├── earthquake/
│   ├── flood/
│   └── sources.json
├── week4_evaluation/
│   ├── dashboard/
│   ├── dataset/
│   ├── exports/
│   ├── reports/
│   ├── results/
│   └── scripts/
├── Dockerfile
└── .gitignore
```

## Getting Started

### Prerequisites

Before running the application, you will need:

- Python compatible with the backend dependencies.
- Node.js and npm.
- Ollama, with a compatible model downloaded locally.
- The Python packages required by the backend.
- The JavaScript packages declared in `frontend/package.json`.

ChromaDB and the embedding model must also be configured as required by the application.

### 1. Clone the Repository

```bash
git clone https://github.com/Anshi-19/DisasterRelief-AI.git
cd DisasterRelief-AI
```

### 2. Set Up the Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite will display the local URL for the frontend in the terminal.

### 3. Configure the Backend

From the project root, review `backend/main.py` and the modules under `backend/services/` to identify the required Python packages and application configuration.

Create and activate a virtual environment, install the required dependencies, and configure Ollama and ChromaDB according to the project implementation.

The repository currently does not include a root-level Python dependency manifest, so the exact backend installation command should be documented after the dependencies have been consolidated into a reproducible requirements file.

### 4. Run the Backend

Start the FastAPI application using the ASGI application entry point defined in `backend/main.py`. The exact launch command depends on the application's import paths and configuration.

Ensure the backend and frontend are configured to communicate with each other before testing the complete application.

### 5. Explore the Evaluation Artifacts

Review `week4_evaluation/README.md` for evaluation-specific information.

The `dataset/`, `scripts/`, `results/`, `reports/`, and `dashboard/` directories contain supporting evaluation materials.

## Limitations

- Generated responses can contain errors or omit important information.
- Retrieval quality depends on the indexed documents, embedding configuration, and retrieval strategy.
- Model behavior and response quality can vary across models and configurations.
- Local execution requires sufficient system resources for the selected language model.
- The presence of evaluation results does not by itself establish real-world emergency-response effectiveness.
- This project should not be treated as a validated emergency-response or life-safety system.

## Future Improvements

Potential areas for further development include:

- Adding reproducible backend dependency management.
- Improving source citations and document-level traceability in responses.
- Expanding evaluation datasets and human review.
- Adding automated tests for retrieval and response generation.
- Improving error handling and API validation.
- Adding deployment automation and application monitoring.
- Evaluating response reliability against a broader set of official disaster-management scenarios.

## Author

**Anshi Tiwari**

GitHub: [@Anshi-19](https://github.com/Anshi-19)

---

*Built as a project exploring Retrieval-Augmented Generation, local LLMs, document retrieval, and model evaluation for disaster-related information access.*
