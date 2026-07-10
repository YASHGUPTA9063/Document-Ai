/* ─── Claim Types ─── */
export const CLAIM_TYPES = [
  'Health Insurance',
  'Motor Insurance',
  'Life Insurance',
  'Travel Insurance',
  'Property Insurance',
  'Fire Insurance',
  'Marine Insurance',
];

export const PRIORITY_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
];

export const DEFAULT_DOCUMENTS = [
  { name: 'Aadhaar Card', present: true },
  { name: 'PAN Card', present: true },
];

/* ─── Sample Claims ─── */
export const SAMPLE_CLAIMS = [
  {
    id: 'CLM-2026-001',
    claimantName: 'Priya S. Kapoor',
    claimType: 'Health Insurance',
    amount: 245000,
    dateSubmitted: '2026-07-08',
    priority: 'high',
    status: 'pending',
    policyNumber: 'HLT-9827-4501',
    description: 'Hospitalization claim for cardiac procedure at Apollo Hospital, Mumbai.',
    documents: [
      { name: 'Aadhaar Card', present: true },
      { name: 'PAN Card', present: true },
      { name: 'Hospital Discharge Summary', present: true },
      { name: 'Medical Bills', present: true },
      { name: 'Prescription Records', present: true },
    ],
  },
  {
    id: 'CLM-2026-002',
    claimantName: 'Rajesh M. Gupta',
    claimType: 'Motor Insurance',
    amount: 87500,
    dateSubmitted: '2026-07-07',
    priority: 'medium',
    status: 'pending',
    policyNumber: 'MTR-3341-7820',
    description: 'Vehicle damage claim due to road accident on NH-48, Pune.',
    documents: [
      { name: 'Aadhaar Card', present: true },
      { name: 'PAN Card', present: false },
      { name: 'FIR Copy', present: true },
      { name: 'Vehicle Registration', present: true },
      { name: 'Repair Estimate', present: false },
    ],
  },
  {
    id: 'CLM-2026-003',
    claimantName: 'Ananya R. Sharma',
    claimType: 'Life Insurance',
    amount: 1500000,
    dateSubmitted: '2026-07-06',
    priority: 'urgent',
    status: 'pending',
    policyNumber: 'LIF-7752-0093',
    description: "Death benefit claim — policyholder's nominee filing for term life payout.",
    documents: [
      { name: 'Aadhaar Card', present: true },
      { name: 'PAN Card', present: true },
      { name: 'Death Certificate', present: true },
      { name: 'Nominee ID Proof', present: true },
      { name: 'Policy Document', present: true },
      { name: 'Bank Account Proof', present: true },
    ],
  },
  {
    id: 'CLM-2026-004',
    claimantName: 'Vikram D. Patel',
    claimType: 'Health Insurance',
    amount: 62000,
    dateSubmitted: '2026-07-05',
    priority: 'low',
    status: 'pending',
    policyNumber: 'HLT-4420-8816',
    description: 'OPD reimbursement claim for dental surgery at Max Healthcare.',
    documents: [
      { name: 'Aadhaar Card', present: true },
      { name: 'PAN Card', present: false },
      { name: 'Hospital Bills', present: true },
      { name: 'Prescription Records', present: false },
      { name: "Doctor's Referral Letter", present: false },
    ],
  },
  {
    id: 'CLM-2026-005',
    claimantName: 'Meera K. Joshi',
    claimType: 'Travel Insurance',
    amount: 180000,
    dateSubmitted: '2026-07-04',
    priority: 'medium',
    status: 'pending',
    policyNumber: 'TRV-6618-2234',
    description: 'Medical emergency during international trip to Thailand — hospitalization reimbursement.',
    documents: [
      { name: 'Aadhaar Card', present: true },
      { name: 'Passport Copy', present: true },
      { name: 'PAN Card', present: true },
      { name: 'Hospital Bills (Foreign)', present: true },
      { name: 'Travel Itinerary', present: true },
      { name: 'Currency Exchange Receipts', present: false },
    ],
  },
  {
    id: 'CLM-2026-006',
    claimantName: 'Arjun B. Nair',
    claimType: 'Property Insurance',
    amount: 520000,
    dateSubmitted: '2026-07-03',
    priority: 'high',
    status: 'pending',
    policyNumber: 'PRP-1190-5567',
    description: 'Fire damage claim for commercial property in Kochi industrial area.',
    documents: [
      { name: 'Aadhaar Card', present: true },
      { name: 'PAN Card', present: true },
      { name: 'Fire Brigade Report', present: true },
      { name: 'Property Valuation Report', present: true },
      { name: 'Insurance Policy Copy', present: true },
      { name: 'Photographs of Damage', present: true },
    ],
  },
];

