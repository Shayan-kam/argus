"""
Agent routing and focused source selection.

This module determines:
1. Which agents are relevant.
2. Which files each agent should receive.
3. Which code regions are most relevant to each agent.
"""

AGENT_ROUTING_RULES = {
    "SQL Injection Agent": {
        "required_any": [
            "sql_query",
            "database_execution"
        ],
        "supporting_signals": [
            "user_input"
        ]
    },

    "Cross-Site Scripting Agent": {
        "required_any": [
            "javascript_dom",
            "dangerous_html_rendering",
            "html_template"
        ],
        "supporting_signals": [
            "user_input"
        ]
    },

    "Hardcoded Secrets Agent": {
        "required_any": [
            "secret_like_content"
        ],
        "supporting_signals": []
    },

    "Binary Exploitation Agent": {
        "required_any": [
            "memory_unsafe",
            "native_code"
        ],
        "supporting_signals": [
            "shell_execution",
            "assembly_code"
        ]
    },

    "Reverse Engineering Agent": {
        "required_any": [
            "unsafe_deserialization",
            "binary_format"
        ],
        "supporting_signals": [
            "native_code",
            "authentication"
        ]
    },

    "Low-Level & Memory Security Agent": {
        "required_any": [
            "memory_allocation",
            "buffer_manipulation",
            "memory_unsafe",
            "memory_lifecycle",
            "alloc_arithmetic"
        ],
        "supporting_signals": [
            "native_code",
            "access_control",
            "race_conditions"
        ]
    },

    "CI/CD & Pipeline Security Agent": {
        "required_any": [
            "workflow_injection",
            "ci_pipeline",
            "container_misconfig"
        ],
        "supporting_signals": [
            "privileged_execution",
            "insecure_action",
            "shell_execution"
        ]
    },

    "HTTP Header Injection Agent": {
        "required_any": [
            "host_header",
            "absolute_url_from_request",
            "response_header_write"
        ],
        "supporting_signals": [
            "user_input",
            "authentication"
        ]
    },

    "Broken Access Control Agent": {
        "required_any": [
            "access_control_risk"
        ],
        "supporting_signals": [
            "missing_auth_boundary",
            "user_input",
            "authentication"
        ]
    }
}


AGENT_SIGNAL_MAPPING = {
    "SQL Injection Agent": [
        "sql_query",
        "database_execution",
        "user_input"
    ],

    "Cross-Site Scripting Agent": [
        "javascript_dom",
        "dangerous_html_rendering",
        "html_template",
        "user_input"
    ],

    "Hardcoded Secrets Agent": [
        "secret_like_content"
    ],

    "Binary Exploitation Agent": [
        "memory_unsafe",
        "native_code",
        "shell_execution",
        "assembly_code"
    ],

    "Reverse Engineering Agent": [
        "unsafe_deserialization",
        "binary_format",
        "native_code",
        "authentication"
    ],

    "Low-Level & Memory Security Agent": [
        "memory_allocation",
        "buffer_manipulation",
        "memory_unsafe",
        "memory_lifecycle",
        "alloc_arithmetic",
        "race_conditions",
        "native_code",
        "access_control"
    ],

    "CI/CD & Pipeline Security Agent": [
        "workflow_injection",
        "ci_pipeline",
        "container_misconfig",
        "privileged_execution",
        "insecure_action",
        "shell_execution"
    ],

    "HTTP Header Injection Agent": [
        "host_header",
        "absolute_url_from_request",
        "response_header_write",
        "user_input",
        "authentication"
    ],

    "Broken Access Control Agent": [
        "access_control_risk",
        "missing_auth_boundary",
        "user_input",
        "authentication"
    ]
}


def calculate_agent_relevance(agent_name, repository_analysis):
    """
    Calculate a simple relevance score for an agent.
    This is a routing score, not a vulnerability confidence score.
    """
    rules = AGENT_ROUTING_RULES.get(agent_name)
    if not rules:
        return 0.0

    signals = repository_analysis.get("signals", {})

    required_matches = 0
    supporting_matches = 0

    for signal in rules["required_any"]:
        if signal in signals:
            required_matches += 1

    for signal in rules["supporting_signals"]:
        if signal in signals:
            supporting_matches += 1

    # No required signal means the agent is not relevant.
    if required_matches == 0:
        return 0.0

    score = 0.70

    if required_matches >= 2:
        score += 0.20

    if supporting_matches >= 1:
        score += 0.10

    return min(score, 1.0)


def select_relevant_agents(agents, repository_analysis):
    """
    Return agents that have enough evidence to justify execution.
    """
    selected_agents = []
    skipped_agents = []

    for agent in agents:
        relevance_score = calculate_agent_relevance(
            agent.name,
            repository_analysis
        )

        if relevance_score >= 0.50:
            selected_agents.append({
                "agent": agent,
                "relevance_score": relevance_score
            })
        else:
            skipped_agents.append({
                "agent_name": agent.name,
                "relevance_score": relevance_score,
                "reason": "No relevant preprocessing signals detected"
            })

    return selected_agents, skipped_agents


def get_relevant_files_for_agent(agent_name, repository_analysis):
    """
    Return files containing signals relevant to the selected agent.
    """
    relevant_signal_names = AGENT_SIGNAL_MAPPING.get(agent_name, [])

    relevant_files = set()
    focused_regions = []

    file_signals = repository_analysis.get("file_signals", {})

    for file_path, signals in file_signals.items():
        file_is_relevant = False

        for signal_name in relevant_signal_names:
            if signal_name not in signals:
                continue

            file_is_relevant = True

            for match in signals[signal_name]:
                focused_regions.append({
                    "file": file_path,
                    "line": match["line"],
                    "evidence": match["content"]
                })

        if file_is_relevant:
            relevant_files.add(file_path)

    return {
        "files": sorted(relevant_files),
        "regions": focused_regions
    }