# Document Processing — Step-by-Step Timing Table

**Run Date:** July 30, 2026  
**Run Time:** 17:46:16 → 17:47:48  
**Total Duration:** 91.486 seconds  

---

## Full Timing Breakdown

| # | Step | Sub-step / Internal Call | Start Time | End Time | Duration | Cumulative |
|---|------|--------------------------|------------|----------|----------|------------|
| — | **Workflow kick-off** | | | | | |
| 1 | Status update → "processing" | DB write | 17:46:16.543 | 17:46:16.550 | 0.007s | 0.007s |
| — | *Scheduler gap* | | 17:46:16.550 | 17:46:17.301 | 0.751s | 0.758s |
| — | **INTAKE** | | | | | |
| 2 | `intake_activity` | *(total)* | 17:46:17.301 | 17:46:17.369 | **0.068s** | 0.826s |
| 2a | ↳ check_document_duplicates | DB lookup | 17:46:17.305 | 17:46:17.368 | 0.064s | |
| — | *Scheduler gap* | | 17:46:17.369 | 17:46:18.037 | 0.668s | 1.494s |
| — | **DUPLICATE FLAG — HUMAN PAUSE** | | | | | |
| 3 | Status update → "awaiting_review" | DB write | 17:46:18.037 | 17:46:18.045 | 0.009s | 1.503s |
| ⏸ | ***Human override decision wait*** | *Human response time* | 17:46:18.045 | 17:46:42.389 | **24.344s** | 25.847s |
| 4 | Status update → "processing" | DB write | 17:46:42.389 | 17:46:42.395 | 0.006s | 25.853s |
| — | *Scheduler gap* | | 17:46:42.395 | 17:46:42.813 | 0.418s | 26.271s |
| — | **PRE-VALIDATION** | | | | | |
| 5 | Status update → "pre_validating" | DB write | 17:46:42.813 | 17:46:42.819 | 0.006s | 26.277s |
| — | *Scheduler gap* | | 17:46:42.819 | 17:46:43.504 | 0.685s | 26.962s |
| 6 | `pre_validator_activity` | *(total)* | 17:46:43.504 | 17:46:51.956 | **8.451s** | 35.413s |
| 6a | ↳ AI Agent call 1 | Initial analysis | 17:46:43.504 | 17:46:44.557 | 1.053s | |
| 6b | ↳ AI Agent call 2 | Quality checks run | 17:46:44.559 | 17:46:51.947 | 7.388s | |
| — | *Scheduler gap* | | 17:46:51.956 | 17:46:52.594 | 0.638s | 36.051s |
| — | **PREPROCESSING** | | | | | |
| 7 | Status update → "preprocessing" | DB write | 17:46:52.594 | 17:46:52.601 | 0.007s | 36.058s |
| — | *Scheduler gap* | | 17:46:52.601 | 17:46:53.272 | 0.671s | 36.729s |
| 8 | `preprocessor_activity` | *(total)* | 17:46:53.272 | 17:46:53.609 | **0.337s** | 37.066s |
| 8a | ↳ enhance_document_image | Local OpenCV | 17:46:53.274 | 17:46:53.609 | 0.335s | |
| — | *Scheduler gap* | | 17:46:53.609 | 17:46:54.245 | 0.636s | 37.702s |
| — | **CLASSIFICATION** | | | | | |
| 9 | Status update → "classifying" | DB write | 17:46:54.245 | 17:46:54.257 | 0.011s | 37.713s |
| — | *Scheduler gap* | | 17:46:54.257 | 17:46:55.046 | 0.789s | 38.502s |
| 10 | `classifier_activity` | *(total)* | 17:46:55.046 | 17:46:58.769 | **3.723s** | 42.225s |
| 10a | ↳ AI Agent call 1 | Doc type detection | 17:46:55.048 | 17:46:58.769 | 3.721s | |
| — | *Scheduler gap* | | 17:46:58.769 | 17:46:59.451 | 0.682s | 42.907s |
| 11 | update_doc_type_activity | DB write | 17:46:59.451 | 17:46:59.459 | 0.007s | 42.914s |
| — | *Scheduler gap* | | 17:46:59.459 | 17:47:00.111 | 0.652s | 43.566s |
| 12 | get_template_metadata_activity | Memory lookup | 17:47:00.111 | 17:47:00.113 | 0.001s | 43.567s |
| — | *Scheduler gap* | | 17:47:00.113 | 17:47:00.736 | 0.623s | 44.190s |
| — | **EXTRACTION** | | | | | |
| 13 | Status update → "extracting" | DB write | 17:47:00.736 | 17:47:00.866 | 0.130s ⚠️ | 44.320s |
| — | *Scheduler gap* | | 17:47:00.866 | 17:47:01.590 | 0.724s | 45.044s |
| 14 | `extractor_activity` | *(total)* | 17:47:01.590 | 17:47:37.521 | **35.932s** | 80.976s |
| 14a | ↳ AI Agent call 1 | Decides to run OCR | 17:47:01.592 | 17:47:05.828 | 4.236s | |
| 14b | ↳ extract_text_from_document | OCR API call | 17:47:05.831 | 17:47:11.786 | 5.957s | |
| 14c | ↳ AI Agent call 2 | Field extraction from OCR | 17:47:11.788 | 17:47:37.517 | **25.729s** | |
| — | *Scheduler gap* | | 17:47:37.521 | 17:47:38.274 | 0.753s | 81.729s |
| — | **VALIDATION** | | | | | |
| 15 | Status update → "validating" | DB write | 17:47:38.274 | 17:47:38.281 | 0.006s | 81.735s |
| — | *Scheduler gap* | | 17:47:38.281 | 17:47:38.971 | 0.690s | 82.425s |
| 16 | `validator_activity` | *(total)* | 17:47:38.971 | 17:47:42.558 | **3.587s** | 86.012s |
| 16a | ↳ AI Agent call 1 | Initial field check | 17:47:38.971 | 17:47:39.595 | 0.624s | |
| 16b | ↳ AI Agent call 2 | Structured validation | 17:47:39.597 | 17:47:42.556 | 2.959s | |
| — | *Scheduler gap* | | 17:47:42.558 | 17:47:43.695 | 1.137s | 87.149s |
| — | **REVIEW** | | | | | |
| 17 | `reviewer_activity` | *(total)* | 17:47:43.695 | 17:47:46.777 | **3.081s** | 90.230s |
| 17a | ↳ AI Agent call 1 | Confidence assessment | 17:47:43.695 | 17:47:44.362 | 0.667s | |
| 17b | ↳ AI Agent call 2 | Review reasoning | 17:47:44.362 | 17:47:45.466 | 1.104s | |
| 17c | ↳ AI Agent call 3 | Structured response | 17:47:45.468 | 17:47:46.775 | 1.307s | |
| — | *Scheduler gap* | | 17:47:46.777 | 17:47:47.985 | 1.208s | 91.438s |
| — | **OUTPUT** | | | | | |
| 18 | `output_activity` | *(total)* | 17:47:47.985 | 17:47:48.029 | **0.043s** | 91.481s |
| 18a | ↳ persist_final_extraction | DB write | 17:47:47.987 | 17:47:48.029 | 0.042s | |

---

## Totals by Category

| Category | Total Time | % of Wall Clock |
|---|---|---|
| Human pause (duplicate override) | 24.344s | 26.6% |
| Extraction (step 14 total) | 35.932s | 39.3% |
| Pre-validation (step 6 total) | 8.451s | 9.2% |
| Scheduler gaps (between steps) | 9.818s | 10.7% |
| Classification (step 10) | 3.723s | 4.1% |
| Validation (step 16) | 3.587s | 3.9% |
| Review (step 17) | 3.081s | 3.4% |
| Status / DB writes | 0.182s | 0.2% |
| Preprocessing + intake + output | 0.448s | 0.5% |
| **Grand Total** | **91.486s** | 100% |

---

## Totals by Internal Call Type

| Call Type | Count | Total Time |
|---|---|---|
| AI Agent calls | 9 calls | 45.748s |
| OCR API call | 1 call | 5.957s |
| DB writes | 7 writes | 0.182s |
| Local tool calls (OpenCV, memory) | 3 calls | 0.400s |
| Scheduler gaps | 14 gaps | 9.818s |
| Human pause | 1 pause | 24.344s |

---

*Source: `performance.log` · Document AI Backend v2 · Run: 2026-07-30 17:46–17:48*
