# Document Processing Workflow — Performance Report

**Date of Run:** July 30, 2026 at 5:46 PM  
**Prepared by:** Engineering Team  
**Document:** Single file processed end-to-end through the full pipeline  

---

## What This Report Covers

This report shows how long each step of our document processing system took during a real run.
The goal is to identify where time is being spent and where we can make it faster.

---

## Summary — Where Did the Time Go?

| Category | Time Spent | % of Total |
|---|---|---|
| ⏸ Human pause (duplicate review) | 24.3s | 27% |
| 🔴 Extraction (reading document fields) | 35.9s | 39% |
| 🟠 Pre-validation (document quality check) | 8.5s | 9% |
| 🟡 Classification (what type of document?) | 3.7s | 4% |
| 🟡 Validation (checking extracted data) | 3.6s | 4% |
| 🟡 Review (confidence check + approval) | 3.1s | 3% |
| System overhead (gaps between steps) | 9.8s | 11% |
| Everything else (intake, output, preprocessing) | 2.6s | 3% |
| **Total wall-clock time** | **91.5s** | 100% |

> **Key insight:** Excluding the human pause, the system itself takes ~67 seconds.
> Of that, **54% is spent in the Extraction step alone.**

---

## Step-by-Step Breakdown

### Step 0 — Workflow Start
- **What happens:** System marks the document as "processing" in the database.
- **Time:** 0.007s ✅

---

### Step 1 — Intake (Duplicate Check)
- **What happens:** The system checks whether this document has been submitted before.
- **Time:** 0.068s ✅
  - Database lookup: 0.064s

---

### ⏸ Human-in-the-Loop Pause — Duplicate Override
- **What happens:** The document was flagged as a potential duplicate. The system paused and waited for a human to decide whether to proceed anyway.
- **Decision received after:** **24.3 seconds**
- **Note:** This is not a system bottleneck — it depends entirely on how fast a human responds. The 24 second wait here was the reviewer making the override decision.

---

### Step 2 — Pre-Validation (Document Quality Check)
- **What happens:** An AI agent inspects the document image for quality issues — blurriness, poor lighting, skewed angle, blank pages, watermarks, etc.
- **Total time: 8.451s** 🟠
  - AI Agent Call 1 (deciding what to check): 1.053s
  - AI Agent Call 2 (running the actual checks): **7.388s**

> **Note:** This step uses an AI language model to perform checks that could potentially be done with standard image processing libraries. See recommendations section.

---

### Step 3 — Preprocessing (Image Enhancement)
- **What happens:** The document image is cleaned up — skew correction, brightness adjustment, noise removal.
- **Time:** 0.337s ✅
  - Image enhancement: 0.335s

---

### Step 4 — Classification (Document Type Detection)
- **What happens:** An AI agent reads the document and identifies what type it is (e.g., KYC document, invoice, medical report, etc.).
- **Total time: 3.723s** 🟡
  - AI Agent Call (single call): 3.721s

---

### Step 4a — Metadata Lookup
- **What happens:** System looks up rules/template for the identified document type.
- **Time:** 0.001s ✅ (instant, from memory)

---

### Step 5 — Extraction (Reading All Fields from the Document)
- **What happens:** This is the most complex step. An AI agent:
  1. Decides it needs to run OCR (text recognition) on the document
  2. Sends the document to the OCR API to extract raw text
  3. Reads that raw text and pulls out all structured fields (names, dates, amounts, etc.)
- **Total time: 35.932s** 🔴 **← Biggest cost in the entire pipeline**
  - AI Agent Call 1 (decides to call OCR): 4.236s
  - OCR API call (text recognition): **5.957s**
  - AI Agent Call 2 (field extraction from OCR text): **25.729s** ← dominant cost

> **Why is call 2 so slow?** The agent receives the entire raw OCR text output and has to read through it carefully to extract every structured field. This is doing a lot of work — the longer or more complex the document, the slower this gets.

---

### Step 6 — Validation (Checking Extracted Data)
- **What happens:** An AI agent reviews the extracted fields and checks for errors, missing values, inconsistencies, or low-confidence data.
- **Total time: 3.587s** 🟡
  - AI Agent Call 1 (initial check): 0.624s
  - AI Agent Call 2 (structured validation output): 2.959s

