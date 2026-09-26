export function buildAudioCsv(results) {
    const columns = ["filename", "synthetic_likelihood", "classification", "manipulation_type", "scoring_method", "error",
        "manipulation_label", "manipulation_status", "manipulation_basis"];
    const escape = (value, column) => {
        let text = String(value ?? "");
        if (column !== "synthetic_likelihood" && /^[\s]*[=+\-@]/.test(text)) text = "'" + text;
        return '"' + text.replaceAll('"', '""') + '"';
    };
    return [columns.join(","), ...results.map((result) => {
        const row = {
            ...result,
            manipulation_label: result.manipulation_assessment?.label,
            manipulation_status: result.manipulation_assessment?.status,
            manipulation_basis: result.manipulation_assessment?.basis,
        };
        return columns.map((column) => escape(row[column], column)).join(",");
    })].join("\r\n") + "\r\n";
}
