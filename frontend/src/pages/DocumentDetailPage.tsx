import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ClipboardCopy, Download, FileText, RefreshCw, UploadCloud } from "lucide-react";
import { documentsApi } from "@/services/api";
import { friendlyError } from "@/lib/errors";
import { cn } from "@/lib/utils";
import {
  Badge,
  ErrorMessage,
  SectionTitle,
  Spinner,
  buttonPrimary,
  buttonSecondary,
  panel,
} from "@/components/ui/primitives";
import type { Document, DocumentPage, ExtractionResult } from "@/types";

const NOT_DETECTED = "Not detected";
const label = (value: string) => value.replace(/_/g, " ");
const percent = (value: number | null | undefined) => (value == null ? "Not scored" : `${Math.round(value * 100)}%`);
const languages: Record<string, string> = { hi: "Hindi", en: "English", mr: "Marathi", bn: "Bengali", gu: "Gujarati", ta: "Tamil", te: "Telugu" };
const activeStates = new Set(["queued", "processing", "preprocessing", "ocr_in_progress", "extraction_in_progress", "validation_in_progress"]);
const LOW_CONFIDENCE = 0.6;

/** True when a value carries no useful extracted information. */
function isEmpty(value: unknown): boolean {
  if (value == null || value === "") return true;
  if (Array.isArray(value)) return value.every(isEmpty);
  if (typeof value === "object") return Object.values(value as Record<string, unknown>).every(isEmpty);
  return false;
}

