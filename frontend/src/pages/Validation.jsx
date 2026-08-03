import { useState } from 'react';
import { Card, CardHeader } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Btn } from '../components/ui/Btn';

const initialRows = [
  { id: 1, doc: 'medical_record_0041.pdf', field: 'DOB', value: '03/04/1987', conf: '71%', issue: 'Ambiguous date format', approved: false },
  { id: 2, doc: 'medical_record_0041.pdf', field: 'Diagnosis Code', value: 'ICD-10: J06.9', conf: '79%', issue: 'Low OCR quality', approved: false },
  { id: 3, doc: 'contract_NDA_Acme.pdf', field: 'Jurisdiction', value: 'State of California', conf: '83%', issue: 'Multiple mentions', approved: false },
];

const validationRules = [
  { label: 'Review Confidence Threshold', badge: '< 80%', variant: 'green' },
  { label: 'Mandatory Field Completeness Check', badge: 'Enabled', variant: 'green' },
  { label: 'Financial Total Reconciliation', badge: 'Enabled', variant: 'green' },
  { label: 'Line Item & Subtotal Verification', badge: 'Enabled', variant: 'green' },
  { label: 'Issue & Expiration Date Chronology Check', badge: 'Enabled', variant: 'green' },
  { label: 'Document Template Schema Alignment', badge: 'Enabled', variant: 'green' },
  { label: 'OCR Error & Typo Normalization', badge: 'Enabled', variant: 'green' },
];

const reviewHistory = [
  { time: '09:14', reviewer: 'AI Auto', action: 'Approved ×47', variant: 'green' },
  { time: '09:22', reviewer: 'Sarah K.', action: 'Edited ×2', variant: 'yellow' },
  { time: '10:05', reviewer: 'AI Auto', action: 'Approved ×31', variant: 'green' },
  { time: '11:30', reviewer: 'Mike R.', action: 'Rejected ×1', variant: 'red' },
  { time: '12:18', reviewer: 'AI Auto', action: 'Approved ×58', variant: 'green' },
];

export function Validation() {
  const [rows, setRows] = useState(initialRows);

  const approve = (id) => setRows((r) => r.map((row) => row.id === id ? { ...row, approved: true } : row));

  return (
    <div className="page page-enter">
      {/* Pending Review */}
      <Card style={{ marginBottom: 20 }}>
        <CardHeader
          title="⚠️ Pending Human Review"
          action={<Badge variant="yellow">{rows.filter((r) => !r.approved).length} documents</Badge>}
        />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Document</th><th>Field</th><th>Extracted Value</th>
                <th>Confidence</th><th>Issue</th><th>Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} style={{ opacity: row.approved ? 0.4 : 1, pointerEvents: row.approved ? 'none' : 'auto' }}>
                  <td>{row.doc}</td>
                  <td>{row.field}</td>
                  <td>{row.value}</td>
                  <td><span style={{ color: 'var(--warn)' }}>{row.conf}</span></td>
                  <td><Badge variant="yellow">{row.issue}</Badge></td>
                  <td>
                    <Btn
                      variant="ghost"
                      style={{ padding: '4px 10px', fontSize: 11 }}
                      onClick={() => approve(row.id)}
                    >
                      {row.approved ? '✓ Approved' : '✓ Approve'}
                    </Btn>
                    <Btn variant="ghost" style={{ padding: '4px 10px', fontSize: 11, marginLeft: 4 }}>
                      ✏️ Edit
                    </Btn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Rules + History */}
      <div className="grid-2">
        <Card>
          <div className="card-title" style={{ marginBottom: 12 }}>Validation Rules</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
            {validationRules.map((r) => (
              <div
                key={r.label}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'var(--surface)', borderRadius: 8 }}
              >
                <span>{r.label}</span>
                <Badge variant={r.variant}>{r.badge}</Badge>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <div className="card-title" style={{ marginBottom: 12 }}>Review History (Today)</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Time</th><th>Reviewer</th><th>Action</th></tr>
              </thead>
              <tbody>
                {reviewHistory.map((h) => (
                  <tr key={h.time + h.reviewer}>
                    <td style={{ color: 'var(--muted)' }}>{h.time}</td>
                    <td>{h.reviewer}</td>
                    <td><Badge variant={h.variant}>{h.action}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
