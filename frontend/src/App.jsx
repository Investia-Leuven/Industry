import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import {
  Activity,
  AlertCircle,
  BarChart3,
  ChevronRight,
  Database,
  Download,
  FileText,
  Layers,
  Loader2,
  Search,
  SlidersHorizontal,
  Sparkles,
  Upload,
  X,
} from 'lucide-react';
import {
  DEFAULT_GRADIENT_META,
  buildHeatmapStats,
  cellHeatmapStyle,
} from './heatmap.js';
import {
  applyClientFilters,
  marketCapRangeFromRows,
  ratingFilterArg,
} from './filters.js';

const API_BASE =
  import.meta.env.VITE_API_BASE ||
  (typeof window !== 'undefined' && window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : '');

const DATA_METHODS = [
  {
    value: 'top_companies',
    label: 'Top companies',
    hint: 'Largest by market cap (Yahoo Finance).',
  },
  {
    value: 'top_growth_companies',
    label: 'Top growth',
    hint: 'Strongest revenue / earnings growth.',
  },
  {
    value: 'top_performing_companies',
    label: 'Top performers',
    hint: 'Best recent price performance.',
  },
];

function formatCell(col, value) {
  if (value == null || value === '') return '—';
  if (typeof value === 'number') {
    if (col.includes('%'))
      return `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return String(value);
}

function LoadingStrip({ show, label }) {
  if (!show) return null;
  return (
    <div className="shrink-0 border-b border-[var(--border)] bg-white/90">
      <div className="loading-bar" />
      <div className="flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold text-cyan-700">
        <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" aria-hidden />
        <span>{label}</span>
      </div>
    </div>
  );
}

export default function App() {
  const [sectors, setSectors] = useState({});
  const [selectedSector, setSelectedSector] = useState(null);
  const [industries, setIndustries] = useState({});
  const [selectedIndustries, setSelectedIndustries] = useState([]);
  const [dataMethod, setDataMethod] = useState('top_companies');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  const [capRange, setCapRange] = useState(null);
  const [capDraft, setCapDraft] = useState([0, 0]);
  const [top20Only, setTop20Only] = useState(false);
  const [ratingSelection, setRatingSelection] = useState({});

  const [loadingIndustries, setLoadingIndustries] = useState(false);
  const [tableBusy, setTableBusy] = useState({ active: false, message: '' });

  const [lastUploadedFileName, setLastUploadedFileName] = useState(null);
  const fileInputRef = useRef(null);
  const sectorBaseRef = useRef(null);
  const snapshotBeforeLastUploadRef = useRef(null);

  const topLoading = loadingIndustries || tableBusy.active;
  const topLabel = tableBusy.active
    ? tableBusy.message
    : loadingIndustries
      ? 'Loading industries from Yahoo Finance…'
      : '';

  const resetFiltersForPayload = useCallback((cols, rows) => {
    const mr = marketCapRangeFromRows(rows, cols);
    if (mr) {
      setCapRange(mr);
      setCapDraft(mr);
    } else {
      setCapRange(null);
      setCapDraft([0, 0]);
    }
    setTop20Only(false);
    if (cols.includes('Rating') && rows?.length) {
      const ratings = [
        ...new Set(
          rows.map((r) =>
            r['Rating'] == null || r['Rating'] === '' ? '' : String(r['Rating'])
          )
        ),
      ].sort();
      const init = {};
      ratings.forEach((r) => {
        init[r] = true;
      });
      setRatingSelection(init);
    } else {
      setRatingSelection({});
    }
  }, []);

  useEffect(() => {
    axios
      .get(`${API_BASE}/api/sectors`)
      .then((res) => setSectors(res.data))
      .catch(() => setError('Cannot reach API. Start the backend or check the URL.'));
  }, []);

  useEffect(() => {
    if (!selectedSector || !sectors[selectedSector]) {
      setIndustries({});
      setSelectedIndustries([]);
      setLoadingIndustries(false);
      return;
    }
    let cancelled = false;
    setLoadingIndustries(true);
    setError(null);
    axios
      .get(`${API_BASE}/api/industries/${sectors[selectedSector]}`)
      .then((res) => {
        if (cancelled) return;
        setIndustries(res.data || {});
        setSelectedIndustries([]);
      })
      .catch(() => {
        if (cancelled) return;
        setIndustries({});
        setError('Industries failed to load (often Yahoo rate limits). Retry shortly.');
      })
      .finally(() => {
        if (!cancelled) setLoadingIndustries(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedSector, sectors]);

  const industryNames = useMemo(() => Object.keys(industries), [industries]);

  useEffect(() => {
    if (!data?.data?.length || !data.columns) return;
    resetFiltersForPayload(data.columns, data.data);
  }, [data, resetFiltersForPayload]);

  const searchFiltered = useMemo(() => {
    if (!data?.data) return [];
    const q = searchTerm.trim().toLowerCase();
    if (!q) return data.data;
    return data.data.filter((row) =>
      Object.values(row).some((val) =>
        String(val ?? '')
          .toLowerCase()
          .includes(q)
      )
    );
  }, [data, searchTerm]);

  const ratingArg = useMemo(
    () => ratingFilterArg(ratingSelection),
    [ratingSelection]
  );

  const filteredData = useMemo(() => {
    if (!data?.columns) return [];
    const topN = top20Only ? 20 : null;
    return applyClientFilters(
      searchFiltered,
      data.columns,
      capRange,
      topN,
      ratingArg
    );
  }, [data?.columns, searchFiltered, capRange, top20Only, ratingArg]);

  const heatmapStats = useMemo(() => {
    const m =
      data?.meta?.gradient_columns && data?.meta?.inverse_gradient_columns
        ? data.meta
        : DEFAULT_GRADIENT_META;
    return buildHeatmapStats(filteredData, data?.columns, m);
  }, [filteredData, data?.columns, data?.meta]);

  const clearUploadAndMaybeRevert = () => {
    setLastUploadedFileName(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (snapshotBeforeLastUploadRef.current) {
      setData(snapshotBeforeLastUploadRef.current);
      snapshotBeforeLastUploadRef.current = null;
      return;
    }
    if (!sectorBaseRef.current?.length) {
      setData(null);
    }
  };

  const handleFetchData = async () => {
    if (!selectedIndustries.length) return;
    setTableBusy({ active: true, message: 'Fetching & enriching company data…' });
    setError(null);
    try {
      const keys = selectedIndustries.map((name) => industries[name]);
      const res = await axios.post(`${API_BASE}/api/fetch`, {
        industry_names: selectedIndustries,
        industry_keys: keys,
        data_method: dataMethod,
      });
      setData(res.data);
      sectorBaseRef.current = res.data.data?.length ? [...res.data.data] : null;
      setLastUploadedFileName(null);
      snapshotBeforeLastUploadRef.current = null;
    } catch (err) {
      setError(err.response?.data?.detail || 'Fetch failed. Try again in a minute.');
    } finally {
      setTableBusy({ active: false, message: '' });
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setTableBusy({ active: true, message: 'Reading Excel & fetching Yahoo metrics…' });
    setError(null);
    const merge = !!sectorBaseRef.current?.length;
    if (merge && data) {
      snapshotBeforeLastUploadRef.current = JSON.parse(JSON.stringify(data));
    } else {
      snapshotBeforeLastUploadRef.current = null;
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('merge', merge ? 'true' : 'false');
    if (merge) {
      formData.append('existing_json', JSON.stringify(sectorBaseRef.current));
    }
    try {
      const res = await axios.post(`${API_BASE}/api/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setData(res.data);
      setLastUploadedFileName(file.name);
      if (!merge) sectorBaseRef.current = null;
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          'Upload failed. One ticker per row, first column.'
      );
      snapshotBeforeLastUploadRef.current = null;
      setLastUploadedFileName(null);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
      setTableBusy({ active: false, message: '' });
    }
  };

  const handleExport = async (type = 'plain') => {
    if (!filteredData.length) return;
    setTableBusy({
      active: true,
      message: type === 'styled' ? 'Rendering formatted Excel…' : 'Building plain Excel…',
    });
    try {
      const endpoint =
        type === 'styled' ? '/api/export/styled' : '/api/export/plain';
      const res = await axios.post(
        `${API_BASE}${endpoint}`,
        { data: filteredData, sheet_name: 'Export' },
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download =
        type === 'styled'
          ? 'industry_companies_styled.xlsx'
          : 'industry_companies_plain.xlsx';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      setError('Export failed.');
    } finally {
      setTableBusy({ active: false, message: '' });
    }
  };

  const toggleIndustry = (name) => {
    setSelectedIndustries((prev) =>
      prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]
    );
  };

  const selectAllIndustries = () => {
    if (selectedIndustries.length === industryNames.length) {
      setSelectedIndustries([]);
    } else {
      setSelectedIndustries([...industryNames]);
    }
  };

  const methodHint = DATA_METHODS.find((m) => m.value === dataMethod)?.hint;

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-[var(--bg)] text-[var(--text)]">
      <LoadingStrip show={topLoading} label={topLabel} />

      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-[var(--border)] bg-white/75 px-4 py-3 backdrop-blur-md">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 to-violet-500 text-white shadow-lg shadow-cyan-500/25">
            <Sparkles className="h-5 w-5" strokeWidth={2} />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-base font-extrabold tracking-tight sm:text-lg">
              <span className="bg-gradient-to-r from-cyan-600 via-violet-600 to-cyan-600 bg-clip-text text-transparent">
                Investia
              </span>{' '}
              <span className="text-slate-800">Sector screening</span>
            </h1>
            <p className="hidden text-xs text-[var(--text-muted)] sm:block">
              Large table · filters · heatmaps · exports
            </p>
          </div>
        </div>
        <a
          href={`${API_BASE}/api/help.pdf`}
          download="investia_sector_help.pdf"
          className="btn-ghost inline-flex shrink-0 items-center gap-2 py-2 text-xs sm:text-sm"
        >
          <FileText className="h-4 w-4 text-cyan-600" />
          Help PDF
        </a>
      </header>

      <div className="flex min-h-0 flex-1 gap-3 p-3">
        <aside className="panel panel-tight flex w-[min(100%,260px)] shrink-0 flex-col gap-3 overflow-hidden p-4">
          <section className="shrink-0">
            <h2 className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-cyan-700">
              <Upload className="h-3 w-3" />
              Upload
            </h2>
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-cyan-200/80 bg-gradient-to-b from-cyan-50/80 to-violet-50/40 px-2 py-6 transition-all hover:border-cyan-400 hover:from-cyan-50">
              <Database className="mb-1 h-6 w-6 text-cyan-500/80" />
              <span className="text-center text-[11px] font-semibold text-slate-600">
                .xlsx · column A
              </span>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".xlsx"
                onChange={handleUpload}
                disabled={tableBusy.active}
              />
            </label>
            {lastUploadedFileName && (
              <div className="mt-2 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50/90 px-2.5 py-2">
                <span className="min-w-0 flex-1 truncate text-[11px] font-semibold text-emerald-900">
                  ✓ {lastUploadedFileName}
                </span>
                <button
                  type="button"
                  onClick={clearUploadAndMaybeRevert}
                  className="flex shrink-0 items-center gap-1 rounded-md border border-emerald-300 bg-white px-2 py-1 text-[10px] font-bold text-emerald-800 hover:bg-emerald-100"
                  title={
                    snapshotBeforeLastUploadRef.current
                      ? 'Remove upload and restore previous table'
                      : 'Clear upload and empty table'
                  }
                >
                  <X className="h-3 w-3" />
                  Remove
                </button>
              </div>
            )}
            <p className="mt-2 text-[10px] leading-snug text-[var(--text-faint)]">
              After a sector load, uploads merge into that snapshot. Use Remove to
              undo a merge or clear an upload-only sheet.
            </p>
          </section>

          <section className="scrollbar-thin flex min-h-0 flex-1 flex-col border-t border-[var(--border)] pt-3">
            <h2 className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-violet-700">
              <Layers className="h-3 w-3" />
              Sector
            </h2>
            <div className="scrollbar-thin mb-2 max-h-[28vh] space-y-1 overflow-y-auto pr-1">
              {Object.keys(sectors).map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => setSelectedSector(name)}
                  className={`flex w-full items-center justify-between rounded-lg border px-2.5 py-2 text-left text-xs font-semibold transition-all ${
                    selectedSector === name
                      ? 'border-cyan-300 bg-cyan-50 text-cyan-900 shadow-sm'
                      : 'border-transparent bg-white/60 text-slate-600 hover:bg-white hover:text-slate-900'
                  }`}
                >
                  <span className="line-clamp-2">{name}</span>
                  {selectedSector === name && (
                    <ChevronRight className="h-3.5 w-3.5 shrink-0 text-cyan-600" />
                  )}
                </button>
              ))}
            </div>

            {selectedSector && (
              <div className="scrollbar-thin flex min-h-0 flex-1 flex-col border-t border-[var(--border)] pt-2">
                <div className="mb-1 flex items-center justify-between gap-1">
                  <span className="text-[10px] font-bold uppercase text-slate-400">
                    Industries
                  </span>
                  <button
                    type="button"
                    onClick={selectAllIndustries}
                    disabled={loadingIndustries || !industryNames.length}
                    className="text-[10px] font-bold text-cyan-700 hover:underline disabled:opacity-40"
                  >
                    {selectedIndustries.length === industryNames.length
                      ? 'Clear'
                      : 'All'}
                  </button>
                </div>
                <div className="relative min-h-[80px] flex-1 overflow-y-auto pr-1">
                  {loadingIndustries && (
                    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 rounded-lg bg-white/85 backdrop-blur-sm">
                      <Loader2
                        className="h-8 w-8 animate-spin text-cyan-500"
                        aria-hidden
                      />
                      <span className="text-center text-[10px] font-semibold text-cyan-800">
                        Loading list…
                      </span>
                    </div>
                  )}
                  <div className="space-y-0.5">
                    {industryNames.map((name) => (
                      <label
                        key={name}
                        className="flex cursor-pointer items-center gap-2 rounded-md px-1.5 py-1.5 hover:bg-violet-50/80"
                      >
                        <input
                          type="checkbox"
                          disabled={loadingIndustries}
                          checked={selectedIndustries.includes(name)}
                          onChange={() => toggleIndustry(name)}
                          className="h-3.5 w-3.5 rounded border-slate-300 text-cyan-600 focus:ring-cyan-500"
                        />
                        <span className="line-clamp-2 text-[11px] leading-tight text-slate-700">
                          {name}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                <select
                  value={dataMethod}
                  onChange={(e) => setDataMethod(e.target.value)}
                  className="mt-2 w-full rounded-lg border border-[var(--border-strong)] bg-white/90 px-2 py-2 text-[11px] font-medium text-slate-800 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100"
                >
                  {DATA_METHODS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
                {methodHint && (
                  <p className="mt-1 line-clamp-2 text-[10px] text-[var(--text-faint)]">
                    {methodHint}
                  </p>
                )}

                <button
                  type="button"
                  onClick={handleFetchData}
                  disabled={
                    tableBusy.active || !selectedIndustries.length || loadingIndustries
                  }
                  className="btn-primary mt-2 flex w-full items-center justify-center gap-2 py-2.5 text-xs"
                >
                  {tableBusy.active ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Activity className="h-4 w-4" />
                  )}
                  Load data
                </button>
              </div>
            )}
          </section>
        </aside>

        <main className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-white/95 shadow-sm">
          {tableBusy.active && (
            <div
              className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-4 bg-white/88 px-6 backdrop-blur-md"
              role="status"
              aria-live="polite"
            >
              <div
                className="spinner-ring h-16 w-16 rounded-full"
                aria-hidden
              />
              <div className="flex items-center gap-2 text-center">
                <Sparkles className="h-5 w-5 shrink-0 text-violet-500" />
                <p className="max-w-sm text-sm font-bold text-slate-800">
                  {tableBusy.message}
                </p>
              </div>
              <p className="text-xs text-slate-500">
                Yahoo Finance can take a little while — please wait
              </p>
            </div>
          )}

          {error && (
            <div
              className="flex shrink-0 items-start gap-2 border-b border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-900"
              role="alert"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
              {error}
            </div>
          )}

          {data?.warnings?.length > 0 && (
            <div className="shrink-0 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-950">
              {data.warnings.map((w, i) => (
                <p key={i}>{w}</p>
              ))}
            </div>
          )}

          <div className="flex shrink-0 flex-col gap-2 border-b border-[var(--border)] bg-gradient-to-r from-cyan-50/50 to-violet-50/40 p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                placeholder="Search table…"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="input-search py-2 pl-9 text-sm"
              />
            </div>
            <div className="flex shrink-0 gap-2">
              <button
                type="button"
                onClick={() => handleExport('plain')}
                disabled={!filteredData.length || tableBusy.active}
                className="btn-ghost inline-flex items-center gap-1.5 py-2 text-xs"
              >
                <Download className="h-3.5 w-3.5" />
                Plain
              </button>
              <button
                type="button"
                onClick={() => handleExport('styled')}
                disabled={!filteredData.length || tableBusy.active}
                className="inline-flex items-center gap-1.5 rounded-xl border border-violet-200 bg-violet-50 px-3 py-2 text-xs font-bold text-violet-800 transition-colors hover:bg-violet-100 disabled:opacity-40"
              >
                <Download className="h-3.5 w-3.5" />
                Formatted
              </button>
            </div>
          </div>

          {data?.columns?.length > 0 && (
            <details
              open
              className="group shrink-0 border-b border-[var(--border)] bg-slate-50/90 px-3 py-2"
            >
              <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-bold text-slate-700 marker:hidden [&::-webkit-details-marker]:hidden">
                <SlidersHorizontal className="h-4 w-4 text-cyan-600" />
                Filters
              </summary>
              <div className="mt-3 grid gap-4 border-t border-slate-200/80 pt-3 sm:grid-cols-2 lg:grid-cols-3">
                {capRange && data.columns.includes('Market Cap (M USD)') && (
                  <div className="space-y-2">
                    <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
                      Market cap (M USD)
                    </p>
                    <div className="flex flex-wrap items-end gap-2">
                      <label className="flex flex-col text-[10px] text-slate-600">
                        Min
                        <input
                          type="number"
                          className="mt-0.5 w-28 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm font-medium text-slate-800"
                          value={capDraft[0]}
                          onChange={(e) => {
                            const v = Number(e.target.value);
                            setCapDraft((d) => {
                              const next = [v, d[1]];
                              setCapRange(next);
                              return next;
                            });
                          }}
                        />
                      </label>
                      <label className="flex flex-col text-[10px] text-slate-600">
                        Max
                        <input
                          type="number"
                          className="mt-0.5 w-28 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm font-medium text-slate-800"
                          value={capDraft[1]}
                          onChange={(e) => {
                            const v = Number(e.target.value);
                            setCapDraft((d) => {
                              const next = [d[0], v];
                              setCapRange(next);
                              return next;
                            });
                          }}
                        />
                      </label>
                    </div>
                  </div>
                )}
                <div className="flex items-end">
                  <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
                    <input
                      type="checkbox"
                      checked={top20Only}
                      onChange={(e) => setTop20Only(e.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-cyan-600"
                    />
                    Top 20 by market cap
                  </label>
                </div>
                {data.columns.includes('Rating') &&
                  Object.keys(ratingSelection).length > 0 && (
                    <div className="sm:col-span-2 lg:col-span-1">
                      <p className="mb-2 text-[10px] font-bold uppercase tracking-wide text-slate-500">
                        Ratings
                      </p>
                      <div className="flex flex-wrap gap-3">
                        {Object.keys(ratingSelection).map((r) => (
                          <label
                            key={r}
                            className="flex items-center gap-1.5 text-xs text-slate-700"
                          >
                            <input
                              type="checkbox"
                              checked={ratingSelection[r]}
                              onChange={(e) =>
                                setRatingSelection((prev) => ({
                                  ...prev,
                                  [r]: e.target.checked,
                                }))
                              }
                              className="h-3.5 w-3.5 rounded border-slate-300 text-cyan-600"
                            />
                            {r === '' ? '—' : r}
                          </label>
                        ))}
                      </div>
                    </div>
                  )}
              </div>
            </details>
          )}

          <p className="shrink-0 border-b border-[var(--border)] bg-slate-50/80 px-3 py-1.5 text-[10px] leading-snug text-slate-500">
            <span className="font-bold text-slate-700">Heatmap</span> (filtered rows,
            p5–p95): <span className="text-red-700">red</span> →{' '}
            <span className="text-amber-700">amber</span> →{' '}
            <span className="text-green-800">green</span> for margins &amp; EBITDA
            (higher better); inverse for P/E, EV, P/FCF (greener = cheaper / better).
          </p>

          <div className="scrollbar-thin min-h-0 flex-1 overflow-auto">
            {!data?.columns?.length ? (
              <div className="flex h-full min-h-[200px] flex-col items-center justify-center p-8 text-center">
                <BarChart3 className="mb-3 h-14 w-14 text-slate-200" />
                <p className="text-sm font-semibold text-slate-500">
                  No data yet — load a sector or upload tickers
                </p>
              </div>
            ) : (
              <table className="w-max min-w-full border-collapse text-left">
                <thead>
                  <tr className="sticky top-0 z-10 border-b border-slate-200 bg-gradient-to-r from-white via-cyan-50/90 to-violet-50/90 shadow-sm backdrop-blur-md">
                    {data.columns.map((col) => (
                      <th
                        key={col}
                        className="whitespace-nowrap px-3 py-2 text-left text-[11px] font-bold uppercase tracking-wide text-slate-500"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="text-[15px] leading-snug text-slate-800">
                  {filteredData.map((row, idx) => (
                    <tr
                      key={idx}
                      className="border-b border-slate-100 transition-colors hover:bg-slate-50/90"
                    >
                      {data.columns.map((col) => {
                        const style = cellHeatmapStyle(
                          col,
                          row[col],
                          heatmapStats
                        );
                        const isNumeric =
                          typeof row[col] === 'number' ||
                          (row[col] != null &&
                            row[col] !== '' &&
                            Number.isFinite(Number(row[col])));
                        return (
                          <td
                            key={col}
                            className={`whitespace-nowrap px-3 py-1.5 ${
                              Object.keys(style).length
                                ? ''
                                : 'text-slate-700'
                            } ${isNumeric ? 'td-mono' : ''}`}
                            style={style}
                          >
                            {formatCell(col, row[col])}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <footer className="shrink-0 border-t border-[var(--border)] bg-slate-50/90 px-3 py-1.5 text-center text-[10px] text-slate-500">
            Investia bèta · Vince Coppens
          </footer>
        </main>
      </div>
    </div>
  );
}
