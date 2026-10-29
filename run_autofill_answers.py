import subprocess
import os
import sys

answers = {
    "Medication Name:": "Epinephrine Auto-Injector",
    "Skin": "X",
}

class InterviewRunner:
    def __init__(self, cmd):
        self.cmd = cmd
        
    def run(self):
        import pty
        import os
        
        master, slave = pty.openpty()
        p = subprocess.Popen(self.cmd, stdin=slave, stdout=slave, stderr=subprocess.STDOUT, env=os.environ, text=True, shell=True)
        os.close(slave)
        
        buffer = ""
        while True:
            try:
                data = os.read(master, 1024).decode()
                buffer += data
                sys.stdout.write(data)
                sys.stdout.flush()
                
                if "Enter value" in buffer:
                    # Find which field we are answering
                    if "Medication Name:" in buffer:
                        os.write(master, b"Epinephrine Auto-Injector\n")
                    elif "Skin" in buffer and "Skin" not in answers:
                        # Wait, answers dict has "Skin"
                        os.write(master, b"X\n")
                        answers["Skin"] = "done" # prevent matching again
                    else:
                        os.write(master, b"\n")
                    buffer = "" # clear buffer
                    
            except OSError:
                break
        p.wait()

runner = InterviewRunner(".venv/bin/python skills/pdf-form-autofill/autofill.py --template /Users/tylercombs/.gemini/antigravity-ide/brain/dd61b84f-040e-41f5-8429-7e67d92c9d5e/media__1787259841091.pdf --profile charlotte_combs --commit-unsafe --missing-mode interview --output /Users/tylercombs/.gemini/antigravity-ide/brain/dd61b84f-040e-41f5-8429-7e67d92c9d5e/charlotte_medication.pdf")
runner.run()
