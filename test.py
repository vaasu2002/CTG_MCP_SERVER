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
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClinicalEvidenceClient:
    """OpenAI client for querying the CIViC MCP server"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        """
        Initialize the client
        
        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (default: gpt-4)
        """
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = model
        self.mcp_server_process = None
    
    def start_mcp_server(self, server_script_path: str = "./server.py"):
        """Start the MCP server process"""
        try:
            self.mcp_server_process = subprocess.Popen(
                [sys.executable, server_script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info("MCP server started successfully")
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise
    
    def stop_mcp_server(self):
        """Stop the MCP server process"""
        if self.mcp_server_process:
            self.mcp_server_process.terminate()
            self.mcp_server_process.wait()
            logger.info("MCP server stopped")
    
    def query_clinical_evidence(
        self,
        query: str,
        context: Optional[str] = None
    ) -> str:
        """
        Query clinical evidence using natural language
        
        Args:
            query: Natural language query about clinical evidence
            context: Optional additional context
            
        Returns:
            Response from the AI assistant
        """
        
        # System prompt for clinical evidence queries
        system_prompt = """
        You are a clinical evidence research assistant with access to the CIViC (Clinical Interpretation of Variants in Cancer) database through MCP tools.

        Available tools:
        - search_clinical_evidence: Search for clinical evidence by disease, therapy, gene, variant, evidence type, etc.
        - get_disease_details: Get detailed information about a specific disease
        - get_gene_details: Get detailed information about a specific gene
        - get_therapy_details: Get detailed information about a specific therapy
        - get_evidence_summary_stats: Get summary statistics from the database

        When answering queries:
        1. Use the appropriate MCP tools to gather relevant clinical evidence
        2. Provide clear, evidence-based responses
        3. Include specific details like evidence levels, clinical significance, and source citations
        4. Explain the clinical relevance and implications
        5. Be precise about limitations and uncertainties

        Focus on providing actionable clinical insights while being scientifically accurate.
        """
        
        # Build the conversation
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        if context:
            messages.append({"role": "user", "content": f"Context: {context}"})
        
        messages.append({"role": "user", "content": query})
        
        # Define the available tools for the OpenAI client
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_clinical_evidence",
                    "description": "Search for clinical evidence in the CIViC database",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "disease_name": {"type": "string", "description": "Disease or condition name"},
                            "therapy_name": {"type": "string", "description": "Therapy or drug name"},
                            "gene_name": {"type": "string", "description": "Gene symbol or name"},
                            "variant_name": {"type": "string", "description": "Variant name"},
                            "evidence_type": {
                                "type": "string", 
                                "enum": ["predictive", "diagnostic", "prognostic", "predisposing", "functional", "oncogenic"]
                            },
                            "evidence_level": {
                                "type": "string",
                                "enum": ["A", "B", "C", "D", "E"]
                            },
                            "clinical_significance": {
                                "type": "string",
                                "enum": ["sensitivity", "resistance", "adverse_response", "reduced_sensitivity", "better_outcome", "poor_outcome", "positive", "negative"]
                            },
                            "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 25}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_disease_details",
                    "description": "Get detailed information about a specific disease",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "disease_name": {"type": "string", "description": "Disease name to look up"}
                        },
                        "required": ["disease_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_gene_details",
                    "description": "Get detailed information about a specific gene",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "gene_name": {"type": "string", "description": "Gene symbol or name to look up"}
                        },
                        "required": ["gene_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_therapy_details",
                    "description": "Get detailed information about a specific therapy",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "therapy_name": {"type": "string", "description": "Therapy or drug name to look up"}
                        },
                        "required": ["therapy_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_evidence_summary_stats",
                    "description": "Get summary statistics from the CIViC database",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]
        
        try:
            # Make the initial request
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            # Process tool calls if any
            message = response.choices[0].message
            
            if message.tool_calls:
                # Add the assistant's message to conversation
                messages.append(message)
                
                # Process each tool call
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Simulate calling the MCP server (in a real implementation, 
                    # you would connect to the actual MCP server)
                    tool_result = self._simulate_mcp_call(function_name, function_args)
                    
                    # Add the tool result to the conversation
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_result
                    })
                
                # Get the final response
                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
                
                return final_response.choices[0].message.content
            else:
                return message.content
                
        except Exception as e:
            logger.error(f"Error querying clinical evidence: {e}")
            return f"Error: {str(e)}"
    
    def _simulate_mcp_call(self, function_name: str, function_args: Dict[str, Any]) -> str:
        """
        Simulate an MCP server call (placeholder implementation)
        In a real implementation, this would communicate with the actual MCP server
        """
        # This is a simplified simulation - replace with actual MCP communication
        if function_name == "search_clinical_evidence":
            return """
            ## Clinical Evidence Search Results
            **Total Evidence Items Found:** 156
            **Showing:** 25 results

            ### 1. Evidence Item 2997
            **Name:** EID2997
            **Evidence Level:** B
            **Evidence Type:** Predictive
            **Clinical Significance:** Sensitivity
            **Status:** Accepted
            **Disease:** Lung Non-small Cell Carcinoma
            **Genes:** EGFR
            **Variants:** L858R
            **Therapies:** Erlotinib
            **Source:** Lynch et al. 2004. Activating mutations in the epidermal growth factor receptor underlying responsiveness of non-small-cell lung cancer to gefitinib. (PMID: 15118073)
            **Description:** EGFR L858R positive NSCLC patients demonstrate sensitivity to erlotinib treatment...
            """
        elif function_name == "get_gene_details":
            return """
            ## Gene Details: EGFR
            **ID:** 19
            **Entrez ID:** 1956
            **Description:** The epidermal growth factor receptor (EGFR) is a receptor tyrosine kinase...
            **Variants:** 89
            **Evidence Items:** 345
            **Assertions:** 23
            """
        else:
            return f"Simulated result for {function_name} with args: {function_args}"

def main():
    """Example usage of the Clinical Evidence Client"""
    
    # Initialize client (replace with your OpenAI API key)
    api_key = "your-openai-api-key-here"
    client = ClinicalEvidenceClient(api_key)
    
    # Example queries
    queries = [
        "What evidence exists for EGFR L858R mutation in lung cancer treatment with erlotinib?",
        "Find predictive evidence for BRAF V600E mutation in melanoma",
        "What are the clinical implications of TP53 mutations in breast cancer?",
        "Show me therapy options for HER2 positive breast cancer",
        "Get summary statistics for the CIViC database"
    ]
    
    print("🧬 Clinical Evidence Research Assistant")
    print("=" * 50)
    
    for i, query in enumerate(queries, 1):
        print(f"\n📋 Query {i}: {query}")
        print("-" * 40)
        
        try:
            response = client.query_clinical_evidence(query)
            print(response)
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("\n" + "=" * 50)
    
    # Interactive mode
    print("\n🔍 Interactive Mode - Enter your clinical evidence queries:")
    print("(Type 'quit' to exit)")
    
    while True:
        try:
            user_query = input("\n💬 Your query: ").strip()
            
            if user_query.lower() in ['quit', 'exit', 'q']:
                break
            
            if not user_query:
                continue
            
            print("\n🔬 Searching clinical evidence...")
            response = client.query_clinical_evidence(user_query)
            print(f"\n📊 Results:\n{response}")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()