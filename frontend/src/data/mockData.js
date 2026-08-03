// ─── Pipeline Steps ───────────────────────────────────────
export const pipelineSteps = [
  { icon: '📥', label: 'Ingestion', time: '0.1s' },
  { icon: '🛡️', label: 'Quality Check', time: '0.2s' },
  { icon: '⚙️', label: 'Pre Processing', time: '0.3s' },
  { icon: '🏷️', label: 'Classification', time: '0.2s' },
  { icon: '🤖', label: 'Extraction', time: '0.8s' },
  { icon: '✅', label: 'Validation', time: '0.4s' },
  { icon: '🔄', label: 'Human Review', time: '0.2s' },
  { icon: '📤', label: 'Output', time: '0.1s' },
];

// ─── Agents ───────────────────────────────────────────────
export const agents = [
  {
    icon: '🎭', color: 'rgba(99,102,241,0.25)', border: '#6366f1',
    name: 'Orchestrator', role: 'Master Controller', status: 'running',
    desc: 'Manages the full pipeline, assigns sub-tasks to specialized agents, handles exceptions and retries.',
    docs: 1240, accuracy: '99.1%', latency: '2.1s',
  },
  {
    icon: '📥', color: 'rgba(6,182,212,0.2)', border: '#06b6d4',
    name: 'Intake Agent', role: 'Document Ingestion', status: 'done',
    desc: 'Validates file formats, extracts metadata, deduplicates, and queues documents for processing.',
    docs: 1243, accuracy: '100%', latency: '0.1s',
  },
  {
    icon: '🏷️', color: 'rgba(139,92,246,0.2)', border: '#8b5cf6',
    name: 'Classifier', role: 'Document Type Detection', status: 'done',
    desc: 'Uses a fine-tuned vision model to classify documents across 40+ categories with 99.3% accuracy.',
    docs: 1243, accuracy: '99.3%', latency: '0.2s',
  },
  {
    icon: '🔍', color: 'rgba(16,185,129,0.2)', border: '#10b981',
    name: 'Extractor', role: 'Field & Entity Extraction', status: 'running',
    desc: 'Employs multi-pass LLM extraction to identify and capture structured fields, tables, and entities.',
    docs: 1198, accuracy: '98.4%', latency: '0.8s',
  },
  {
    icon: '✅', color: 'rgba(245,158,11,0.2)', border: '#f59e0b',
    name: 'Validator', role: 'Quality Assurance', status: 'running',
    desc: 'Cross-validates extracted data using business rules, math checks, and external reference lookups.',
    docs: 1195, accuracy: '99.6%', latency: '0.4s',
  },
  {
    icon: '🔄', color: 'rgba(239,68,68,0.2)', border: '#ef4444',
    name: 'Enricher', role: 'Data Augmentation', status: 'idle',
    desc: 'Augments extracted data with external sources — ERP lookups, geocoding, entity resolution.',
    docs: 1180, accuracy: '97.2%', latency: '0.3s',
  },
];

// ─── Log Messages ─────────────────────────────────────────
export const logMessages = [
  ['🎭', 'log-accent', 'Orchestrator', 'New document ingested: invoice_Q2_2024.pdf (2.1 MB)'],
  ['📥', 'log-cyan', 'Intake', 'File validated — PDF/A, 2 pages, no corruption detected'],
  ['📥', 'log-cyan', 'Intake', 'SHA-256 hash computed — no duplicate found in index'],
  ['🎭', 'log-accent', 'Orchestrator', 'Routing to Classifier agent...'],
  ['🏷️', 'log-success', 'Classifier', 'Document type: INVOICE (confidence: 99.3%)'],
  ['🏷️', 'log-success', 'Classifier', 'Sub-type: B2B / Accounts Payable invoice detected'],
  ['🎭', 'log-accent', 'Orchestrator', 'Activating Extractor with INVOICE schema v3.2'],
  ['🔍', 'log-success', 'Extractor', 'OCR pass 1 complete — 847 tokens extracted'],
  ['🔍', 'log-success', 'Extractor', 'Header fields extracted: invoice_no, dates, vendor_name'],
  ['🔍', 'log-success', 'Extractor', 'Line items table parsed — 6 rows, 4 columns'],
  ['🔍', 'log-success', 'Extractor', 'Financial summary extracted: subtotal, tax, total'],
  ['✅', 'log-warn', 'Validator', 'Running math validation... ✓ $48,200 + $4,337.40 = $52,537.40'],
  ['✅', 'log-warn', 'Validator', 'Vendor "Acme Software Corp" matched in vendor registry'],
  ['✅', 'log-warn', 'Validator', 'Tax ID partially redacted — flagging for review (conf: 88%)'],
  ['🔄', 'log-error', 'Enricher', 'ERP vendor lookup: Account #V-00847 → Net 30 terms'],
  ['🎭', 'log-accent', 'Orchestrator', 'Pipeline complete — 18 fields extracted, 1 review flag'],
  ['📤', 'log-success', 'Output', 'Structured JSON written to output store → doc_id: INV-2024-00847'],
];

// ─── Confidence Bars ──────────────────────────────────────
export const confBarsData = [
  { label: 'Invoice fields', pct: 99.2, color: '#6366f1' },
  { label: 'Contract clauses', pct: 96.8, color: '#8b5cf6' },
  { label: 'Medical entities', pct: 91.4, color: '#06b6d4' },
  { label: 'Financial figures', pct: 99.7, color: '#10b981' },
  { label: 'Identity fields', pct: 97.1, color: '#f59e0b' },
];

