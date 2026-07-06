# Agent Tools & Functions Mapping

This file contains the mapping of project agents to the specific tools and functions they use, including pointers to the source implementations in the codebase.

---

## 🤖 Core Agents Mapping

### 1. **Intake Agent** (Enhance Document Handling)
* **Tools / Functions Used**:
  * `check_document_duplicates` defined in [tools/intake.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/intake.py#L32)
* **Purpose**: Checks the database for duplicates by file hash or filename before processing.

### 2. **Pre Validation Agent** (Document Quality check)
* **Tools / Functions Used**:
  * `get_file_metadata` defined in [tools/pre_validator.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/pre_validator.py#L34)
* **Purpose**: Determines the file extension, MIME type, and checks if visual analysis (base64 image attachment) is required.

### 3. **Document Classifier Agent** (Document type identification)
* **Tools / Functions Used**:
  * `get_supported_document_types` defined in [tools/classifier.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/classifier.py#L14)
  * `get_document_text` defined in [tools/classifier.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/classifier.py#L58)
* **Purpose**: Fetches templates list and runs OCR on the first two pages to identify the document type.

### 4. **Fraud Check Agent** (KYC forensic fraud check)
* **Tools / Functions Used**:
  * `run_identity_proofing` defined in [tools/fraud_checker.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/fraud_checker.py#L67)
* **Purpose**: Executes Google Document AI Identity Proofing or parses fallback local mock files to verify document authenticity.

### 5. **Extraction Agents** (Document Extraction & Data Normalization)
* **Tools / Functions Used**:
  * `extract_text_from_document` defined in [tools/extractor.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/extractor.py#L191)
  * `crop_kyc_images` defined in [tools/extractor.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/extractor.py#L226)
* **Purpose**: Extracts raw text and parses fields matching schema templates, and crops signature and photo images if processing KYC documents.

### 6. **Auto-Verifier Agent** (Automated Identity, Signature verification)
* **Tools / Functions Used**:
  * `find_customer_reference` defined in [tools/auto_verifier.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/auto_verifier.py#L80)
  * `verify_signature` defined in [tools/auto_verifier.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/auto_verifier.py#L154)
  * `verify_face` defined in [tools/auto_verifier.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/auto_verifier.py#L186)
* **Purpose**: Retrieves baseline records from database, matches signatures using DINOv2, and kicks off face verification pipelines.

### 7. **Face Verification Agent 1** (Face geometry & morphology check)
* **Tools / Functions Used**: **None** (No external tools used)
* **Purpose**: Forensic biometric analyst evaluating facial geometry, eyes, and nose. Processes base64 image structures directly via text/image prompts as defined in [create_face_agents.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/create_face_agents.py#L33-L82).

### 8. **Face Verification Agent 2** (Lower-Face & Secondary Biometric Feature Analysis)
* **Tools / Functions Used**: **None** (No external tools used)
* **Purpose**: Forensic biometric analyst evaluating mouth, lips, ears, chin, and markings. Processes base64 image structures directly as defined in [create_face_agents.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/create_face_agents.py#L84-L139).

### 9. **Face Verification Agent 3** (Face age variance analysis)
* **Tools / Functions Used**: **None** (No external tools used)
* **Purpose**: Biometric analyst identifying age-gap vs. structural modifications. Processes base64 image structures directly as defined in [create_face_agents.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/create_face_agents.py#L141-L192).

### 10. **Face Verification Judge** (Biometric Decision Orchestration & Verdict)
* **Tools / Functions Used**: **None** (No external tools used)
* **Purpose**: Receives JSON outputs from Specialist Agents 1, 2, and 3, returning arbitration codes: `1` (Different Person), `3` (Needs Human Review), or `5` (Same Person) as defined in [create_face_agents.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/create_face_agents.py#L194-L231).

### 11. **Human Review Assistant** (Human-in-the-Loop Decision Support & Reviewer)
* **Tools / Functions Used**:
  * `get_review_context` defined in [tools/reviewer.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/reviewer.py#L17)
* **Purpose**: Fetches the validated payload and confidence score to decide if manual intervention is needed and formats the case summaries.

---

## 🛠️ Other Workflow Agents (For Completeness)

### **Preprocessing Agent**
* **Tools / Functions Used**: 
  * `enhance_document_image` defined in [tools/preprocessor.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/preprocessor.py#L30)
* **Purpose**: Performs resolution, CLAHE, Gaussian blur, and skew adjustments on raw documents.

### **Validator Agent**
* **Tools / Functions Used**: 
  * `get_validation_schema` defined in [tools/validator.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/validator.py#L13)
* **Purpose**: Retrieves schema restrictions for verification.

### **Output Agent**
* **Tools / Functions Used**: 
  * `persist_final_extraction` defined in [tools/output.py](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend-v2/tools/output.py#L14)
* **Purpose**: Writes metadata, OCR confidence, verification outputs, and final validations to the database.
