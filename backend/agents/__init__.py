from agents.sql_injection import SQLInjectionAgent
from agents.xss import XSSAgent
from agents.secrets import SecretsAgent
from agents.binary_exploit import BinaryExploitAgent
from agents.reverse_engineering import ReverseEngineeringAgent
from agents.low_level_agent import LowLevelAgent

__all__ = [
    "SQLInjectionAgent",
    "XSSAgent",
    "SecretsAgent",
    "BinaryExploitAgent",
    "ReverseEngineeringAgent",
    "LowLevelAgent",
    "ALL_AGENTS"
]

ALL_AGENTS = [
    SQLInjectionAgent,
    XSSAgent,
    SecretsAgent,
    BinaryExploitAgent,
    ReverseEngineeringAgent,
    LowLevelAgent
]