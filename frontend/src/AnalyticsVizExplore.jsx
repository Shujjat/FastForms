import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, formatApiError } from "./api";

/** @typedef {{ id: number, text: string, question_type: string, options?: string[] }} QMeta */
/** @typedef {{ id: number, submitted_at: string, answers: { question_id: number, value: unknown }[] }} VizRow */

function formatAnswerDisplay(value) {
  if (value == null) return "—";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/**
 * @param {string} qtype
 * @param {unknown} val
 * @returns {number | null}
 */
export function answerToNumeric(qtype, val) {
  if (val == null || val === "") return null;
  if (qtype === "rating") {
    const n = Number(val);
    return Number.isFinite(n) ? n : null;
  }
  if (qtype === "date") {
    const t = Date.parse(String(val));
    return Number.isFinite(t) ? t : null;
  }
  if (qtype === "short_text" || qtype === "paragraph") {
    const s = String(val).trim().replace(/,/g, "");
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/**
 * @param {unknown} val
 * @returns {string | null}
 */
export function answerToCategory(val) {
  if (val == null || val === "") return null;
  if (Array.isArray(val)) return val.length ? val.map(String).join(", ") : null;
  return String(val);
}

/**
 * Ordinary least squares y ~ a + b*x
 * @param {{ x: number, y: number }[]} pts
 */
export function linearRegression(pts) {
  const n = pts.length;
  if (n < 2) return null;
  let sx = 0;
  let sy = 0;
  let sxx = 0;
  let sxy = 0;
  let syy = 0;
  for (const p of pts) {
    sx += p.x;
    sy += p.y;
    sxx += p.x * p.x;
    sxy += p.x * p.y;
    syy += p.y * p.y;
  }
  const denom = n * sxx - sx * sx;
  if (Math.abs(denom) < 1e-12) return null;
  const slope = (n * sxy - sx * sy) / denom;
  const intercept = (sy - slope * sx) / n;
  const meanY = sy / n;
  let ssTot = 0;
  let ssRes = 0;
  for (const p of pts) {
    const pred = slope * p.x + intercept;
    ssTot += (p.y - meanY) ** 2;
    ssRes += (p.y - pred) ** 2;
  }
  const r2 = ssTot < 1e-12 ? 1 : Math.max(0, Math.min(1, 1 - ssRes / ssTot));
  return { slope, intercept, r2, n };
}

function rowLookup(row) {
  const m = {};
  for (const a of row.answers || []) m[a.question_id] = a.value;
  return m;
}

function isCategoricalType(qtype) {
  return qtype === "single_choice" || qtype === "dropdown" || qtype === "multi_choice";
}

const COLORS = ["#6366f1", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0ea5e9"];

/**
 * @param {{ formId: string }} props
 */
export function AnalyticsVizExplore({ formId }) {
  /** @type {[any, (v: any) => void]} */
  const [bundle, setBundle] = useState(null);
  const [loadErr, setLoadErr] = useState("");
  const [qX, setQX] = useState("");
  const [qY, setQY] = useState("");
  const [compareIds, setCompareIds] = useState(() => new Set());

  const load = useCallback(async () => {
    setLoadErr("");
    try {
      const { data } = await api.get(`/api/forms/${formId}/viz_matrix`);
      setBundle(data);
    } catch (e) {
      setBundle(null);
      setLoadErr(formatApiError(e));
    }
  }, [formId]);

  useEffect(() => {
    void load();
  }, [load]);

  const questions = bundle?.questions || [];
  const responses = bundle?.responses || [];

  const qById = useMemo(() => {
    const m = {};
    for (const q of questions) m[q.id] = q;
    return m;
  }, [questions]);

  const allQuestionIds = useMemo(() => questions.map((q) => String(q.id)), [questions]);

  const analysis = useMemo(() => {
    const ix = qX ? Number(qX) : null;
    const iy = qY ? Number(qY) : null;
    if (!ix || !iy || !questions.length) {
      return { kind: "none", message: "Select two fields below." };
    }
    const qA = qById[ix];
    const qB = qById[iy];
    if (!qA || !qB) return { kind: "none", message: "Invalid field selection." };

    const ptsNumeric = [];
    const catNumGroups = new Map();
    const catCatCells = new Map();
    const catA = isCategoricalType(qA.question_type);
    const catB = isCategoricalType(qB.question_type);

    for (const row of responses) {
      const lu = rowLookup(row);
      const va = lu[ix];
      const vb = lu[iy];

      const na = answerToNumeric(qA.question_type, va);
      const nb = answerToNumeric(qB.question_type, vb);
      const ca = answerToCategory(va);
      const cb = answerToCategory(vb);

      if (na != null && nb != null) {
        ptsNumeric.push({ x: na, y: nb, response_id: row.id });
      }

      if (catA && catB && ca != null && cb != null) {
        const key = `${ca}\0${cb}`;
        catCatCells.set(key, (catCatCells.get(key) || 0) + 1);
      } else {
        if (catA && ca != null && nb != null) {
          if (!catNumGroups.has(ca)) catNumGroups.set(ca, []);
          catNumGroups.get(ca).push(nb);
        }
        if (catB && cb != null && na != null) {
          if (!catNumGroups.has(cb)) catNumGroups.set(cb, []);
          catNumGroups.get(cb).push(na);
        }
      }
    }

    if (ptsNumeric.length >= 2) {
      const reg = linearRegression(ptsNumeric.map((p) => ({ x: p.x, y: p.y })));
      const xs = ptsNumeric.map((p) => p.x);
      const xMin = Math.min(...xs);
      const xMax = Math.max(...xs);
      const lineData =
        reg && xMax > xMin
          ? [
              { x: xMin, y: reg.slope * xMin + reg.intercept },
              { x: xMax, y: reg.slope * xMax + reg.intercept },
            ]
          : reg && xMax === xMin
            ? [
                { x: xMin - 1, y: reg.slope * (xMin - 1) + reg.intercept },
                { x: xMax + 1, y: reg.slope * (xMax + 1) + reg.intercept },
              ]
            : [];
      return {
        kind: "numeric_numeric",
        qA,
        qB,
        points: ptsNumeric,
        reg,
        lineData,
        xLabel: qA.text,
        yLabel: qB.text,
      };
    }

    if (catA && catB && catCatCells.size > 0) {
      const rowsLabels = new Set();
      const colsLabels = new Set();
      for (const key of catCatCells.keys()) {
        const [a, b] = key.split("\0");
        rowsLabels.add(a);
        colsLabels.add(b);
      }
      const rowArr = [...rowsLabels].sort();
      const colArr = [...colsLabels].sort();
      const maxC = Math.max(1, ...catCatCells.values());
      return {
        kind: "categorical_categorical",
        qA,
        qB,
        rowArr,
        colArr,
        cells: catCatCells,
        maxC,
      };
    }

    if (catNumGroups.size > 0) {
      const bars = [];
      for (const [label, arr] of catNumGroups) {
        const sum = arr.reduce((a, b) => a + b, 0);
        bars.push({
          category: label.length > 40 ? `${label.slice(0, 37)}…` : label,
          mean: arr.length ? sum / arr.length : 0,
          count: arr.length,
        });
      }
      bars.sort((a, b) => b.count - a.count);
      return {
        kind: "categorical_numeric",
        qA,
        qB,
        bars: bars.slice(0, 24),
      };
    }

    return {
      kind: "empty",
      message:
        "No overlapping pairs for these fields. Try two numeric fields (e.g. ratings), a choice field vs a rating, or two choice fields.",
    };
  }, [qX, qY, questions, qById, responses]);

  const toggleCompare = (id) => {
    setCompareIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 5) next.add(id);
      return next;
    });
  };

  const selectedRows = useMemo(
    () => responses.filter((r) => compareIds.has(r.id)),
    [responses, compareIds]
  );

  if (loadErr) {
    return <p className="msg msg-error">{loadErr}</p>;
  }
  if (!bundle) {
    return <p style={{ color: "#6b7280" }}>Loading visualization data…</p>;
  }

  return (
    <div className="stack" style={{ gap: 20 }}>
      <div className="card stack">
        <h3 style={{ margin: 0, fontSize: 16 }}>Field analysis &amp; regression</h3>
        <p style={{ margin: 0, fontSize: 13, color: "#6b7280" }}>
          Pick two questions. The tool detects numeric vs categorical types: scatter + ordinary least squares when both
          sides are numeric (ratings, numbers parsed from short text, or dates as timestamps); bar chart of means when one
          side is a choice; heatmap when both are choices.
        </p>
        <div className="row" style={{ flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12 }}>
            Horizontal (X) field
            <select value={qX} onChange={(e) => setQX(e.target.value)} style={{ minWidth: 220, padding: 8 }}>
              <option value="">—</option>
              {allQuestionIds.map((id) => (
                <option key={id} value={id}>
                  {qById[Number(id)]?.text?.slice(0, 60) || id} ({qById[Number(id)]?.question_type})
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12 }}>
            Vertical (Y) field
            <select value={qY} onChange={(e) => setQY(e.target.value)} style={{ minWidth: 220, padding: 8 }}>
              <option value="">—</option>
              {allQuestionIds.map((id) => (
                <option key={`y-${id}`} value={id}>
                  {qById[Number(id)]?.text?.slice(0, 60) || id} ({qById[Number(id)]?.question_type})
                </option>
              ))}
            </select>
          </label>
        </div>
        <p style={{ margin: 0, fontSize: 12, color: "#9ca3af" }}>
          Numeric-capable types: rating, date (as time), short text / paragraph if values look like numbers.
        </p>

        {analysis.kind === "numeric_numeric" && (
          <div style={{ marginTop: 8 }}>
            {analysis.reg && (
              <div className="card" style={{ background: "#f8fafc", marginBottom: 12 }}>
                <p style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Linear regression (OLS)</p>
                <p style={{ margin: "6px 0 0", fontSize: 13, fontFamily: "ui-monospace, monospace" }}>
                  y = {analysis.reg.slope.toFixed(6)} · x + {analysis.reg.intercept.toFixed(4)}
                </p>
                <p style={{ margin: "4px 0 0", fontSize: 13 }}>
                  R² = {analysis.reg.r2.toFixed(4)} · n = {analysis.reg.n}
                </p>
                <p style={{ margin: "8px 0 0", fontSize: 12, color: "#6b7280" }}>
                  Interpret with care: association only; causation is not implied. Dates use millisecond timestamps on the
                  axis.
                </p>
              </div>
            )}
            <div style={{ width: "100%", height: 360 }}>
              <ResponsiveContainer>
                <ScatterChart margin={{ top: 16, right: 16, bottom: 28, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    type="number"
                    dataKey="x"
                    name={analysis.xLabel}
                    label={{ value: analysis.xLabel, position: "bottom", offset: 0 }}
                  />
                  <YAxis
                    type="number"
                    dataKey="y"
                    name={analysis.yLabel}
                    width={56}
                    label={{ value: analysis.yLabel, angle: -90, position: "insideLeft" }}
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    formatter={(v, name) => [v, name]}
                    labelFormatter={() => "Response"}
                  />
                  <Legend />
                  {analysis.reg && analysis.lineData?.length === 2 && (
                    <ReferenceLine
                      stroke="#dc2626"
                      strokeWidth={2}
                      segment={[
                        { x: analysis.lineData[0].x, y: analysis.lineData[0].y },
                        { x: analysis.lineData[1].x, y: analysis.lineData[1].y },
                      ]}
                      ifOverflow="extendDomain"
                    />
                  )}
                  <Scatter name="Responses" data={analysis.points} fill={COLORS[0]} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {analysis.kind === "categorical_numeric" && (
          <div style={{ marginTop: 8 }}>
            <p style={{ fontSize: 13, color: "#4b5563", marginBottom: 8 }}>
              Mean of numeric answers grouped by category (top {analysis.bars.length} categories by count).
            </p>
            <div style={{ width: "100%", height: Math.min(480, 120 + analysis.bars.length * 28) }}>
              <ResponsiveContainer>
                <BarChart data={analysis.bars} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis type="category" dataKey="category" width={160} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v, k) => (k === "mean" ? [Number(v).toFixed(3), "Mean"] : [v, k])} />
                  <Bar dataKey="mean" name="Mean" fill={COLORS[1]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {analysis.kind === "categorical_categorical" && (
          <div style={{ marginTop: 8, overflowX: "auto" }}>
            <p style={{ fontSize: 13, color: "#4b5563" }}>Counts: {analysis.qA.text} (rows) vs {analysis.qB.text} (columns)</p>
            <table style={{ borderCollapse: "collapse", fontSize: 12, marginTop: 8 }}>
              <thead>
                <tr>
                  <th style={{ padding: 6, border: "1px solid #e5e7eb", background: "#f8fafc" }} />
                  {analysis.colArr.map((c) => (
                    <th
                      key={c}
                      style={{
                        padding: 6,
                        border: "1px solid #e5e7eb",
                        background: "#f8fafc",
                        maxWidth: 120,
                        whiteSpace: "normal",
                      }}
                      title={c}
                    >
                      {c.length > 20 ? `${c.slice(0, 18)}…` : c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {analysis.rowArr.map((r) => (
                  <tr key={r}>
                    <td
                      style={{
                        padding: 6,
                        border: "1px solid #e5e7eb",
                        fontWeight: 500,
                        maxWidth: 140,
                        whiteSpace: "normal",
                      }}
                      title={r}
                    >
                      {r.length > 24 ? `${r.slice(0, 22)}…` : r}
                    </td>
                    {analysis.colArr.map((c) => {
                      const n = analysis.cells.get(`${r}\0${c}`) || 0;
                      const intensity = analysis.maxC ? n / analysis.maxC : 0;
                      const bg = `rgba(99, 102, 241, ${0.12 + intensity * 0.75})`;
                      return (
                        <td
                          key={c}
                          style={{
                            padding: 6,
                            border: "1px solid #e5e7eb",
                            textAlign: "center",
                            background: bg,
                          }}
                        >
                          {n || "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {(analysis.kind === "empty" || analysis.kind === "none") && (
          <p style={{ color: "#6b7280", fontSize: 14 }}>{analysis.message}</p>
        )}
      </div>

      <div className="card stack">
        <h3 style={{ margin: 0, fontSize: 16 }}>Compare responses</h3>
        <p style={{ margin: 0, fontSize: 13, color: "#6b7280" }}>
          Select up to five submissions (checkboxes). Answers appear side by side for each question.
        </p>
        <div style={{ overflowX: "auto", maxHeight: 220, border: "1px solid #e5e7eb", borderRadius: 8 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ background: "#f8fafc" }}>
                <th style={{ padding: 6, textAlign: "left" }}>Pick</th>
                <th style={{ padding: 6, textAlign: "left" }}>ID</th>
                <th style={{ padding: 6, textAlign: "left" }}>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {responses.slice(0, 50).map((row) => (
                <tr key={row.id}>
                  <td style={{ padding: 6, borderBottom: "1px solid #f3f4f6" }}>
                    <input
                      type="checkbox"
                      checked={compareIds.has(row.id)}
                      disabled={!compareIds.has(row.id) && compareIds.size >= 5}
                      onChange={() => toggleCompare(row.id)}
                    />
                  </td>
                  <td style={{ padding: 6, borderBottom: "1px solid #f3f4f6" }}>{row.id}</td>
                  <td style={{ padding: 6, borderBottom: "1px solid #f3f4f6" }}>
                    {new Date(row.submitted_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {selectedRows.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", fontSize: 13, minWidth: 400 }}>
              <thead>
                <tr>
                  <th style={{ padding: 8, border: "1px solid #e5e7eb", background: "#f8fafc", textAlign: "left" }}>
                    Question
                  </th>
                  {selectedRows.map((r, i) => (
                    <th
                      key={r.id}
                      style={{
                        padding: 8,
                        border: "1px solid #e5e7eb",
                        background: "#eef2ff",
                        textAlign: "left",
                        minWidth: 140,
                      }}
                    >
                      #{r.id}
                      <span style={{ color: COLORS[i % COLORS.length], marginLeft: 6 }}>●</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {questions.map((q) => (
                  <tr key={q.id}>
                    <td
                      style={{
                        padding: 8,
                        border: "1px solid #e5e7eb",
                        verticalAlign: "top",
                        fontWeight: 500,
                        maxWidth: 220,
                      }}
                    >
                      {q.text}
                      <div style={{ fontSize: 11, color: "#9ca3af", fontWeight: 400 }}>{q.question_type}</div>
                    </td>
                    {selectedRows.map((r) => {
                      const lu = rowLookup(r);
                      return (
                        <td
                          key={`${r.id}-${q.id}`}
                          style={{
                            padding: 8,
                            border: "1px solid #e5e7eb",
                            verticalAlign: "top",
                            whiteSpace: "pre-wrap",
                          }}
                        >
                          {formatAnswerDisplay(lu[q.id])}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
