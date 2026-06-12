import { useApp } from '../store/AppStore';
import { Settings as SettingsIcon, CheckCircle2, Circle } from 'lucide-react';

export function Settings() {
  const { confidenceMode, setConfidenceMode, toast } = useApp();

  const isWordActive = confidenceMode === 'word' || confidenceMode === 'both';
  const isPageActive = confidenceMode === 'page' || confidenceMode === 'both';

  const toggleWord = () => {
    if (isWordActive && !isPageActive) {
      toast('At least one confidence score type must be active.', 'error');
      return;
    }
    const nextMode = isWordActive ? 'page' : 'both';
    setConfidenceMode(nextMode);
    toast(`Confidence score granularity set to ${nextMode === 'both' ? 'Both Word-wise & Page-wise' : 'Page-wise'} ✓`, 'success');
  };

  const togglePage = () => {
    if (isPageActive && !isWordActive) {
      toast('At least one confidence score type must be active.', 'error');
      return;
    }
    const nextMode = isPageActive ? 'word' : 'both';
    setConfidenceMode(nextMode);
    toast(`Confidence score granularity set to ${nextMode === 'both' ? 'Both Word-wise & Page-wise' : 'Word-wise'} ✓`, 'success');
  };

  return (
    <div className="page" style={{ maxWidth: 640, margin: '0 auto' }}>
      <div className="card" style={{ padding: 24, borderRadius: 'var(--radius)' }}>
        <div className="card-header" style={{ borderBottom: '1px solid var(--border)', paddingBottom: 16, marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="empty-icon-wrap" style={{ width: 38, height: 38, background: 'var(--accent-dim)', color: 'var(--accent)', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', flexShrink: 0 }}>
              <SettingsIcon size={20} />
            </div>
            <div>
              <div className="card-title" style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>Extraction Settings</div>
              <div className="card-sub" style={{ fontSize: 13, color: 'var(--muted)', marginTop: 2 }}>Configure confidence score calculation and UI display preferences</div>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Section: Confidence Score Granularity */}
          <div>
            <label style={{ display: 'block', fontSize: 14, fontWeight: 600, color: 'var(--text)', marginBottom: 8 }}>
              Confidence Score Granularity
            </label>
            <p style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 16, lineHeight: 1.5 }}>
              Choose how the confidence scores are calculated and displayed on the Extraction page. You can select one or both score granularities.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Option 1: Word-wise */}
              <div
                onClick={toggleWord}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 14,
                  padding: 16,
                  borderRadius: 'var(--radius-sm)',
                  border: isWordActive ? '1px solid var(--accent)' : '1px solid var(--border)',
                  background: isWordActive ? 'var(--accent-dim)' : 'var(--card-alt)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
                className="setting-option"
              >
                <div style={{ marginTop: 2, flexShrink: 0 }}>
                  {isWordActive ? (
                    <CheckCircle2 size={18} color="var(--accent)" />
                  ) : (
                    <Circle size={18} color="var(--muted)" />
                  )}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, color: isWordActive ? 'var(--accent)' : 'var(--text)' }}>
                    Word-wise Confidence (Recommended)
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4, lineHeight: 1.5 }}>
                    Displays word-level confidence scores for individual fields (e.g., Vendor Name, Total Amount). The overall document confidence will be computed as the average of all extracted field-level confidences.
                  </div>
                </div>
              </div>

              {/* Option 2: Page-wise */}
              <div
                onClick={togglePage}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 14,
                  padding: 16,
                  borderRadius: 'var(--radius-sm)',
                  border: isPageActive ? '1px solid var(--accent)' : '1px solid var(--border)',
                  background: isPageActive ? 'var(--accent-dim)' : 'var(--card-alt)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
                className="setting-option"
              >
                <div style={{ marginTop: 2, flexShrink: 0 }}>
                  {isPageActive ? (
                    <CheckCircle2 size={18} color="var(--accent)" />
                  ) : (
                    <Circle size={18} color="var(--muted)" />
                  )}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, color: isPageActive ? 'var(--accent)' : 'var(--text)' }}>
                    Page-wise Confidence
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4, lineHeight: 1.5 }}>
                    Displays the average page-level OCR confidence score returned by Mistral. Field-level variation badges are hidden, giving a cleaner simplified view of the layout's structural accuracy.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
