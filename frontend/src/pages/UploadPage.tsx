import { useCallback, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { useNavigate } from "react-router-dom";
import { FileText, Info, UploadCloud, X } from "lucide-react";
import { documentsApi } from "@/services/api";
import { friendlyError } from "@/lib/errors";
import { cn, formatBytes } from "@/lib/utils";
import { ErrorMessage, Spinner, buttonPrimary, buttonSecondary, panel } from "@/components/ui/primitives";

const MAX_BYTES = 20 * 1024 * 1024;
const ACCEPTED = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/tiff": [".tif", ".tiff"],
  "image/webp": [".webp"],
};

const languageOptions = [
  { value: "auto", label: "Auto detect (recommended)" },
  { value: "hi", label: "Hindi — हिन्दी" },
  { value: "en", label: "English" },
  { value: "hi+en", label: "Hindi + English" },
];

type Stage = "idle" | "uploading" | "starting";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState("auto");
  const [error, setError] = useState("");
  const [stage, setStage] = useState<Stage>("idle");
  const navigate = useNavigate();
  const busy = stage !== "idle";

  const onDrop = useCallback((accepted: File[], rejected: FileRejection[]) => {
    if (rejected.length) {
      const code = rejected[0]?.errors[0]?.code;
      setError(
        code === "file-too-large"
          ? "This document is larger than the 20MB limit. Please upload a smaller scan."
          : code === "too-many-files"
            ? "Please upload one document at a time."
            : "Unsupported file type. Upload a PDF, PNG, JPG, TIFF or WEBP document.",
      );
      return;
    }
    if (accepted[0]) {
      setError("");
      setFile(accepted[0]);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxFiles: 1,
    maxSize: MAX_BYTES,
    multiple: false,
    noClick: true,
    noKeyboard: true,
  });

  const submit = async () => {
    if (!file) {
      setError("Select a document before starting processing.");
      return;
    }
    setError("");
    setStage("uploading");
    try {
      const { data } = await documentsApi.upload(file, language === "auto" ? undefined : language);
      setStage("starting");
      await documentsApi.process(data.id);
      navigate(`/documents/${data.id}`);
    } catch (caught) {
      setStage("idle");
      setError(friendlyError(caught, "The document could not be uploaded or queued for processing. Please try again."));
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Upload land document</h1>
        <p className="mt-1 text-sm text-slate-500">
          Scanned records, PDFs and photographs are supported. Hindi and English documents are recognised.
        </p>
      </header>

      <section className={cn(panel, "p-5 sm:p-6")}>
        <div
          {...getRootProps()}
          className={cn(
            "rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors duration-200",
            isDragActive ? "border-primary-500 bg-primary-50" : "border-slate-300 bg-slate-50",
          )}
        >
          <input {...getInputProps()} aria-label="Document file" />
          <UploadCloud size={30} className="mx-auto text-slate-400" aria-hidden />
          <p className="mt-3 text-sm font-medium text-slate-800">
            {isDragActive ? "Drop the document to attach it" : "Drag and drop a document here"}
          </p>
          <p className="mt-1 text-xs text-slate-500">PDF, PNG, JPG, TIFF or WEBP · maximum 20MB · one document at a time</p>
          <button type="button" onClick={open} disabled={busy} className={cn(buttonSecondary, "mt-4")}>
            Browse files
          </button>
        </div>

        {file && (
          <div className="mt-4 flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-3.5">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-50 text-primary-700" aria-hidden>
                <FileText size={18} />
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-800">{file.name}</p>
                <p className="text-xs text-slate-500">
                  {formatBytes(file.size)} · {file.type || file.name.split(".").pop()?.toUpperCase()}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button type="button" onClick={open} disabled={busy} className={cn(buttonSecondary, "px-3 py-1.5")}>
                Change
              </button>
              <button
                type="button"
                onClick={() => { setFile(null); setError(""); }}
                disabled={busy}
                aria-label="Remove selected document"
                className="rounded-lg p-2 text-slate-500 transition-colors duration-200 hover:bg-slate-100 hover:text-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600 disabled:opacity-50"
              >
                <X size={16} />
              </button>
            </div>
          </div>
        )}

        <div className="mt-5 max-w-sm">
          <label htmlFor="language" className="block text-sm font-medium text-slate-700">
            Document language
          </label>
          <select
            id="language"
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
            disabled={busy}
            className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm transition-colors duration-200 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100 disabled:opacity-50"
          >
            {languageOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <p className="mt-1.5 flex items-start gap-1.5 text-xs text-slate-500">
            <Info size={13} className="mt-0.5 shrink-0" aria-hidden />
            Auto detect handles mixed Hindi and English records; the detected language is reported with the result.
          </p>
        </div>

        {error && <ErrorMessage message={error} className="mt-5" />}

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => void submit()} disabled={!file || busy} className={buttonPrimary}>
            {busy && <Spinner />}
            {stage === "uploading" ? "Uploading document…" : stage === "starting" ? "Starting processing…" : "Process document"}
          </button>
          {busy && (
            <p role="status" className="text-sm text-slate-500">
              Please keep this page open until processing starts.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
