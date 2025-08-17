#!/usr/bin/env python3

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

import aiohttp
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import (
    Resource,
    TextContent,
    Tool,
    ImageContent
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ClinicalEvidenceConfig:
    """Configuration for clinical evidence search"""
    base_url: str = "https://civicdb.org/api/graphql"
    timeout: int = 30
    max_results: int = 100

"""
[CLASS] CivicAPI
[DESCRIPTION] Client for CIViC (Clinical Interpretation of Variants in Cancer) GraphQL API
[ATTRIBUTES]
    - config: ClinicalEvidenceConfig: Configuration for clinical evidence search
    - session: aiohttp.ClientSession: HTTP session for API requests
[METHODS]
    - _get_session: Get or create aiohttp session
    - close: Close the HTTP session
    - search_clinical_evidence: Search for clinical evidence in the CIViC database
    - get_disease_details: Get detailed information about a specific disease
    - get_gene_details: Get detailed information about a specific gene
    - get_therapy_details: Get detailed information about a specific therapy
    - get_evidence_summary_stats: Get summary statistics about the CIViC database
"""
class CivicAPI:
    """Client for CIViC (Clinical Interpretation of Variants in Cancer) GraphQL API"""
    
    def __init__(self, config: ClinicalEvidenceConfig = None):
        self.config = config or ClinicalEvidenceConfig()
        self.session = None
    
    """
    [METHOD] _get_session 
    [DESCRIPTION] Gets or creates an aiohttp session (handles HTTP session managnment)
    aiohttp -> an async HTTP client/server framework
    [RETURN] aiohttp.ClientSession: HTTP session for API requests
    """
    async def _get_session(self) -> aiohttp.ClientSession:
        # Creates a new session if one doesn't exists or is closed
        if self.session is None or self.session.closed:

            # Creates a new session with a timeout and headers
            self.session = aiohttp.ClientSession(
                # Sets a timeout for the session
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                # Sets headers for the session
                headers={
                    "Content-Type": "application/json", # Specifies the data format of the request body
                    "User-Agent": "CIViC-MCP-Server/1.0", # Identifies the client making the request
                    "Accept": "application/json" # Specifies the expected response format
                }
            )

        return self.session
    
    """
    [METHOD] close
    [DESCRIPTION] Closes the HTTP session
    [RETURN] None
    """
    async def close(self):
        # Closes the session if it exists and is not already closed
        if self.session and not self.session.closed:
            await self.session.close()
    
    """
    [METHOD] search_clinical_evidence
    [DESCRIPTION] Searches for clinical evidence in the CIViC database
    [RETURN] Dict[str, Any]: Dictionary containing the search results
    [PARAMETERS]
        - disease_name: Disease or condition name : eg- "breast cancer"
        - therapy_name: Therapy or drug name : eg- "Herceptin"
        - gene_name: Gene symbol or name : eg- "BRCA1"
        - variant_name: Variant name : eg- "BRCA1:c.1852C>T"
        - evidence_type: Type of evidence (predictive, diagnostic, prognostic, etc.)
        - evidence_level: Evidence level (A, B, C, D, E) 
        - clinical_significance: Clinical significance : eg- "Strong"
        - therapy_type: Type of therapy : eg- "antibody"
        - molecular_profile_name: Molecular profile name : eg- "BRCA1:c.1852C>T"
        - source_type: Source type (PubMed, ASCO, etc.) 
        - page_size: Number of results to return : eg- 10
    [NOTES]
        - Filters can be applied to the query to narrow down the search results
        - The query is built dynamically based on the provided parameters
        - The results are returned as a dictionary containing the search results
        - The results are sorted by evidence level in ascending order
        - The results are limited to the maximum number of results specified in the config
    """
    async def search_clinical_evidence(
        self,
        disease_name: Optional[str] = None,
        therapy_name: Optional[str] = None,
        gene_name: Optional[str] = None,
        variant_name: Optional[str] = None,
        evidence_type: Optional[str] = None,
        evidence_level: Optional[str] = None,
        clinical_significance: Optional[str] = None,
        therapy_type: Optional[str] = None,
        molecular_profile_name: Optional[str] = None,
        source_type: Optional[str] = None,
        page_size: int = 25
    ) -> Dict[str, Any]:
        """
        Search for clinical evidence in the CIViC database
        
        Args:
            disease_name: Disease or condition name
            therapy_name: Therapy or drug name
            gene_name: Gene symbol or name
            variant_name: Variant name
            evidence_type: Type of evidence (predictive, diagnostic, prognostic, etc.)
            evidence_level: Evidence level (A, B, C, D, E)
            clinical_significance: Clinical significance
            therapy_type: Type of therapy
            molecular_profile_name: Molecular profile name
            source_type: Source type (PubMed, ASCO, etc.)
            page_size: Number of results to return
        """
        
        # Builds the filters for the GraphQL query
        filters = []
        
        # Adds the filters to the list, if they are not None
        if disease_name:
            filters.append(f'diseaseName: "{disease_name}"')
        if therapy_name:
            filters.append(f'therapyName: "{therapy_name}"')
        if gene_name:
            filters.append(f'geneName: "{gene_name}"')
        if variant_name:
            filters.append(f'variantName: "{variant_name}"')
        if evidence_type:
            filters.append(f'evidenceType: {evidence_type.upper()}')
        if evidence_level:
            filters.append(f'evidenceLevel: {evidence_level.upper()}')
        if clinical_significance:
            filters.append(f'clinicalSignificance: {clinical_significance.upper()}')
        if therapy_type:
            filters.append(f'therapyType: "{therapy_type}"')
        if molecular_profile_name:
            filters.append(f'molecularProfileName: "{molecular_profile_name}"')
        if source_type:
            filters.append(f'sourceType: "{source_type}"')
        
        # Joins the filters with a comma
        filter_string = ", ".join(filters) if filters else ""
        
        # Builds the GraphQL query with filters
        # query -> the GraphQL query to be executed
        # evidenceItems -> the type of data to be returned
        # first -> the number of results to return
        # sortBy -> the field to sort the results by
        # field -> the field to sort the results by
        # direction -> the direction to sort the results by
        """
        Builds the GraphQL query with filters and returns the results
        [QUERY] SearchClinicalEvidence
        [DESCRIPTION] Searches for clinical evidence in the CIViC database
        [RETURN] Dict[str, Any]: Dictionary containing the search results
        [NOTES]
            - filter_string: String containing the filters for the query
            - page_size: Number of results to return
            - evidenceItems -> the type of data to be returned
            - first -> the number of results to return
            - sortBy -> the field to sort the results by
            - field -> the field to sort the results by
            - direction -> the direction to sort the results by
        """
        query = f"""
        query SearchClinicalEvidence {{
            evidenceItems(
                {filter_string}
                first: {min(page_size, self.config.max_results)}
                sortBy: {{
                    field: EVIDENCE_LEVEL
                    direction: ASC
                }}
            ) {{
                totalCount
                pageInfo {{
                    hasNextPage
                    hasPreviousPage
                    startCursor
                    endCursor
                }}
                edges {{
                    node {{
                        id
                        name
                        description
                        evidenceLevel
                        evidenceType
                        evidenceDirection
                        clinicalSignificance
                        therapyInteractionType
                        status
                        significance
                        molecularProfile {{
                            id
                            name
                            variants {{
                                id
                                name
                                gene {{
                                    id
                                    name
                                    entrezId
                                }}
                            }}
                        }}
                        disease {{
                            id
                            name
                            doid
                            diseaseUrl
                        }}
                        therapies {{
                            id
                            name
                            ncitId
                            therapyUrl
                        }}
                        source {{
                            id
                            citation
                            sourceType
                            publicationDate
                            journal
                            fullJournalTitle
                            pubmedId
                        }}
                        phenotypes {{
                            id
                            name
                            hpoId
                        }}
                        variantOrigin
                        ampLevel
                        nccnGuideline
                        fdaApproval
                        regulatoryApproval
                    }}
                }}
            }}
        }}
        """
        
        # Gets the session
        session = await self._get_session()
        
        # Executes the query
        try:
            # Sends the query to the API
            async with session.post(
                self.config.base_url,
                json={"query": query}
            ) as response:
                # Checks if the response is successful
                if response.status == 200:
                    # Parses the response as JSON
                    result = await response.json()
                    # Checks if there are any errors in the response
                    if "errors" in result:
                        raise Exception(f"GraphQL errors: {result['errors']}")
                    return result["data"]
                else:
                    # If the response is not successful, raises an exception
                    error_text = await response.text()
                    raise Exception(f"API request failed with status {response.status}: {error_text}")
        except Exception as e:
            logger.error(f"Error searching clinical evidence: {e}")
            raise
    

    """
    [METHOD] get_disease_details
    [DESCRIPTION] Gets detailed information about a specific disease from the CIViC database
    [RETURN] Dict[str, Any]: Dictionary containing the disease details
    [PARAMETERS]
        - disease_name: Disease or condition name : eg- "breast cancer"
    """
    async def get_disease_details(self, disease_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific disease"""
        
        query = f"""
        query GetDiseaseDetails {{
            diseases(name: "{disease_name}") {{
                id
                name
                doid
                diseaseUrl
                diseaseAliases {{
                    name
                }}
                evidenceItems {{
                    totalCount
                }}
                assertions {{
                    totalCount
                }}
                molecularProfiles {{
                    totalCount
                }}
            }}
        }}
        """
        
        session = await self._get_session()
        
        try:
            async with session.post(
                self.config.base_url,
                json={"query": query}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if "errors" in result:
                        raise Exception(f"GraphQL errors: {result['errors']}")
                    return result["data"]
                else:
                    error_text = await response.text()
                    raise Exception(f"API request failed with status {response.status}: {error_text}")
        except Exception as e:
            logger.error(f"Error getting disease details: {e}")
            raise
    
    """
    [METHOD] get_gene_details
    [DESCRIPTION] Gets detailed information about a specific gene from the CIViC database
    [RETURN] Dict[str, Any]: Dictionary containing the gene details
    [PARAMETERS]
        - gene_name: Gene symbol or name : eg- "BRCA1"
    """
    async def get_gene_details(self, gene_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific gene"""
        
        query = f"""
        query GetGeneDetails {{
            genes(name: "{gene_name}") {{
                id
                name
                entrezId
                description
                geneAliases {{
                    name
                }}
                variants {{
                    totalCount
                    edges {{
                        node {{
                            id
                            name
                            variantAliases {{
                                name
                            }}
                            molecularProfiles {{
                                totalCount
                            }}
                            evidenceItems {{
                                totalCount
                            }}
                        }}
                    }}
                }}
                evidenceItems {{
                    totalCount
                }}
                assertions {{
                    totalCount
                }}
            }}
        }}
        """
        
        session = await self._get_session()
        
        try:
            async with session.post(
                self.config.base_url,
                json={"query": query}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if "errors" in result:
                        raise Exception(f"GraphQL errors: {result['errors']}")
                    return result["data"]
                else:
                    error_text = await response.text()
                    raise Exception(f"API request failed with status {response.status}: {error_text}")
        except Exception as e:
            logger.error(f"Error getting gene details: {e}")
            raise
    
    """
    [METHOD] get_therapy_details
    [DESCRIPTION] Gets detailed information about a specific therapy from the CIViC database
    [RETURN] Dict[str, Any]: Dictionary containing the therapy details
    [PARAMETERS]
        - therapy_name: Therapy or drug name : eg- "Herceptin"
    """
    async def get_therapy_details(self, therapy_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific therapy"""
        
        query = f"""
        query GetTherapyDetails {{
            therapies(name: "{therapy_name}") {{
                id
                name
                ncitId
                therapyUrl
                therapyAliases {{
                    name
                }}
                evidenceItems {{
                    totalCount
                }}
                assertions {{
                    totalCount
                }}
            }}
        }}
        """
        
        session = await self._get_session()
        
        try:
            async with session.post(
                self.config.base_url,
                json={"query": query}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if "errors" in result:
                        raise Exception(f"GraphQL errors: {result['errors']}")
                    return result["data"]
                else:
                    error_text = await response.text()
                    raise Exception(f"API request failed with status {response.status}: {error_text}")
        except Exception as e:
            logger.error(f"Error getting therapy details: {e}")
            raise
    
    """
    [METHOD] get_evidence_summary_stats
    [DESCRIPTION] Gets summary statistics about the CIViC database
    [RETURN] Dict[str, Any]: Dictionary containing the summary statistics
    [PARAMETERS]
        - None
    """
    async def get_evidence_summary_stats(self) -> Dict[str, Any]:
        
        query = """
        query GetSummaryStats {
            evidenceItems {
                totalCount
            }
            genes {
                totalCount
            }
            variants {
                totalCount
            }
            diseases {
                totalCount
            }
            therapies {
                totalCount
            }
            molecularProfiles {
                totalCount
            }
            assertions {
                totalCount
            }
        }
        """
        
        session = await self._get_session()
        
        try:
            async with session.post(
                self.config.base_url,
                json={"query": query}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if "errors" in result:
                        raise Exception(f"GraphQL errors: {result['errors']}")
                    return result["data"]
                else:
                    error_text = await response.text()
                    raise Exception(f"API request failed with status {response.status}: {error_text}")
        except Exception as e:
            logger.error(f"Error getting summary statistics: {e}")
            raise


# Initialize the CIViC API client
api_client = CivicAPI()

# Create MCP server
app = Server("civic-clinical-evidence-mcp")


@app.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="search_clinical_evidence",
            description="""
            Search for clinical evidence in the CIViC (Clinical Interpretation of Variants in Cancer) database.
            Returns evidence items with details about variants, diseases, therapies, and clinical significance.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "disease_name": {
                        "type": "string",
                        "description": "Disease or condition name (e.g., 'Lung Non-small Cell Carcinoma', 'Breast Cancer')"
                    },
                    "therapy_name": {
                        "type": "string",
                        "description": "Therapy or drug name (e.g., 'Trastuzumab', 'Erlotinib')"
                    },
                    "gene_name": {
                        "type": "string",
                        "description": "Gene symbol or name (e.g., 'EGFR', 'BRAF', 'TP53')"
                    },
                    "variant_name": {
                        "type": "string",
                        "description": "Variant name (e.g., 'L858R', 'V600E')"
                    },
                    "evidence_type": {
                        "type": "string",
                        "description": "Type of clinical evidence",
                        "enum": ["predictive", "diagnostic", "prognostic", "predisposing", "functional", "oncogenic"]
                    },
                    "evidence_level": {
                        "type": "string",
                        "description": "Evidence level rating",
                        "enum": ["A", "B", "C", "D", "E"]
                    },
                    "clinical_significance": {
                        "type": "string",
                        "description": "Clinical significance of the evidence",
                        "enum": ["sensitivity", "resistance", "adverse_response", "reduced_sensitivity", "better_outcome", "poor_outcome", "positive", "negative"]
                    },
                    "therapy_type": {
                        "type": "string",
                        "description": "Type of therapy (e.g., 'targeted therapy', 'chemotherapy')"
                    },
                    "molecular_profile_name": {
                        "type": "string",
                        "description": "Molecular profile name"
                    },
                    "source_type": {
                        "type": "string",
                        "description": "Source type for evidence",
                        "enum": ["PubMed", "ASCO", "ASH", "AACR", "ESMO"]
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Number of results to return (1-100)",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 25
                    }
                }
            }
        ),
        Tool(
            name="get_disease_details",
            description="""
            Get detailed information about a specific disease from the CIViC database.
            Returns disease information, aliases, and related evidence counts.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "disease_name": {
                        "type": "string",
                        "description": "Disease name to look up (e.g., 'Lung Non-small Cell Carcinoma')"
                    }
                },
                "required": ["disease_name"]
            }
        ),
        Tool(
            name="get_gene_details", 
            description="""
            Get detailed information about a specific gene from the CIViC database.
            Returns gene information, variants, and related evidence counts.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "gene_name": {
                        "type": "string", 
                        "description": "Gene symbol or name to look up (e.g., 'EGFR', 'BRAF')"
                    }
                },
                "required": ["gene_name"]
            }
        ),
        Tool(
            name="get_therapy_details",
            description="""
            Get detailed information about a specific therapy from the CIViC database.
            Returns therapy information, aliases, and related evidence counts.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "therapy_name": {
                        "type": "string",
                        "description": "Therapy or drug name to look up (e.g., 'Trastuzumab', 'Erlotinib')"
                    }
                },
                "required": ["therapy_name"]
            }
        ),
        Tool(
            name="get_evidence_summary_stats",
            description="""
            Get summary statistics from the CIViC database including total counts
            of evidence items, genes, variants, diseases, therapies, and molecular profiles.
            """,
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    
    if name == "search_clinical_evidence":
        try:
            # Extract search parameters
            search_params = {
                "disease_name": arguments.get("disease_name"),
                "therapy_name": arguments.get("therapy_name"),
                "gene_name": arguments.get("gene_name"),
                "variant_name": arguments.get("variant_name"),
                "evidence_type": arguments.get("evidence_type"),
                "evidence_level": arguments.get("evidence_level"),
                "clinical_significance": arguments.get("clinical_significance"),
                "therapy_type": arguments.get("therapy_type"),
                "molecular_profile_name": arguments.get("molecular_profile_name"),
                "source_type": arguments.get("source_type"),
                "page_size": arguments.get("page_size", 25)
            }
            
            # Remove None values
            search_params = {k: v for k, v in search_params.items() if v is not None}
            
            result = await api_client.search_clinical_evidence(**search_params)
            
            # Format the response
            evidence_items = result.get('evidenceItems', {})
            total_count = evidence_items.get('totalCount', 0)
            edges = evidence_items.get('edges', [])
            
            if not edges:
                return [TextContent(
                    type="text",
                    text="No clinical evidence found matching the specified criteria."
                )]
            
            # Create formatted report
            report_lines = [
                f"## Clinical Evidence Search Results",
                f"**Total Evidence Items Found:** {total_count:,}",
                f"**Showing:** {len(edges)} results",
                ""
            ]
            
            for i, edge in enumerate(edges, 1):
                evidence = edge['node']
                
                report_lines.extend([
                    f"### {i}. Evidence Item {evidence['id']}",
                    f"**Name:** {evidence.get('name', 'N/A')}",
                    f"**Evidence Level:** {evidence.get('evidenceLevel', 'N/A')}",
                    f"**Evidence Type:** {evidence.get('evidenceType', 'N/A')}",
                    f"**Clinical Significance:** {evidence.get('clinicalSignificance', 'N/A')}",
                    f"**Status:** {evidence.get('status', 'N/A')}",
                    ""
                ])
                
                # Disease information
                disease = evidence.get('disease')
                if disease:
                    report_lines.append(f"**Disease:** {disease.get('name', 'N/A')}")
                
                # Gene and variant information
                molecular_profile = evidence.get('molecularProfile')
                if molecular_profile:
                    variants = molecular_profile.get('variants', [])
                    if variants:
                        genes = [v.get('gene', {}).get('name', 'Unknown') for v in variants if v.get('gene')]
                        variant_names = [v.get('name', 'Unknown') for v in variants]
                        report_lines.extend([
                            f"**Genes:** {', '.join(set(genes))}",
                            f"**Variants:** {', '.join(variant_names)}"
                        ])
                
                # Therapy information
                therapies = evidence.get('therapies', [])
                if therapies:
                    therapy_names = [t.get('name', 'Unknown') for t in therapies]
                    report_lines.append(f"**Therapies:** {', '.join(therapy_names)}")
                
                # Source information
                source = evidence.get('source')
                if source:
                    citation = source.get('citation', 'N/A')
                    pubmed_id = source.get('pubmedId')
                    if pubmed_id:
                        report_lines.append(f"**Source:** {citation} (PMID: {pubmed_id})")
                    else:
                        report_lines.append(f"**Source:** {citation}")
                
                # Description
                description = evidence.get('description')
                if description:
                    # Truncate long descriptions
                    if len(description) > 300:
                        description = description[:297] + "..."
                    report_lines.extend([
                        f"**Description:** {description}",
                        ""
                    ])
                else:
                    report_lines.append("")
            
            return [TextContent(
                type="text",
                text="\n".join(report_lines)
            )]
            
        except Exception as e:
            logger.error(f"Error in search_clinical_evidence: {e}")
            return [TextContent(
                type="text",
                text=f"Error searching clinical evidence: {str(e)}"
            )]
    
    elif name == "get_disease_details":
        try:
            disease_name = arguments["disease_name"]
            result = await api_client.get_disease_details(disease_name)
            
            diseases = result.get('diseases', [])
            if not diseases:
                return [TextContent(
                    type="text",
                    text=f"No disease found with name: {disease_name}"
                )]
            
            disease = diseases[0]
            
            # Format disease details
            report_lines = [
                f"## Disease Details: {disease.get('name', 'N/A')}",
                f"**ID:** {disease.get('id', 'N/A')}",
                f"**DOID:** {disease.get('doid', 'N/A')}",
                ""
            ]
            
            # Aliases
            aliases = disease.get('diseaseAliases', [])
            if aliases:
                alias_names = [alias.get('name') for alias in aliases if alias.get('name')]
                report_lines.extend([
                    f"**Aliases:** {', '.join(alias_names)}",
                    ""
                ])
            
            # Evidence counts
            evidence_count = disease.get('evidenceItems', {}).get('totalCount', 0)
            assertion_count = disease.get('assertions', {}).get('totalCount', 0)
            profile_count = disease.get('molecularProfiles', {}).get('totalCount', 0)
            
            report_lines.extend([
                f"**Evidence Items:** {evidence_count:,}",
                f"**Assertions:** {assertion_count:,}",
                f"**Molecular Profiles:** {profile_count:,}",
                ""
            ])
            
            # URL
            disease_url = disease.get('diseaseUrl')
            if disease_url:
                report_lines.append(f"**URL:** {disease_url}")
            
            return [TextContent(
                type="text",
                text="\n".join(report_lines)
            )]
            
        except Exception as e:
            logger.error(f"Error in get_disease_details: {e}")
            return [TextContent(
                type="text",
                text=f"Error getting disease details: {str(e)}"
            )]
    
    elif name == "get_gene_details":
        try:
            gene_name = arguments["gene_name"]
            result = await api_client.get_gene_details(gene_name)
            
            genes = result.get('genes', [])
            if not genes:
                return [TextContent(
                    type="text",
                    text=f"No gene found with name: {gene_name}"
                )]
            
            gene = genes[0]
            
            # Format gene details
            report_lines = [
                f"## Gene Details: {gene.get('name', 'N/A')}",
                f"**ID:** {gene.get('id', 'N/A')}",
                f"**Entrez ID:** {gene.get('entrezId', 'N/A')}",
                ""
            ]
            
            # Description
            description = gene.get('description')
            if description:
                report_lines.extend([
                    f"**Description:** {description}",
                    ""
                ])
            
            # Aliases
            aliases = gene.get('geneAliases', [])
            if aliases:
                alias_names = [alias.get('name') for alias in aliases if alias.get('name')]
                report_lines.extend([
                    f"**Aliases:** {', '.join(alias_names)}",
                    ""
                ])
            
            # Counts
            variant_count = gene.get('variants', {}).get('totalCount', 0)
            evidence_count = gene.get('evidenceItems', {}).get('totalCount', 0)
            assertion_count = gene.get('assertions', {}).get('totalCount', 0)
            
            report_lines.extend([
                f"**Variants:** {variant_count:,}",
                f"**Evidence Items:** {evidence_count:,}",
                f"**Assertions:** {assertion_count:,}",
                ""
            ])
            
            # Top variants
            variant_edges = gene.get('variants', {}).get('edges', [])
            if variant_edges:
                report_lines.append("**Top Variants:**")
                for i, edge in enumerate(variant_edges[:5], 1):
                    variant = edge['node']
                    variant_name = variant.get('name', 'Unknown')
                    variant_evidence_count = variant.get('evidenceItems', {}).get('totalCount', 0)
                    report_lines.append(f"  {i}. {variant_name} ({variant_evidence_count} evidence items)")
            
            return [TextContent(
                type="text",
                text="\n".join(report_lines)
            )]
            
        except Exception as e:
            logger.error(f"Error in get_gene_details: {e}")
            return [TextContent(
                type="text",
                text=f"Error getting gene details: {str(e)}"
            )]
    
    elif name == "get_therapy_details":
        try:
            therapy_name = arguments["therapy_name"]
            result = await api_client.get_therapy_details(therapy_name)
            
            therapies = result.get('therapies', [])
            if not therapies:
                return [TextContent(
                    type="text",
                    text=f"No therapy found with name: {therapy_name}"
                )]
            
            therapy = therapies[0]
            
            # Format therapy details
            report_lines = [
                f"## Therapy Details: {therapy.get('name', 'N/A')}",
                f"**ID:** {therapy.get('id', 'N/A')}",
                f"**NCIT ID:** {therapy.get('ncitId', 'N/A')}",
                ""
            ]
            
            # Aliases
            aliases = therapy.get('therapyAliases', [])
            if aliases:
                alias_names = [alias.get('name') for alias in aliases if alias.get('name')]
                report_lines.extend([
                    f"**Aliases:** {', '.join(alias_names)}",
                    ""
                ])
            
            # Evidence counts
            evidence_count = therapy.get('evidenceItems', {}).get('totalCount', 0)
            assertion_count = therapy.get('assertions', {}).get('totalCount', 0)
            
            report_lines.extend([
                f"**Evidence Items:** {evidence_count:,}",
                f"**Assertions:** {assertion_count:,}",
                ""
            ])
            
            # URL
            therapy_url = therapy.get('therapyUrl')
            if therapy_url:
                report_lines.append(f"**URL:** {therapy_url}")
            
            return [TextContent(
                type="text",
                text="\n".join(report_lines)
            )]
            
        except Exception as e:
            logger.error(f"Error in get_therapy_details: {e}")
            return [TextContent(
                type="text",
                text=f"Error getting therapy details: {str(e)}"
            )]
    
    elif name == "get_evidence_summary_stats":
        try:
            result = await api_client.get_evidence_summary_stats()
            
            # Format summary statistics
            report_lines = [
                "## CIViC Database Summary Statistics",
                ""
            ]
            
            stats = [
                ("Evidence Items", result.get('evidenceItems', {}).get('totalCount', 0)),
                ("Genes", result.get('genes', {}).get('totalCount', 0)),
                ("Variants", result.get('variants', {}).get('totalCount', 0)),
                ("Diseases", result.get('diseases', {}).get('totalCount', 0)),
                ("Therapies", result.get('therapies', {}).get('totalCount', 0)),
                ("Molecular Profiles", result.get('molecularProfiles', {}).get('totalCount', 0)),
                ("Assertions", result.get('assertions', {}).get('totalCount', 0))
            ]
            
            for label, count in stats:
                report_lines.append(f"**{label}:** {count:,}")
            
            return [TextContent(
                type="text",
                text="\n".join(report_lines)
            )]
            
        except Exception as e:
            logger.error(f"Error in get_evidence_summary_stats: {e}")
            return [TextContent(
                type="text",
                text=f"Error getting summary statistics: {str(e)}"
            )]
    
    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]

async def main():
    """Main entry point"""
    # Import required for MCP server
    from mcp.server.stdio import stdio_server
    
    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream, 
                write_stream, 
                InitializationOptions(
                    server_name="civic-clinical-evidence-mcp",
                    server_version="1.0.0",
                    capabilities={}
                )
            )
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        await api_client.close()

if __name__ == "__main__":
    asyncio.run(main())