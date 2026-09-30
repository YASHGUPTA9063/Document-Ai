"""
Settings, Templates & Agents Router
===================================
Normalization / classification / vLLM settings, extraction template CRUD and
AI-assisted template generation, plus the agent pipeline listing.

Moved verbatim from branch-vm3's monolithic main.py. The vLLM settings
endpoints are a branch-vm3 feature with no counterpart on `development`; they
drive the vLLM fallback re-extraction pass
(platform_core/providers/llm/vllm_fallback.py).
"""

import json
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Query

from config import settings
from utils.file_handler import save_file, delete_file
from utils.norm_config import load_normalization_config, save_normalization_config
from utils.classification_config import load_classification_config, save_classification_config
from utils.split_config import load_split_config, save_split_config
from utils.checklist_config import load_checklist_config, save_checklist_config
from utils.templates import load_templates, save_templates_to_file
from platform_core.prompts.manager import PromptManager
from api.deps import get_mistral_client

logger = logging.getLogger(__name__)

# Managed prompt template — see platform_core/prompts/template_generator.md
PROMPTS = PromptManager()

router = APIRouter(tags=["Settings & Templates"])


# ─── Settings ────────────────────────────────────────────────────────────────

@router.get("/settings/normalization")
async def get_normalization_settings():
    return load_normalization_config()


@router.put("/settings/normalization")
async def update_normalization_settings(config: dict):
    save_normalization_config(config)
    return {"success": True}


@router.get("/settings/classification")
async def get_classification_settings():
    return load_classification_config()


@router.put("/settings/classification")
async def update_classification_settings(doc_types: list[str]):
    save_classification_config(doc_types)
    return {"success": True}


@router.get("/settings/splitting")
async def get_splitting_settings():
    """
    Runtime tuning for the Step 1.5 packet splitter.

    `enabled` is reported for reference but is read-only: splitting is switched
    on and off by ENABLE_DOC_SPLITTING alone, so a value sent back to the PUT is
    ignored. Everything else here is a live knob.
    """
    return load_split_config()


