import os
import sys
import json
import urllib.request
import subprocess

class LLMClient:
    def __init__(self, endpoint="http://localhost:20128/v1", api_key="9r-98fa4daf16ff4b9680a1aad8e8676c08"):
        self.endpoint = endpoint
        self.api_key = api_key
        # Models alias config
        self.model = "kr/deepseek-3.2"

    def is_9router_available(self):
        """Check if local 9Router is listening on its port."""
        try:
            # Short timeout check
            req = urllib.request.Request(self.endpoint + "/models", method="GET")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    def query(self, system_prompt, user_prompt):
        """Send completion request to 9Router, falling back to gemini CLI if offline."""
        if self.is_9router_available():
            print("[+] Using local 9Router API...")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            body = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1,
                "stream": False
            }
            req = urllib.request.Request(
                self.endpoint + "/chat/completions",
                data=json.dumps(body).encode('utf-8'),
                headers=headers,
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    res = json.loads(response.read().decode('utf-8'))
                    return res['choices'][0]['message']['content']
            except Exception as e:
                print(f"[-] 9Router request failed: {e}")
        
        # Fallback: Pipe prompts to local gemini CLI via stdin to bypass CLI argument limits
        print("[+] Querying global gemini CLI via stdin...")
        import time
        start_time = time.time()
        combined_input = f"System Instruction:\n{system_prompt}\n\nUser Message:\n{user_prompt}"
        try:
            # We use --prompt to command the model to output raw completion based on the stdin context
            cmd = ["gemini", "--prompt", "Extract the instruction from the system/user input on stdin, complete the task, and return the response text in raw format without any markdown or code blocks."]
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True
            )
            stdout, stderr = process.communicate(input=combined_input)
            print(f"[+] Gemini CLI query completed in {time.time() - start_time:.2f} seconds.")
            if process.returncode == 0:
                # Clean up the output to extract the model's text response
                cleaned = stdout.strip()
                return cleaned
            else:
                print(f"[-] Gemini CLI error: {stderr}")
                return None
        except Exception as e:
            print(f"[-] Failed to invoke gemini CLI: {e}")
            return None
