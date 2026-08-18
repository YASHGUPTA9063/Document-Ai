"""
Settings & Templates Routes (v1)
================================
Handles system settings, classification config, normalization config,
and document template generation.
"""

import logging
from fastapi import APIRouter, HTTPException, File, UploadFile
from typing import List

from utils.norm_config import load_normalization_config, save_normalization_config
from utils.classification_config import load_classification_config, save_classification_config
from utils.file_handler import get_file_as_base64
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings & Templates"])


@router.get("/settings/normalization")
async def get_normalization_settings():
    """Get the field normalization configuration."""
    return load_normalization_config()


@router.put("/settings/normalization")
async def update_normalization_settings(config: dict):
    """Update the field normalization configuration."""
    save_normalization_config(config)
    return {"message": "Normalization settings updated successfully"}


@router.get("/settings/classification")
async def get_classification_settings():
    """Get the supported document types."""
    return load_classification_config()


@router.put("/settings/classification")
async def update_classification_settings(doc_types: list[str]):
    """Update the supported document types."""
    save_classification_config(doc_types)
    return {"message": "Classification settings updated successfully"}


@router.get("/templates")
async def get_templates():
    """Get all extraction templates."""
    from utils.templates import load_templates
    return load_templates()


@router.put("/templates")
async def save_templates_route(templates_data: dict):
    """Save extraction templates."""
    from utils.templates import save_templates_to_file
    save_templates_to_file(templates_data)
    return {"message": "Templates saved successfully"}


@router.delete("/templates/{template_name}")
async def delete_template(template_name: str):
    """Delete an extraction template."""
    from utils.templates import load_templates, save_templates_to_file
    templates = load_templates()
    if template_name not in templates:
        raise HTTPException(status_code=404, detail="Template not found")
    del templates[template_name]
    save_templates_to_file(templates)
    return {"message": f"Template {template_name} deleted successfully"}


