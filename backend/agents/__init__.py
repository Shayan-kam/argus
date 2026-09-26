from agents.sql_injection import SQLInjectionAgent
from agents.xss import XSSAgent
from agents.secrets import SecretsAgent
from agents.binary_exploit import BinaryExploitAgent
from agents.reverse_engineering import ReverseEngineeringAgent
from agents.low_level_agent import LowLevelAgent
from agents.http_header_injection import HTTPHeaderInjectionAgent
from agents.pipeline_agent import PipelineSecurityAgent
from agents.access_control import AccessControlAgent

__all__ = [
    "SQLInjectionAgent",
    "XSSAgent",
    "SecretsAgent",
    "BinaryExploitAgent",
    "ReverseEngineeringAgent",
    "LowLevelAgent",
    "HTTPHeaderInjectionAgent",
    "PipelineSecurityAgent",
    "AccessControlAgent",
    "ALL_AGENTS"
]

ALL_AGENTS = [
    SQLInjectionAgent,
    XSSAgent,
    SecretsAgent,
    BinaryExploitAgent,
    ReverseEngineeringAgent,
    LowLevelAgent,
    HTTPHeaderInjectionAgent,
    PipelineSecurityAgent,
    AccessControlAgent
]