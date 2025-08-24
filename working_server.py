#!/usr/bin/env python3

import asyncio
import json
import sys
import logging
from typing import Any, Dict
import aiohttp

# Configure logging to stderr so it doesn't interfere with JSON-RPC
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

class CivicAPI:
    """CIViC API client - simplified and working"""
    
    def __init__(self):
        self.base_url = "https://civicdb.org/api/graphql"
        self.session = None
    
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "CIViC-MCP-Server/1.0"
                }
            )
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_stats(self):
        """Get database statistics"""
        query = """
        query GetStats {
            evidenceItems {
                totalCount
            }
            genes {
                totalCount
            }
        }
        """
        
        session = await self._get_session()
        
        async with session.post(self.base_url, json={"query": query}) as response:
            if response.status == 200:
                result = await response.json()
                if "errors" in result:
                    raise Exception(f"GraphQL errors: {result['errors']}")
                return result["data"]
            else:
                error_text = await response.text()
                raise Exception(f"API request failed: {response.status} - {error_text}")
    
    async def search_evidence(self, disease_name: str, limit: int = 5):
        """Search for evidence by disease"""
        query = f"""
        query SearchEvidence {{
            evidenceItems(diseaseName: "{disease_name}", first: {limit}) {{
                totalCount
                edges {{
                    node {{
                        id
                        name
                        evidenceLevel
                        evidenceType
                        status
                        disease {{
                            name
                        }}
                        molecularProfile {{
                            name
                        }}
                        source {{
                            citation
                            publicationYear
                        }}
                    }}
                }}
            }}
        }}
        """
        
        session = await self._get_session()
        
        async with session.post(self.base_url, json={"query": query}) as response:
            if response.status == 200:
                result = await response.json()
                if "errors" in result:
                    raise Exception(f"GraphQL errors: {result['errors']}")
                return result["data"]
            else:
                error_text = await response.text()
                raise Exception(f"API request failed: {response.status} - {error_text}")

# Global API client
api_client = CivicAPI()

async def handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP requests"""
    
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params", {})
    
    try:
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "civic-clinical-evidence-mcp",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "get_civic_stats",
                            "description": "Get basic statistics from the CIViC database (evidence items and genes count)",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "additionalProperties": False
                            }
                        },
                        {
                            "name": "search_disease_evidence",
                            "description": "Search for clinical evidence by disease name",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "disease_name": {
                                        "type": "string",
                                        "description": "Name of the disease to search for (e.g., 'Lung Cancer', 'Breast Cancer')"
                                    },
                                    "limit": {
                                        "type": "integer",
                                        "description": "Maximum number of results to return (1-10)",
                                        "minimum": 1,
                                        "maximum": 10,
                                        "default": 5
                                    }
                                },
                                "required": ["disease_name"],
                                "additionalProperties": False
                            }
                        }
                    ]
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if tool_name == "get_civic_stats":
                result = await api_client.get_stats()
                
                evidence_count = result.get('evidenceItems', {}).get('totalCount', 0)
                gene_count = result.get('genes', {}).get('totalCount', 0)
                
                response_text = f"""## CIViC Database Statistics

**Evidence Items:** {evidence_count:,}
**Genes:** {gene_count:,}

The CIViC database contains curated clinical interpretations of variants in cancer."""
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": response_text
                            }
                        ]
                    }
                }
            
            elif tool_name == "search_disease_evidence":
                disease_name = tool_args["disease_name"]
                limit = tool_args.get("limit", 5)
                
                result = await api_client.search_evidence(disease_name, limit)
                
                evidence_items = result.get('evidenceItems', {})
                total_count = evidence_items.get('totalCount', 0)
                edges = evidence_items.get('edges', [])
                
                if total_count == 0:
                    response_text = f"No evidence found for '{disease_name}'"
                else:
                    lines = [
                        f"## Evidence for {disease_name}",
                        f"**Total found:** {total_count:,}",
                        f"**Showing:** {len(edges)} results",
                        ""
                    ]
                    
                    for i, edge in enumerate(edges, 1):
                        evidence = edge['node']
                        
                        lines.extend([
                            f"### {i}. {evidence.get('name', 'N/A')}",
                            f"- **Level:** {evidence.get('evidenceLevel', 'N/A')}",
                            f"- **Type:** {evidence.get('evidenceType', 'N/A')}",
                            f"- **Status:** {evidence.get('status', 'N/A')}",
                            f"- **Molecular Profile:** {evidence.get('molecularProfile', {}).get('name', 'N/A')}",
                        ])
                        
                        # Add source info if available
                        source = evidence.get('source')
                        if source:
                            citation = source.get('citation', 'N/A')
                            year = source.get('publicationYear')
                            if year:
                                lines.append(f"- **Source:** {citation} ({year})")
                            else:
                                lines.append(f"- **Source:** {citation}")
                        
                        lines.append("")
                    
                    response_text = "\n".join(lines)
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": response_text
                            }
                        ]
                    }
                }
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
    
    except Exception as e:
        logger.error(f"Error handling {method}: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

async def main():
    """Main server loop"""
    logger.info("[CIViC MCP SERVER].main Starting the CIViC MCP Server..........")
    
    try:
        # Infinite loop to keep the server running
        while True:
            # This is where JSON-RPC requests from MCP client arrive.
            # sys.stdin.readline() is a blocking call, using run_in_executor to avoid freezing
            # It offloads the "waiting" part to a background thread, ensuring the main application remains fluid and responsive
            line = await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline 
            )
            
            # If readline() reaches the end of the input stream (EOF), it returns an empty string ("").
            # That means the client (or pipe) has closed the connection.
            if not line: 
                break # EOF → stop server
            
            line = line.strip()
            # Not an EOF and not an empty line
            if not line:
                # Empty line
                continue # blank line → ignore
            
            try:
                request = json.loads(line) # Parse JSON-RPC into a Python dict
                
                # Notifications means no "id" key
                # When its a Notifications, then no response is needed
                if "id" not in request:
                    # "initialized" is a standard lifecycle notification in MCP / JSON-RPC flows, meaning the client has finished setting itself up.
                    if request.get("method") == "initialized":
                        logger.info("[CIViC MCP SERVER].main Client initialized")
                    continue
                
                # Handle requests
                response = await handle_request(request)
                
                # Send response
                response_str = json.dumps(response)
                print(response_str)
                sys.stdout.flush()
                
            except json.JSONDecodeError as e:
                logger.error(f"[CIViC MCP SERVER].main JSON decode error: {e}")
            except Exception as e:
                logger.error(f"[CIViC MCP SERVER].main Error handling request: {e}")
    
    except KeyboardInterrupt:
        logger.info("[CIViC MCP SERVER].main Server stopped")
    finally:
        await api_client.close()

if __name__ == "__main__":
    asyncio.run(main())