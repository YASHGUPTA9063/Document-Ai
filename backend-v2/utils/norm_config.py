import os
import json
from config import settings

NORM_CONFIG_FILE = os.path.join(settings.STORAGE_DIR, "norm_config.json")

DEFAULT_NORM_CONFIG = {
    "date_format": "YYYY-MM-DD",
    "number_format": "float",
    "name_casing": "Title Case",
    "name_sequence": "First Name Last Name",
    "custom_rules": ""
}

def load_normalization_config() -> dict:
    if os.path.exists(NORM_CONFIG_FILE):
        try:
            with open(NORM_CONFIG_FILE, "r") as f:
                config = json.load(f)
                # Ensure all default keys exist
                for k, v in DEFAULT_NORM_CONFIG.items():
                    if k not in config:
                        config[k] = v
                return config
        except Exception as e:
            pass
    return DEFAULT_NORM_CONFIG.copy()

def save_normalization_config(config: dict):
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    # Filter to only allow valid keys
    filtered_config = {}
    for k in DEFAULT_NORM_CONFIG.keys():
        filtered_config[k] = config.get(k, DEFAULT_NORM_CONFIG[k])
    
    with open(NORM_CONFIG_FILE, "w") as f:
        json.dump(filtered_config, f, indent=2)

def build_normalization_rules_prompt() -> str:
    config = load_normalization_config()
    
    date_opt = config.get("date_format", "YYYY-MM-DD")
    num_opt = config.get("number_format", "float")
    casing_opt = config.get("name_casing", "Title Case")
    custom_rules = config.get("custom_rules", "")
    
    # 1. Date rule
    if date_opt == "YYYY-MM-DD":
        date_str = "Normalize to YYYY-MM-DD format (e.g. '25 June 2026' -> '2026-06-25'). If invalid or missing, keep empty."
    elif date_opt == "MM/DD/YYYY":
        date_str = "Normalize to MM/DD/YYYY format (e.g. '25 June 2026' -> '06/25/2026'). If invalid or missing, keep empty."
    elif date_opt == "DD/MM/YYYY":
        date_str = "Normalize to DD/MM/YYYY format (e.g. '25 June 2026' -> '25/06/2026'). If invalid or missing, keep empty."
    else:
        date_str = "Keep the date in its original raw string format as extracted."
        
    # 2. Number rule
    if num_opt == "float":
        num_str = "Convert monetary amounts to float/integer numbers (e.g. '$1,250.50' -> 1250.5). Strip currency symbols. (Note: rate/percentage fields are preserved separately)."
    elif num_opt == "integer":
        num_str = "Convert monetary amounts to integer numbers (e.g. '$1,250.50' -> 1250). Strip decimals and currency symbols. (Note: rate/percentage fields are preserved separately)."
    else:
        num_str = "Keep numbers as strings (e.g. '$1,250.50' -> '$1,250.50')."
        
    # 3. Rate & Percentage rule
    rate_str = "For rate, percentage, or withholding fields (e.g. 'Tax Treaty Withholding Rate', 'Tax Rate', 'Interest Rate', etc.), always preserve or append the percentage sign '%' in normalized_extracted (e.g. '21%' or 21 -> '21%'). Do NOT strip the '%' sign from rate/percentage fields."

    # 4. Casing rule
    pincode_note = " For addresses, include the pincode/postal code if one is present in the document."
    if casing_opt == "Title Case":
        casing_str = "Normalize spelling and standardize to Title Case." + pincode_note
    elif casing_opt == "UPPERCASE":
        casing_str = "Normalize spelling and convert to UPPERCASE." + pincode_note
    else:
        casing_str = "Keep name/address casing exactly as it is written in the document." + pincode_note
        
    # 5. Name structure sequence rule
    seq_opt = config.get("name_sequence", "First Name Last Name")
    if seq_opt in ("Firstname Lastname", "First Name Last Name"):
        seq_str = "Format person names as 'First Name Last Name' (e.g. 'John Doe')."
    elif seq_opt == "Firstname Middlename Lastname":
        seq_str = "Format person names as 'Firstname Middlename Lastname' (e.g. 'John Albert Doe'). If no middle name exists, omit it."
    elif seq_opt == "Lastname Firstname":
        seq_str = "Format person names as 'Lastname Firstname' (e.g. 'Doe John')."
    elif seq_opt == "Lastname, Firstname Middlename":
        seq_str = "Format person names as 'Lastname, Firstname Middlename' (e.g. 'Doe, John Albert')."
    elif seq_opt == "Title Firstname Lastname":
        seq_str = "Format person names as 'Title Firstname Lastname' (e.g. 'Mr. John Doe'). If no title is in the document, omit it."
    elif seq_opt == "Title Firstname Middlename Lastname":
        seq_str = "Format person names as 'Title Firstname Middlename Lastname' (e.g. 'Mr. John Albert Doe'). If no title/middle name is in the document, omit them."
    else:
        seq_str = "Keep the original order of names exactly as written in the document."

    rules = [
        f"   - Dates: {date_str}",
        f"   - Amounts/Numbers: {num_str}",
        f"   - Rates & Percentages: {rate_str}",
        f"   - Names & Addresses: {casing_str}",
        f"   - Name Structure: {seq_str}"
    ]
    
    if custom_rules.strip():
        # Indent each line of custom rules to match layout
        formatted_custom = "\n".join(f"   {line}" for line in custom_rules.split("\n"))
        rules.append(formatted_custom)
        
    return "\n".join(rules)

