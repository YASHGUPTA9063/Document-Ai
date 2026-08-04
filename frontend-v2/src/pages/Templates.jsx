import { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  FileCode, Plus, RotateCcw, Edit2, Trash2, Calendar, 
  Type, Hash, ToggleLeft, List, Table, Check, X, Search, 
  AlertCircle, CheckCircle2, ChevronRight, Image, ShieldCheck,
  Crop
} from 'lucide-react';
import { Modal } from '../components/ui/Modal';
import { RegionSelector } from '../components/ui/RegionSelector';
import { useApp } from '../store/AppStore';
import { getTemplates, saveTemplates, generateTemplateFromSample, deleteTemplate, getClassificationConfig } from '../api/client';

const DEFAULT_TEMPLATES = {};

const TYPE_ICONS = {
  'Text': Type,
  'Number': Hash,
  'Date': Calendar,
  'Boolean': ToggleLeft,
  'Array of Text': List,
  'Array of Objects': Table,
  'Image': Image
};

export function Templates() {
  const { toast, fieldHighlightThreshold } = useApp();
  const [activeTab, setActiveTab] = useState('');
  const [templates, setTemplates] = useState(DEFAULT_TEMPLATES);
  const [loading, setLoading] = useState(true);

  const [searchQuery, setSearchQuery] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingField, setEditingField] = useState(null); // null means adding a new field
  const [formData, setFormData] = useState({
    key: '',
    label: '',
    type: 'Text',
    required: false,
    description: '',
    confidence_threshold: ''
  });

  const [createTemplateModalOpen, setCreateTemplateModalOpen] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState('');
  const [isKycTemplate, setIsKycTemplate] = useState(false);
  const [sampleFile, setSampleFile] = useState(null);
  const [generatingTemplate, setGeneratingTemplate] = useState(false);
  const [createKycRegions, setCreateKycRegions] = useState({ signature: null, photo: null });
  // A template is looked up by the doc_type the classifier assigns, so the name
  // has to be one of the configured types — otherwise it silently never applies.
  const [docTypes, setDocTypes] = useState([]);

  useEffect(() => {
    getClassificationConfig()
      .then((types) => setDocTypes(Array.isArray(types) ? types : []))
      .catch(() => setDocTypes([]));
  }, []);

  const normalizeKey = (name) => name.trim().toLowerCase().replace(/[\s-]+/g, '_');
  const templateNameMatchesDocType =
    !newTemplateName.trim() ||
    docTypes.length === 0 ||
    docTypes.some((t) => normalizeKey(t) === normalizeKey(newTemplateName));

  // Preview URL for the sample file (only for images)
  const samplePreviewUrl = useMemo(() => {
    if (!sampleFile) return null;
    const imageTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
    if (imageTypes.includes(sampleFile.type)) {
      return URL.createObjectURL(sampleFile);
    }
    return null;
  }, [sampleFile]);

  // Cleanup preview URL on unmount or change
  useEffect(() => {
    return () => {
      if (samplePreviewUrl) URL.revokeObjectURL(samplePreviewUrl);
    };
  }, [samplePreviewUrl]);

  useEffect(() => {
    getTemplates()
      .then(data => {
        const loadedTemplates = data || DEFAULT_TEMPLATES;
        setTemplates(loadedTemplates);
        const keys = Object.keys(loadedTemplates);
        if (keys.length > 0) {
          if (!activeTab || !loadedTemplates[activeTab]) {
            setActiveTab(keys[0]);
          }
        } else {
          setActiveTab('');
        }
      })
      .catch(err => {
        toast('Failed to load templates: ' + err.message, 'error');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [toast, activeTab]);

  const currentFields = useMemo(() => {
    const t = templates[activeTab];
    if (!t) return [];
    // Handle both old (list) and new ({fields, is_kyc}) formats
    if (Array.isArray(t)) return t;
    return t.fields || [];
  }, [templates, activeTab]);

  const isActiveKyc = useMemo(() => {
    const t = templates[activeTab];
    if (!t || Array.isArray(t)) return false;
    return t.is_kyc === true;
  }, [templates, activeTab]);



  const filteredFields = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return currentFields;
    return currentFields.filter(f => 
      f.key.toLowerCase().includes(q) || 
      f.label.toLowerCase().includes(q) || 
      f.description.toLowerCase().includes(q)
    );
  }, [currentFields, searchQuery]);

  const requiredCount = useMemo(() => {
    return currentFields.filter(f => f.required).length;
  }, [currentFields]);

  const handleOpenAddModal = () => {
    setEditingField(null);
    setFormData({
      key: '',
      label: '',
      type: 'Text',
      required: false,
      description: '',
      confidence_threshold: ''
    });
    setModalOpen(true);
  };

  const handleOpenEditModal = (field) => {
    setEditingField(field);
    setFormData({
      key: field.key,
      label: field.label,
      type: field.type,
      required: field.required,
      description: field.description || '',
      confidence_threshold: field.confidence_threshold !== undefined && field.confidence_threshold !== null ? field.confidence_threshold : ''
    });
    setModalOpen(true);
  };

  const handleDeleteField = async (fieldKey) => {
    if (window.confirm(`Are you sure you want to delete the field "${fieldKey}"?`)) {
      const updatedList = currentFields.filter(f => f.key !== fieldKey);
      // Preserve template metadata (is_kyc flag) when updating fields
      const existingTemplate = templates[activeTab];
      const templateMeta = (existingTemplate && !Array.isArray(existingTemplate)) ? existingTemplate : {};
      const updatedTemplates = { ...templates, [activeTab]: { ...templateMeta, fields: updatedList } };
      
      try {
        setTemplates(updatedTemplates);
        await saveTemplates(updatedTemplates);
        toast(`Field "${fieldKey}" deleted successfully ✓`, 'info');
      } catch (err) {
        toast(`Failed to delete field: ${err.message}`, 'error');
      }
    }
  };

  const handleDeleteTemplate = async () => {
    if (!activeTab) return;
    if (window.confirm(`Are you sure you want to delete the entire "${activeTab.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}" template? This cannot be undone.`)) {
      try {
        await deleteTemplate(activeTab);
        toast(`Template deleted successfully ✓`, 'info');
        const data = await getTemplates();
        const loadedTemplates = data || {};
        setTemplates(loadedTemplates);
        const keys = Object.keys(loadedTemplates);
        if (keys.length > 0) {
          setActiveTab(keys[0]);
        } else {
          setActiveTab('');
        }
      } catch (err) {
        toast(`Failed to delete template: ${err.message}`, 'error');
      }
    }
  };



  const handleGenerateTemplate = async (e) => {
    e.preventDefault();
    if (!newTemplateName.trim()) {
      alert('Template Name is required');
      return;
    }
    if (!sampleFile) {
      alert('Please select a sample document file');
      return;
    }
    
    setGeneratingTemplate(true);
    try {
      // Build kyc_boxes from drawn regions (only non-null entries)
      let kycBoxesToSend = null;
      if (isKycTemplate && (createKycRegions.signature || createKycRegions.photo)) {
        kycBoxesToSend = {};
        if (createKycRegions.signature) kycBoxesToSend.signature = createKycRegions.signature;
        if (createKycRegions.photo) kycBoxesToSend.photo = createKycRegions.photo;
      }

      const res = await generateTemplateFromSample(newTemplateName, sampleFile, isKycTemplate, kycBoxesToSend);
      toast(`Template "${res.template_name}" generated successfully ✓`, 'success');
      const updated = await getTemplates();
      setTemplates(updated || {});
      setActiveTab(res.template_name);
      setCreateTemplateModalOpen(false);
      setNewTemplateName('');
      setIsKycTemplate(false);
      setSampleFile(null);
      setCreateKycRegions({ signature: null, photo: null });
    } catch (err) {
      toast(`Failed to generate template: ${err.message}`, 'error');
    } finally {
      setGeneratingTemplate(false);
    }
  };

  const handleSaveField = async (e) => {
    e.preventDefault();
    const key = formData.key.trim().toLowerCase().replace(/\s+/g, '_');
    
    if (!key) {
      alert('Field Key is required');
      return;
    }

    if (!formData.label.trim()) {
      alert('Field Label is required');
      return;
    }

    // Validate snake_case key pattern
    if (!/^[a-z0-9_]+$/.test(key)) {
      alert('Field Key must only contain lowercase letters, numbers, and underscores');
      return;
    }

    // Check uniqueness if adding new OR renaming
    const isNew = !editingField;
    const isRename = editingField && editingField.key !== key;
    if (isNew || isRename) {
      const exists = currentFields.some(f => f.key === key);
      if (exists) {
        alert(`A field with key "${key}" already exists in this template.`);
        return;
      }
    }

    const fieldObj = {
      key,
      label: formData.label.trim(),
      type: formData.type,
      required: formData.required,
      description: formData.description.trim(),
      confidence_threshold: formData.confidence_threshold !== '' ? Number(formData.confidence_threshold) : null
    };

    let updatedList;
    if (isNew) {
      updatedList = [...currentFields, fieldObj];
    } else {
      updatedList = currentFields.map(f => f.key === editingField.key ? fieldObj : f);
    }
    // Preserve template metadata (is_kyc flag) when updating fields
    const existingTemplate = templates[activeTab];
    const templateMeta = (existingTemplate && !Array.isArray(existingTemplate)) ? existingTemplate : {};
    const updatedTemplates = { ...templates, [activeTab]: { ...templateMeta, fields: updatedList } };

    try {
      setTemplates(updatedTemplates);
      await saveTemplates(updatedTemplates);
      setModalOpen(false);
      toast(`Field "${key}" ${isNew ? 'added' : 'updated'} successfully ✓`, 'success');
    } catch (err) {
      toast(`Failed to save field: ${err.message}`, 'error');
    }
  };

  if (loading) {
    return (
      <div className="page anim-slide-in" style={{ padding: '20px 0' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="skeleton" style={{ height: 40, width: '40%' }} />
          <div className="skeleton" style={{ height: 20, width: '60%' }} />
          <div className="skeleton" style={{ height: 260, width: '100%', marginTop: 20 }} />
        </div>
      </div>
    );
  }

  const templateKeys = Object.keys(templates);

  return (
    <div className="page anim-slide-in">
      {/* ── Page Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7, maxWidth: 660, margin: 0 }}>
            Configure target fields for standard Document Processing workflows. Adding or editing fields here dictates which elements the underlying extraction agents look for.
          </p>
          
          {templateKeys.length > 0 && (
            <div style={{ display: 'flex', gap: 12, marginTop: 12, flexWrap: 'wrap' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--accent)', background: 'var(--accent-dim)', border: '1px solid rgba(79,110,247,0.2)', borderRadius: 99, padding: '3px 10px' }}>
                <FileCode size={10} /> {currentFields.length} Total Fields
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--success)', background: 'var(--success-dim)', border: '1px solid var(--success-border)', borderRadius: 99, padding: '3px 10px' }}>
                <CheckCircle2 size={10} /> {requiredCount} Required Fields
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-dim)', background: 'var(--card-alt)', border: '1px solid var(--border)', borderRadius: 99, padding: '3px 10px' }}>
                {currentFields.length - requiredCount} Optional Fields
              </span>
            </div>
          )}
        </div>

        {/* Global actions */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button 
            className="btn btn-primary btn-sm" 
            onClick={() => setCreateTemplateModalOpen(true)}
            id="templates-create-template-btn"
          >
            <Plus size={12} /> Create Template
          </button>
        </div>
      </div>

      {templateKeys.length === 0 ? (
        <div className="card" style={{ padding: '64px 24px', textAlign: 'center', marginTop: 20 }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, maxWidth: 480, margin: '0 auto' }}>
            <div style={{
              background: 'rgba(79, 110, 247, 0.1)',
              color: 'var(--accent)',
              padding: 20,
              borderRadius: '50%',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 8
            }}>
              <FileCode size={40} />
            </div>
            <h3 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: 'var(--text)' }}>No Templates Configured</h3>
            <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6, margin: 0 }}>
              You don't have any document templates set up yet. Upload a sample document to automatically generate a template schema for your document type.
            </p>
            <button 
              className="btn btn-primary" 
              style={{ marginTop: 8 }}
              onClick={() => setCreateTemplateModalOpen(true)}
            >
              <Plus size={14} style={{ marginRight: 6 }} /> Create Template from Sample
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* ── Document Type Tabs ── */}
          <div className="tabs">
            {templateKeys.map((key) => {
            const tpl = templates[key];
            const kycFlag = tpl && !Array.isArray(tpl) && tpl.is_kyc;
            return (
              <div 
                key={key}
                className={`tab ${activeTab === key ? 'active' : ''}`}
                onClick={() => { setActiveTab(key); setSearchQuery(''); }}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                {kycFlag && <ShieldCheck size={12} style={{ color: 'var(--accent)' }} />}
                {key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                {kycFlag && (
                  <span style={{
                    fontSize: 9, fontWeight: 700, color: 'var(--accent)',
                    background: 'var(--accent-dim)', border: '1px solid rgba(79,110,247,0.25)',
                    padding: '1px 5px', borderRadius: 4, marginLeft: 2
                  }}>KYC</span>
                )}
              </div>
            );
          })}
          </div>

          {/* ── Search Bar & Filter Strip ── */}
          <div className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14, justifyContent: 'space-between', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexGrow: 1, minWidth: 240 }}>
              <Search size={14} style={{ color: 'var(--muted)' }} />
              <input 
                type="text" 
                placeholder="Filter fields by name, key, or description..."
                className="styled-input" 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ border: 'none', background: 'transparent', padding: 0, fontSize: 13, width: '100%' }}
              />
              {searchQuery && (
                <button 
                  className="btn btn-ghost btn-sm" 
                  onClick={() => setSearchQuery('')}
                  style={{ padding: '2px 6px', border: 'none', background: 'transparent' }}
                >
                  <X size={12} />
                </button>
              )}
            </div>
            
            {/* Template specific actions aligned next to the search */}
            <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
              {activeTab && (
                <button 
                  className="btn btn-danger btn-sm" 
                  onClick={handleDeleteTemplate}
                  title="Delete active template"
                  id="templates-delete-template-btn"
                >
                  <Trash2 size={12} /> Delete Template
                </button>
              )}
              {activeTab && (
                <button 
                  className="btn btn-primary btn-sm" 
                  onClick={handleOpenAddModal}
                  id="templates-add-field-btn"
                >
                  <Plus size={12} /> Add Field
                </button>
              )}
            </div>
          </div>

          {/* ── Fields Table Card ── */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div className="table-wrap" style={{ maxHeight: 'calc(100vh - 280px)', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--card-alt)' }}>
                    <th style={{ padding: '12px 16px', width: '20%', position: 'sticky', top: 0, zIndex: 10, background: 'var(--card-alt)' }}>Field Name / Key</th>
                    <th style={{ padding: '12px 16px', width: '12%', position: 'sticky', top: 0, zIndex: 10, background: 'var(--card-alt)' }}>Type</th>
                    <th style={{ padding: '12px 16px', width: '33%', position: 'sticky', top: 0, zIndex: 10, background: 'var(--card-alt)' }}>Description</th>
                    <th style={{ padding: '12px 16px', width: '15%', textAlign: 'center', position: 'sticky', top: 0, zIndex: 10, background: 'var(--card-alt)' }}>Highlight Threshold</th>
                    <th style={{ padding: '12px 16px', width: '10%', textAlign: 'center', position: 'sticky', top: 0, zIndex: 10, background: 'var(--card-alt)' }}>Required</th>
                    <th style={{ padding: '12px 16px', width: '10%', textAlign: 'right', position: 'sticky', top: 0, zIndex: 10, background: 'var(--card-alt)' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFields.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--muted)' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                          <AlertCircle size={24} style={{ opacity: 0.5 }} />
                          <span>No fields match the search query</span>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    filteredFields.map((field, idx) => {
                      const TypeIcon = TYPE_ICONS[field.type] || Type;
                      return (
                        <tr key={field.key} style={{ cursor: 'default' }}>
                          <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                            <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)' }}>
                              {field.label}
                            </div>
                            <code style={{ fontSize: 11, color: 'var(--muted)', background: 'var(--surface-sunken)', padding: '2px 5px', borderRadius: 4, marginTop: 4, display: 'inline-block', fontFamily: 'monospace' }}>
                              {field.key}
                            </code>
                          </td>
                          <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                            <span style={{ 
                              display: 'inline-flex', 
                              alignItems: 'center', 
                              gap: 6, 
                              fontSize: 11, 
                              fontWeight: 500,
                              color: 'var(--text-dim)',
                              background: 'var(--card-alt)',
                              border: '1px solid var(--border)',
                              padding: '3px 8px',
                              borderRadius: 6
                            }}>
                              <TypeIcon size={11} style={{ color: 'var(--accent)' }} />
                              {field.type}
                            </span>
                          </td>
                          <td style={{ padding: '12px 16px', verticalAlign: 'top', color: 'var(--text-dim)', fontSize: 12, lineHeight: 1.5, whiteSpace: 'normal', maxBreakWord: 'break-all' }}>
                            {field.description || <span style={{ fontStyle: 'italic', color: 'var(--muted)' }}>No description provided.</span>}
                          </td>
                          <td style={{ padding: '12px 16px', verticalAlign: 'top', textAlign: 'center' }}>
                            {field.confidence_threshold !== undefined && field.confidence_threshold !== null ? (
                              <span style={{ fontWeight: 600, color: 'var(--warn)' }}>{field.confidence_threshold}%</span>
                            ) : (
                              <span style={{ color: 'var(--muted)', fontSize: 11 }}>{fieldHighlightThreshold}% (Default)</span>
                            )}
                          </td>
                          <td style={{ padding: '12px 16px', verticalAlign: 'top', textAlign: 'center' }}>
                            {field.required ? (
                              <span className="badge badge-green" style={{ fontSize: 9 }}>Yes</span>
                            ) : (
                              <span className="badge badge-gray" style={{ fontSize: 9, opacity: 0.6 }}>No</span>
                            )}
                          </td>
                          <td style={{ padding: '12px 16px', verticalAlign: 'top', textAlign: 'right' }}>
                            <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                              <button 
                                className="btn btn-ghost btn-sm" 
                                style={{ padding: 4 }}
                                onClick={() => handleOpenEditModal(field)}
                                title="Edit Field"
                              >
                                <Edit2 size={11} />
                              </button>
                              <button 
                                className="btn btn-danger btn-sm" 
                                style={{ padding: 4 }}
                                onClick={() => handleDeleteField(field.key)}
                                title="Delete Field"
                              >
                                <Trash2 size={11} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>


        </>
      )}

      {/* ── Edit/Add Field Modal ── */}
      {modalOpen && (
        <Modal
          title={editingField ? 'Edit Extraction Field' : 'Add Extraction Field'}
          subtitle={editingField ? `Modify parameters for ${editingField.key}` : 'Configure a new target field for this document schema'}
          onClose={() => setModalOpen(false)}
          footer={
            <div style={{ display: 'flex', gap: 8, width: '100%', justifyContent: 'flex-end' }}>
              <button 
                type="button" 
                className="btn btn-ghost btn-sm"
                onClick={() => setModalOpen(false)}
              >
                Cancel
              </button>
              <button 
                type="submit" 
                form="field-form"
                className="btn btn-primary btn-sm"
              >
                Save Field
              </button>
            </div>
          }
        >
          <form id="field-form" onSubmit={handleSaveField} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Field Key */}
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Field Key (Database Identifier) <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <input
                type="text"
                className="styled-input"
                value={formData.key}
                disabled={!!editingField} // Disable renaming database key once created to preserve system map references
                placeholder="e.g. tax_registration_number"
                onChange={(e) => setFormData(prev => ({ ...prev, key: e.target.value }))}
                required
              />
              <span style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, display: 'block' }}>
                Must be snake_case (lowercase letters, numbers, underscores only). {editingField && 'Key cannot be renamed.'}
              </span>
            </div>

            {/* Field Label */}
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Display Label <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <input
                type="text"
                className="styled-input"
                value={formData.label}
                placeholder="e.g. Tax Registration Number"
                onChange={(e) => setFormData(prev => ({ ...prev, label: e.target.value }))}
                required
              />
            </div>

            {/* Data Type */}
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Data Type <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <select
                className="styled-select"
                value={formData.type}
                onChange={(e) => setFormData(prev => ({ ...prev, type: e.target.value }))}
              >
                <option value="Text">Text</option>
                <option value="Number">Number</option>
                <option value="Date">Date</option>
                <option value="Boolean">Boolean</option>
                <option value="Array of Text">Array of Text</option>
                <option value="Array of Objects">Array of Objects</option>
              </select>
            </div>

            {/* Description */}
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Description / Context Hint
              </label>
              <textarea
                className="styled-input"
                value={formData.description}
                placeholder="Explain what the extractor agent should look for..."
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                style={{ minHeight: 60, resize: 'vertical' }}
              />
            </div>

            {/* Custom Confidence Threshold */}
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Custom Highlight Threshold (%)
              </label>
              <input
                type="number"
                min="0"
                max="100"
                className="styled-input"
                value={formData.confidence_threshold}
                placeholder={`Leave blank to use default (${fieldHighlightThreshold}%)`}
                onChange={(e) => setFormData(prev => ({ ...prev, confidence_threshold: e.target.value }))}
              />
              <span style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, display: 'block' }}>
                Highlight this field if its extraction confidence falls below this value.
              </span>
            </div>

            {/* Required Toggle */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
              <input
                type="checkbox"
                id="required-checkbox"
                checked={formData.required}
                onChange={(e) => setFormData(prev => ({ ...prev, required: e.target.checked }))}
                style={{ width: 14, height: 14, accentColor: 'var(--accent)', cursor: 'pointer' }}
              />
              <label htmlFor="required-checkbox" style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', cursor: 'pointer' }}>
                Required Field (validations fail if missing)
              </label>
            </div>
          </form>
        </Modal>
      )}

      {/* ── Create Template Modal ── */}
      {createTemplateModalOpen && (
        <Modal
          title="Create Template from Sample Document"
          subtitle="Upload a sample document and the AI will analyze its layout and fields to generate a template."
          onClose={() => !generatingTemplate && setCreateTemplateModalOpen(false)}
          wide={isKycTemplate && !!samplePreviewUrl}
          footer={
            <div style={{ display: 'flex', gap: 8, width: '100%', justifyContent: 'flex-end' }}>
              <button 
                type="button" 
                className="btn btn-ghost btn-sm"
                onClick={() => setCreateTemplateModalOpen(false)}
                disabled={generatingTemplate}
              >
                Cancel
              </button>
              <button 
                type="submit" 
                form="generate-template-form"
                className="btn btn-primary btn-sm"
                disabled={generatingTemplate}
              >
                {generatingTemplate ? (
                  <>
                    <span className="spinner" style={{ marginRight: 6 }} />
                    Generating Schema...
                  </>
                ) : 'Generate Template'}
              </button>
            </div>
          }
        >
          <form id="generate-template-form" onSubmit={handleGenerateTemplate} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Template / Document Type Name <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <input
                type="text"
                className="styled-input"
                list="supported-doc-types"
                value={newTemplateName}
                placeholder="e.g. pan_card, utility_bill, invoice"
                onChange={(e) => setNewTemplateName(e.target.value)}
                required
                disabled={generatingTemplate}
              />
              <datalist id="supported-doc-types">
                {docTypes.map((t) => <option key={t} value={t} />)}
              </datalist>
              <span style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, display: 'block' }}>
                Must match one of the classifier's document types — pick from the list.
                A template whose name isn't a configured type is never applied.
              </span>
              {!templateNameMatchesDocType && (
                <span style={{ fontSize: 10, color: 'var(--warn)', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <AlertCircle size={11} />
                  "{newTemplateName}" isn't a configured document type. Add it under
                  Settings → Classification, or choose an existing type.
                </span>
              )}
            </div>

            {/* KYC Document Toggle */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
              background: isKycTemplate ? 'rgba(79, 110, 247, 0.08)' : 'var(--surface-sunken)',
              border: isKycTemplate ? '1.5px solid rgba(79, 110, 247, 0.3)' : '1px solid var(--border)',
              borderRadius: 'var(--radius)', cursor: 'pointer',
              transition: 'all 0.2s ease'
            }} onClick={() => !generatingTemplate && setIsKycTemplate(prev => !prev)}>
              <input
                type="checkbox"
                id="kyc-toggle"
                checked={isKycTemplate}
                onChange={(e) => setIsKycTemplate(e.target.checked)}
                disabled={generatingTemplate}
                style={{ width: 16, height: 16, accentColor: 'var(--accent)', cursor: 'pointer' }}
              />
              <div style={{ flex: 1 }}>
                <label htmlFor="kyc-toggle" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <ShieldCheck size={14} style={{ color: 'var(--accent)' }} />
                  KYC Identity Document
                </label>
                <span style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2, display: 'block' }}>
                  Enable signature and photo extraction from identity cards (Aadhaar, PAN, etc.)
                </span>
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Upload Sample Document <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <div 
                style={{
                  border: '1.5px dashed var(--border)',
                  borderRadius: 'var(--radius)',
                  padding: '24px 16px',
                  textAlign: 'center',
                  background: 'var(--surface-sunken)',
                  cursor: 'pointer',
                  position: 'relative'
                }}
                onClick={() => !generatingTemplate && document.getElementById('sample-file-input').click()}
              >
                <input
                  id="sample-file-input"
                  type="file"
                  accept=".pdf,.docx,.png,.jpg,.jpeg,.webp"
                  onChange={(e) => {
                    if (e.target.files.length) {
                      setSampleFile(e.target.files[0]);
                    }
                  }}
                  style={{ display: 'none' }}
                  disabled={generatingTemplate}
                />
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                  <span style={{ color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Plus size={24} />
                  </span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
                    {sampleFile ? sampleFile.name : 'Select sample file...'}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                    {sampleFile ? `${(sampleFile.size / 1024).toFixed(0)} KB` : 'Accepts PDF, DOCX, PNG, JPG up to 10MB'}
                  </span>
                </div>
              </div>
            </div>

            {/* Visual Region Selector — shown when KYC + image file */}
            {isKycTemplate && samplePreviewUrl && (
              <div style={{
                padding: 16, borderRadius: 'var(--radius)',
                background: 'rgba(79, 110, 247, 0.04)',
                border: '1px solid rgba(79, 110, 247, 0.15)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                  <Crop size={14} style={{ color: 'var(--accent)' }} />
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>Select Extraction Regions</span>
                  <span style={{
                    fontSize: 9, fontWeight: 700, color: 'var(--accent)',
                    background: 'var(--accent-dim)', border: '1px solid rgba(79,110,247,0.25)',
                    padding: '1px 5px', borderRadius: 4,
                  }}>Optional</span>
                </div>
                <p style={{ fontSize: 11, color: 'var(--muted)', margin: '0 0 10px 0', lineHeight: 1.5 }}>
                  Draw rectangles on the sample image to define where the signature and photo are located. These coordinates will be used for precise extraction.
                </p>
                <RegionSelector
                  imageUrl={samplePreviewUrl}
                  regions={createKycRegions}
                  onChange={setCreateKycRegions}
                />
              </div>
            )}

            {/* PDF notice */}
            {isKycTemplate && sampleFile && !samplePreviewUrl && (
              <div style={{
                padding: '10px 14px', borderRadius: 'var(--radius)',
                background: 'rgba(245, 158, 11, 0.08)',
                border: '1px solid rgba(245, 158, 11, 0.2)',
                fontSize: 11, color: 'var(--warn)', lineHeight: 1.5,
              }}>
                <strong>Note:</strong> Visual region selection is available for image files (PNG, JPG, WEBP). For PDFs, you can set extraction coordinates manually after the template is created.
              </div>
            )}
          </form>
        </Modal>
      )}
    </div>
  );
}