---

### Step 7 — Review (Confidence Check & Approval Decision)
- **What happens:** An AI agent scores the overall confidence of the extraction. If confidence is ≥ 80%, it auto-approves. Below that, it would flag for human review.
- **Total time: 3.081s** 🟡
  - AI Agent Call 1: 0.667s
  - AI Agent Call 2: 1.104s
  - AI Agent Call 3 (final structured response): 1.307s

---

### Step 8 — Output (Save Final Results)
- **What happens:** Final validated and approved data is written to the database.
- **Time:** 0.043s ✅
  - Database write: 0.042s

---

## System Overhead Between Steps

Between every step, there is a small delay caused by the workflow orchestration system (scheduling the next activity, serializing state, etc.). These gaps average **0.6–1.2 seconds** each and add up to **~9.8 seconds** across the full run.

This is infrastructure overhead — not application code — and is normal for this type of workflow system.

---

## What Is Normal vs. What Can Be Improved

| Step | Current | Status | Comment |
|---|---|---|---|
| Intake (duplicate check) | 0.068s | ✅ Normal | Fast |
| Preprocessing (image cleanup) | 0.337s | ✅ Normal | Fast |
| Classification | 3.7s | ✅ Acceptable | One AI call, expected |
| Validation | 3.6s | ✅ Acceptable | Two AI calls, expected |
| Review | 3.1s | ✅ Acceptable | Three AI calls, expected |
| Output (DB write) | 0.043s | ✅ Normal | Fast |
| **Pre-validation** | **8.5s** | 🟠 Can improve | AI doing image-processing work |
| **Extraction** | **35.9s** | 🔴 Needs attention | LLM field extraction is slow |
| System overhead (gaps) | 9.8s | 🟡 Acceptable | Normal for this workflow type |

---

## Recommendations (Priority Order)

### 🔴 Priority 1 — Reduce Extraction Time (~35.9s)

**The problem:** After OCR runs, the AI agent receives the full raw text of the document and takes 25.7 seconds to extract all fields.

**Two ways to improve this:**

1. **Trim the text sent to the AI** — Instead of sending the entire OCR output, pre-process it to send only the relevant sections. This reduces the amount of text the AI has to read, which directly reduces its response time. Estimated saving: **5–15 seconds.**

2. **Review extraction agent instructions** — The agent may be doing multiple internal reasoning steps. Simplifying its instructions to be more direct could reduce thinking time. Estimated saving: **2–5 seconds.**

---

### 🟠 Priority 2 — Replace Pre-Validation AI with Local Image Checks (~8.5s)

**The problem:** Checking a document for blur, skew, brightness, and blank pages is currently done by an AI language model, which takes 8.5 seconds.

**The solution:** These are standard image processing operations that can be done locally using libraries like OpenCV — no AI needed. This would bring pre-validation from **8.5s → ~0.3s**.

**Estimated saving: ~8 seconds per document.**

---

### 🟡 Priority 3 — Reduce Inter-Step Scheduling Gaps (~9.8s)

**The problem:** There is ~0.6–1.2s of dead time between every step, just from the workflow scheduler.

**Options:**
- Bundle consecutive tiny steps (status updates) to reduce the number of scheduling hops.
- Investigate whether the workflow SDK allows pipelining.

**Estimated saving: 2–4 seconds.**

---

## Potential Total Savings

| Optimization | Estimated Saving |
|---|---|
| Trim OCR text sent to agent | 5–15s |
| Replace pre-validation with local checks | ~8s |
| Reduce scheduling gaps | 2–4s |
| **Total potential saving** | **15–27 seconds** |
| **Current runtime (excl. human pause)** | **67.2s** |
| **Target runtime after optimizations** | **~40–52s** |

That's a **25–40% reduction** in processing time per document.

---

## Notes

- The human-in-the-loop pause (24.3s in this run) is not a system bottleneck — it is an intentional design feature to allow human override of duplicate detections. The actual system time if no duplicate is flagged would be ~67s total.
- All database operations are fast and are **not** a bottleneck.
- All timings are from a single run. Results may vary slightly run-to-run depending on AI model response times.

---

*Report generated from `performance.log` · Document AI Backend v2*