function formatValue(value: unknown): string {
  if (isEmpty(value)) return NOT_DETECTED;
  if (Array.isArray(value)) return value.filter((item) => !isEmpty(item)).map(formatValue).join("; ");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => !isEmpty(item))
      .map(([key, item]) => `${label(key)}: ${formatValue(item)}`)
      .join(" · ");
  }
  return String(value);
}

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
          documentsApi.get(id),
          documentsApi.pages(id),
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
      } catch (caught) {
        if (!cancelled) setError(friendlyError(caught, "The document results could not be loaded. Use Refresh to try again."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [id, refresh]);

  useEffect(() => {
    setPageIndex(0);
    setDoc(null);
    setPages([]);
    setExt(null);
    setNotice("");
  }, [id]);

  const page = pages[pageIndex] ?? pages[0];
  const rawText = page?.raw_text ?? "";
  // Old records may contain one word per line. Offer an explicitly labelled
  // reflow without modifying stored OCR or implying a recovered table layout.
  const lines = rawText.split(/\r?\n/).filter((line) => line.trim());
  const fragmented = lines.length > 12 && lines.filter((line) => line.trim().split(/\s+/).length <= 2).length / lines.length > 0.7;
  const readableText = fragmented ? lines.map((line) => line.trim()).join(" ") : rawText.replace(/\n{3,}/g, "\n\n");

  const issues = useMemo(() => ext?.validation.issues ?? [], [ext]);
  const attention = issues.filter((issue) => issue.status !== "passed");
  const passed = issues.filter((issue) => issue.status === "passed");
  const needsReview = Boolean(ext?.validation.needs_review) || doc?.status === "review_needed" || attention.length > 0;
  const isProcessing = Boolean(doc && activeStates.has(doc.status));
  const hasFailed = doc?.status === "failed";

  const copyText = useCallback(async (text: string, done: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setNotice(done);
    } catch {
      setNotice("Copying is not available in this browser. Select the text manually or use Download.");
    }
  }, []);

  const downloadText = () => {
    const text = pages.map((p) => `Page ${p.page_number}\n${p.raw_text ?? ""}`).join("\n\n");
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${doc?.original_filename ?? "document"}.ocr.txt`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const structuredJson = () => JSON.stringify(ext?.structured_data ?? ext?.mapped_record.fields ?? {}, null, 2);

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-8">
      <Link to="/documents" className="inline-flex items-center gap-2 text-sm text-primary-700 hover:underline">
        <ArrowLeft size={16} aria-hidden /> Documents
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Document workspace</p>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="break-words text-2xl font-bold text-slate-900">{doc?.original_filename ?? "Loading document…"}</h1>
            {doc && needsReview && !isProcessing && <Badge tone="review">Needs review</Badge>}
            {hasFailed && <Badge tone="error">Processing failed</Badge>}
          </div>
          <p className="mt-2 text-sm text-slate-500">Review the extracted land record, then check the raw OCR text if anything needs verifying.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={buttonSecondary} disabled={loading} onClick={() => setRefresh((value) => value + 1)}>
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} aria-hidden /> Refresh
          </button>
          <Link to="/upload" className={buttonPrimary}>
            <UploadCloud size={16} aria-hidden /> Upload another document
          </Link>
        </div>
      </header>

      {error && <ErrorMessage message={error} />}

      {!doc && !error && (
        <div role="status" className={cn(panel, "flex items-center gap-3 p-6 text-sm text-slate-600")}>
          <Spinner size={18} className="text-primary-600" /> Loading document…
        </div>
      )}

      {doc && (
        <>
          <section aria-label="Document information" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["Status", label(doc.status)],
              ["Detected language", languages[doc.detected_language ?? ""] ?? doc.detected_language ?? NOT_DETECTED],
              ["Document type", doc.document_type ? label(doc.document_type) : NOT_DETECTED],
              ["Pages", String(doc.page_count ?? (pages.length || NOT_DETECTED))],
            ].map(([name, value]) => (
              <div key={name} className={cn(panel, "p-4")}>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{name}</p>
                <p className={cn("mt-2 text-lg font-semibold capitalize", name === "Status" && needsReview ? "text-amber-700" : "text-slate-800")}>{value}</p>
              </div>
            ))}
          </section>

          {isProcessing && (
            <div role="status" className={cn(panel, "flex items-start gap-3 border-primary-200 bg-primary-50 p-4 text-sm text-primary-900")}>
              <Spinner size={18} className="mt-0.5 text-primary-700" />
              <div>
                <p className="font-medium">Processing this document</p>
                <p className="mt-1 text-primary-800">
                  Preprocessing, OCR and extraction are running. Results appear here automatically as each stage completes.
                </p>
              </div>
            </div>
          )}

          {hasFailed && (
            <ErrorMessage message="This document could not be processed. The scan may be unreadable or in an unsupported format. Try uploading a clearer copy." />
          )}

          <div className="grid items-start gap-6 lg:grid-cols-2">
            <StructuredResults
              ext={ext}
              isProcessing={isProcessing}
              notice={notice}
              onCopy={() => void copyText(structuredJson(), "Structured data copied.")}
            />

            <section className={cn(panel, "p-5 sm:p-6")} aria-label="Validation checks">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="font-semibold text-slate-900">Validation checks</h2>
                {ext && (
                  <Badge tone={attention.length ? "review" : "success"}>
                    {attention.length ? `${attention.length} need attention` : label(ext.validation.status)}
                  </Badge>
                )}
              </div>
              <p className="mt-2 text-xs leading-relaxed text-slate-500">Checks assess extracted data completeness and consistency.</p>

              {attention.length > 0 && (
                <div className="mt-5 space-y-3">
                  {attention.map((issue, index) => (
                    <div
                      key={index}
                      className={cn(
                        "rounded-xl border p-4",
                        issue.status === "failed" ? "border-red-200 bg-red-50 text-red-800" : "border-amber-200 bg-amber-50 text-amber-900",
                      )}
                    >
                      <p className="text-xs font-semibold uppercase tracking-wide">
                        {label(issue.status ?? "Needs review")}
                        {issue.field_name ? ` · ${label(issue.field_name)}` : ""}
                      </p>
                      {issue.message && <p className="mt-2 text-sm leading-relaxed">{issue.message}</p>}
                    </div>
                  ))}
                </div>
              )}

              {passed.length > 0 && (
                <details className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                  <summary className="cursor-pointer text-sm font-medium text-emerald-800">{passed.length} checks passed</summary>
                  <ul className="mt-3 space-y-2 text-sm text-emerald-800">
                    {passed.map((issue, index) => (
                      <li key={index}>{issue.message}</li>
                    ))}
                  </ul>
                </details>
              )}

              {!ext && (
                <p className="py-6 text-sm text-slate-500">
                  {isProcessing ? "Validation runs after extraction completes." : "Validation results are not available for this document."}
                </p>
              )}

              {ext && needsReview && (
                <Link to={`/review/${id}`} className={cn(buttonPrimary, "mt-5")}>
                  Review and correct fields
                </Link>
              )}
            </section>
          </div>

          <details className={panel}>
            <summary className="cursor-pointer select-none p-5 font-semibold text-slate-900">View raw OCR text</summary>

            <div className="flex flex-wrap items-center justify-between gap-4 border-y border-slate-100 p-5">
              <div className="flex items-center gap-3">
                <span className="rounded-xl bg-primary-50 p-3 text-primary-700" aria-hidden>
                  <FileText size={20} />
                </span>
                <div>
                  <h2 className="font-semibold text-slate-900">Recognized text</h2>
                  <p className="mt-1 text-xs text-slate-500">
                    OCR confidence: {percent(page?.ocr_confidence)} · {rawText.trim() ? rawText.trim().split(/\s+/).length : 0} words on this page
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  className={buttonSecondary}
                  disabled={!rawText}
                  onClick={() => void copyText(view === "raw" ? rawText : readableText, "Raw text copied.")}
                >
                  <ClipboardCopy size={15} aria-hidden /> Copy raw text
                </button>
                <button className={buttonSecondary} disabled={!pages.length} onClick={downloadText}>
                  <Download size={15} aria-hidden /> Download text
                </button>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 px-5 py-3">
              <div className="flex flex-wrap items-center gap-3">
                <label className="text-sm text-slate-600">
                  Page
                  <select
                    aria-label="OCR page"
                    className="ml-2 rounded-lg border border-slate-300 bg-white p-2"
                    value={pages.length ? Math.min(pageIndex, pages.length - 1) : 0}
                    onChange={(event) => {
                      setPageIndex(Number(event.target.value));
                      setNotice("");
                    }}
                    disabled={!pages.length}
                  >
                    {pages.length ? (
                      pages.map((p, index) => (
                        <option key={p.id} value={index}>
                          {p.page_number} of {pages.length}
                        </option>
                      ))
                    ) : (
                      <option value={0}>—</option>
                    )}
                  </select>
                </label>
                <div className="flex rounded-lg border border-slate-300 bg-white p-1">
                  {(["readable", "raw"] as const).map((mode) => (
                    <button
                      key={mode}
                      aria-pressed={view === mode}
                      onClick={() => setView(mode)}
                      className={cn(
                        "rounded-md px-3 py-1.5 text-sm transition-colors duration-200",
                        view === mode ? "bg-primary-600 text-white" : "text-slate-600 hover:bg-slate-100",
                      )}
                    >
                      {mode === "readable" ? "Readable" : "Raw text"}
                    </button>
                  ))}
                </div>
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-600">
                Text size
                <input
                  aria-label="OCR text size"
                  type="range"
                  min="14"
                  max="26"
                  step="2"
                  value={fontSize}
                  onChange={(event) => setFontSize(Number(event.target.value))}
                />
              </label>
            </div>

            {notice && (
              <p role="status" className="px-5 pt-3 text-sm text-primary-700">
                {notice}
              </p>
            )}

            {view === "readable" && fragmented && (
              <p className="mx-5 mt-4 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">
                Reflowed for readability. This OCR result contains word-by-word line breaks; the original table layout cannot be recovered from text alone. Raw text is unchanged.
              </p>
            )}

            <div className="max-h-[65vh] min-h-[240px] overflow-auto p-5 sm:p-8" tabIndex={0} aria-label="OCR text content">
              {rawText ? (
                <div
                  lang={page?.detected_language ?? doc.detected_language ?? undefined}
                  className={
                    view === "raw"
                      ? "whitespace-pre-wrap break-words font-mono text-slate-700"
                      : "mx-auto max-w-4xl whitespace-pre-wrap break-words leading-loose text-slate-800"
                  }
                  style={{ fontSize, lineHeight: 1.95 }}
                >
                  {view === "raw" ? rawText : readableText}
                </div>
              ) : (
                <p className="py-16 text-center text-sm text-slate-500">
                  {isProcessing ? "Text will appear as processing completes." : "No OCR text is available for this document."}
                </p>
              )}
            </div>
          </details>
        </>
      )}
    </div>
  );
}

interface FieldRow {
  key: string;
  value: unknown;
  /** Field name used to look up an extraction confidence score, when it differs from the key. */
  scoreKey?: string;
}

function StructuredResults({
  ext,
  isProcessing,
  notice,
  onCopy,
}: {
  ext: ExtractionResult | null;
  isProcessing: boolean;
  notice: string;
  onCopy: () => void;
}) {
  const data = ext?.structured_data;
  const toRows = (values: Record<string, unknown>): FieldRow[] => Object.entries(values).map(([key, value]) => ({ key, value }));

  const Fields = ({ rows }: { rows: FieldRow[] }) => (
    <dl className="grid gap-3 sm:grid-cols-2">
      {rows.map(({ key, value, scoreKey }) => {
        const score = ext?.confidence.fields[scoreKey ?? key]?.composite;
        const missing = isEmpty(value);
        const low = score != null && score < LOW_CONFIDENCE;
        return (
          <div key={key} className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <dt className="text-xs font-medium capitalize text-slate-500">{label(key)}</dt>
            <dd className={cn("mt-2 whitespace-pre-wrap break-words text-base", missing ? "text-slate-400" : "text-slate-900")}>
              {formatValue(value)}
            </dd>
            {!missing && low && (
              <dd className="mt-2">
                <Badge tone="review">Needs review · {percent(score)}</Badge>
              </dd>
            )}
            {!missing && score != null && !low && <dd className="mt-2 text-xs text-slate-500">Confidence {percent(score)}</dd>}
          </div>
        );
      })}
    </dl>
  );

  /** Optional groups render only when at least one field carries extracted data. */
  const Group = ({ title, rows, always = false }: { title: string; rows: FieldRow[]; always?: boolean }) => {
    if (!always && !rows.some((row) => !isEmpty(row.value))) return null;
    return (
      <section className="space-y-3">
        <SectionTitle>{title}</SectionTitle>
        <Fields rows={rows} />
      </section>
    );
  };

  const owners = data?.owner_details.filter((owner) => !isEmpty(owner)) ?? [];

  return (
    <section className={cn(panel, "space-y-6 p-5 sm:p-6")} aria-label="Structured land record">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold text-slate-900">Extracted land record</h2>
        {ext && (
          <button className={buttonSecondary} onClick={onCopy}>
            <ClipboardCopy size={15} aria-hidden /> Copy structured data
          </button>
        )}
      </div>

      {notice && (
        <p role="status" className="text-sm text-primary-700">
          {notice}
        </p>
      )}

      {!!ext?.warnings?.length && (
        <ul role="status" className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          {ext.warnings.map((warning, index) => (
            <li key={index}>{warning}</li>
          ))}
        </ul>
      )}

      {ext && (
        <p className="text-xs text-slate-500">
          Extraction confidence: {percent(ext.confidence.overall)} · fields that could not be read are shown as {NOT_DETECTED}.
        </p>
      )}

      {data ? (
        <>
          <Group
            always
            title="Document Information"
            rows={[
              { key: "document_language", value: languages[data.document_language ?? ""] ?? data.document_language },
              { key: "document_type", value: data.document_type },
            ]}
          />

          <section className="space-y-3">
            <SectionTitle>Owner Details</SectionTitle>
            {owners.length ? (
              <div className="space-y-3">
                {owners.map((owner, index) => (
                  <Fields
                    key={index}
                    rows={[
                      { key: "owner_name", value: owner.name },
                      { key: "father_or_husband_name", value: owner.father_or_husband_name },
                      ...(isEmpty(owner.address) ? [] : [{ key: "address", value: owner.address }]),
                    ]}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-400">{NOT_DETECTED}</p>
            )}
          </section>

          <Group
            always
            title="Land Identification"
            rows={toRows({
              survey_number: data.survey_number,
              khasra_number: data.khasra_number,
              khata_number: data.khata_number,
              plot_number: data.plot_number,
            })}
          />

          <Group always title="Location" rows={toRows({ village: data.village, tehsil: data.tehsil, district: data.district, state: data.state })} />

          <Group
            always
            title="Area & Classification"
            rows={toRows({
              area: data.area.value,
              area_unit: data.area.unit,
              land_classification: data.land_classification,
              ownership_type: data.ownership_type,
            })}
          />

          <Group title="Mutation / Registration" rows={[{ key: "mutation_details", value: data.mutation_details }, ...toRows(data.registration_details)]} />

          <Group title="Additional Extracted Fields" rows={toRows(data.additional_fields)} />
        </>
      ) : ext ? (
        <Fields rows={toRows(ext.mapped_record.fields)} />
      ) : (
        <p className="text-sm text-slate-500">
          {isProcessing ? "Structured results will appear when processing completes." : "No structured land-record data is available for this document."}
        </p>
      )}
    </section>
  );
}
