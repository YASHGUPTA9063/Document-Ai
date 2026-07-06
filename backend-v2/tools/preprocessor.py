from config import settings
from utils.preprocessor import preprocess_image

# ─── TOOL SCHEMAS ───
PREPROCESSOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "enhance_document_image",
            "description": "Applies image resolution normalization, brightness CLAHE adjustment, Gaussian noise removal, and skew angle correction to the document file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The file path of the document to preprocess."
                    },
                    "output_path": {
                        "type": "string",
                        "description": "The output file path where the preprocessed file should be saved."
                    }
                },
                "required": ["file_path", "output_path"]
            }
        }
    }
]

# ─── TOOL FUNCTIONS ───
def enhance_document_image(file_path: str, output_path: str) -> dict:
    return preprocess_image(
        file_path=file_path,
        output_path=output_path,
        preprocess_pdf=settings.ENABLE_PREPROCESSING_PDF,
    )
