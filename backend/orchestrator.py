"""
Argus staged security-analysis orchestrator.

Pipeline:

1. Collect source files.
2. Preprocess the repository.
3. Run deterministic security rules.
4. Select only relevant AI agents.
5. Send each agent only focused source files.
6. Run selected agents concurrently.
7. Merge and deduplicate findings.
8. Return findings, routing information, and performance metrics.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import threading
import time

from repository import collect_source_code

from preprocessor import preprocess_repository

from routing import (
    select_relevant_agents,
    get_relevant_files_for_agent
)

from rules import run_rule_based_scans

from findings import deduplicate_findings

from agents import ALL_AGENTS


def agent_progress_message(agent_name):
    """
    Turn an agent name into the live status shown while it runs.
    """

    labels = {
        "SQL Injection Agent": "Checking for SQL injection",
        "Cross-Site Scripting Agent": "Checking for cross-site scripting",
        "Hardcoded Secrets Agent": "Checking for hardcoded secrets",
        "Binary Exploitation Agent": "Checking for binary exploitation",
        "Reverse Engineering Agent": "Checking for reverse-engineering issues",
    }

    return labels.get(
        agent_name,
        f"Checking {agent_name}"
    )


class SecurityOrchestrator:
    """
    Coordinates deterministic rules and specialized AI agents.
    """

    def __init__(self):
        self.agents = [
            agent_class()
            for agent_class in ALL_AGENTS
        ]

    def build_focused_source_files(
        self,
        all_source_files,
        selected_agent,
        repository_analysis
    ):
        """
        Select only files relevant to a specific agent.

        For example:
        - SQL Injection Agent receives database-related files.
        - XSS Agent receives frontend/template-related files.
        - Secrets Agent receives files containing secret-like signals.

        This prevents every agent from analyzing the entire repository.
        """

        routing_result = get_relevant_files_for_agent(
            selected_agent.name,
            repository_analysis
        )

        relevant_file_paths = set(
            routing_result.get("files", [])
        )

        focused_source_files = []

        for source_file in all_source_files:
            file_path = source_file["file"]

            if file_path in relevant_file_paths:
                focused_source_files.append(source_file)

        return focused_source_files

    def run_one_agent(
        self,
        agent,
        all_source_files,
        repository_analysis,
        on_start=None
    ):
        """
        Run one selected agent using focused source files.
        """

        if on_start is not None:
            on_start(agent)

        focused_source_files = (
            self.build_focused_source_files(
                all_source_files,
                agent,
                repository_analysis
            )
        )

        if not focused_source_files:
            print(
                f"{agent.name}: no focused files found. Skipping."
            )

            return {
                "agent_name": agent.name,
                "findings": [],
                "elapsed_seconds": 0.0,
                "files_analyzed": [],
                "status": "skipped",
                "reason": "No focused source files found"
            }

        print(
            f"{agent.name}: analyzing "
            f"{len(focused_source_files)} focused file(s)."
        )

        start_time = time.perf_counter()

        try:
            agent_result = agent.analyze(
                focused_source_files
            )

            elapsed_seconds = (
                time.perf_counter() - start_time
            )

            # Your current agent implementation returns:
            # findings, elapsed_seconds
            #
            # This supports that format while also measuring time
            # at the orchestrator level.

            if (
                isinstance(agent_result, tuple)
                and len(agent_result) == 2
            ):
                findings, agent_reported_time = agent_result

                # Prefer the agent's reported time when available.
                if isinstance(agent_reported_time, (int, float)):
                    elapsed_seconds = agent_reported_time

            else:
                # Supports agents that return only a findings list.
                findings = agent_result

            print(
                f"{agent.name}: completed in "
                f"{elapsed_seconds:.2f} seconds."
            )

            return {
                "agent_name": agent.name,
                "findings": findings or [],
                "elapsed_seconds": round(
                    elapsed_seconds,
                    3
                ),
                "files_analyzed": [
                    source_file["file"]
                    for source_file in focused_source_files
                ],
                "status": "completed",
                "reason": None
            }

        except Exception as error:
            elapsed_seconds = (
                time.perf_counter() - start_time
            )

            print(
                f"{agent.name} failed after "
                f"{elapsed_seconds:.2f} seconds: {error}"
            )

            return {
                "agent_name": agent.name,
                "findings": [],
                "elapsed_seconds": round(
                    elapsed_seconds,
                    3
                ),
                "files_analyzed": [
                    source_file["file"]
                    for source_file in focused_source_files
                ],
                "status": "failed",
                "reason": str(error)
            }

    def build_quick_scan_result(
        self,
        source_files,
        repository_analysis,
        rule_findings
    ):
        """
        Return a result for quick scans.

        Quick scans use deterministic rules only and do not call Gemini.
        """

        skipped_agents = []

        for agent in self.agents:
            skipped_agents.append({
                "agent_name": agent.name,
                "relevance_score": 0.0,
                "reason": (
                    "Skipped because quick scans use "
                    "deterministic rules only"
                )
            })

        return {
            "findings": deduplicate_findings(
                rule_findings
            ),

            "repository_analysis": repository_analysis,

            "routing": {
                "selected_agents": [],
                "skipped_agents": skipped_agents
            },

            "agent_results": [],

            "files_collected": len(source_files),

            "rule_findings": len(rule_findings),

            "llm_findings": 0
        }

    def analyze_repository(
        self,
        repository_path,
        scan_profile="standard",
        on_progress=None
    ):
        """
        Analyze a repository using the selected scan profile.

        Supported profiles:
        - quick: deterministic rules only
        - standard: rules + relevant AI agents
        - deep: rules + relevant AI agents, with room for future verification
        """

        valid_profiles = {
            "quick",
            "standard",
            "deep"
        }

        if scan_profile not in valid_profiles:
            raise ValueError(
                "Invalid scan profile. "
                "Choose quick, standard, or deep."
            )

        includes_agents = scan_profile != "quick"

        def report(percent, ceiling, message):
            if on_progress is None:
                return

            bounded_percent = max(0, min(100, percent))
            bounded_ceiling = max(
                bounded_percent,
                min(100, ceiling)
            )
            on_progress(
                bounded_percent,
                bounded_ceiling,
                message
            )

        total_start_time = time.perf_counter()

        # ---------------------------------------------------------
        # Stage 1: Collect source files
        # ---------------------------------------------------------

        collection_start_time = time.perf_counter()

        if includes_agents:
            report(12, 20, "Collecting source files")
        else:
            report(16, 34, "Collecting source files")

        print("\nCollecting source files...")

        source_files = collect_source_code(
            repository_path
        )

        collection_elapsed = (
            time.perf_counter() - collection_start_time
        )

        print(
            f"Collected {len(source_files)} source file(s) "
            f"in {collection_elapsed:.2f} seconds."
        )

        # ---------------------------------------------------------
        # Stage 2: Preprocess repository
        # ---------------------------------------------------------

        preprocessing_start_time = time.perf_counter()

        file_count = len(source_files)
        signal_message = (
            f"Scanning {file_count} files for security signals"
        )

        if includes_agents:
            report(20, 28, signal_message)
        else:
            report(34, 52, signal_message)

        print("\nPreprocessing repository...")

        repository_analysis = preprocess_repository(
            source_files
        )

        preprocessing_elapsed = (
            time.perf_counter() - preprocessing_start_time
        )

        detected_signals = list(
            repository_analysis.get(
                "signals",
                {}
            ).keys()
        )

        print(
            "Detected signals:",
            detected_signals
        )

        print(
            f"Preprocessing completed in "
            f"{preprocessing_elapsed:.2f} seconds."
        )

        # ---------------------------------------------------------
        # Stage 3: Run deterministic rules
        # ---------------------------------------------------------

        rules_start_time = time.perf_counter()

        rules_message = (
            f"Running security rules on {file_count} files"
        )

        if includes_agents:
            report(28, 36, rules_message)
        else:
            report(52, 78, rules_message)

        print("\nRunning deterministic rules...")

        rule_findings = run_rule_based_scans(
            source_files
        )

        rules_elapsed = (
            time.perf_counter() - rules_start_time
        )

        print(
            f"Rules returned {len(rule_findings)} finding(s) "
            f"in {rules_elapsed:.2f} seconds."
        )

        # ---------------------------------------------------------
        # Quick scan ends here
        # ---------------------------------------------------------

        if scan_profile == "quick":
            report(78, 90, "Merging findings")

            result = self.build_quick_scan_result(
                source_files=source_files,
                repository_analysis=repository_analysis,
                rule_findings=rule_findings
            )

            total_elapsed = (
                time.perf_counter() - total_start_time
            )

            result["timing"] = {
                "collection_seconds": round(
                    collection_elapsed,
                    3
                ),
                "preprocessing_seconds": round(
                    preprocessing_elapsed,
                    3
                ),
                "rules_seconds": round(
                    rules_elapsed,
                    3
                ),
                "total_seconds": round(
                    total_elapsed,
                    3
                )
            }

            return result

        # ---------------------------------------------------------
        # Stage 4: Select relevant AI agents
        # ---------------------------------------------------------

        routing_start_time = time.perf_counter()

        report(36, 44, "Choosing which checks to run")

        selected_agents, skipped_agents = (
            select_relevant_agents(
                self.agents,
                repository_analysis
            )
        )

        routing_elapsed = (
            time.perf_counter() - routing_start_time
        )

        print("\nAgent routing results:")

        for selected_agent in selected_agents:
            agent = selected_agent["agent"]
            relevance_score = (
                selected_agent["relevance_score"]
            )

            print(
                f"RUN: {agent.name} "
                f"(relevance: {relevance_score:.2f})"
            )

        for skipped_agent in skipped_agents:
            print(
                f"SKIP: {skipped_agent['agent_name']} "
                f"({skipped_agent['reason']})"
            )

        # ---------------------------------------------------------
        # Stage 5: Run only selected agents concurrently
        # ---------------------------------------------------------

        llm_findings = []
        agent_results = []

        if selected_agents:
            print(
                f"\nRunning {len(selected_agents)} "
                f"selected agent(s) concurrently..."
            )

            agent_span_start = 44
            agent_span_end = 90
            agent_span = agent_span_end - agent_span_start
            total_agents = len(selected_agents)
            finished_agents = 0
            running_agents = []
            progress_lock = threading.Lock()

            def publish_agent_progress():
                percent = (
                    agent_span_start
                    + (finished_agents / total_agents) * agent_span
                )

                if running_agents:
                    upcoming = (
                        agent_span_start
                        + (
                            (finished_agents + 1) / total_agents
                        ) * agent_span
                    )
                    ceiling = max(percent + 1, upcoming - 0.8)

                    if len(running_agents) == 1:
                        message = agent_progress_message(
                            running_agents[0]
                        )
                    else:
                        details = [
                            agent_progress_message(name).removeprefix(
                                "Checking for "
                            )
                            for name in running_agents
                        ]
                        message = "Checking " + " and ".join(details)
                else:
                    ceiling = min(agent_span_end, percent + 1)
                    message = "Finishing security checks"

                report(percent, ceiling, message)

            def handle_agent_start(agent):
                with progress_lock:
                    running_agents.append(agent.name)
                    publish_agent_progress()

            def handle_agent_finish(agent_name):
                nonlocal finished_agents

                with progress_lock:
                    if agent_name in running_agents:
                        running_agents.remove(agent_name)

                    finished_agents += 1
                    publish_agent_progress()

            # Limit concurrency to reduce Gemini rate-limit spikes.
            max_concurrent = int(
                os.getenv("GEMINI_MAX_CONCURRENT")
                or os.getenv("GEMINI_MAX_CONCURRENT_AGENTS", "1")
            )

            max_workers = min(
                len(selected_agents),
                max(1, max_concurrent)
            )

            with ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:

                future_to_agent = {}

                for index, selected_agent in enumerate(selected_agents):
                    agent = selected_agent["agent"]

                    # Stagger submissions to avoid thundering herd.
                    if index > 0:
                        time.sleep(0.5)

                    future = executor.submit(
                        self.run_one_agent,
                        agent,
                        source_files,
                        repository_analysis,
                        handle_agent_start
                    )

                    future_to_agent[future] = agent

                for future in as_completed(
                    future_to_agent
                ):
                    agent = future_to_agent[future]

                    try:
                        result = future.result()

                        agent_results.append(
                            result
                        )

                        llm_findings.extend(
                            result.get(
                                "findings",
                                []
                            )
                        )

                    except Exception as error:
                        # This is a fallback in case run_one_agent
                        # itself unexpectedly raises an exception.
                        print(
                            f"{agent.name} failed unexpectedly: "
                            f"{error}"
                        )

                        agent_results.append({
                            "agent_name": agent.name,
                            "findings": [],
                            "elapsed_seconds": 0.0,
                            "files_analyzed": [],
                            "status": "failed",
                            "reason": str(error)
                        })

                    finally:
                        handle_agent_finish(agent.name)

        else:
            report(44, 90, "No extra security checks needed")

            print(
                "\nNo relevant AI agents selected. "
                "Skipping all LLM analysis."
            )

        # Append agents that were not selected so all registered agents display in results
        for skipped in skipped_agents:
            agent_results.append({
                "agent_name": skipped["agent_name"],
                "findings": [],
                "elapsed_seconds": 0.0,
                "files_analyzed": [],
                "status": "skipped",
                "reason": skipped.get("reason", "No relevant preprocessing signals detected")
            })

        # ---------------------------------------------------------
        # Stage 6: Merge and deduplicate findings
        # ---------------------------------------------------------

        report(90, 94, "Merging findings")

        all_findings = (
            rule_findings +
            llm_findings
        )

        final_findings = deduplicate_findings(
            all_findings
        )

        # ---------------------------------------------------------
        # Stage 7: Final timing and response
        # ---------------------------------------------------------

        total_elapsed = (
            time.perf_counter() - total_start_time
        )

        print(
            f"\nScan completed in "
            f"{total_elapsed:.2f} seconds."
        )

        return {
            "findings": final_findings,

            "repository_analysis": repository_analysis,

            "routing": {
                "selected_agents": [
                    item["agent"].name
                    for item in selected_agents
                ],
                "skipped_agents": skipped_agents
            },

            "agent_results": agent_results,

            "files_collected": len(source_files),

            "rule_findings": len(rule_findings),

            "llm_findings": len(llm_findings),

            "timing": {
                "collection_seconds": round(
                    collection_elapsed,
                    3
                ),
                "preprocessing_seconds": round(
                    preprocessing_elapsed,
                    3
                ),
                "rules_seconds": round(
                    rules_elapsed,
                    3
                ),
                "routing_seconds": round(
                    routing_elapsed,
                    3
                ),
                "agent_times": {
                    result["agent_name"]: result[
                        "elapsed_seconds"
                    ]
                    for result in agent_results
                },
                "total_seconds": round(
                    total_elapsed,
                    3
                )
            }
        }