@router.put("/settings/splitting")
async def update_splitting_settings(config: dict):
    try:
        return save_split_config(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/settings/checklist")
async def get_checklist_settings():
    """Document types that skip the Step 3.2 batch checklist."""
    return load_checklist_config()


@router.put("/settings/checklist")
async def update_checklist_settings(config: dict):
    """
    Save the skip list, then re-judge every batch currently held at the gate.

    A batch held only for a type that has just been put on the skip list has
    nothing outstanding any more, so it is released here rather than left
    waiting for a reviewer to press Re-check on each one.
    """
    try:
        saved = save_checklist_config(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from activities.checklist import evaluate_batch
    import db.checklist_operations as checklist_db

    released = []
    for batch_id in await checklist_db.get_open_gate_batch_ids():
        try:
            verdict = await evaluate_batch(batch_id)
            if verdict.get("action") == "released":
                released.append(batch_id)
        except Exception as e:
            # The settings are saved either way; a batch that could not be
            # re-judged simply stays at the gate for a manual Re-check.
            logger.warning(f"[Batch {batch_id}] Re-check after checklist settings change failed: {e}")

    return {**saved, "released_batches": released}


@router.get("/settings/features")
async def get_feature_flags():
    """
    Which optional pipeline stages are switched on for this deployment.

    The UI reads this to decide what to draw: a stage the workflow will never
    run must not show up as a step in the live pipeline, as an agent card, or as
    a settings section.

    Both flags are environment-only — `ENABLE_DOC_SPLITTING` for Step 1.5 and
    `ENABLE_DOC_CHECKLIST` for Step 3.2. Neither has a runtime override, so a
    deploy is the only way to turn a stage on or off and this endpoint is the
    single answer to "does it run here".
    """
    return {
        "doc_splitting": bool(settings.ENABLE_DOC_SPLITTING),
        "doc_checklist": bool(settings.ENABLE_DOC_CHECKLIST),
    }


@router.get("/settings/vllm")
async def get_vllm_settings():
    from utils.vllm_settings import load_vllm_settings
    return load_vllm_settings()


@router.put("/settings/vllm")
async def update_vllm_settings(config: dict):
    from utils.vllm_settings import save_vllm_settings
    save_vllm_settings(config)
    return {"success": True}


# ─── Templates ───────────────────────────────────────────────────────────────

@router.get("/templates")
async def get_templates():
    return load_templates()


@router.put("/templates")
async def save_templates(templates_data: dict):
    # save_templates_to_file validates any optional `id_marker` regex — catching it
    # here turns an author typo into a 400 instead of a mid-workflow crash later.
    try:
        save_templates_to_file(templates_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True}


@router.delete("/templates/{template_name}")
async def delete_template(template_name: str):
    templates = load_templates()
    normalized_name = template_name.strip().lower().replace(" ", "_")
    if normalized_name in templates:
        del templates[normalized_name]
        save_templates_to_file(templates)
        return {"success": True}
    else:
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")


@router.post("/templates/generate")
async def generate_template_from_sample(
    template_name: str = Query(...),
    is_kyc: bool = Query(False),
    use_vlm: bool = Query(False),
    kyc_boxes: str = Query(None, description="JSON string of {signature: {x1,y1,x2,y2}, photo: {x1,y1,x2,y2}} percentages"),
    file: UploadFile = File(...)
):
    # Save the file temporarily
    file_path, file_hash = await save_file(file, settings.STORAGE_DIR)

    try:
        from utils.ocr import extract_with_ocr
        # Perform OCR
        ocr_result = extract_with_ocr(file_path, "unknown")
        raw_text = ocr_result.get("raw_text", "")

        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from the sample document.")

        # Send OCR text to Mistral LLM to generate the fields schema
        prompt = PROMPTS.render(
            "template_generator", template_name=template_name, raw_text=raw_text
        )

        response = get_mistral_client().chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS
        )

        content = response.choices[0].message.content
        logger.info(f"Generated schema for template '{template_name}': {content}")

        # Parse generated fields
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "fields" in parsed:
            fields = parsed["fields"]
        elif isinstance(parsed, dict):
            # Try to find a list inside the dictionary
            fields = None
            for k, v in parsed.items():
                if isinstance(v, list):
                    fields = v
                    break
            if fields is None:
                if all(isinstance(v, dict) and 'label' in v for v in parsed.values()):
                    fields = []
                    for k, v in parsed.items():
                        fields.append({
                            "key": k,
                            "label": v.get("label", k),
                            "type": v.get("type", "Text"),
                            "required": v.get("required", False),
                            "description": v.get("description", "")
                        })
                else:
                    fields = list(parsed.values())
        else:
            fields = parsed

        if not isinstance(fields, list):
            raise ValueError("Invalid schema format generated by AI. Expected a list of fields.")

        valid_types = {"Text", "Number", "Date", "Boolean", "Array of Text", "Array of Objects"}
        validated_fields = []
        for f in fields:
            if not isinstance(f, dict) or "key" not in f or "label" not in f:
                continue
            key = str(f["key"]).strip().lower().replace(" ", "_")
            key = "".join([c for c in key if c.isalnum() or c == "_"])
            if not key:
                continue
            t = str(f.get("type", "Text")).strip()
            if t not in valid_types:
                t = "Text"
            validated_fields.append({
                "key": key,
                "label": str(f["label"]).strip(),
                "type": t,
                "required": bool(f.get("required", False)),
                "description": str(f.get("description", "")).strip()
            })

        if not validated_fields:
            raise ValueError("No valid fields could be parsed from the generated schema.")

        # If KYC, auto-append signature_image and photo_image fields
        if is_kyc:
            kyc_image_fields = [
                {
                    "key": "signature_image",
                    "label": "Signature",
                    "type": "Image",
                    "required": False,
                    "description": "Handwritten signature extracted from the KYC document."
                },
                {
                    "key": "photo_image",
                    "label": "Photo",
                    "type": "Image",
                    "required": False,
                    "description": "Cardholder photograph extracted from the KYC document."
                },
                {
                    "key": "signature_detected",
                    "label": "Signature Detected",
                    "type": "Boolean",
                    "required": False,
                    "description": "Whether a handwritten signature was found in the document."
                },
                {
                    "key": "photo_detected",
                    "label": "Photo Detected",
                    "type": "Boolean",
                    "required": False,
                    "description": "Whether a cardholder photo was found in the document."
                }
            ]
            # Remove any duplicates (in case AI already generated these)
            existing_keys = {f["key"] for f in validated_fields}
            for kf in kyc_image_fields:
                if kf["key"] not in existing_keys:
                    validated_fields.append(kf)

        # Save to templates (new format with is_kyc metadata)
        templates = load_templates()
        normalized_name = template_name.strip().lower().replace(" ", "_")
        template_entry = {
            "fields": validated_fields,
            "is_kyc": is_kyc,
            "use_vlm": use_vlm
        }

        # Parse and attach kyc_boxes if provided
        if kyc_boxes:
            try:
                parsed_boxes = json.loads(kyc_boxes)
                if isinstance(parsed_boxes, dict):
                    template_entry["kyc_boxes"] = parsed_boxes
                    logger.info(f"Saved kyc_boxes for template '{normalized_name}': {parsed_boxes}")
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse kyc_boxes: {e}")

        templates[normalized_name] = template_entry
        save_templates_to_file(templates)

        return {"success": True, "template_name": normalized_name, "fields": validated_fields, "is_kyc": is_kyc}
    except Exception as e:
        logger.error(f"Error generating template from sample: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup sample file
        import os
        if os.path.exists(file_path):
            delete_file(file_path)


# ─── Pipeline metadata enrichment ────────────────────────────────────────────
# Maps each agent role to static info that Mistral's API doesn't store:
# step index, icon, accent color, and the workflow tools it runs alongside.

AGENT_PIPELINE_META = {
    "intake": {
        "step": 1,
        "role": "Document ingestion and duplicate checking",
        "emoji": "📥",
        "color": "rgba(6,192,219,0.15)",
        "border": "#06c0db",
        "pipeline_tools": ["check_document_duplicates"],
    },
    "pre_validator": {
        "step": 2,
        "role": "Document quality check",
        "emoji": "🛡️",
        "color": "rgba(6,182,212,0.15)",
        "border": "#06b6d4",
        "pipeline_tools": ["get_file_metadata"],
    },
    "preprocessing": {
        "step": 2.5,
        "role": "Document pre-processing",
        "emoji": "⚙️",
        "color": "rgba(16,185,129,0.15)",
        "border": "#10b981",
        "pipeline_tools": ["enhance_document_image"],
    },
    "splitter": {
        "step": 1.5,
        "role": "Multi-document packet splitting",
        "emoji": "\u2702\ufe0f",
        "color": "rgba(217,119,6,0.15)",
        "border": "#d97706",
        "pipeline_tools": ["classify_packet_pages", "split_pdf"],
    },
    "classifier": {
        "step": 3,
        "role": "Document classification",
        "emoji": "🏷️",
        "color": "rgba(124,58,237,0.15)",
        "border": "#7c3aed",
        "pipeline_tools": ["get_document_text", "get_supported_document_types"],
    },
    "checklist": {
        "step": 3.2,
        "role": "Batch document checklist reconciliation",
        "emoji": "📋",
        "color": "rgba(13,148,136,0.15)",
        "border": "#0d9488",
        "pipeline_tools": ["build_required_types", "reconcile_batch"],
    },
    "fraud_checker": {
        "step": 3.5,
        "role": "KYC  fraud check",
        "emoji": "🛡️",
        "color": "rgba(225,29,72,0.15)",
        "border": "#e11d48",
        "pipeline_tools": ["run_identity_proofing"],
    },
    # ── Extractor (step 4) ──────────────────
    "others_extractor": {
        "step": 4,
        "role": "Document extraction",
        "emoji": "📄",
        "color": "rgba(107,114,128,0.15)",
        "border": "#6b7280",
        "pipeline_tools": ["extract_text_from_document", "crop_kyc_images"],
    },
    # ─────────────────────────────────────────────────────────────────────────
    "validator": {
        "step": 5,
        "role": "Document validation & quality assurance",
        "emoji": "✅",
        "color": "rgba(245,158,11,0.15)",
        "border": "#f59e0b",
        "pipeline_tools": ["get_validation_schema"],
    },
    "auto_verifier": {
        "step": 5.5,
        "role": "Automated reference verification",
        "emoji": "👤",
        "color": "rgba(168,85,247,0.15)",
        "border": "#a855f7",
        "pipeline_tools": ["find_customer_reference", "verify_signature", "verify_face"],
    },
    "signature_vision_agent": {
        "step": 5.5,
        "role": "Signature visual feature analysis",
        "emoji": "🔍",
        "color": "rgba(168,85,247,0.15)",
        "border": "#a855f7",
        "pipeline_tools": ["compare_signature_features"],
    },
    "signature_judge_agent": {
        "step": 5.5,
        "role": "Signature authenticity verdict",
        "emoji": "⚖️",
        "color": "rgba(168,85,247,0.15)",
        "border": "#a855f7",
        "pipeline_tools": ["evaluate_signature_match"],
    },
    "face_morphology1_agent": {
        "step": 5.5,
        "role": "Face geometry & morphology check",
        "emoji": "👤",
        "color": "rgba(59,130,246,0.15)",
        "border": "#3b82f6",
        "pipeline_tools": ["analyze_facial_geometry"],
    },
    "face_morphology2_agent": {
        "step": 5.5,
        "role": "Face secondary features check",
        "emoji": "👤",
        "color": "rgba(59,130,246,0.15)",
        "border": "#3b82f6",
        "pipeline_tools": ["analyze_secondary_features"],
    },
    "face_age_agent": {
        "step": 5.5,
        "role": "Face age variance analysis",
        "emoji": "👤",
        "color": "rgba(59,130,246,0.15)",
        "border": "#3b82f6",
        "pipeline_tools": ["evaluate_age_variance"],
    },
    "face_judge_agent": {
        "step": 5.5,
        "role": "Face match verdict judge",
        "emoji": "⚖️",
        "color": "rgba(59,130,246,0.15)",
        "border": "#3b82f6",
        "pipeline_tools": ["render_face_match_decision"],
    },
    "reviewer": {
        "step": 6,
        "role": "Human review",
        "emoji": "👤",
        "color": "rgba(240,64,96,0.15)",
        "border": "#f04060",
        "pipeline_tools": ["get_review_context"],
    },
    "output": {
        "step": 7,
        "role": "Document output persistence and export",
        "emoji": "📤",
        "color": "rgba(79,110,247,0.15)",
        "border": "#4f6ef7",
        "pipeline_tools": ["persist_final_extraction"],
    },
}

# Static agents that don't have Mistral agent IDs (they're pure workflow activities)
STATIC_AGENTS = []


@router.get("/agents")
async def list_agents():
    """
    Returns the full agent pipeline — all live Mistral agents.
    Includes the pre-validator, preprocessing, classifier, fraud checker,
    all 6 type-specific extractors, validator, auto-verifier, sub-verifiers, reviewer, and output agents.
    Each agent is fetched from the Mistral API to get its real name, description, and model.
    """
    # Optional stages only appear when they are actually switched on — an agent
    # the workflow will never call has no place in the pipeline listing. A blank
    # ID is skipped below, so gating is just "report no ID when disabled".
    splitter_id = settings.SPLITTER_AGENT_ID if settings.ENABLE_DOC_SPLITTING else ""
    checklist_id = settings.CHECKLIST_AGENT_ID if settings.ENABLE_DOC_CHECKLIST else ""

    agent_configs = [
        ("intake",                 settings.INTAKE_AGENT_ID),
        ("pre_validator",          settings.PRE_VALIDATOR_AGENT_ID),
        ("preprocessing",          settings.PREPROCESSING_AGENT_ID),
        ("splitter",               splitter_id),
        ("classifier",             settings.CLASSIFIER_AGENT_ID),
        ("checklist",              checklist_id),
        ("fraud_checker",          settings.FRAUD_AGENT_ID),
        ("others_extractor",       settings.GENERAL_EXTRACTOR_AGENT_ID),
        ("validator",              settings.VALIDATOR_AGENT_ID),
        ("auto_verifier",          settings.AUTO_VERIFIER_AGENT_ID),
        ("signature_vision_agent", settings.SIGNATURE_VISION_AGENT_ID),
        ("signature_judge_agent",  settings.SIGNATURE_JUDGE_AGENT_ID),
        ("face_morphology1_agent", settings.FACE_MORPHOLOGY1_AGENT_ID),
        ("face_morphology2_agent", settings.FACE_MORPHOLOGY2_AGENT_ID),
        ("face_age_agent",         settings.FACE_AGE_AGENT_ID),
        ("face_judge_agent",       settings.FACE_JUDGE_AGENT_ID),
        ("reviewer",               settings.REVIEWER_AGENT_ID),
        ("output",                 settings.OUTPUT_AGENT_ID),
    ]

    name_mapping = {
        "intake": "Ingestion Agent",
        "pre_validator": "Quality Check Agent",
        "preprocessing": "Pre Processing Agent",
        "splitter": "Document Splitter Agent",
        "classifier": "Classification Agent",
        "checklist": "Document Checklist Agent",
        "others_extractor": "Extraction Agent",
        "validator": "Validation Agent",
        "reviewer": "Human Review Agent",
        "output": "Output Agent"
    }

    client = get_mistral_client()
    mistral_agents = []
    for key, agent_id in agent_configs:
        if not agent_id:
            continue
        meta = AGENT_PIPELINE_META[key]
        display_name = " ".join(w.capitalize() for w in key.split("_"))
        agent_default_name = name_mapping.get(key, display_name + " Agent")
        try:
            agent_data = client.beta.agents.get(agent_id=agent_id)
            # agent_data.tools is a list of tool objects; extract names safely
            tool_names = []
            if agent_data.tools:
                for t in agent_data.tools:
                    if hasattr(t, 'function') and hasattr(t.function, 'name'):
                        tool_names.append(t.function.name)
                    elif hasattr(t, 'type'):
                        tool_names.append(str(t.type))
                    else:
                        tool_names.append(str(t))
            mistral_agents.append({
                "key": key,
                "name": agent_data.name or agent_default_name,
                "step": meta["step"],
                "role": meta["role"],
                "description": agent_data.description or f"Mistral-hosted agent for {display_name.lower()} tasks.",
                "emoji": meta["emoji"],
                "color": meta["color"],
                "border": meta["border"],
                "model": agent_data.model,
                "agent_id": agent_id,
                "tools": tool_names or meta["pipeline_tools"],
                "source": "mistral",
            })
        except Exception as e:
            logger.warning(f"Failed to fetch Mistral agent '{key}' ({agent_id}): {e}")
            # Graceful fallback — still show the agent with static data
            mistral_agents.append({
                "key": key,
                "name": agent_default_name,
                "step": meta["step"],
                "role": meta["role"],
                "description": f"Mistral-hosted agent for {display_name.lower()} tasks. (Metadata fetch failed)",
                "emoji": meta["emoji"],
                "color": meta["color"],
                "border": meta["border"],
                "model": "mistral-agent",
                "agent_id": agent_id,
                "tools": meta["pipeline_tools"],
                "source": "mistral_fallback",
            })

    # Merge: static agents + mistral agents, sorted by pipeline step
    all_agents = STATIC_AGENTS + mistral_agents

    all_agents.sort(key=lambda a: a["step"])
    return all_agents