/* ─── Workflow Steps ─── */
export const INITIAL_STEPS = [
  {
    id: 'case-setup',
    label: 'Claim Case Setup',
    summary: 'Initializes claim case file, verifies policy validity, and loads claimant profile.',
    outputKind: 'json',
    agentThought:
      "I need to first verify that the policy number is valid and active. Let me cross-reference the claimant's details with our policyholder database. I'm checking the policy inception date, premium payment history, and coverage limits. The policy HLT-9827-4501 is active with premiums paid through July 2026. The claimant Priya S. Kapoor matches the policyholder on record. Coverage type is comprehensive health with a sum insured of ₹10,00,000. No prior claims in the last 12 months. Waiting period of 30 days has been satisfied. I'll now set up the case file and proceed to validation.",
    output: {
      case_id: 'CLM-2026-001',
      policy_number: 'HLT-9827-4501',
      policy_status: 'active',
      claimant: 'Priya S. Kapoor',
      claim_type: 'Health Insurance — Hospitalization',
      sum_insured: 1000000,
      claim_amount: 245000,
      premium_status: 'paid_up',
      waiting_period: 'satisfied',
      prior_claims_12m: 0,
      documents_received: 5,
    },
  },
  {
    id: 'integrity-validator',
    label: 'Claim Integrity Validator',
    summary: 'Validates document authenticity, cross-references data, and detects anomalies.',
    outputKind: 'json',
    agentThought:
      "Starting integrity validation. I'll examine each submitted document for authenticity markers. The Aadhaar Card shows valid QR code pattern and UIDAI format — no signs of tampering. PAN Card format matches Income Tax Department standards with correct checksum. Hospital discharge summary has official Apollo Hospital letterhead with registration number verified against hospital registry. Medical bills contain sequential invoice numbers consistent with Apollo Hospital's billing system. Prescription records bear valid MCI registration numbers for the attending physicians. Cross-referencing claimant identity: name and date of birth match across all documents. Address on Aadhaar aligns with policy records. No duplicate claim submissions detected in the system. Document timestamps are chronologically consistent — admission date precedes discharge, prescriptions dated during hospitalization period. Overall integrity assessment: PASS with high confidence.",
    output: {
      overall_integrity: 'PASS',
      document_verification: {
        aadhaar_card: { authentic: true, tamper_score: 0.01 },
        pan_card: { authentic: true, tamper_score: 0.02 },
        discharge_summary: { authentic: true, tamper_score: 0.03 },
        medical_bills: { authentic: true, tamper_score: 0.01 },
        prescriptions: { authentic: true, tamper_score: 0.02 },
      },
      identity_cross_match: true,
      duplicate_claim_check: 'no_duplicates',
      chronological_consistency: true,
      anomaly_flags: [],
    },
  },
  {
    id: 'medical-validator',
    label: 'Medical Validator',
    summary: 'Validates medical diagnosis, treatment protocols, and clinical necessity.',
    outputKind: 'json',
    agentThought:
      "Analyzing the medical documentation for clinical validity. The discharge summary indicates a diagnosis of acute coronary syndrome (ACS) — ICD-10 code I21.9. The patient presented with chest pain and elevated troponin levels, which is consistent with the diagnosis. Treatment involved percutaneous coronary intervention (PCI) with a drug-eluting stent placement — this is the standard of care for this condition. The 4-day hospitalization duration (July 4-8, 2026) is within normal range for PCI procedures. Medications prescribed post-discharge include dual antiplatelet therapy (Aspirin + Clopidogrel), statin, and beta-blocker — all consistent with ACC/AHA guidelines for post-ACS management. The attending cardiologist Dr. R. Mehta has MCI registration MH-12847 which I've verified as valid. ICU stay of 2 days post-procedure is clinically appropriate. Lab work shows improving cardiac markers during hospitalization. No red flags for unnecessary procedures or extended stay. Medical necessity: CONFIRMED.",
    output: {
      diagnosis: 'Acute Coronary Syndrome (I21.9)',
      procedure: 'Percutaneous Coronary Intervention (PCI) with DES',
      clinical_necessity: 'confirmed',
      treatment_guideline_compliance: 'ACC/AHA compliant',
      hospitalization_duration: '4 days (appropriate)',
      icu_days: 2,
      attending_physician: 'Dr. R. Mehta (MCI: MH-12847)',
      physician_verified: true,
      prescribed_medications: ['Aspirin', 'Clopidogrel', 'Atorvastatin', 'Metoprolol'],
      lab_trend: 'improving cardiac markers',
      medical_necessity_score: 0.96,
    },
  },
  {
    id: 'treatment-validator',
    label: 'Treatment Validator',
    summary: 'Validates treatment costs, procedure codes, and billing accuracy.',
    outputKind: 'json',
    agentThought:
      "Now I'll validate the financial aspects of the treatment. The total claim amount is ₹2,45,000. Breaking it down: Room charges (₹8,000/day × 4 days = ₹32,000) — this is within the policy's room rent limit of ₹10,000/day. ICU charges (₹15,000/day × 2 days = ₹30,000) — within network hospital ICU rates. PCI procedure with drug-eluting stent: ₹1,20,000 — I'm cross-referencing with the NPPA-capped stent price and Apollo Hospital's standard procedure rate. The stent cost is within the government-mandated ceiling price. Investigation charges (Echo, Angiography, Blood work): ₹28,000 — consistent with standard diagnostic pricing. Medication charges: ₹15,000 — aligns with prescribed drugs and hospital pharmacy rates. Surgeon and anesthesiologist fees: ₹20,000 — within CGHS/NABH benchmark rates. No billing anomalies detected — all procedure codes map correctly to the treatments documented. The sub-limits under the policy are not breached. One minor observation: the consumables charge of ₹12,000 is slightly above average but within acceptable variance (15%). Billing validation: PASS.",
    output: {
      total_claimed: 245000,
      breakdown: {
        room_charges: 32000,
        icu_charges: 30000,
        procedure_stent: 120000,
        diagnostics: 28000,
        medications: 15000,
        surgeon_fees: 20000,
      },
      room_rent_within_limit: true,
      stent_price_compliance: 'within NPPA ceiling',
      procedure_code_match: true,
      billing_anomalies: 0,
      cost_benchmark: 'within_range',
      consumables_variance: '15% above avg (acceptable)',
      sub_limit_breach: false,
      billing_validation: 'PASS',
    },
  },
  {
    id: 'disability-mgmt',
    label: 'Disability Management',
    summary: 'Assesses post-treatment disability, recovery timeline, and rehabilitation needs.',
    outputKind: 'json',
    agentThought:
      'Evaluating post-treatment disability and recovery trajectory. Based on the discharge summary and post-operative notes, the patient underwent successful PCI with good angiographic result — TIMI 3 flow achieved. Expected recovery timeline: The patient should be able to resume light activities within 1-2 weeks and return to normal work within 4-6 weeks. Cardiac rehabilitation is recommended — Phase I (in-hospital) was completed, Phase II (outpatient supervised exercise) should begin 2 weeks post-discharge. No permanent disability is anticipated from this procedure — ejection fraction on discharge echo was 52% (mildly reduced but expected to improve with medical therapy). The patient will need cardiac follow-up at 1 month, 3 months, and 6 months. Dual antiplatelet therapy should continue for minimum 12 months. No occupational restrictions beyond avoiding heavy physical exertion for 6 weeks. This is a temporary disability case with full recovery expected. No additional disability benefits applicable under the current policy terms. Recovery prognosis: FAVORABLE.',
    output: {
      disability_type: 'temporary',
      recovery_timeline: '4-6 weeks to full activity',
      permanent_disability: false,
      ejection_fraction: '52% (mildly reduced, improving)',
      cardiac_rehab: 'Phase II recommended',
      work_restriction: '6 weeks — no heavy exertion',
      follow_up_schedule: ['1 month', '3 months', '6 months'],
      antiplatelet_duration: '12 months minimum',
      prognosis: 'favorable',
      disability_benefit_applicable: false,
      recovery_score: 0.88,
    },
  },
  {
    id: 'litigation-validator',
    label: 'Litigation Validator',
    summary: 'Assesses legal risk, policy exclusions, regulatory compliance, and fraud indicators.',
    outputKind: 'json',
    agentThought:
      "Conducting litigation risk assessment and regulatory compliance check. First, checking policy exclusions: Pre-existing disease clause — the claimant's policy has completed the 4-year waiting period for pre-existing conditions, so even if coronary artery disease was pre-existing, it's now covered. The policy does not have any specific cardiac exclusion riders. Checking for moral hazard: No pattern of frequent claims, no history of claim disputes, and the claimant has been with the insurer for 6 years with consistent premium payments. IRDAI compliance check: The claim is within the timeline (filed within 24 hours of discharge as required), all mandatory documents are submitted, and the hospital is within the approved network. Third-party liability assessment: This is a medical event, not an accident, so no third-party recovery applies. Anti-fraud screening: Cross-referencing with the Insurance Information Bureau (IIB) — no fraud flags on the claimant, no suspicious patterns with the hospital or physician. Legal risk assessment: Very low. The claim is straightforward with complete documentation, valid medical necessity, and no exclusion triggers. Recommendation: No legal hold required, standard processing pathway appropriate. Litigation risk: LOW.",
    output: {
      pre_existing_clause: 'cleared (4-year waiting satisfied)',
      policy_exclusions_triggered: [],
      moral_hazard_indicators: 'none',
      irdai_compliance: 'fully_compliant',
      claim_filing_timeline: 'within 24 hours',
      third_party_liability: 'not_applicable',
      iib_fraud_flags: 0,
      legal_hold_required: false,
      regulatory_risk: 'low',
      litigation_risk_score: 0.05,
      recommendation: 'standard processing — no legal review needed',
    },
  },
];

