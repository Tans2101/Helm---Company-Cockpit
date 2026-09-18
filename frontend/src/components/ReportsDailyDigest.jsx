import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Upload } from "lucide-react";
import { api } from "@/lib/api";
import { fetchErrorMessage } from "@/hooks/useFetch";
import { GlassCard, SectionLabel, SkeletonCardList } from "@/components/kit";
import AiSummaryMeta from "@/components/AiSummaryMeta";

const REPORT_UPLOAD_TYPES = [
  "application/pdf",
  "image/png",
  "image/jpeg",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "text/csv",
  "application/csv",
];
const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;

function todayIso() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function shiftIso(iso, deltaDays) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() + deltaDays);
  const yy = dt.getFullYear();
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const dd = String(dt.getDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

function acceptFile(file) {
  if (!file) return false;
  if (REPORT_UPLOAD_TYPES.includes(file.type)) return true;
  const name = (file.name || "").toLowerCase();
  return name.endsWith(".xlsx") || name.endsWith(".csv")
    || name.endsWith(".pdf") || name.endsWith(".png")
    || name.endsWith(".jpg") || name.endsWith(".jpeg");
}

function mimeForFile(file) {
  if (file.type && REPORT_UPLOAD_TYPES.includes(file.type)) return file.type;
  const name = (file.name || "").toLowerCase();
  if (name.endsWith(".xlsx")) return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  if (name.endsWith(".csv")) return "text/csv";
  if (name.endsWith(".pdf")) return "application/pdf";
  if (name.endsWith(".png")) return "image/png";
  if (name.endsWith(".jpg") || name.endsWith(".jpeg")) return "image/jpeg";
  return file.type || "application/octet-stream";
}

/**
 * Running daily digest of uploaded report files (xlsx/csv/pdf/images).
 * Distinct from Weekly CEO Pack and auto_fin/team/exec cards.
 */
export default function ReportsDailyDigest({ canWrite }) {
  const [date, setDate] = useState(todayIso);
  const [digest, setDigest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef(null);

  const loadDigest = useCallback(async (day) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get("/reports/digest", { params: { date: day } });
      setDigest(data);
    } catch (e) {
      setDigest(null);
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDigest(date);
  }, [date, loadDigest]);

  const processFiles = async (fileList) => {
    const files = Array.from(fileList || []).filter(Boolean);
    if (!files.length) return;
    for (const file of files) {
      if (!acceptFile(file)) {
        toast.error(`${file.name}: use PDF, PNG, JPEG, XLSX, or CSV`);
        return;
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        toast.error(`${file.name}: must be 15MB or smaller`);
        return;
      }
    }
    setUploading(true);
    try {
      for (const file of files) {
        const fd = new FormData();
        const blob = new File([file], file.name, { type: mimeForFile(file) });
        fd.append("file", blob);
        fd.append("report_date", date);
        const { data: uploaded } = await api.post("/reports/documents/upload", fd, {
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 60000,
        });
        await api.post(`/reports/documents/${uploaded.document_id}/summarize`, null, {
          timeout: 120000,
        });
      }
      toast.success(files.length === 1 ? "Report added to digest" : `${files.length} reports added`);
      await loadDigest(date);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not add report");
      await loadDigest(date);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const isToday = date === todayIso();
  const reports = digest?.reports || [];
  const combined = (digest?.combined_digest || "").trim();

  return (
    <GlassCard className="p-6 mb-6 fade-up border-helm-line" data-testid="reports-daily-digest">
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-4">
        <div>
          <SectionLabel>Today&apos;s Reports</SectionLabel>
          <p className="text-sm text-helm-muted max-w-xl mt-1">
            Drop the day&apos;s Excel, CSV, or PDF reports here. Helm reads each file and folds the numbers into one short briefing you can open anytime.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value || todayIso())}
            data-testid="digest-date"
            className="rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-2.5 py-2 focus:outline-none focus:border-helm-gold/40"
          />
          {!isToday && (
            <button
              type="button"
              data-testid="digest-today-btn"
              onClick={() => setDate(todayIso())}
              className="text-xs text-helm-gold hover:text-helm-gold-hover font-medium"
            >
              Today
            </button>
          )}
          <button
            type="button"
            data-testid="digest-yesterday-btn"
            onClick={() => setDate(shiftIso(todayIso(), -1))}
            className="text-xs text-helm-muted hover:text-helm-fg font-medium"
          >
            Yesterday
          </button>
        </div>
      </div>

      {canWrite && (
        <div className="mb-5">
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.xlsx,.csv,application/pdf,image/png,image/jpeg,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
            multiple
            className="hidden"
            data-testid="digest-file-input"
            onChange={(e) => processFiles(e.target.files)}
          />
          <button
            type="button"
            data-testid="digest-upload-btn"
            disabled={uploading}
            onClick={() => inputRef.current?.click()}
            className="inline-flex items-center gap-2 rounded-md bg-helm-gold text-helm-navy text-sm font-medium px-4 py-2.5 hover:bg-helm-gold-hover disabled:opacity-60"
          >
            <Upload className="w-4 h-4" />
            {uploading ? "Reading reports…" : "Add report files"}
          </button>
          <p className="text-[11px] text-helm-muted mt-2">PDF, PNG, JPEG, XLSX, or CSV. Multiple files at once are fine.</p>
        </div>
      )}

      {loading && !digest ? (
        <SkeletonCardList count={2} />
      ) : error && !digest ? (
        <p className="text-sm text-helm-muted">
          {fetchErrorMessage(error, "Could not load this day&apos;s reports.")}{" "}
          <button type="button" className="text-helm-gold hover:underline" onClick={() => loadDigest(date)}>Retry</button>
        </p>
      ) : reports.length === 0 ? (
        <p className="text-sm text-helm-muted leading-relaxed" data-testid="digest-empty">
          No reports for this day yet.
          {canWrite ? " Add the first file above and Helm will write a grounded summary from what is actually in it." : ""}
        </p>
      ) : (
        <>
          {combined ? (
            <div className="rounded-lg border border-helm-line bg-helm-fg/[0.02] p-4 mb-5" data-testid="digest-combined">
              <AiSummaryMeta
                asOf={digest?.data_as_of}
                detailHref="/app/reports"
                detailLabel="uploaded reports"
                className="mb-2"
              />
              <p className="text-[10px] font-mono uppercase tracking-wider text-helm-muted mb-2">Combined digest</p>
              <div className="text-sm text-helm-fg leading-relaxed whitespace-pre-wrap">{combined}</div>
            </div>
          ) : (
            <p className="text-sm text-helm-muted mb-5">
              {uploading || reports.some((r) => r.status === "uploaded")
                ? "Summaries are still running…"
                : "Individual reports are listed below. Combined digest will appear once at least one file is summarized."}
            </p>
          )}

          <SectionLabel className="mb-3">Files for {date}</SectionLabel>
          <ul className="space-y-3" data-testid="digest-file-list">
            {reports.map((r) => (
              <li
                key={r.id}
                className="rounded-lg border border-helm-line bg-helm-fg/[0.02] px-3 py-3"
                data-testid={`digest-file-${r.id}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm text-helm-fg font-medium truncate">{r.filename}</p>
                  <span className="text-[10px] font-mono uppercase text-helm-muted shrink-0">
                    {r.status === "summarized" ? "Ready" : r.status === "failed" ? "Failed" : "Pending"}
                  </span>
                </div>
                {r.summary && (
                  <p className={`text-sm mt-1.5 leading-relaxed ${r.unclear ? "text-helm-status-warning" : "text-helm-muted"}`}>
                    {r.summary}
                  </p>
                )}
                {r.key_figures?.length > 0 && (
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
                    {r.key_figures.map((f) => (
                      <span key={`${f.label}-${f.value}`} className="text-[11px] font-mono text-helm-muted">
                        <span className="text-helm-fg/80">{f.label}:</span> {f.value}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </GlassCard>
  );
}
