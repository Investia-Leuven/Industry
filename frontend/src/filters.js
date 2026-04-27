/** Client-side filters matching Streamlit apply_filters behaviour. */

const CAP_COL = 'Market Cap (M USD)';

export function marketCapRangeFromRows(rows, columns) {
  if (!rows?.length || !columns?.includes(CAP_COL)) return null;
  const nums = rows
    .map((r) => Number(r[CAP_COL]))
    .filter((n) => Number.isFinite(n));
  if (!nums.length) return null;
  const minV = Math.floor(Math.min(...nums)) - 1;
  const maxV = Math.ceil(Math.max(...nums)) + 1;
  return [minV, maxV];
}

export function applyClientFilters(rows, columns, capRange, topN, selectedRatings) {
  if (!rows?.length) return [];
  let out = rows.map((r) => ({ ...r }));
  if (columns.includes(CAP_COL) && capRange) {
    const [lo, hi] = capRange;
    out = out.filter((r) => {
      const v = Number(r[CAP_COL]);
      return Number.isFinite(v) && v >= lo && v <= hi;
    });
  }
  if (topN && columns.includes(CAP_COL)) {
    out = [...out].sort(
      (a, b) => (Number(b[CAP_COL]) || 0) - (Number(a[CAP_COL]) || 0)
    );
    out = out.slice(0, topN);
  }
  if (
    selectedRatings != null &&
    selectedRatings.length &&
    columns.includes('Rating')
  ) {
    out = out.filter((r) =>
      selectedRatings.includes(
        r['Rating'] == null || r['Rating'] === '' ? '' : String(r['Rating'])
      )
    );
  }
  return out;
}

/** Match Streamlit: all on or all off → no rating filter. */
export function ratingFilterArg(ratingSelection) {
  const keys = Object.keys(ratingSelection);
  if (!keys.length) return null;
  const selected = keys.filter((k) => ratingSelection[k]);
  if (selected.length === 0 || selected.length === keys.length) return null;
  return selected;
}