export const STEP_DURATIONS = {
  'case-setup': 1200,
  'integrity-validator': 2200,
  'medical-validator': 2800,
  'treatment-validator': 2400,
  'disability-mgmt': 2000,
  'litigation-validator': 1800,
};

export function stepDuration(id) {
  return STEP_DURATIONS[id] ?? 1500;
}

/* ─── Completion Summary Data ─── */
export const PROS = [
  'Policy is active with continuous premium payments for 6 years — strong policyholder history',
  'All 5 submitted documents pass authenticity checks with near-zero tamper scores',
  'Medical diagnosis (ACS) is well-documented with supporting lab results and imaging',
  'Treatment follows ACC/AHA clinical guidelines — PCI with DES is standard of care',
  'Billing amounts are within NPPA ceilings and CGHS/NABH benchmark rates',
  'No prior claims in 12 months — no pattern of excessive utilization',
  'Pre-existing disease waiting period fully satisfied (4+ years)',
  'Hospital is within approved network — no out-of-network complications',
  'No fraud indicators flagged by IIB or internal anomaly detection',
  'Claim filed within 24 hours of discharge — full IRDAI timeline compliance',
];

export const CONS = [
  'Consumables charges are 15% above average (₹12,000) — within tolerance but notable',
  'Ejection fraction at 52% indicates mildly reduced cardiac function post-procedure',
  'Patient will require ongoing cardiac medication for minimum 12 months — future claim risk',
  'Single coronary event may indicate underlying cardiovascular disease — potential for recurrence',
];
