import re

with open("skills/pdf-form-autofill/schema_extractor.py", "r") as f:
    content = f.read()

content = content.replace("import anthropic\nfrom dotenv import load_dotenv\nload_dotenv('/Users/tylercombs/Dev/executive-assistant/.env')", "import anthropic")

with open("skills/pdf-form-autofill/schema_extractor.py", "w") as f:
    f.write(content)