// ─── SLA Metrics ──────────────────────────────────────────
export const slaData = [
  { label: 'Uptime (30d)', pct: 99.98, color: '#10b981' },
  { label: 'SLA Met (<5s)', pct: 99.1, color: '#6366f1' },
  { label: 'Automation Rate', pct: 97.3, color: '#8b5cf6' },
  { label: 'First-pass Accuracy', pct: 98.3, color: '#06b6d4' },
];

// ─── Analytics ────────────────────────────────────────────
export const accuracyData = [
  { label: 'Invoices', pct: 99.2, color: '#6366f1' },
  { label: 'Contracts', pct: 96.8, color: '#8b5cf6' },
  { label: 'Medical', pct: 91.4, color: '#06b6d4' },
  { label: 'Financial', pct: 99.7, color: '#10b981' },
  { label: 'Legal', pct: 94.2, color: '#f59e0b' },
  { label: 'ID Docs', pct: 97.1, color: '#ef4444' },
];

export const agentPerfData = [
  { label: 'Orchestrator', pct: 99.1, color: '#6366f1' },
  { label: 'Classifier', pct: 99.3, color: '#8b5cf6' },
  { label: 'Extractor', pct: 98.4, color: '#10b981' },
  { label: 'Validator', pct: 99.6, color: '#f59e0b' },
  { label: 'Enricher', pct: 97.2, color: '#ef4444' },
];

// ─── Processing Modal Steps ───────────────────────────────
export const procStepsData = [
  { icon: '📥', name: 'Document Intake', detail: 'Validating file format and computing hash...', doneLabel: 'Intake complete ✓' },
  { icon: '🔍', name: 'OCR & Parsing', detail: 'Extracting text and layout from PDF...', doneLabel: 'OCR complete ✓' },
  { icon: '🏷️', name: 'Classification', detail: 'Identifying document type and schema...', doneLabel: 'Invoice detected ✓' },
  { icon: '🤖', name: 'Field Extraction', detail: 'Running multi-pass LLM extraction...', doneLabel: '18 fields extracted ✓' },
  { icon: '🔢', name: 'Table Extraction', detail: 'Parsing structured tables and line items...', doneLabel: '6 line items found ✓' },
  { icon: '✅', name: 'Validation', detail: 'Cross-checking values against business rules...', doneLabel: 'All checks passed ✓' },
  { icon: '📤', name: 'Export & Store', detail: 'Writing structured JSON to output store...', doneLabel: 'Stored as doc_id:INV-00847 ✓' },
];
export const procDelays = [600, 900, 700, 1400, 800, 1000, 500];
export const procPcts = [10, 22, 38, 58, 72, 88, 100];

// ─── Upload Queue ─────────────────────────────────────────
export const initialQueueFiles = [
  { id: 1, name: 'invoice_Q2_2024.pdf', size: '2.1 MB', icon: '📄', type: 'Invoice' },
  { id: 2, name: 'contract_NDA_Acme.pdf', size: '1.4 MB', icon: '📋', type: 'Contract' },
  { id: 3, name: 'bank_statement_Mar.pdf', size: '0.8 MB', icon: '💰', type: 'Financial' },
];

// ─── Sparkline Data ───────────────────────────────────────
export const sparklineVals = [420, 580, 390, 720, 810, 650, 930, 1040, 870, 950, 1120, 980, 1050, 1240];

// ─── Donut Chart ──────────────────────────────────────────
export const donutData = [38, 22, 18, 12, 10];
export const donutColors = ['#6366f1', '#8b5cf6', '#06b6d4', '#f59e0b', '#10b981'];
export const donutLabels = ['Invoices', 'Contracts', 'Medical', 'Legal', 'Financial'];
export const donutPcts = ['38%', '22%', '18%', '12%', '10%'];

// ─── Extraction Progress (Processing page) ────────────────
export const extractionProgress = [
  { label: 'Vendor Name', pct: 100 },
  { label: 'Invoice Number', pct: 100 },
  { label: 'Issue Date', pct: 100 },
  { label: 'Line Items', pct: 72 },
  { label: 'Total Amount', pct: 85 },
  { label: 'Tax Details', pct: 60 },
];

// ─── Nav items ────────────────────────────────────────────
export const navSections = [
  {
    label: 'Workspace',
    items: [
      { icon: '📊', label: 'Dashboard', page: 'dashboard' },
      { icon: '📤', label: 'Upload Docs', page: 'upload', badge: 3 },
      { icon: '⚙️', label: 'Processing', page: 'processing' },
      { icon: '🔍', label: 'Extraction', page: 'extraction' },
    ],
  },
  {
    label: 'AI Agents',
    items: [
      { icon: '🤖', label: 'Agent Hub', page: 'agents' },
      { icon: '🔀', label: 'Workflows', page: 'workflows' },
    ],
  },
  {
    label: 'Insights',
    items: [
      { icon: '📈', label: 'Analytics', page: 'analytics' },
      { icon: '✅', label: 'Validation', page: 'validation' },
    ],
  },
  {
    label: 'System',
    items: [
      { icon: '⚙️', label: 'Settings', page: null },
      { icon: '🔑', label: 'API Keys', page: null },
    ],
  },
];

export const pageTitles = {
  dashboard: ['Dashboard', 'Overview of your intelligent document processing pipeline'],
  upload: ['Upload Documents', 'Drag, drop, or browse — AI agents handle the rest'],
  processing: ['Processing Pipeline', 'Real-time agentic workflow execution'],
  extraction: ['Extraction Results', 'Structured data extracted by AI agents'],
  agents: ['Agent Hub', 'Manage and monitor your specialized AI agents'],
  workflows: ['Workflows', 'Pre-built and custom document processing pipelines'],
  analytics: ['Analytics', 'Performance metrics and operational insights'],
  validation: ['Validation Queue', 'Human-in-the-loop review for low-confidence extractions'],
};
