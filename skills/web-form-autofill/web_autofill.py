import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib import profile_loader
from lib import role_resolver
from lib import vault
from browser_use import Agent
from langchain_google_genai import ChatGoogleGenerativeAI


def load_and_prepare_profile(profile_id: str) -> str:
    """Loads the profile, resolves vault fields, and returns a flattened JSON string."""
    all_profiles = profile_loader._load_all_profiles()
    
    if profile_id not in all_profiles:
        print(f"Error: Profile '{profile_id}' not found.")
        sys.exit(1)
        
    profile = all_profiles[profile_id]

    try:
        profile_json_str = json.dumps(profile)
        vault_items = vault.load_vault()
        
        import re
        def replace_vault(match):
            key = match.group(1)
            if key in vault_items:
                return vault_items[key]
            return match.group(0)
            
        unlocked_json = re.sub(r'\[\[vault:([^\]]+)\]\]', replace_vault, profile_json_str)
        return unlocked_json
    except Exception as e:
        print(f"Warning: Failed to fully resolve vault fields: {e}")
        return json.dumps(profile)


async def main():
    parser = argparse.ArgumentParser(description="Web Form Autofill via browser-use")
    parser.add_argument("--profile", required=True, help="Profile ID to use for autofill (e.g. tyler_combs)")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY is not set. Please add it to your .env file or environment variables.")
        sys.exit(1)

    print(f"Loading profile: {args.profile}...")
    profile_data_str = load_and_prepare_profile(args.profile)
    
    # Initialize the LLM
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0)

    # Define the task for the Agent
    task_description = (
        "You are an executive assistant helping fill out a web form for a user. "
        "Read the active web page and map the available form inputs to the user's profile data provided below. "
        "Fill out all the fields you confidently can. "
        "DO NOT click any 'Submit' or 'Continue' buttons that would finalize the form submission. Stop after filling."
        f"\n\nPROFILE DATA (JSON):\n{profile_data_str}"
    )

    print("Initializing Browser-Use Agent. The agent will connect to your browser and begin filling the form...")
    print("Please ensure your target web form is open in Chrome.")
    
    agent = Agent(
        task=task_description,
        llm=llm,
    )
    
    result = await agent.run()
    
    print("\nTask complete! Please review the form in your browser and submit it manually.")
    
    
if __name__ == "__main__":
    asyncio.run(main())
