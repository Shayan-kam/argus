const SCAN_PROFILES = [
    { id: "quick", label: "Quick", description: "Rules only" },
    { id: "standard", label: "Standard", description: "Rules + AI agents" },
    { id: "deep", label: "Deep", description: "Full analysis" }
];

function ScanForm({
    repositoryUrl,
    onRepositoryUrlChange,
    scanProfile,
    onScanProfileChange,
    githubToken,
    onGithubTokenChange,
    showTokenField,
    onToggleTokenField,
    loading,
    onSubmit
}) {
    return (
        <section className="scan-form">
            <div className="input-section">
                <input
                    type="text"
                    value={repositoryUrl}
                    onChange={(event) => onRepositoryUrlChange(event.target.value)}
                    placeholder="https://github.com/user/repository"
                    disabled={loading}
                    aria-label="GitHub repository URL"
                />

                <button type="button" onClick={onSubmit} disabled={loading}>
                    {loading ? "Analyzing..." : "Analyze Repository"}
                </button>
            </div>

            <div className="scan-options">
                <div className="option-group">
                    <span className="option-label">Scan profile</span>
                    <div className="profile-selector">
                        {SCAN_PROFILES.map((profile) => (
                            <button
                                key={profile.id}
                                type="button"
                                className={`profile-chip ${scanProfile === profile.id ? "active" : ""}`}
                                onClick={() => onScanProfileChange(profile.id)}
                                disabled={loading}
                                title={profile.description}
                            >
                                {profile.label}
                            </button>
                        ))}
                    </div>
                </div>

                <button
                    type="button"
                    className="link-button"
                    onClick={onToggleTokenField}
                    disabled={loading}
                >
                    {showTokenField ? "Hide token" : "Private repo? Add token"}
                </button>
            </div>

            {showTokenField && (
                <div className="token-field">
                    <input
                        type="password"
                        value={githubToken}
                        onChange={(event) => onGithubTokenChange(event.target.value)}
                        placeholder="GitHub personal access token (repo scope)"
                        disabled={loading}
                        aria-label="GitHub token for private repositories"
                    />
                    <p className="token-hint">
                        Required for private repositories. Token is used only for cloning
                        and is not stored.
                    </p>
                </div>
            )}
        </section>
    );
}

export default ScanForm;
