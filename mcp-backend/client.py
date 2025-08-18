import asyncio
import os
from typing import Optional, Dict, Any, List
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google.generativeai import GenerativeModel, configure
from google.generativeai.types import Tool, FunctionDeclaration
from dotenv import load_dotenv
import json
import logging
logging.basicConfig(level=logging.DEBUG)

load_dotenv()

class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={"max_output_tokens": 2000}
        )

    async def connect_to_server(self, server_script_path: str):
        command = "../mcp-server/.venv/Scripts/python.exe"
        server_params = StdioServerParameters(command=command, args=[server_script_path])
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.stdin = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.stdin))
        await self.session.initialize()
        response = await self.session.list_tools()
        logging.debug("Connected to server with tools: %s", [tool.name for tool in response.tools])

    def sanitize_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Clean schema for Gemini FunctionDeclaration compatibility."""
        if not isinstance(schema, dict):
            return schema

        allowed_keys = {"type", "properties", "required", "description"}
        cleaned = {}

        for k, v in schema.items():
            if k in allowed_keys:
                if isinstance(v, dict):
                    cleaned[k] = self.sanitize_schema(v)
                else:
                    cleaned[k] = v

        # ✅ Fix required: keep only valid property names
        if "required" in cleaned and "properties" in cleaned:
            props = cleaned["properties"].keys()
            cleaned["required"] = [r for r in cleaned["required"] if r in props]

        return cleaned


    """ async def process_query(self, query: str) -> str:
        if not self.session:
            raise ValueError("Not connected to server")

        response = await self.session.list_tools()
        gemini_tools = [
            Tool(function_declarations=[
                FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                     parameters=self.sanitize_schema(tool.inputSchema) if tool.inputSchema else {}
                )
            ]) for tool in response.tools
        ]

        messages = [{"role": "user", "parts": [{"text": query}]}]
        final_text = ""
        iteration = 0
        max_iterations = 5

        while iteration < max_iterations:
            try:
                response = self.model.generate_content(
                    contents=messages,
                    tools=gemini_tools if gemini_tools else None
                )
            except Exception as e:
                return f"Error from Gemini: {str(e)}"

            candidate = response.candidates[0]
            if not candidate.content.parts:
                final_text += "No response from Gemini.\n"
                break

            has_tool_call = False
            for part in candidate.content.parts:
                if part.text:
                    final_text += part.text + "\n"
                    messages.append({"role": "model", "parts": [{"text": part.text}]})
                elif hasattr(part, 'function_call') and part.function_call:
                    has_tool_call = True
                    tool_name = part.function_call.name
                    tool_args = dict(part.function_call.args)
                    result = await self.session.call_tool(tool_name, tool_args)
                    tool_output = None
                    if result.content and hasattr(result.content[0], "text"):
                        import json
                        try:
                            tool_output = json.loads(result.content[0].text)
                        except Exception:
                            tool_output = {"raw": result.content[0].text}
                    else:
                        tool_output = {"raw": str(result.content)}
                    final_text += f"[Tool result from {tool_name}: {tool_output}]\n"
                    logging.debug(f"Tool {tool_name} called with args: {tool_args}, output: {tool_output}")
                    # Append tool response to messages
                    messages.append({
                        "role": "user",
                        "parts": [{
                            "function_response": {
                                "name": tool_name,
                                "response": tool_output
                            }
                        }]
                    })

            if not has_tool_call:
                break
            iteration += 1

        return final_text.strip() """
    
    async def process_query(self, query: str) -> str:
        if not self.session:
            raise ValueError("Not connected to server")

        response = await self.session.list_tools()
        gemini_tools = [
            Tool(function_declarations=[
                FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=self.sanitize_schema(tool.inputSchema) if tool.inputSchema else {}
                )
            ]) for tool in response.tools
        ]

        messages = [{"role": "user", "parts": [{"text": query}]}]
        final_text = ""
        iteration = 0
        max_iterations = 5

        while iteration < max_iterations:
            try:
                response = self.model.generate_content(
                    contents=messages,
                    tools=gemini_tools if gemini_tools else None
                )
            except Exception as e:
                return f"Error from Gemini: {str(e)}"

            candidate = response.candidates[0]
            if not candidate.content.parts:
                final_text += "No response from Gemini.\n"
                break

            # Collect all parts from the model's response
            model_parts = []
            function_calls = []
            
            for part in candidate.content.parts:
                if part.text:
                    final_text += part.text + "\n"
                    model_parts.append({"text": part.text})
                elif hasattr(part, 'function_call') and part.function_call:
                    # Store the function call part as-is for the model message
                    model_parts.append(part)
                    function_calls.append(part.function_call)

            # Add the complete model response (including function calls)
            if model_parts:
                messages.append({
                    "role": "model", 
                    "parts": model_parts
                })

            # If there are function calls, execute them and add responses
            if function_calls:
                function_responses = []
                
                for func_call in function_calls:
                    tool_name = func_call.name
                    tool_args = dict(func_call.args)

                    try:
                        result = await self.session.call_tool(tool_name, tool_args)

                        # Process the tool result
                        tool_output = None
                        if result.content and hasattr(result.content[0], "text"):
                            import json
                            try:
                                tool_output = json.loads(result.content[0].text)
                            except Exception:
                                tool_output = {"raw": result.content[0].text}
                        else:
                            tool_output = {"raw": str(result.content)}

                        final_text += f"[Tool result from {tool_name}: {tool_output}]\n"
                        logging.debug(f"Tool {tool_name} called with args: {tool_args}, output: {tool_output}")

                        # Create function response part
                        function_responses.append({
                            "function_response": {
                                "name": tool_name,
                                "response": tool_output
                            }
                        })
                        
                    except Exception as e:
                        logging.error(f"Error calling tool {tool_name}: {e}")
                        function_responses.append({
                            "function_response": {
                                "name": tool_name,
                                "response": {"error": str(e)}
                            }
                        })

                # Add all function responses in a single user message
                if function_responses:
                    messages.append({
                        "role": "user",
                        "parts": function_responses
                    })
            else:
                # No function calls, we're done
                break
                
            iteration += 1

        return final_text.strip()



    async def close(self):
        await self.exit_stack.aclose()