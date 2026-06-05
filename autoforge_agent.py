import os
import sys
import asyncio
import json
from typing import Any, List, Optional, TypeVar, Union, overload
from pydantic import BaseModel

from llm_client import LLMClient
from browser_use import Agent, Browser
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion

T = TypeVar('T', bound=Union[BaseModel, str])

# ── Custom LLM Adapter implementing browser-use BaseChatModel ───────────────
class AutoForgeLLM(BaseChatModel):
    model: str = "autoforge-local"

    @property
    def provider(self) -> str:
        return "custom"

    @property
    def name(self) -> str:
        return "autoforge-local-llm"

    @overload
    async def ainvoke(
        self, messages: List[BaseMessage], output_format: None = None, **kwargs: Any
    ) -> ChatInvokeCompletion[str]: ...

    @overload
    async def ainvoke(
        self, messages: List[BaseMessage], output_format: type[T], **kwargs: Any
    ) -> ChatInvokeCompletion[T]: ...

    async def ainvoke(
        self, messages: List[BaseMessage], output_format: type[T] | None = None, **kwargs: Any
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        client = LLMClient()
        system_prompt = ""
        user_prompt = ""
        
        # Compile system and user prompts
        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.text
            else:
                user_prompt += f"\n[{msg.role}]: {msg.text}"
                
        # If output_format is requested, append the json schema rules
        if output_format is not None:
            schema = output_format.model_json_schema()
            system_prompt += f"\n\nYou MUST return a JSON object that strictly complies with this JSON Schema:\n{json.dumps(schema)}\nDo not include any thinking or markdown code blocks (like ```json) in your final response - return ONLY raw JSON."

        # Query local LLM / CLI fallback
        response_text = client.query(system_prompt, user_prompt)
        
        if not response_text:
            response_text = "{}"
            
        # Strip any code block wrappers
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif response_text.startswith("```"):
            response_text = response_text.split("```")[1].split("```")[0].strip()

        if output_format is not None:
            try:
                parsed = output_format.model_validate_json(response_text)
                return ChatInvokeCompletion(
                    completion=parsed,
                    usage=None,
                    stop_reason="end_turn"
                )
            except Exception as e:
                print(f"[-] JSON validation failed: {e}\nResponse was:\n{response_text}")
                # Construct a minimal valid fallback object to keep the loop alive
                try:
                    # Try validating with a dummy dict
                    parsed = output_format.model_validate({})
                    return ChatInvokeCompletion(
                        completion=parsed,
                        usage=None,
                        stop_reason="end_turn"
                    )
                except Exception:
                    raise e
        else:
            return ChatInvokeCompletion(
                completion=response_text,
                usage=None,
                stop_reason="end_turn"
            )

# ── Unified E2E Automation Runner ───────────────────────────────────────────
async def run_autoforge_agent(task_prompt: str, headless: bool = False):
    print(f"\n[+] Starting AutoForge Agent...")
    print(f"[+] Task: {task_prompt}")
    
    # 1. Initialize our resilient LLM client
    llm = AutoForgeLLM()
    
    # 2. Configure browser-use to launch Chrome directly
    browser = Browser(
        headless=headless,
        disable_security=True,  # Bypasses security blocks during local automation
        args=["--start-maximized"]
    )
    
    # 3. Create the agent instance
    agent = Agent(
        task=task_prompt,
        llm=llm,
        browser=browser
    )
    
    # 4. Run the browser-use loop
    try:
        history = await agent.run()
        print("[+] Agent run completed successfully!")
        
        # Analyze history results
        print("\n--- Execution History Summary ---")
        for i, step in enumerate(history.history):
            thinking = step.model_output.thinking if (step.model_output and hasattr(step.model_output, 'thinking')) else None
            print(f"Step {i+1}: {thinking or 'Action executed'}")
        
    except Exception as e:
        print(f"[-] Agent run failed with exception: {e}")
    finally:
        await browser.close()

if __name__ == "__main__":
    prompt = "Go to https://www.wikipedia.org, type 'Software engineering' into the search input, submit the form, and verify the title."
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
        
    asyncio.run(run_autoforge_agent(prompt, headless=False))
