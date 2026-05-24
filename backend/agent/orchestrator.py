import os
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
import asyncio
from backend.mcp_config import MCP_FILESYSTEM_SERVER
from anthropic import Anthropic
from backend.config import settings
from backend.rag.pipeline import search_policies 
import json
import re
from backend.agent.system_prompts import AUDIT_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT, CRITIC_SYSTEM_PROMPT


anthropic = Anthropic(api_key=settings.anthropic_api_key)
params = StdioServerParameters(**MCP_FILESYSTEM_SERVER)


async def build_claude_tools(session) -> list[dict]:
    tools = await session.list_tools()
    claude_tools = []
    for t in tools.tools:
        tool = {
            "name": t.name,
            "description": t.description,
            "input_schema": t.inputSchema,
        }
        claude_tools.append(tool)

    search_tool = {
                "name":"search_policies",
                "description":"Search the company's indexed policy documents semantically. Returns the most relevant policy chunks with their source file. Use this when you need to find policy rules related to a topic, clause, or compliance question.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The query to search for."
                        }
                    },
                    "required": ["query"]
                }
            }
    claude_tools.append(search_tool)
    return claude_tools


async def run_tool(block, session) -> str:
    if block.name == "search_policies":
        result = search_policies(**block.input)
        result_json = json.dumps(result)
    else:
        result = await session.call_tool(block.name, block.input)
        result_json = result.content[0].text
    return result_json

def parse_final_report(message) -> dict:
    final_report = ""
    for block in message.content:
        if block.type == "text":
            final_report += block.text
    match = re.search(r'\{.*\}', final_report, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    else:
        return {"error": "no JSON found", "raw": final_report}


def list_policy_files() -> list[str]:
    pdfs = [f for f in os.listdir(settings.policies_dir) if f.endswith(".pdf")]
    return sorted(pdfs)


def parse_additional_findings(message) -> list[dict]:
    final_text = ""
    for block in message.content:
        if block.type == "text":
            final_text += block.text
    match = re.search(r'\{.*\}', final_text, re.DOTALL)
    if match:
        parsed = json.loads(match.group(0))
        return parsed.get("additional_findings", [])
    else:
        return []


async def critique_report(report: dict, contract_path: str, session, claude_tools) -> list[dict]:
    policy_files = list_policy_files()
    context = (
        f"CONTRACT FILE: {contract_path}\n\n"
        f"POLICY FILES ON DISK (sweep each one):\n  - "
        + "\n  - ".join(policy_files)
        + f"\n\nJUNIOR AUDITOR'S REPORT (do not duplicate these findings):\n"
        + json.dumps(report, indent=2)[:8000]
        + "\n\nReview the report. Find any violations the junior MISSED. "
          "Return only the JSON object with additional_findings."
    )

    messages = [{"role": "user", "content": context}]
    max_iterations = 10;

    for i in range(max_iterations):
        message = anthropic.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            temperature=0,
            system=CRITIC_SYSTEM_PROMPT,
            messages=messages,
            tools=claude_tools,
        )

        if message.stop_reason == "end_turn":
            break

        if message.stop_reason == "tool_use":
            tool_results = []
            for block in message.content:
                if block.type == "tool_use":
                    result_json = await run_tool(block, session)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_json,
                    })
            messages.append({"role" : "assistant", "content" : message.content})
            messages.append({"role" : "user", "content" : tool_results})

            continue
        break
    else:
        print("Critic: max iterations reached")

    return parse_additional_findings(message)


async def audit_contract(contract_name: str) -> dict:
    contract_path = os.path.join(settings.contracts_dir, contract_name)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            claude_tools = await build_claude_tools(session)

            messages = [
                {
                        "role": "user",
                        "content": f"Audit this contract for compliance with company policies: {contract_path}"
                    }
            ]
            max_iterations = 20;

            for i in range(max_iterations):
                message = anthropic.messages.create(
                    model="claude-opus-4-7",
                    max_tokens=8192,
                    temperature=0,
                    system=AUDIT_SYSTEM_PROMPT,
                    messages=messages,
                    tools=claude_tools,
                )

                if message.stop_reason == "end_turn":
                    break

                if message.stop_reason == "tool_use":
                    tool_results = []
                    for block in message.content:
                        if block.type == "tool_use":
                            result_json = await run_tool(block, session)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_json,
                            })
                    messages.append({"role" : "assistant", "content" : message.content})
                    messages.append({"role" : "user", "content" : tool_results})

                    continue
                break
            else:
                print("Max iterations reached")

            report = parse_final_report(message)

            extras = await critique_report(report, contract_path, session, claude_tools)
            if extras:
                report["findings"] = report.get("findings", []) + extras
                report["critic_added"] = len(extras)

    return report
           
            
          
    

async def chat_about_audit(contract_name: str, audit_report: dict, history: list, user_message: str) -> str:
    contract_path = os.path.join(settings.contracts_dir, contract_name)
    context_block = (
        f"Contract under discussion: {contract_path}\n\n"
        f"Audit report (JSON):\n{json.dumps(audit_report, indent=2)[:6000]}"
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            claude_tools = await build_claude_tools(session)

            messages = [{"role": "user", "content": context_block}]
            for turn in history:
                role = turn.get("role")
                if role in ("user", "assistant"):
                    messages.append({"role": role, "content": turn["content"]})
            messages.append({"role": "user", "content": user_message})

            max_iterations = 20
            for i in range(max_iterations):
                message = anthropic.messages.create(
                    model="claude-opus-4-7",
                    max_tokens=4096,
                    temperature=0,
                    system=CHAT_SYSTEM_PROMPT,
                    messages=messages,
                    tools=claude_tools,
                )

                if message.stop_reason == "end_turn":
                    break

                if message.stop_reason == "tool_use":
                    tool_results = []
                    for block in message.content:
                        if block.type == "tool_use":
                            result_json = await run_tool(block, session)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_json,
                            })
                    messages.append({"role": "assistant", "content": message.content})
                    messages.append({"role": "user", "content": tool_results})
                    continue
                break

    
    reply = ""
    for b in message.content:
        if b.type == "text":
            reply += b.text
    return reply


if __name__ == "__main__":
    result = asyncio.run(audit_contract("contract_01_software_development_agreement.txt"))
    print(json.dumps(result, indent=2))