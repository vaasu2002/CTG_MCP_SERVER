#!/usr/bin/env python3

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from openai import OpenAI
import subprocess
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPOpenAIClient:
    """OpenAI client that can use MCP tools"""
    
    def __init__(self, model: str = "gpt-4"):
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = model
        self.mcp_process = None
        self.request_id = 1
    
    async def start_mcp_server(self, server_script: str = "working_server.py"):
        """Start the MCP server"""
        self.mcp_process = await asyncio.create_subprocess_exec(
            "python", server_script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Initialize the server
        await self._initialize_mcp()
        logger.info("✅ MCP server started and connected")
    
    async def stop_mcp_server(self):
        """Stop the MCP server"""
        if self.mcp_process:
            self.mcp_process.terminate()
            await self.mcp_process.wait()
            logger.info("🛑 MCP server stopped")
    
    async def _send_mcp_request(self, method: str, params: Dict[str, Any] = None):
        """Send a request to the MCP server"""
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method
        }
        
        if params is not None:
            request["params"] = params
        
        self.request_id += 1
        
        # Send request
        request_str = json.dumps(request) + "\n"
        self.mcp_process.stdin.write(request_str.encode())
        await self.mcp_process.stdin.drain()
        
        # Read response
        response_line = await self.mcp_process.stdout.readline()
        response_str = response_line.decode().strip()
        
        response = json.loads(response_str)
        
        if "error" in response:
            raise Exception(f"MCP Error: {response['error']}")
        
        return response.get("result", {})
    
    async def _initialize_mcp(self):
        """Initialize the MCP server"""
        # Send initialize
        await self._send_mcp_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "openai-mcp-client", "version": "1.0.0"}
        })
        
        # Send initialized notification
        notification = {"jsonrpc": "2.0", "method": "initialized"}
        notification_str = json.dumps(notification) + "\n"
        self.mcp_process.stdin.write(notification_str.encode())
        await self.mcp_process.stdin.drain()
    
    async def get_available_tools(self):
        """Get list of available MCP tools"""
        result = await self._send_mcp_request("tools/list")
        return result.get("tools", [])
    
    async def call_mcp_tool(self, name: str, arguments: Dict[str, Any]):
        """Call an MCP tool"""
        result = await self._send_mcp_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        
        # Extract text content from MCP response
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            return content[0]["text"]
        else:
            return str(result)
    
    async def chat_with_mcp(self, user_message: str, conversation_history: List[Dict] = None):
        """Have a conversation with OpenAI that can use MCP tools"""
        
        if conversation_history is None:
            conversation_history = []
        
        # Get available MCP tools
        mcp_tools = await self.get_available_tools()
        
        # Convert MCP tools to OpenAI function format
        openai_tools = []
        for tool in mcp_tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"]
                }
            })
        
        # System message
        system_message = {
            "role": "system",
            "content": """You are a clinical research assistant with access to the CIViC (Clinical Interpretation of Variants in Cancer) database. 

You can help users:
- Get statistics about the CIViC database
- Search for clinical evidence by disease name
- Understand cancer variants and their clinical significance
- Find information about specific cancers and treatments

Use the available tools to provide accurate, evidence-based information from the CIViC database. Always cite specific evidence when possible."""
        }
        
        # Build conversation
        messages = [system_message] + conversation_history + [{"role": "user", "content": user_message}]
        
        # Make OpenAI API call
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        
        # Handle tool calls
        if message.tool_calls:
            # Add assistant message to conversation
            conversation_history.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]
            })
            
            # Process each tool call
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"🔧 Calling MCP tool: {function_name} with {function_args}")
                
                # Call the MCP tool
                try:
                    tool_result = await self.call_mcp_tool(function_name, function_args)
                    
                    # Add tool result to conversation
                    conversation_history.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_result
                    })
                    
                except Exception as e:
                    logger.error(f"Error calling MCP tool {function_name}: {e}")
                    conversation_history.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": f"Error: {str(e)}"
                    })
            
            # Get final response from OpenAI
            final_response = self.client.chat.completions.create(
                model=self.model,
                messages=[system_message] + conversation_history,
                tools=openai_tools,
                tool_choice="auto"
            )
            
            final_message = final_response.choices[0].message
            conversation_history.append({
                "role": "assistant",
                "content": final_message.content
            })
            
            return final_message.content, conversation_history
        else:
            # No tool calls needed
            conversation_history.append({
                "role": "assistant",
                "content": message.content
            })
            return message.content, conversation_history

async def main():
    """Main chat interface"""
    print("🧬 CIViC Clinical Evidence Chat Assistant")
    print("=" * 60)
    print("Connecting to CIViC database via MCP server...")
    
    client = MCPOpenAIClient()
    
    try:
        # Start MCP server
        await client.start_mcp_server()
        
        # Show available tools
        tools = await client.get_available_tools()
        print(f"\n✅ Connected! Available tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
        
        print(f"\n💬 Chat started! Ask me about cancer clinical evidence.")
        print("Examples:")
        print("- 'What statistics are available in the CIViC database?'")
        print("- 'Find evidence for lung cancer treatments'")
        print("- 'What do we know about breast cancer variants?'")
        print("\nType 'quit' to exit.\n")
        
        conversation_history = []
        
        while True:
            try:
                # Get user input
                user_input = input("🔬 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                if not user_input:
                    continue
                
                print("\n🤖 Assistant: ", end="", flush=True)
                
                # Get response from OpenAI with MCP tools
                response, conversation_history = await client.chat_with_mcp(
                    user_input, 
                    conversation_history
                )
                
                print(response)
                print("\n" + "-" * 60)
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                logger.error(f"Chat error: {e}")
    
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        logger.error(f"Startup error: {e}")
    
    finally:
        await client.stop_mcp_server()

if __name__ == "__main__":
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        print("Please add it to your .env file or set it as an environment variable")
        sys.exit(1)
    
    asyncio.run(main())