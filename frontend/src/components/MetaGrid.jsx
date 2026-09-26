function MetaGrid({ scanData, repositoryUrl }) {
    return (
        <div className="meta-grid">
            <div className="meta-card">
                <span className="meta-label">Repository</span>
                <strong>{scanData?.repository_url || repositoryUrl}</strong>
            </div>
            <div className="meta-card">
                <span className="meta-label">Files analyzed</span>
                <strong>{scanData?.files_analyzed ?? 0}</strong>
            </div>
            <div className="meta-card">
                <span className="meta-label">Scan profile</span>
                <strong>{scanData?.scan_profile || "standard"}</strong>
            </div>
            <div className="meta-card">
                <span className="meta-label">Runtime</span>
                <strong>{scanData?.timing?.total_seconds ?? 0}s</strong>
            </div>
        </div>
    );
}

export default MetaGrid;
