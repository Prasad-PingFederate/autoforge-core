import os
import sys
import json
import subprocess
from playwright.sync_api import sync_playwright

class AutoForgeAgent:
    def __init__(self, use_browserbase=False, browserbase_key=None, browserbase_project=None):
        self.use_browserbase = use_browserbase
        self.browserbase_key = browserbase_key
        self.browserbase_project = browserbase_project

    def call_local_cli(self, system_prompt, user_prompt):
        """Call the local gemini CLI command to generate code."""
        combined_prompt = f"{system_prompt}\n\nTask: {user_prompt}"
        try:
            # Run the local gemini command
            # gemini-cli -m 9r-super "Your prompt here"
            cmd = ["gemini", "run", combined_prompt]
            # If that fails/doesn't exist, we will try running with python wrapper
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                return result.stdout
            else:
                print(f"[-] CLI returned error code {result.returncode}: {result.stderr}")
                return None
        except Exception as e:
            print(f"[-] Failed to execute local CLI: {e}")
            return None

    def execute_code(self, code_str):
        """Execute the generated python playwright script dynamically."""
        print("[+] Executing generated code...")
        
        # Define local context for exec()
        local_context = {
            "sync_playwright": sync_playwright,
            "browserbase_key": self.browserbase_key,
            "browserbase_project": self.browserbase_project,
            "use_browserbase": self.use_browserbase
        }
        
        # Wrap generated code to capture status/exceptions
        wrapped_code = f"""
def run_test():
    import traceback
    try:
{code_str}
        return True, "Success"
    except Exception as e:
        return False, str(e) + "\\n" + traceback.format_exc()

success, msg = run_test()
"""
        try:
            exec(wrapped_code, globals(), local_context)
            success = local_context.get("success", False)
            msg = local_context.get("msg", "")
            return success, msg
        except Exception as e:
            return False, str(e)

    def run(self, task_description):
        print(f"[+] Task received: {task_description}")
        
        system_prompt = """You are the AutoForge GeneratorAgent. You write clean, robust Python code using Playwright sync_api.
Your code must handle browser launch/connection, page creation, actions, and assertions.
If use_browserbase is True, connect over CDP:
    browser = p.chromium.connect_over_cdp(f"wss://connect.browserbase.com?apiKey={browserbase_key}&projectId={browserbase_project}")
Else:
    browser = p.chromium.launch(headless=False)

Ensure you import: from playwright.sync_api import sync_playwright
Return ONLY the raw python code inside a python markdown block (```python ... ```) and nothing else.
Do not include explanations outside the code block."""

        print("[+] Generating Playwright script via local gemini CLI...")
        llm_response = self.call_local_cli(system_prompt, task_description)
        
        if not llm_response:
            print("[!] CLI offline or errored. Using local template for demo...")
            code_str = """        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto("https://www.google.com")
            print("Page title:", page.title())
            browser.close()"""
        else:
            # Extract code from markdown block
            if "```python" in llm_response:
                code_str = llm_response.split("```python")[1].split("```")[0]
            elif "```" in llm_response:
                code_str = llm_response.split("```")[1].split("```")[0]
            else:
                code_str = llm_response
        
        # Format indentation for python exec() function body
        indented_code = ""
        for line in code_str.strip().split("\n"):
            indented_code += "        " + line + "\n"
            
        print(f"--- GENERATED CODE ---\n{code_str}\n----------------------")
        
        success, msg = self.execute_code(indented_code)
        if success:
            print(f"[+] Task succeeded!")
        else:
            print(f"[-] Task failed:\n{msg}")

if __name__ == "__main__":
    agent = AutoForgeAgent(use_browserbase=False)
    agent.run("Go to https://www.wikipedia.org, search for 'Artificial Intelligence', and verify the page header is visible.")
