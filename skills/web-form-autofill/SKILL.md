---
name: web-form-autofill
description: Fill out web forms using a family member's profile and an autonomous browser agent. Triggers on "fill out this web form", "autofill this webpage".
---

# web-form-autofill

Fill web forms autonomously using `browser-use` and profile data.

## Usage

You must pass the target profile ID to the script:

```bash
python skills/web-form-autofill/web_autofill.py --profile tyler_combs
```

The script will launch a browser-use agent connected to the active Chrome tab and fill out the visible form fields using the provided profile data.

**Note:** The script will *not* click the final submit button. The user must manually review and submit the form.
