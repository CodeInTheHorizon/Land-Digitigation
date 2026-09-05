// =============================================================================
// TypeScript interfaces matching backend Pydantic schemas
// =============================================================================

/** Auth */
export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

/** Documents */
export interface Document {
  id: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  status: DocumentStatus;
  document_type: string | null;
  detected_language: string | null;
  page_count: number | null;
  created_at: string;
  updated_at: string;
}

export type DocumentStatus =
  | "processing"
  | "processed"
  | "uploaded"
  | "queued"
  | "preprocessing"
  | "ocr_in_progress"
  | "extraction_in_progress"
  | "validation_in_progress"
  | "review_needed"
  | "completed"
  | "failed";

/** Land Records */
export interface LandRecord {
  id: string;
  document_id: string;
  village: string | null;
  tehsil: string | null;
  district: string | null;
  state: string | null;
  survey_number: string | null;
  khasra_number: string | null;
  khata_number: string | null;
  plot_number: string | null;
  area: number | null;
  area_unit: string | null;
  land_classification: string | null;
  document_type: string | null;
  document_number: string | null;
  owners?: Ownership[];
  mutations?: Mutation[];
  registrations?: Registration[];
  overall_confidence: number | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Ownership { id: string; landowner_id: string; landowner_name?: string | null; ownership_type: string | null; ownership_percentage: number | null; is_current: boolean; }
export interface Mutation { id: string; mutation_number: string | null; mutation_type: string | null; mutation_date: string | null; from_owner: string | null; to_owner: string | null; }
export interface Registration { id: string; registration_number: string | null; registration_date: string | null; registration_office: string | null; transaction_type: string | null; }
export interface DocumentPage { id: string; page_number: number; raw_text: string | null; detected_language: string | null; ocr_confidence: number | null; }
export interface ExtractionResult { structured_data?: StructuredLandRecord; warnings?: string[]; raw_text?: string; detected_language?: string | null; success?: boolean; document_id: string; classification: { category: string; confidence: number }; mapped_record: { fields: Record<string, unknown>; persons: Array<{name: string; confidence?: number}>; field_count: number }; confidence: { overall: number; fields: Record<string, { composite: number; confidence?: number }> }; validation: { status: string; issues: Array<{message?: string; status?: string; severity?: string; field_name?: string}>; needs_review: boolean }; }

/** Dashboard */
export interface DashboardStats {
  total_documents: number;
  total_land_records: number;
  documents_processed: number;
  documents_pending: number;
  documents_failed: number;
  pending_reviews: number;
  average_confidence: number | null;
  documents_by_type: Record<string, number>;
  documents_by_language: Record<string, number>;
}

/** Health */
export interface HealthResponse {
  status: string;
  version: string;
  database: string;
}

/** Pagination */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

/** Common */
export interface ErrorResponse {
  detail: string;
}

export interface StructuredLandRecord {
  document_language: string | null;
  document_type: string | null;
  owner_details: Array<{ name: string | null; father_or_husband_name: string | null; address: string | null }>;
  survey_number: string | null;
  khasra_number: string | null;
  khata_number: string | null;
  plot_number: string | null;
  village: string | null;
  tehsil: string | null;
  district: string | null;
  state: string | null;
  area: { value: number | null; unit: string | null };
  land_classification: string | null;
  ownership_type: string | null;
  mutation_details: Array<Record<string, unknown>>;
  registration_details: Record<string, unknown>;
  additional_fields: Record<string, unknown>;
  raw_text: string;
}
