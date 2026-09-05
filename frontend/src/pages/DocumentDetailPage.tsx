import { useEffect, useState } from "react";
import axios from "axios";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Copy, Download, FileText, RefreshCw } from "lucide-react";
import { documentsApi } from "@/services/api";
import type { Document, DocumentPage, ExtractionResult } from "@/types";

const panel = "rounded-2xl border border-slate-200 bg-white shadow-sm";
const button = "inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50 focus-visible:outline-blue-600 disabled:opacity-40";
const label = (value: string) => value.replace(/_/g, " ");
const percent = (value: number | null | undefined) => value == null ? "Not scored" : `${Math.round(value * 100)}%`;
const languages: Record<string, string> = { hi: "Hindi", en: "English", mr: "Marathi", bn: "Bengali", gu: "Gujarati", ta: "Tamil", te: "Telugu" };
const activeStates = new Set(["queued", "processing", "preprocessing", "ocr_in_progress", "extraction_in_progress", "validation_in_progress"]);

export default function DocumentDetailPage() {
  const { id = "" } = useParams();
  const [doc, setDoc] = useState<Document | null>(null);
  const [pages, setPages] = useState<DocumentPage[]>([]);
  const [ext, setExt] = useState<ExtractionResult | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pageIndex, setPageIndex] = useState(0);
  const [view, setView] = useState<"readable" | "raw">("readable");
  const [fontSize, setFontSize] = useState(18);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      setLoading(true);
      try {
        const [documentResponse, pageResponse, extractionResponse] = await Promise.all([
          documentsApi.get(id), documentsApi.pages(id),
          documentsApi.extraction(id).catch((err: unknown) => {
            if (axios.isAxiosError(err) && err.response?.status === 404) return { data: null };
            throw err;
          }),
        ]);
        if (cancelled) return;
        setDoc(documentResponse.data);
        setPages([...pageResponse.data].sort((a, b) => a.page_number - b.page_number));
        setExt(extractionResponse.data);
        setError("");
        if (activeStates.has(documentResponse.data.status)) timer = setTimeout(() => void load(), 5000);
      } catch {
        if (!cancelled) setError("Could not refresh document results. Please try Refresh.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [id, refresh]);

  useEffect(() => { setPageIndex(0); setDoc(null); setPages([]); setExt(null); setNotice(""); }, [id]);
  const page = pages[pageIndex] ?? pages[0];
  const rawText = page?.raw_text ?? "";
  // Old records may contain one word per line. Offer an explicitly labelled
  // reflow without modifying stored OCR or implying a recovered table layout.
  const lines = rawText.split(/\r?\n/).filter(line => line.trim());
  const fragmented = lines.length > 12 && lines.filter(line => line.trim().split(/\s+/).length <= 2).length / lines.length > 0.7;
  const readableText = fragmented ? lines.map(line => line.trim()).join(" ") : rawText.replace(/\n{3,}/g, "\n\n");
  const issues = ext?.validation.issues ?? [];
  const passed = issues.filter(issue => issue.status === "passed");
  const attention = issues.filter(issue => issue.status !== "passed");
  const copy = async () => {
    try { await navigator.clipboard.writeText(view === "raw" ? rawText : readableText); setNotice("Page text copied."); }
    catch { setNotice("Copy unavailable. Select the text or use Download."); }
  };
  const download = () => {
    const text = pages.map(p => `Page ${p.page_number}\n${p.raw_text ?? ""}`).join("\n\n");
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `${doc?.original_filename ?? "document"}.ocr.txt`;
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return <div className="mx-auto max-w-7xl space-y-6 pb-8">
    <Link to="/documents" className="inline-flex items-center gap-2 text-sm text-blue-700 hover:underline"><ArrowLeft size={16}/> Documents</Link>
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0"><p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Document workspace</p><h1 className="break-words text-2xl font-bold text-slate-900">{doc?.original_filename ?? "Loading document…"}</h1><p className="mt-2 text-sm text-slate-500">Read the OCR output, check extracted details, and resolve validation issues.</p></div>
      <button className={button} disabled={loading} onClick={() => setRefresh(value => value + 1)}><RefreshCw size={16} className={loading ? "animate-spin" : ""}/> Refresh</button>
    </header>
    {error && <div role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</div>}
    {doc && <>
      <section aria-label="Document summary" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[["Status", label(doc.status)], ["Language", languages[doc.detected_language ?? ""] ?? doc.detected_language ?? "Pending"], ["Detected type", doc.document_type ? label(doc.document_type) : "Pending"], ["Pages", String(doc.page_count ?? pages.length)]].map(([name, value]) => <div key={name} className={`${panel} p-4`}><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{name}</p><p className={`mt-2 text-lg font-semibold capitalize ${name === "Status" && doc.status === "review_needed" ? "text-amber-700" : "text-slate-800"}`}>{value}</p></div>)}
      </section>
      {activeStates.has(doc.status) && <p role="status" className="rounded-xl bg-blue-50 p-4 text-sm text-blue-800">Processing is in progress. Results refresh automatically every 5 seconds.</p>}
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <StructuredResults ext={ext}/>
        <section className={`${panel} p-5 sm:p-6`}><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold text-slate-900">Validation checks</h2>{ext && <span className={`rounded-full px-3 py-1 text-xs font-medium ${attention.length ? "bg-amber-50 text-amber-800" : "bg-emerald-50 text-emerald-800"}`}>{attention.length ? `${attention.length} need attention` : label(ext.validation.status)}</span>}</div>
          <p className="mt-2 text-xs leading-relaxed text-slate-500">Checks assess extracted data completeness and consistency.</p>
          <div className="mt-5 space-y-3">{attention.map((issue, index) => <div key={index} className={`rounded-xl border p-4 ${issue.status === "failed" ? "border-red-100 bg-red-50 text-red-800" : "border-amber-100 bg-amber-50 text-amber-900"}`}><p className="text-xs font-semibold uppercase tracking-wide">{label(issue.status ?? "Needs review")}{issue.field_name ? ` · ${label(issue.field_name)}` : ""}</p><p className="mt-2 text-sm leading-relaxed">{issue.message}</p></div>)}</div>
          {!!passed.length && <details className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50 p-4"><summary className="cursor-pointer text-sm font-medium text-emerald-800">{passed.length} checks passed</summary><ul className="mt-3 space-y-2 text-sm text-emerald-800">{passed.map((issue, index) => <li key={index}>{issue.message}</li>)}</ul></details>}
          {!ext && <p className="py-6 text-sm text-slate-500">Validation results are not available yet.</p>}
          {(attention.length > 0 || doc.status === "review_needed") && <Link to={`/review/${id}`} className="mt-5 inline-flex rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700">Review and correct fields</Link>}
        </section>
      </div>
      <details className={panel}>
        <summary className="cursor-pointer p-5 font-semibold text-slate-900">View raw OCR text</summary>
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 p-5">
          <div className="flex items-center gap-3"><div className="rounded-xl bg-blue-50 p-3 text-blue-700"><FileText size={22}/></div><div><h2 id="ocr-heading" className="font-semibold text-slate-900">Recognized text</h2><p className="mt-1 text-xs text-slate-500">OCR confidence: {percent(page?.ocr_confidence)} · {rawText.trim() ? rawText.trim().split(/\s+/).length : 0} words on this page</p></div></div>
          <div className="flex flex-wrap gap-2"><button className={button} disabled={!rawText} onClick={() => void copy()}><Copy size={15}/> Copy page</button><button className={button} disabled={!pages.length} onClick={download}><Download size={15}/> Download text</button></div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 px-5 py-3">
          <div className="flex flex-wrap items-center gap-3"><label className="text-sm text-slate-600">Page <select aria-label="OCR page" className="ml-2 rounded-lg border border-slate-200 bg-white p-2" value={pages.length ? Math.min(pageIndex, pages.length - 1) : 0} onChange={event => { setPageIndex(Number(event.target.value)); setNotice(""); }} disabled={!pages.length}>{pages.length ? pages.map((p, index) => <option key={p.id} value={index}>{p.page_number} of {pages.length}</option>) : <option value={0}>—</option>}</select></label><div className="flex rounded-lg border border-slate-200 bg-white p-1">{(["readable", "raw"] as const).map(mode => <button key={mode} aria-pressed={view === mode} onClick={() => setView(mode)} className={`rounded-md px-3 py-1.5 text-sm ${view === mode ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{mode === "readable" ? "Readable" : "Raw text"}</button>)}</div></div>
          <label className="flex items-center gap-2 text-xs text-slate-600">Text size <input aria-label="OCR text size" type="range" min="14" max="26" step="2" value={fontSize} onChange={event => setFontSize(Number(event.target.value))}/></label>
        </div>
        {notice && <p role="status" className="px-5 pt-3 text-sm text-blue-700">{notice}</p>}
        {view === "readable" && fragmented && <p className="mx-5 mt-4 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">Reflowed for readability. This older OCR result contains word-by-word line breaks; original table layout cannot be recovered from text alone. Raw text is unchanged.</p>}
        <div className="max-h-[65vh] min-h-[240px] overflow-auto p-5 sm:p-8" tabIndex={0} aria-label="OCR text content">
          {rawText ? <div lang={page?.detected_language ?? doc.detected_language ?? undefined} className={view === "raw" ? "whitespace-pre font-mono text-slate-700" : "mx-auto max-w-4xl whitespace-pre-wrap break-words font-sans leading-loose text-slate-800"} style={{ fontSize, lineHeight: 1.95 }}>{view === "raw" ? rawText : readableText}</div> : <p className="py-16 text-center text-sm text-slate-500">{activeStates.has(doc.status) ? "Text will appear as processing completes." : "No OCR text is available for this document."}</p>}
        </div>
      </details>
    </>}
  </div>;
}

function StructuredResults({ ext }: { ext: ExtractionResult | null }) {
  const data = ext?.structured_data;
  const format = (value: unknown): string => {
    if (value == null || value === "") return "Not extracted";
    if (Array.isArray(value)) return value.length ? value.map(format).join("; ") : "Not extracted";
    if (typeof value === "object") return Object.entries(value).map(([key, item]) => `${label(key)}: ${format(item)}`).join(" · ");
    return String(value);
  };
  const fields = (values: Record<string, unknown>) => <dl className="grid gap-3 sm:grid-cols-2">{Object.entries(values).map(([key, value]) => {
    const score = ext?.confidence.fields[key]?.composite;
    return <div key={key} className="min-w-0 rounded-xl border border-slate-100 bg-slate-50 p-4"><dt className="text-xs font-medium capitalize text-slate-500">{label(key)}</dt><dd className="mt-2 whitespace-pre-wrap break-words text-base text-slate-900">{format(value)}</dd>{score != null && <dd className={`mt-2 text-xs ${score < 0.6 ? "text-amber-800" : "text-slate-500"}`}>{percent(score)}{score < 0.6 ? " · Verify against scan" : ""}</dd>}</div>;
  })}</dl>;
  const group = (title: string, values: Record<string, unknown>) => <section className="space-y-3"><h3 className="font-semibold text-slate-800">{title}</h3>{fields(values)}</section>;
  return <section className={`${panel} space-y-6 p-5 sm:p-6`} aria-label="Structured land record">
    <h2 className="font-semibold text-slate-900">Extracted land record</h2>
    {!!ext?.warnings?.length && <ul role="status" className="space-y-2 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">{ext.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}
    {ext && <p className="text-xs text-slate-500">Extraction confidence: {percent(ext.confidence.overall)}. Missing values are shown as Not extracted.</p>}
    {data ? <>
      <section className="space-y-3"><h3 className="font-semibold text-slate-800">Owner Details</h3>{data.owner_details.length ? data.owner_details.map((owner, index) => <div key={index}>{fields({ name: owner.name, father_or_husband_name: owner.father_or_husband_name, address: owner.address })}</div>) : <p className="text-sm text-slate-500">Not extracted</p>}</section>
      {group("Land Identification", { survey_number: data.survey_number, khasra_number: data.khasra_number, khata_number: data.khata_number, plot_number: data.plot_number })}
      {group("Location", { village: data.village, tehsil: data.tehsil, district: data.district, state: data.state })}
      {group("Area / Land Details", { area: data.area.value, area_unit: data.area.unit, land_classification: data.land_classification, ownership_type: data.ownership_type })}
      {group("Mutation / Registration Details", { mutation_details: data.mutation_details, ...data.registration_details })}
      {group("Additional Extracted Fields", Object.keys(data.additional_fields).length ? data.additional_fields : { additional_fields: null })}
    </> : ext ? fields(ext.mapped_record.fields) : <p className="text-sm text-slate-500">Structured results will appear when processing completes.</p>}
  </section>;
}
