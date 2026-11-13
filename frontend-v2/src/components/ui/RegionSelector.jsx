import { useState, useRef, useCallback, useEffect } from 'react';
import { Edit2, Image, RotateCcw, MousePointer2 } from 'lucide-react';

/**
 * RegionSelector — Visual drag-to-select crop region picker.
 *
 * Props:
 *   imageUrl   — Object URL or data URL of the sample image
 *   regions    — { signature: {x1,y1,x2,y2}|null, photo: {x1,y1,x2,y2}|null } (percentages 0-100)
 *   onChange   — (regions) => void — called with updated percentage-based regions
 */
export function RegionSelector({ imageUrl, regions, onChange }) {
  const containerRef = useRef(null);
  const imgRef = useRef(null);
  const [imgLoaded, setImgLoaded] = useState(false);
  const [activeMode, setActiveMode] = useState(null); // 'signature' | 'photo' | null
  const [drawing, setDrawing] = useState(false);
  const [startPt, setStartPt] = useState(null);
  const [currentPt, setCurrentPt] = useState(null);

  // Where the picture is actually drawn inside the <img> box, in px. The img is
  // `object-fit: contain` under a max-height, so a portrait page (a KYC form) is
  // letterboxed — drawn narrower than its box with empty bands either side.
  // Coordinates are measured against this drawn area, never the whole box:
  // measuring against the box skewed every saved x toward the centre, so the
  // crop on the real image covered only part of the photo / signature.
  const [contentBox, setContentBox] = useState(null);

  const getContentBox = useCallback(() => {
    const img = imgRef.current;
    if (!img || !img.naturalWidth || !img.naturalHeight) return null;
    const w = img.clientWidth;
    const h = img.clientHeight;
    const scale = Math.min(w / img.naturalWidth, h / img.naturalHeight);
    const cw = img.naturalWidth * scale;
    const ch = img.naturalHeight * scale;
    // object-position defaults to centre
    return { left: (w - cw) / 2, top: (h - ch) / 2, width: cw, height: ch };
  }, []);

  const measure = useCallback(() => setContentBox(getContentBox()), [getContentBox]);

  // Reset loaded state when image changes
  useEffect(() => {
    setImgLoaded(false);
    setContentBox(null);
  }, [imageUrl]);

  // Keep the overlay on the picture when the modal / window is resized.
  useEffect(() => {
    const img = imgRef.current;
    if (!img || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(measure);
    ro.observe(img);
    return () => ro.disconnect();
  }, [measure, imgLoaded]);

  const MODE_CONFIG = {
    signature: {
      label: 'Signature',
      color: 'rgba(79, 110, 247, 0.25)',
      border: 'rgba(79, 110, 247, 0.8)',
      icon: Edit2,
      btnColor: 'var(--accent)',
      btnBg: 'var(--accent-dim)',
    },
    photo: {
      label: 'Photo',
      color: 'rgba(16, 185, 129, 0.25)',
      border: 'rgba(16, 185, 129, 0.8)',
      icon: Image,
      btnColor: '#10b981',
      btnBg: 'rgba(16, 185, 129, 0.1)',
    },
  };

  // Convert page-relative mouse coords to a percentage of the image itself
  // (0-100 across the drawn picture, letterbox bands excluded).
  const toPercent = useCallback((clientX, clientY) => {
    const img = imgRef.current;
    const box = getContentBox();
    if (!img || !box) return null;
    const rect = img.getBoundingClientRect();
    const px = clientX - rect.left - box.left;
    const py = clientY - rect.top - box.top;
    const pctX = Math.max(0, Math.min(100, (px / box.width) * 100));
    const pctY = Math.max(0, Math.min(100, (py / box.height) * 100));
    return { x: Math.round(pctX * 10) / 10, y: Math.round(pctY * 10) / 10 };
  }, [getContentBox]);

  const handleMouseDown = useCallback((e) => {
    if (!activeMode) return;
    e.preventDefault();
    const pt = toPercent(e.clientX, e.clientY);
    if (!pt) return;
    setDrawing(true);
    setStartPt(pt);
    setCurrentPt(pt);
  }, [activeMode, toPercent]);

  const handleMouseMove = useCallback((e) => {
    if (!drawing) return;
    e.preventDefault();
    const pt = toPercent(e.clientX, e.clientY);
    if (pt) setCurrentPt(pt);
  }, [drawing, toPercent]);

  const handleMouseUp = useCallback((e) => {
    if (!drawing || !startPt || !activeMode) {
      setDrawing(false);
      return;
    }
    e.preventDefault();
    const end = toPercent(e.clientX, e.clientY);
    if (!end) { setDrawing(false); return; }

    const x1 = Math.min(startPt.x, end.x);
    const y1 = Math.min(startPt.y, end.y);
    const x2 = Math.max(startPt.x, end.x);
    const y2 = Math.max(startPt.y, end.y);

    // Minimum size check (at least 2% in each dimension)
    if (x2 - x1 < 2 || y2 - y1 < 2) {
      setDrawing(false);
      setStartPt(null);
      setCurrentPt(null);
      return;
    }

    const newRegions = {
      ...regions,
      // One decimal place: whole percents can be ~10px off on a scan-sized page.
      [activeMode]: { x1, y1, x2, y2 },
    };
    onChange(newRegions);
    setDrawing(false);
    setStartPt(null);
    setCurrentPt(null);
    setActiveMode(null); // Deactivate after drawing
  }, [drawing, startPt, activeMode, toPercent, regions, onChange]);

  // Also handle mouse leaving the image area
  const handleMouseLeave = useCallback(() => {
    if (drawing) {
      setDrawing(false);
      setStartPt(null);
      setCurrentPt(null);
    }
  }, [drawing]);

  const handleClearRegion = (mode) => {
    onChange({ ...regions, [mode]: null });
  };

  const handleClearAll = () => {
    onChange({ signature: null, photo: null });
  };

  // Render a region overlay (either saved or being drawn)
  const renderRegion = (mode, box, isDraft = false) => {
    if (!box) return null;
    const cfg = MODE_CONFIG[mode];
    return (
      <div
        key={mode + (isDraft ? '-draft' : '')}
        style={{
          position: 'absolute',
          left: `${box.x1}%`,
          top: `${box.y1}%`,
          width: `${box.x2 - box.x1}%`,
          height: `${box.y2 - box.y1}%`,
          background: cfg.color,
          border: `2px ${isDraft ? 'dashed' : 'solid'} ${cfg.border}`,
          borderRadius: 4,
          pointerEvents: 'none',
          zIndex: 2,
          transition: isDraft ? 'none' : 'all 0.15s ease',
        }}
      >
        <span style={{
          position: 'absolute',
          top: -20,
          left: 0,
          fontSize: 10,
          fontWeight: 700,
          color: cfg.border,
          background: 'rgba(0,0,0,0.7)',
          padding: '1px 6px',
          borderRadius: 3,
          whiteSpace: 'nowrap',
          letterSpacing: 0.5,
        }}>
          {cfg.label}
        </span>
      </div>
    );
  };

  // Draft box while drawing
  const draftBox = drawing && startPt && currentPt ? {
    x1: Math.min(startPt.x, currentPt.x),
    y1: Math.min(startPt.y, currentPt.y),
    x2: Math.max(startPt.x, currentPt.x),
    y2: Math.max(startPt.y, currentPt.y),
  } : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Mode Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginRight: 4 }}>
          Draw region:
        </span>
        {Object.entries(MODE_CONFIG).map(([mode, cfg]) => {
          const Icon = cfg.icon;
          const isActive = activeMode === mode;
          const hasRegion = regions[mode] != null;
          return (
            <div key={mode} style={{ display: 'flex', gap: 4 }}>
              <button
                type="button"
                onClick={() => setActiveMode(isActive ? null : mode)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  fontSize: 11, fontWeight: 600, padding: '5px 10px',
                  borderRadius: 6, border: `1.5px solid ${isActive ? cfg.border : 'var(--border)'}`,
                  background: isActive ? cfg.btnBg : 'transparent',
                  color: isActive ? cfg.btnColor : 'var(--text-dim)',
                  cursor: 'pointer', transition: 'all 0.15s ease',
                }}
              >
                <Icon size={12} />
                {cfg.label}
                {hasRegion && <span style={{ color: '#10b981', marginLeft: 2 }}>✓</span>}
              </button>
              {hasRegion && (
                <button
                  type="button"
                  onClick={() => handleClearRegion(mode)}
                  title={`Clear ${cfg.label}`}
                  style={{
                    display: 'inline-flex', alignItems: 'center',
                    fontSize: 10, padding: '3px 6px', borderRadius: 4,
                    border: '1px solid var(--border)', background: 'transparent',
                    color: 'var(--muted)', cursor: 'pointer',
                  }}
                >
                  ✕
                </button>
              )}
            </div>
          );
        })}

        <div style={{ flex: 1 }} />
        {(regions.signature || regions.photo) && (
          <button
            type="button"
            onClick={handleClearAll}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              fontSize: 10, fontWeight: 600, padding: '4px 8px',
              borderRadius: 4, border: '1px solid var(--border)',
              background: 'transparent', color: 'var(--muted)', cursor: 'pointer',
            }}
          >
            <RotateCcw size={10} /> Reset All
          </button>
        )}
      </div>

      {/* Active mode instruction */}
      {activeMode && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '6px 12px', borderRadius: 6,
          background: MODE_CONFIG[activeMode].color,
          border: `1px solid ${MODE_CONFIG[activeMode].border}`,
          fontSize: 11, fontWeight: 600, color: MODE_CONFIG[activeMode].border,
        }}>
          <MousePointer2 size={12} />
          Click and drag on the image to select the <strong>{MODE_CONFIG[activeMode].label}</strong> region
        </div>
      )}

      {/* Image + Overlay Container */}
      <div
        ref={containerRef}
        style={{
          position: 'relative',
          borderRadius: 'var(--radius)',
          overflow: 'hidden',
          border: activeMode ? `2px solid ${MODE_CONFIG[activeMode].border}` : '2px solid var(--border)',
          cursor: activeMode ? 'crosshair' : 'default',
          userSelect: 'none',
          transition: 'border-color 0.2s ease',
          background: 'var(--surface-sunken)',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
      >
        <img
          ref={imgRef}
          src={imageUrl}
          alt="Sample document"
          onLoad={() => { setImgLoaded(true); measure(); }}
          draggable={false}
          style={{
            display: 'block',
            width: '100%',
            height: 'auto',
            maxHeight: 500,
            objectFit: 'contain',
            pointerEvents: 'none',
          }}
        />

        {/* Overlay for drawn regions */}
        {imgLoaded && contentBox && (
          <div style={{
            // Exactly over the drawn picture, so a region's percentages are
            // percentages of the image — the same numbers the backend crops by.
            position: 'absolute',
            left: contentBox.left, top: contentBox.top,
            width: contentBox.width, height: contentBox.height,
            pointerEvents: 'none',
          }}>
            {regions.signature && renderRegion('signature', regions.signature)}
            {regions.photo && renderRegion('photo', regions.photo)}
            {draftBox && activeMode && renderRegion(activeMode, draftBox, true)}
          </div>
        )}

        {/* Loading state */}
        {!imgLoaded && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 60, color: 'var(--muted)', fontSize: 12,
          }}>
            Loading image preview...
          </div>
        )}
      </div>

      {/* Coordinate summary */}
      {(regions.signature || regions.photo) && (
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8,
          fontSize: 10, color: 'var(--muted)',
        }}>
          {regions.signature && (
            <div style={{
              padding: '6px 10px', borderRadius: 4,
              background: 'rgba(79, 110, 247, 0.06)',
              border: '1px solid rgba(79, 110, 247, 0.15)',
            }}>
              <strong style={{ color: 'var(--accent)' }}>Signature:</strong>{' '}
              ({regions.signature.x1}%, {regions.signature.y1}%) → ({regions.signature.x2}%, {regions.signature.y2}%)
            </div>
          )}
          {regions.photo && (
            <div style={{
              padding: '6px 10px', borderRadius: 4,
              background: 'rgba(16, 185, 129, 0.06)',
              border: '1px solid rgba(16, 185, 129, 0.15)',
            }}>
              <strong style={{ color: '#10b981' }}>Photo:</strong>{' '}
              ({regions.photo.x1}%, {regions.photo.y1}%) → ({regions.photo.x2}%, {regions.photo.y2}%)
            </div>
          )}
        </div>
      )}
    </div>
  );
}
