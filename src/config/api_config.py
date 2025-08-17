from dataclasses import dataclass

@dataclass
class ClinicalEvidenceConfig:
    """Configuration for clinical evidence search"""
    base_url: str = "https://civicdb.org/api/graphql"
    timeout: int = 30
    max_results: int = 100

