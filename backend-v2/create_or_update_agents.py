"""
Utility script to create or update all configured Mistral agents in Mistral AI Studio
and automatically update the .env file with the corresponding Agent IDs.

Usage:
    python create_or_update_agents.py
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

# Import configurations
sys.path.append(base_dir)
from agents_config import AGENT_CONFIGS

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
    print("=== Mistral AI Studio Agent Creator & Updater ===\n")
    print(f"Loaded {len(AGENT_CONFIGS)} agent configurations.")

    new_ids = {}

    for agent_cfg in AGENT_CONFIGS:
        name = agent_cfg["name"]
        env_var = agent_cfg["env_var"]
        description = agent_cfg["description"]
        instructions = agent_cfg["instructions"]
        model = agent_cfg.get("model", "mistral-small-latest")
        completion_args = agent_cfg.get("completion_args", {})

        existing_id = os.getenv(env_var)

        # Prepare arguments for creation/update
        kwargs = {
            "name": name,
            "description": description,
            "instructions": instructions,
            "model": model,
        }
        if completion_args:
            kwargs["completion_args"] = completion_args

        if existing_id:
            print(f"\nChecking/Updating existing agent: {name} ({env_var}: {existing_id})...")
            try:
                # Try updating the agent in Mistral Studio
                updated_agent = client.beta.agents.update(
                    agent_id=existing_id,
                    **kwargs
                )
                print(f"  -> Successfully updated! ID: {updated_agent.id}")
                new_ids[env_var] = updated_agent.id
                continue
            except Exception as e:
                print(f"  -> Update failed ({e}). Recreating agent...")

        # Create new agent
        print(f"\nCreating new agent: {name} ({env_var})...")
        try:
            new_agent = client.beta.agents.create(**kwargs)
            print(f"  -> Successfully created! ID: {new_agent.id}")
            new_ids[env_var] = new_agent.id
            # Update local env so subsequent steps in the same execution see the new ID if needed
            os.environ[env_var] = new_agent.id
        except Exception as e:
            print(f"  -> ERROR creating agent {name}: {e}")
            sys.exit(1)

    if new_ids:
        print("\nUpdating .env file with Agent IDs...")
        update_env_file(env_path, new_ids)
        print("\n[SUCCESS] Agent registrations/updates completed and saved to .env!")
    else:
        print("\n[SUCCESS] All agents are already up to date!")


if __name__ == "__main__":
    main()