@router.post("/templates/generate")
async def generate_template_from_sample(
    template_name: str,
    is_kyc: bool = False,
    kyc_boxes: str | None = None,
    file: UploadFile = File(...)
):
    """
    Generate a template configuration by analyzing a sample document.
    Uses the Vision/LLM provider to extract a schema.
    """
    import os
    import tempfile
    
    ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")
        
    temp_path = ""
    try:
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        if file.content_type == "application/pdf":
            import fitz
            doc = fitz.open(temp_path)
            page = doc.load_page(0)
            pix = page.get_pixmap()
            png_bytes = pix.tobytes("png")
            import base64
            base64_data = base64.b64encode(png_bytes).decode('utf-8')
            mime_type = "image/png"
        else:
            base64_data = get_file_as_base64(temp_path)
            mime_type = file.content_type
        
        # Use new ProviderRegistry
        from platform_core.registry import ProviderRegistry
        registry = ProviderRegistry.get()
        llm = registry.get_llm_chain("template_generator")
        
        prompt = f"""
        Analyze this sample document of type '{template_name}'.
        Generate a comprehensive list of all fields that can be extracted from this type of document.
        For each field, determine its logical name (snake_case) and data type (string, date, number, boolean, array).
        Also provide a concise description for the AI to understand what this field represents.
        
        Return the result as a JSON array of objects with keys: name, type, description.
        Only output the valid JSON array, without markdown formatting.
        """
        
        # We need a vision model to analyze the image/PDF
        vision = registry.get_vision_chain("template_generator")
        
        # If the vision provider supports data URLs:
        data_url = f"data:{mime_type};base64,{base64_data}"
        
        response = await vision.call(
            method="analyze",
            images=[data_url],
            prompt=prompt,
            response_format={"type": "json_object"}
        )
        
        import json
        import re
        
        text = response.content
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            text = match.group(0)
            
        try:
            fields_list = json.loads(text)
        except json.JSONDecodeError:
            if isinstance(text, dict):
                fields_list = text.get("fields", [])
            else:
                fields_list = []
                
        # Format the result to match the expected template structure
        generated_template = {
            "is_kyc": is_kyc,
            "fields": []
        }
        
        if kyc_boxes:
            try:
                generated_template["kyc_boxes"] = json.loads(kyc_boxes)
            except json.JSONDecodeError:
                pass
        
        for field in fields_list:
            if isinstance(field, dict) and "name" in field:
                name = field["name"]
                generated_template["fields"].append({
                    "key": name,
                    "label": name.replace("_", " ").title(),
                    "type": field.get("type", "string"),
                    "description": field.get("description", f"Extracted {name}"),
                    "required": True
                })
                
        from utils.templates import load_templates, save_templates_to_file
        from tools.extractor import _normalize_template_key

        # Store under the same normalized key the extractor looks templates up
        # by, so a template named "Pan Card" is found for doc_type "pan_card".
        normalized_name = _normalize_template_key(template_name)
        templates = load_templates()
        templates[normalized_name] = generated_template
        save_templates_to_file(templates)

        return {
            "message": "Template generated successfully",
            "template_name": normalized_name,
            "template": generated_template
        }
        
    except Exception as e:
        logger.error(f"Error generating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)



# ─── Pipeline metadata enrichment ────────────────────────────────────────────
# Maps each agent role to static info that Mistral's API doesn't store:
# step index, icon, accent color, and the workflow tools it runs alongside.
AGENT_PIPELINE_META = {
    "intake": {
        "step": 1,
        "role": "Document intake and duplicate checking",
        "emoji": "📥",
        "color": "rgba(6,192,219,0.15)",
        "border": "#06c0db",
        "pipeline_tools": ["check_document_duplicates"],
    },
    "pre_validator": {
        "step": 2,
        "role": "Document quality gate",
        "emoji": "🛡️",
        "color": "rgba(6,182,212,0.15)",
        "border": "#06b6d4",
        "pipeline_tools": ["get_file_metadata"],
    },
    "preprocessing": {
        "step": 2.5,
        "role": "Document image enhancement",
        "emoji": "⚙️",
        "color": "rgba(16,185,129,0.15)",
        "border": "#10b981",
        "pipeline_tools": ["enhance_document_image"],
    },
    "classifier": {
        "step": 3,
        "role": "Document type identification",
        "emoji": "🏷️",
        "color": "rgba(124,58,237,0.15)",
        "border": "#7c3aed",
        "pipeline_tools": ["get_document_text", "get_supported_document_types"],
    },
    "fraud_checker": {
        "step": 3.5,
        "role": "KYC forensic fraud check",
        "emoji": "🛡️",
        "color": "rgba(225,29,72,0.15)",
        "border": "#e11d48",
        "pipeline_tools": ["run_identity_proofing"],
    },
    "others_extractor": {
        "step": 4,
        "role": "General document extraction",
        "emoji": "📄",
        "color": "rgba(107,114,128,0.15)",
        "border": "#6b7280",
        "pipeline_tools": ["extract_text_from_document", "crop_kyc_images"],
    },
    "validator": {
        "step": 5,
        "role": "Data quality assurance",
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
        "role": "Human-in-the-loop review",
        "emoji": "👤",
        "color": "rgba(240,64,96,0.15)",
        "border": "#f04060",
        "pipeline_tools": ["get_review_context"],
    },
    "output": {
        "step": 7,
        "role": "Result persistence and export",
        "emoji": "📤",
        "color": "rgba(79,110,247,0.15)",
        "border": "#4f6ef7",
        "pipeline_tools": ["persist_final_extraction"],
    },
}


@router.get("/agents")
async def list_agents():
    """
    Returns the full agent pipeline — all live Mistral agents.
    Includes the pre-validator, preprocessing, classifier, fraud checker,
    extractor, validator, auto-verifier, sub-verifiers, reviewer, and output agents.
    Each agent is fetched from the Mistral API to get its real name, description, and model.
    """
    from mistralai.client import Mistral

    mistral_client = Mistral(api_key=settings.MISTRAL_API_KEY)

    agent_configs = [
        ("intake",                 settings.INTAKE_AGENT_ID),
        ("pre_validator",          settings.PRE_VALIDATOR_AGENT_ID),
        ("preprocessing",          settings.PREPROCESSING_AGENT_ID),
        ("classifier",             settings.CLASSIFIER_AGENT_ID),
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

    mistral_agents = []
    for key, agent_id in agent_configs:
        if not agent_id:
            continue
        meta = AGENT_PIPELINE_META.get(key)
        if not meta:
            continue
        try:
            agent_data = mistral_client.beta.agents.get(agent_id=agent_id)
            # Extract tool names from agent_data.tools
            tool_names = []
            if agent_data.tools:
                for t in agent_data.tools:
                    if hasattr(t, 'function') and hasattr(t.function, 'name'):
                        tool_names.append(t.function.name)
                    elif hasattr(t, 'type'):
                        tool_names.append(str(t.type))
                    else:
                        tool_names.append(str(t))
            display_name = " ".join(w.capitalize() for w in key.split("_"))
            mistral_agents.append({
                "key": key,
                "name": agent_data.name or display_name + " Agent",
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
            display_name = " ".join(w.capitalize() for w in key.split("_"))
            # Graceful fallback — still show the agent with static data
            mistral_agents.append({
                "key": key,
                "name": display_name + " Agent",
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

    mistral_agents.sort(key=lambda a: a["step"])
    return mistral_agents
