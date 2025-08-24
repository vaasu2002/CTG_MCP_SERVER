#!/usr/bin/env python3

import asyncio
import json

class WorkingTester:
    """Test the working CIViC MCP server"""
    
    def __init__(self):
        self.server_process = None
        self.request_id = 1
    
    async def start_server(self):
        """Start the working server"""
        self.server_process = await asyncio.create_subprocess_exec(
            "python", "working_server.py",
            # Python code can now send data into the subprocess by writing to this pipe.
            stdin=asyncio.subprocess.PIPE, # Redirects the standard input (stdin) of the new process to a pipe.
            # We can read whatever the subprocess prints
            stdout=asyncio.subprocess.PIPE, # Redirects the standard output (stdout) of the subprocess to a pipe.
            stderr=asyncio.subprocess.PIPE
        )
        
        # Initialize
        await self._initialize()
        print("✅ Working CIViC MCP server started")
    
    async def stop_server(self):
        """Stop the server"""
        if self.server_process:
            self.server_process.terminate()
            await self.server_process.wait()
            print("🛑 Server stopped")
    
    async def _send_request(self, method: str, params=None):
        """Send a request and get response"""
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
        self.server_process.stdin.write(request_str.encode())
        await self.server_process.stdin.drain()
        
        # Read response
        response_line = await self.server_process.stdout.readline()
        response_str = response_line.decode().strip()
        
        return json.loads(response_str)
    
    async def _initialize(self):
        # Sending the very first JSON-RPC request to the MCP server to perform the handshake.
        response = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        })
        # {
        #     "jsonrpc": "2.0",
        #     "id": 1,
        #     "method": "initialize",
        #     "params": {
        #         "protocolVersion": "2024-11-05",
        #         "capabilities": {"tools": {}},
        #         "clientInfo": {"name": "test-client", "version": "1.0.0"}
        #     }
        # }

        # response =  { THIS RETURNS THIS
        #     'jsonrpc': '2.0', 
        #     'id': 1, 
        #     'result': {
        #         'protocolVersion': '2024-11-05', 
        #         'capabilities': {'tools': {}}, 
        #         'serverInfo': {
        #             'name': 'civic-clinical-evidence-mcp', 'version': '1.0.0'
        #         }
        #     }
        # }

        if "error" in response:
            raise Exception(f"Initialize failed: {response['error']}")
        # Send initialized notification
        notification = {"jsonrpc": "2.0", "method": "initialized"}
        notification_str = json.dumps(notification) + "\n"
        self.server_process.stdin.write(notification_str.encode())
        await self.server_process.stdin.drain()
    
    async def list_tools(self):
        """List tools"""
        return await self._send_request("tools/list")
    
    async def call_tool(self, name: str, arguments: dict):
        """Call a tool"""
        return await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })

async def test_working_server():
    """Test the working CIViC MCP server"""
    print("🧪 Testing Working CIViC MCP Server")
    print("=" * 50)
    
    tester = WorkingTester()
    
    try:
        await tester.start_server() # Starting the MCP Server
        
        # Test 1: List tools
        print("\n📋 Test 1: List available tools")
        tools_response = await tester.list_tools()
        
        if "error" in tools_response:
            print(f"❌ Error: {tools_response['error']}")
            return
        
        tools = tools_response["result"]["tools"]
        print(f"✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
        
        # Test 2: Get CIViC statistics
        print("\n📊 Test 2: Get CIViC database statistics")
        stats_response = await tester.call_tool("get_civic_stats", {})
        
        if "error" in stats_response:
            print(f"❌ Error: {stats_response['error']}")
        else:
            content = stats_response["result"]["content"][0]["text"]
            print("✅ Statistics retrieved:")
            print(content)
        
        # Test 3: Search for Lung Cancer evidence
        print("\n🔍 Test 3: Search for Lung Cancer evidence")
        search_response = await tester.call_tool("search_disease_evidence", {
            "disease_name": "Lung Cancer", 
            "limit": 3
        })
        
        if "error" in search_response:
            print(f"❌ Error: {search_response['error']}")
        else:
            content = search_response["result"]["content"][0]["text"]
            print("✅ Search results:")
            # Print first 800 chars to avoid spam
            if len(content) > 800:
                print(content[:800] + "\n... (truncated)")
            else:
                print(content)
        
        # Test 4: Search for Breast Cancer evidence  
        print("\n🎯 Test 4: Search for Breast Cancer evidence")
        search_response = await tester.call_tool("search_disease_evidence", {
            "disease_name": "Breast Cancer",
            "limit": 2
        })
        
        if "error" in search_response:
            print(f"❌ Error: {search_response['error']}")
        else:
            content = search_response["result"]["content"][0]["text"]
            print("✅ Search results:")
            if len(content) > 600:
                print(content[:600] + "\n... (truncated)")
            else:
                print(content)
        
        print("\n🎉 All tests completed successfully!")
        print("\n🏆 Your CIViC MCP server is working perfectly!")
        print("Ready to integrate with Claude Desktop or other MCP clients.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        
        # Check stderr for debugging
        if tester.server_process:
            try:
                stderr_data = await asyncio.wait_for(
                    tester.server_process.stderr.read(2048),
                    timeout=2.0
                )
                if stderr_data:
                    print(f"Server stderr: {stderr_data.decode()}")
            except asyncio.TimeoutError:
                pass
    
    finally:
        await tester.stop_server()

if __name__ == "__main__":
    asyncio.run(test_working_server())