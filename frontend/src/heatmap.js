export const DEFAULT_GRADIENT_META = {
  gradient_columns: ["Gross Margin (%)", "EBIT Margin (%)", "EBITDA Margin (%)"],
  inverse_gradient_columns: ["P/E", "EV/EBITDA", "EV/Sales", "P/FCF"],
};

export function buildHeatmapStats(rows, columns, meta) {
  if (!rows || !rows.length || !columns) return {};
  const stats = {};
  const { gradient_columns, inverse_gradient_columns } = meta || DEFAULT_GRADIENT_META;

  columns.forEach((col) => {
    if (gradient_columns.includes(col) || inverse_gradient_columns.includes(col)) {
      const vals = rows
        .map((r) => r[col])
        .filter((v) => typeof v === "number" && Number.isFinite(v));
      if (vals.length > 0) {
        stats[col] = {
          min: Math.min(...vals),
          max: Math.max(...vals),
          isInverse: inverse_gradient_columns.includes(col),
        };
      }
    }
  });
  return stats;
}

export function cellHeatmapStyle(col, value, stats) {
  // 1. Missing Value Check (Grey Style)
  if (value === null || value === undefined || value === "") {
    return {
      backgroundColor: "rgba(255, 255, 255, 0.05)",
      color: "rgba(0, 0, 0, 0.2)",
      fontStyle: "italic",
    };
  }

  const s = stats[col];
  if (!s || typeof value !== "number") return {};

  const { min, max, isInverse } = s;
  if (min === max) return {};

  let ratio = (value - min) / (max - min);
  if (isInverse) ratio = 1 - ratio;

  // Clip ratio
  ratio = Math.max(0, Math.min(1, ratio));

  // Vibrant Color Logic (Non-pastel)
  // Red: #ef4444, Yellow: #eab308, Green: #22c55e
  let r, g, b;
  if (ratio < 0.5) {
    // Red to Yellow
    const f = ratio * 2;
    r = 239;
    g = Math.round(68 + f * (179 - 68));
    b = Math.round(68 + f * (8 - 68));
  } else {
    // Yellow to Green
    const f = (ratio - 0.5) * 2;
    r = Math.round(234 - f * (234 - 34));
    g = Math.round(179 + f * (197 - 179));
    b = Math.round(8 + f * (94 - 8));
  }

  return {
    backgroundColor: `rgba(${r}, ${g}, ${b}, 0.35)`, // Higher opacity for "non-pastel"
    color: `rgb(${Math.max(0, r - 40)}, ${Math.max(0, g - 40)}, ${Math.max(0, b - 40)})`, // Darker text for readability
    fontWeight: "700",
  };
}
