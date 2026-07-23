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
        templates = load_templates()
        templates[template_name] = generated_template
        save_templates_to_file(templates)
        
        return {
            "message": "Template generated successfully",
            "template_name": template_name,
            "template": generated_template
        }
        
    except Exception as e:
        logger.error(f"Error generating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/agents")
async def list_agents():
    """
    List all configured agents in the system.
    """
    # Use registry summary
    from platform_core.registry import ProviderRegistry
    registry = ProviderRegistry.get()
    
    # We could combine this with AGENT_PIPELINE_META from main.py
    return {
        "status": "success",
        "providers": registry.summary()
    }
