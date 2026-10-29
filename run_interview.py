import pexpect
import sys

child = pexpect.spawn('.venv/bin/python skills/pdf-form-autofill/autofill.py --template /Users/tylercombs/.gemini/antigravity-ide/brain/dd61b84f-040e-41f5-8429-7e67d92c9d5e/media__1787259841091.pdf --profile charlotte_combs --missing-mode interview --output /Users/tylercombs/.gemini/antigravity-ide/brain/dd61b84f-040e-41f5-8429-7e67d92c9d5e/charlotte_medication.pdf')
child.logfile = sys.stdout.buffer

answers = {
    "Medication Name:": "Epinephrine Auto-Injector",
    "Skin": "X",
    "Teacher:": "Ellen Harris",
    "Dose": "0.3 mg, intramuscular auto-injector",
    "Prescription": "X",
    "Reason": "Allergic reaction (anaphylaxis)",
    "Special Instructions:": "Only use for anaphylactic reaction to peanuts. Administer 50mg Benadryl before use.",
    "Duration: start date": "09/01/2026",
    "end date": "06/15/2027",
    "prescriber": "Kaliq Williams",
    "Time/frequency of administration": "As needed"
}

while True:
    try:
        index = child.expect([
            r"Enter value.*?:",
            r"Approve saving these changes to your profile\? \[Y\]es / \[N\]o \(abort\):",
            pexpect.EOF
        ], timeout=120)
        
        if index == 0:
            output = child.before.decode()
            field_name = None
            for line in reversed(output.splitlines()):
                if "— no match" in line or "— LOW" in line:
                    parts = line.split('"')
                    if len(parts) >= 3:
                        field_name = parts[1]
                        break
            
            # Find matching answer
            matched = False
            if field_name:
                for k, v in answers.items():
                    if k in field_name:
                        child.sendline(v)
                        matched = True
                        break
            if not matched:
                child.sendline("") # Skip by default
        elif index == 1:
            child.sendline("Y")
        elif index == 2:
            break
            
    except pexpect.TIMEOUT:
        print("Timeout waiting for prompt.")
        break
