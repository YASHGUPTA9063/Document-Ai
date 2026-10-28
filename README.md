# 🧠 DocuMind AI — Intelligent Document Processing (IDP) Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-flat)](http://makeapullrequest.com)
[![Modern UI](https://img.shields.io/badge/UI-Modern%20Dark-indigo.svg)](#aesthetics)

**DocuMind AI** is a state-of-the-art, interactive Intelligent Document Processing (IDP) platform dashboard. It simulates a complete multi-agent orchestration pipeline to ingest, extract, analyze, validate, and audit enterprise documents using advanced AI agents.

---

## 🌟 Key Features

*   📊 **Real-time Analytics Dashboard** — High-fidelity key metrics (extraction accuracy, average processing times, agent counts) with micro-interactive data tables.
*   🤖 **AI Agent Orchestration Hub** — Multi-agent setup featuring specialized agents (OCR Engine, Schema Validator, PII Redactor, Semantic Classifier) showing detailed status, descriptions, and performance indexes.
*   📤 **Interactive Document Upload** — Dynamic drag-and-drop zone with format chips and instant visual feedback.
*   ⚙️ **Live Pipeline Visualization** — Visual step-by-step pipeline tracker (Ingestion ➔ OCR ➔ Classification ➔ Extraction ➔ Validation ➔ Human-in-the-loop) with active state cues.
*   🔍 **OCR Extraction Inspector** — High-precision visual OCR overlay overlaying extracted fields with target confidence levels.
*   📟 **Agent Activity Console** — Real-time interactive simulated streaming console log capturing OCR outputs, agent interactions, and validation steps.
*   ⚡ **Fluid Responsive UI** — Built from scratch with glassmorphism aesthetics, glowing gradient borders, tailored HSL color schemes, and seamless UI transitions.

---

## 🎨 Design & Aesthetics

The application is engineered using professional, premium front-end styling practices:
*   **Modern Color Palette** — Carefully curated dark theme built on sleek midnight blues, deep indigo shadows, and vibrant neon accents (purple, cyan, and emerald).
*   **Micro-Animations** — Smooth CSS transitions, active indicator pulsing, hover scale-up transforms, and rotating loader cues.
*   **Glassmorphism** — Subtle translucid layer overlays and high-contrast borders for card modules.
*   **Modern Typography** — Integrated clean system font stacks and high-contrast metadata layers.

---

## 🚀 Getting Started

**DocuMind AI** is composed of a FastAPI backend and a Vite+React frontend.

### 1. Start the Backend

1. Navigate to the `backend` directory.
2. Create your `.env` file from the example: `cp .env.example .env` and fill in your API keys and Mistral Agent IDs.
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

### 2. Start the Frontend

1. Navigate to the `frontend-v2` directory.
2. Install the frontend dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```
4. Open the displayed local URL in your browser to access the dashboard.

### 3. Deploy on an Azure VM

On a fresh Ubuntu VM, from the repo root (with the real secrets in `backend-v2/.env`):

```bash
chmod +x deploy-azure.sh
./deploy-azure.sh            # installs Docker, builds, starts the whole stack
./deploy-azure.sh status     # or: logs [service] | restart | stop
```

The app is served on port 80 (nginx serves the UI and proxies `/api/`), so the
NSG needs inbound 22 (SSH, your IP only) and 80. The API stays bound to
`127.0.0.1:8000` unless you pass `--expose-api`.

---

## 🛠️ Built With

**Frontend (`frontend-v2`):**
*   **Vite & React** — Fast build tool and component-based UI framework.
*   **Vanilla CSS3** — CSS Custom Variables, modern layouts, and premium glassmorphism filters.
*   **Lucide React** — Elegant iconography.

**Backend (`backend`):**
*   **FastAPI & Uvicorn** — High-performance asynchronous API framework.
*   **Mistral AI & Workflows** — Intelligent agents for document extraction, classification, and validation.
*   **SQLAlchemy & SQLite** — Asynchronous data persistence.

---

