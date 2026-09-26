function AgentRoutingPanel({ routing }) {
    const selectedAgents = Array.isArray(routing?.selected_agents)
        ? routing.selected_agents.map((item) => {
            if (typeof item === "string") {
                return item;
            }

            return item?.agent?.name || item?.agent_name || "Agent";
        }).filter(Boolean)
        : [];

    const skippedAgents = Array.isArray(routing?.skipped_agents)
        ? routing.skipped_agents
        : [];

    return (
        <div className="insight-panel">
            <p className="section-eyebrow">ROUTING</p>
            <h3>Triggered agents</h3>

            {selectedAgents.length > 0 ? (
                <div className="chip-list">
                    {selectedAgents.map((agentName) => (
                        <span key={agentName} className="chip chip-success">
                            {agentName}
                        </span>
                    ))}
                </div>
            ) : (
                <p className="muted">No specialized agents were triggered.</p>
            )}

            {skippedAgents.length > 0 && (
                <div className="skip-panel">
                    <h4>Skipped ({skippedAgents.length})</h4>
                    <div className="chip-list">
                        {skippedAgents.slice(0, 6).map((item) => (
                            <span
                                key={item.agent_name}
                                className="chip chip-muted"
                                title={item.reason}
                            >
                                {item.agent_name}
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

export default AgentRoutingPanel;
