"""
One-time script to register the Claim Processing agents on the Mistral account
according to agents_config.py and automatically update the .env file.

Usage:
    python create_claim_agents.py
"""

import os
import sys
from dotenv import load_dotenv
from mistralai.client import Mistral

# Locate directories relative to this file
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, ".env")

# Load environment variables
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

api_key = os.getenv("MISTRAL_API_KEY")
if not api_key:
    print("ERROR: MISTRAL_API_KEY not found in environment or .env file.")
    sys.exit(1)

# Import the claim agents configuration
sys.path.append(base_dir)
from agents_config import CLAIM_AGENTS

client = Mistral(api_key=api_key)

def update_env_file(env_file_path, updates):
    """
    Safely updates or appends key-value pairs in the .env file.
    """
    if not os.path.exists(env_file_path):
        print(f"Creating new .env file at {env_file_path}")
        with open(env_file_path, "w", encoding="utf-8") as f:
            for k, v in updates.items():
                f.write(f"{k}={v}\n")
        return

    with open(env_file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Map key to its index in the lines list
    key_to_line_idx = {}
    for idx, line in enumerate(lines):
        line_stripped = line.strip()
        # Find active (non-commented) settings
        if line_stripped and not line_stripped.startswith("#") and "=" in line_stripped:
            k = line_stripped.split("=", 1)[0].strip()
            key_to_line_idx[k] = idx

    for k, v in updates.items():
        if k in key_to_line_idx:
            idx = key_to_line_idx[k]
            # Replace the existing line
            lines[idx] = f"{k}={v}\n"
            print(f"Updated existing env var in .env: {k}")
        else:
            # Ensure there is a newline at the end of the file before appending
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(f"{k}={v}\n")
            print(f"Added new env var to .env: {k}")

    with open(env_file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    print("Creating Claim Processing agents...\n")
    new_ids = {}

    for agent_cfg in CLAIM_AGENTS:
        name = agent_cfg["name"]
        env_var = agent_cfg["env_var"]
        description = agent_cfg["description"]
        instructions = agent_cfg["instructions"]

        print(f"Creating agent: {name} ({env_var})...")
        try:
            agent = client.beta.agents.create(
                model="mistral-small-latest",
                name=name,
                description=description,
                instructions=instructions,
            )
            print(f"  -> Created successfully! ID: {agent.id}")
            new_ids[env_var] = agent.id
        except Exception as e:
            print(f"  -> ERROR creating agent {name}: {e}")
            sys.exit(1)

    print("\nUpdating .env file with new Agent IDs...")
    update_env_file(env_path, new_ids)
    print("\n[SUCCESS] All claim processing agents registered and saved to .env successfully!")

if __name__ == "__main__":
    main()
