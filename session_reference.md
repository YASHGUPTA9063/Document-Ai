# Document AI Platform Migration — Session Reference

> **Conversation ID**: `d414d136-abc1-4f88-8d19-d88d8d264b38`
> **Date**: 2026-07-16
> **Goal**: Transform the Mistral-coupled Document AI backend into a plug-and-play, model-agnostic platform.

---

## 1. What We Did

### Design Phase
1. **Mapped the current codebase** — created [BACKEND_V2_CODE_GRAPH.md](file:///c:/Users/MrHarshGurjar/Desktop/code/Document-Ai/BACKEND_V2_CODE_GRAPH.md) with full dependency graph and Mermaid architecture diagrams.
2. **Created the production design document** — [production_recommendations.md](file:///C:/Users/MrHarshGurjar/.gemini/antigravity-ide/brain/d414d136-abc1-4f88-8d19-d88d8d264b38/production_recommendations.md) — a 13-section blueprint covering:
   - Provider abstraction (5 interfaces)
   - Fallback chains + circuit breakers
   - Pipeline engine with checkpoints
   - Process isolation (sandboxing)
   - Directory structure, config schema, deployment topology
   - Implementation roadmap (5 phases)
   - File-by-file migration map
3. **User-requested modifications**:
   - Removed the Security Architecture layer (Section 8) to reduce complexity
   - Added complete Mistral provider implementations (LLM, OCR, Vision) derived from current code
   - Document was approved by the user

### Implementation Phase (Phase 1 — Foundation)
Built the `platform_core/` package with 9 modules, all imports verified passing.

---

## 2. Files Created

### Platform Core (`backend-v2/platform_core/`)

| File | Purpose |
|---|---|
| [interfaces.py](file:///c:/Users/MrHarshGurjar/Desktop/code/Document-Ai/backend-v2/platform_core/providers/interfaces.py) | 5 abstract base classes: `LLMProvider`, `OCRProvider`, `StorageProvider`, `EmbeddingProvider`, `VisionProvider` + response dataclasses (`LLMResponse`, `OCRResponse`, `EmbeddingResponse`) |
| [mistral.py](file:///c:/Users/MrHarshGurjar/Desktop/code/Document-Ai/backend-v2/platform_core/providers/llm/mistral.py) | `MistralLLM(LLMProvider)` — wraps `client.chat.complete_async()`, normalizes tool_calls to provider-agnostic format |
| [mistral_ocr.py](file:///c:/Users/MrHarshGurjar/Desktop/code/Document-Ai/backend-v2/platform_core/providers/ocr/mistral_ocr.py) | `MistralOCR(OCRProvider)` — wraps `client.ocr.process()`, parses pages/blocks/confidence/bounding boxes |
| [mistral_vision.py](file:///c:/Users/MrHarshGurjar/Desktop/code/Document-Ai/backend-v2/platform_core/providers/vision/mistral_vision.py) | `MistralVision(VisionProvider)` — wraps pixtral multimodal chat for signature/face comparison |
| [registry.py](file:///c:/Users/MrHarshGurjar/Desktop/code/Document-Ai/backend-v2/platform_core/registry.py) | `ProviderRegistry` — singleton factory, builds from config dict, provides direct access + fallback chain access |
| [fallback.py](file:///c:/Users/MrHarshGurjar/Desktop/code/Document-Ai/backend-v2/platform_core/resilience/fallback.py) | `FallbackChain[T]` — tries providers in order, skips open circuit breakers, raises `AllProvidersFailedError` |
| [circuit_breaker.py](file:///c:/Users/MrHarshGurjar/Desktop/code/Document-Ai/backend-v2/platform_core/resilience/circuit_breaker.py) | `CircuitBreaker` — 3-state machine (CLOSED→OPEN→HALF_OPEN), configurable threshold + recovery timeout |
| [retry.py](file:///c:/Users/MrHarshGurjar/Desktop/code/Document-Ai/backend-v2/platform_core/resilience/retry.py) | `RetryPolicy` — exponential backoff with jitter, only retries transient errors |
| [manager.py](file:///c:/Users/MrHarshGurjar/Desktop/code/Document-Ai/backend-v2/platform_core/prompts/manager.py) | `PromptManager` — loads system prompts from `.md` files (replaces Mistral Agent IDs) |

### Artifacts

| Artifact | Path |
|---|---|
| Design Document | [production_recommendations.md](file:///C:/Users/MrHarshGurjar/.gemini/antigravity-ide/brain/d414d136-abc1-4f88-8d19-d88d8d264b38/production_recommendations.md) |
| Task Tracker | [task.md](file:///C:/Users/MrHarshGurjar/.gemini/antigravity-ide/brain/d414d136-abc1-4f88-8d19-d88d8d264b38/task.md) |
| Phase 1 Walkthrough | [walkthrough.md](file:///C:/Users/MrHarshGurjar/.gemini/antigravity-ide/brain/d414d136-abc1-4f88-8d19-d88d8d264b38/walkthrough.md) |
| Architecture Diagram | [architecture_diagram](file:///C:/Users/MrHarshGurjar/.gemini/antigravity-ide/brain/d414d136-abc1-4f88-8d19-d88d8d264b38/architecture_diagram_1784196649328.png) |
| Detailed Architecture | [detailed_architecture](file:///C:/Users/MrHarshGurjar/.gemini/antigravity-ide/brain/d414d136-abc1-4f88-8d19-d88d8d264b38/detailed_architecture_1784196826832.png) |
| System Architecture | [system_architecture.md](file:///C:/Users/MrHarshGurjar/.gemini/antigravity-ide/brain/d414d136-abc1-4f88-8d19-d88d8d264b38/system_architecture.md) |

---

## 3. Key Design Decisions

| Decision | Rationale |
|---|---|
| **Package named `platform_core/`** not `platform/` | Python's stdlib has a `platform` module; naming conflict breaks `httpx` → `mistralai` imports |
| **Security layer removed** | User requested simplification — no auth, RBAC, encryption, or audit logging |
| **Prompts as `.md` files** not Mistral Agent IDs | Makes the system provider-agnostic — same prompt works with any LLM |
| **FallbackChain is generic `[T]`** | Same chain pattern works for LLM, OCR, Vision, Storage |
| **Registry uses `from_config()` factory** | Single YAML file drives all provider initialization at startup |
| **OCR response includes bounding blocks** | Needed for citation highlighting in the frontend (current feature) |

---

## 4. Current State

### ✅ Phase 1 — Done
- Provider interfaces (5 ABCs)
- Mistral providers (LLM, OCR, Vision)
- Resilience primitives (FallbackChain, CircuitBreaker, RetryPolicy)
- Provider Registry (singleton, config-driven)
- Prompt Manager

### 📋 Phase 1 — Remaining
- `LocalStorage` provider (`platform_core/providers/storage/local.py`)
- `DINOv2Embedding` provider (`platform_core/providers/embedding/dinov2.py`)
- System prompt `.md` files (extract from Mistral Studio agent instructions)
- `HealthMonitor` (`platform_core/resilience/health.py`)
- `config/platform.yaml` + config loader

### ⏳ Future Phases
- **Phase 2**: Pipeline Engine (engine.py, checkpoint.py, HITL, migrate steps)
- **Phase 3**: Infrastructure (PostgreSQL, Redis queue, sandbox, API routers)
- **Phase 4**: Observability (OpenTelemetry, Prometheus, Docker)
- **Phase 5**: Testing (unit, integration, load)

---

## 5. How to Continue

### For the next agent:
1. Read the **design document**: [production_recommendations.md](file:///C:/Users/MrHarshGurjar/.gemini/antigravity-ide/brain/d414d136-abc1-4f88-8d19-d88d8d264b38/production_recommendations.md)
2. Read the **task tracker**: [task.md](file:///C:/Users/MrHarshGurjar/.gemini/antigravity-ide/brain/d414d136-abc1-4f88-8d19-d88d8d264b38/task.md)
3. Continue with remaining Phase 1 items or move to Phase 2
4. All imports are verified — `python -c "from platform_core.registry import ProviderRegistry"` works

### Key files in the existing codebase to reference:
- `backend-v2/activities/*.py` — 16 activity files, all follow same Mistral agent pattern
- `backend-v2/utils/ocr.py` — OCR logic ported to MistralOCR
- `backend-v2/utils/signature_verifier.py` — Vision + DINOv2 logic (DINOv2 provider still pending)
- `backend-v2/utils/file_handler.py` — Storage logic (LocalStorage provider still pending)
- `backend-v2/config.py` — Current settings (flat `.env`, Mistral Agent IDs)
- `backend-v2/workflow.py` — Current pipeline orchestration (Mistral workflows SDK)
