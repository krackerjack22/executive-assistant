# Graphify Usage
Always use the graphify skill to query and navigate the workspace before exploring manually with bash commands. If graphify-out exists, treat all codebase questions as graphify queries.

# Temporary Files & Logs
NEVER use `/tmp` or `/private/tmp` for temporary files or logs. Always create a local `.tmp` folder inside the current workspace or use the conversation's scratch directory.

# Environment Variables & API Keys
Always read the `.env` file in the root of this workspace (`/Users/tylercombs/Dev/skills/executive-assistant/.env`) before running scripts or skills. Extract and export any required API keys (such as `GEMINI_API_KEY`) into your environment before executing commands that rely on them. Do not prompt the user for API keys if they already exist in the `.env` file.
