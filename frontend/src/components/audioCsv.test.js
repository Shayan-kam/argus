import { test } from "node:test";
import assert from "node:assert/strict";
import { buildAudioCsv } from "./audioCsv.js";

test("CSV preserves zero scores and leaves failed predictions blank", () => {
    const csv = buildAudioCsv([
        { filename: "real.wav", synthetic_likelihood: 0, classification: "real", scoring_method: "experimental_baseline" },
        { filename: "bad.wav", synthetic_likelihood: null, classification: "error", error: "Could not decode." },
    ]);
    assert.ok(csv.includes('"real.wav","0","real"'));
    assert.ok(csv.includes('"bad.wav","","error","","","Could not decode."'));
    assert.equal(csv.split("\r\n").length, 4);
});

test("CSV quotes names and neutralizes spreadsheet formulas", () => {
    const csv = buildAudioCsv([{ filename: '=SUM(1,2)"\n.wav', manipulation_type: "+type", error: "@error" }]);
    assert.ok(csv.includes('"' + "'=SUM(1,2)" + '""\n.wav"'));
    assert.ok(csv.includes('"' + "'+type" + '"'));
    assert.ok(csv.includes('"' + "'@error" + '"'));
});

test("CSV carries the manipulation assessment and distinguishes known source from prediction", () => {
    const csv = buildAudioCsv([{
        filename: "demo.wav", synthetic_likelihood: 59.7, classification: "synthetic",
        manipulation_type: "generated_test_audio", scoring_method: "experimental_baseline",
        manipulation_assessment: { label: "Generated test audio", status: "known_source", basis: "Known demo" },
    }]);
    assert.ok(csv.includes("manipulation_label,manipulation_status,manipulation_basis"));
    assert.ok(csv.includes('"Generated test audio","known_source","Known demo"'));
});
