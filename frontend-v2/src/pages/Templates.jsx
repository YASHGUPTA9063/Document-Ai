import { useState, useEffect, useMemo } from 'react';
import { 
  FileCode, Plus, RotateCcw, Edit2, Trash2, Calendar, 
  Type, Hash, ToggleLeft, List, Table, Check, X, Search, 
  AlertCircle, CheckCircle2, ChevronRight 
} from 'lucide-react';
import { Modal } from '../components/ui/Modal';
import { useApp } from '../store/AppStore';
import { getTemplates, saveTemplates } from '../api/client';

const DEFAULT_TEMPLATES = {
  invoice: [
    { key: 'invoice_number', label: 'Invoice Number', type: 'Text', required: true, description: 'Unique identifier of the invoice' },
    { key: 'invoice_date', label: 'Invoice Date', type: 'Date', required: true, description: 'Date the invoice was issued' },
    { key: 'vendor_name', label: 'Vendor Name', type: 'Text', required: true, description: 'Name of the issuing vendor' },
    { key: 'vendor_address', label: 'Vendor Address', type: 'Text', required: false, description: 'Address of the vendor' },
    { key: 'bill_to', label: 'Bill To', type: 'Text', required: false, description: 'Recipient or entity being billed' },
    { key: 'subtotal', label: 'Subtotal', type: 'Number', required: false, description: 'Amount before taxes or discounts' },
    { key: 'tax', label: 'Tax', type: 'Number', required: false, description: 'Calculated tax amount' },
    { key: 'total_amount', label: 'Total Amount', type: 'Number', required: true, description: 'Final total amount due' },
    { key: 'currency', label: 'Currency', type: 'Text', required: false, description: 'Transaction currency code (e.g. USD, EUR)' },
    { key: 'due_date', label: 'Due Date', type: 'Date', required: false, description: 'Deadline for invoice payment' },
    { key: 'payment_terms', label: 'Payment Terms', type: 'Text', required: false, description: 'Terms of payment (e.g. Net 30)' },
    { key: 'line_items', label: 'Line Items', type: 'Array of Objects', required: false, description: 'Tabular items representing purchased items or services' }
  ],
  bank_record: [
    { key: 'account_holder', label: 'Account Holder', type: 'Text', required: true, description: 'Full name of the account holder' },
    { key: 'account_number', label: 'Account Number', type: 'Text', required: true, description: 'Bank account number' },
    { key: 'bank_name', label: 'Bank Name', type: 'Text', required: true, description: 'Name of the banking institution' },
    { key: 'statement_period_start', label: 'Statement Start Date', type: 'Date', required: false, description: 'Start date of the statement period' },
    { key: 'statement_period_end', label: 'Statement End Date', type: 'Date', required: false, description: 'End date of the statement period' },
    { key: 'opening_balance', label: 'Opening Balance', type: 'Number', required: false, description: 'Starting balance at the beginning of the period' },
    { key: 'closing_balance', label: 'Closing Balance', type: 'Number', required: false, description: 'Ending balance at the end of the period' },
    { key: 'currency', label: 'Currency', type: 'Text', required: false, description: 'Account currency code (e.g. USD)' },
    { key: 'transactions', label: 'Transactions', type: 'Array of Objects', required: false, description: 'List of account transactions (date, description, amount, balance)' }
  ],
  medical_record: [
    { key: 'patient_name', label: 'Patient Name', type: 'Text', required: true, description: 'Full name of the patient' },
    { key: 'patient_dob', label: 'Patient Date of Birth', type: 'Date', required: true, description: 'Date of birth of the patient' },
    { key: 'record_date', label: 'Record Date', type: 'Date', required: false, description: 'Date of the medical encounter or record creation' },
    { key: 'provider_name', label: 'Provider Name', type: 'Text', required: true, description: 'Name of the healthcare clinic, provider or hospital' },
    { key: 'provider_address', label: 'Provider Address', type: 'Text', required: false, description: 'Physical address of the provider' },
    { key: 'diagnoses', label: 'Diagnoses', type: 'Array of Text', required: false, description: 'Identified medical conditions or diagnoses' },
    { key: 'medications', label: 'Medications', type: 'Array of Text', required: false, description: 'Prescribed or active medications' },
    { key: 'procedures', label: 'Procedures', type: 'Array of Text', required: false, description: 'Medical procedures performed' },
    { key: 'lab_results', label: 'Lab Results', type: 'Array of Text', required: false, description: 'Laboratory test outcomes or values' },
    { key: 'notes', label: 'Notes', type: 'Text', required: false, description: 'Encounter summaries, clinical observations or general notes' }
  ],
  contract: [
    { key: 'contract_title', label: 'Contract Title', type: 'Text', required: true, description: 'Title or type of the contract' },
    { key: 'parties', label: 'Parties', type: 'Array of Text', required: true, description: 'Names of the parties involved in the contract' },
    { key: 'effective_date', label: 'Effective Date', type: 'Date', required: true, description: 'The date the contract starts or becomes active' },
    { key: 'expiration_date', label: 'Expiration Date', type: 'Date', required: false, description: 'The date the contract expires or terminates' },
    { key: 'governing_law', label: 'Governing Law', type: 'Text', required: false, description: 'The jurisdiction or governing law under which the contract is executed' },
    { key: 'contract_value', label: 'Contract Value', type: 'Number', required: false, description: 'Total financial value of the contract' }
  ],
  kyc: [
    { key: 'full_name', label: 'Full Name', type: 'Text', required: true, description: 'Full name of the individual' },
    { key: 'document_type', label: 'Document Type', type: 'Text', required: true, description: 'Type of identity document (e.g. Passport, Drivers License, National ID)' },
    { key: 'document_number', label: 'Document Number', type: 'Text', required: true, description: 'Unique number or identifier of the identity document' },
    { key: 'date_of_birth', label: 'Date of Birth', type: 'Date', required: true, description: 'Date of birth of the individual' },
    { key: 'expiry_date', label: 'Expiry Date', type: 'Date', required: false, description: 'Expiration date of the identity document' },
    { key: 'nationality', label: 'Nationality', type: 'Text', required: false, description: 'Nationality or country of citizenship of the individual' }
  ],
  others: [
    { key: 'document_title', label: 'Document Title', type: 'Text', required: true, description: 'Title or main heading of the document' },
    { key: 'creation_date', label: 'Creation Date', type: 'Date', required: false, description: 'The date the document was created or published' },
    { key: 'author', label: 'Author', type: 'Text', required: false, description: 'The author, creator, or issuing organization of the document' },
    { key: 'summary', label: 'Summary', type: 'Text', required: false, description: 'A brief summary of the document content' }
  ]
};

const TYPE_ICONS = {
  'Text': Type,
  'Number': Hash,
  'Date': Calendar,
  'Boolean': ToggleLeft,
  'Array of Text': List,
  'Array of Objects': Table
};

export function Templates() {
  const { toast } = useApp();
  const [activeTab, setActiveTab] = useState('invoice');
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
    description: ''
  });

  useEffect(() => {
    getTemplates()
      .then(data => {
        const loadedTemplates = data || DEFAULT_TEMPLATES;
        setTemplates(loadedTemplates);
        if (loadedTemplates && !loadedTemplates[activeTab]) {
          const keys = Object.keys(loadedTemplates);
          if (keys.length > 0) {
            setActiveTab(keys[0]);
          }
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
    return templates[activeTab] || [];
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
      description: ''
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
      description: field.description
    });
    setModalOpen(true);
  };

  const handleDeleteField = async (fieldKey) => {
    if (window.confirm(`Are you sure you want to delete the field "${fieldKey}"?`)) {
      const updatedList = currentFields.filter(f => f.key !== fieldKey);
      const updatedTemplates = { ...templates, [activeTab]: updatedList };
      
      try {
        setTemplates(updatedTemplates);
        await saveTemplates(updatedTemplates);
        toast(`Field "${fieldKey}" deleted successfully ✓`, 'info');
      } catch (err) {
        toast(`Failed to delete field: ${err.message}`, 'error');
      }
    }
  };

  const handleResetToDefault = async () => {
    if (window.confirm(`Are you sure you want to reset the "${activeTab.replace('_', ' ')}" template to default fields?`)) {
      const updatedTemplates = {
        ...templates,
        [activeTab]: JSON.parse(JSON.stringify(DEFAULT_TEMPLATES[activeTab]))
      };
      
      try {
        setTemplates(updatedTemplates);
        await saveTemplates(updatedTemplates);
        toast(`Template reset to default schema ✓`, 'success');
      } catch (err) {
        toast(`Failed to reset template: ${err.message}`, 'error');
      }
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
      description: formData.description.trim()
    };

    let updatedList;
    if (isNew) {
      updatedList = [...currentFields, fieldObj];
    } else {
      updatedList = currentFields.map(f => f.key === editingField.key ? fieldObj : f);
    }
    const updatedTemplates = { ...templates, [activeTab]: updatedList };

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

  return (
    <div className="page anim-slide-in">
      {/* ── Page Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7, maxWidth: 660, margin: 0 }}>
            Configure target fields for standard Document Processing workflows. Adding or editing fields here dictates which elements the underlying extraction agents look for.
          </p>
          
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
        </div>

        {/* Global actions */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button 
            className="btn btn-ghost btn-sm" 
            onClick={handleResetToDefault}
            title="Restore default schema configuration"
          >
            <RotateCcw size={12} /> Reset to Default
          </button>
          <button 
            className="btn btn-primary btn-sm" 
            onClick={handleOpenAddModal}
            id="templates-add-field-btn"
          >
            <Plus size={12} /> Add Field
          </button>
        </div>
      </div>

      {/* ── Document Type Tabs ── */}
      <div className="tabs">
        {Object.keys(templates).map((key) => (
          <div 
            key={key}
            className={`tab ${activeTab === key ? 'active' : ''}`}
            onClick={() => { setActiveTab(key); setSearchQuery(''); }}
          >
            {key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')} Template
          </div>
        ))}
      </div>

      {/* ── Search Bar & Filter Strip ── */}
      <div className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <Search size={14} style={{ color: 'var(--muted)' }} />
        <input 
          type="text" 
          placeholder="Filter fields by name, key, or description..."
          className="styled-input" 
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ border: 'none', background: 'transparent', padding: 0, fontSize: 13 }}
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

      {/* ── Fields Table Card ── */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-wrap">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--card-alt)' }}>
                <th style={{ padding: '12px 16px', width: '25%' }}>Field Name / Key</th>
                <th style={{ padding: '12px 16px', width: '15%' }}>Type</th>
                <th style={{ padding: '12px 16px', width: '40%' }}>Description</th>
                <th style={{ padding: '12px 16px', width: '10%', textAlign: 'center' }}>Required</th>
                <th style={{ padding: '12px 16px', width: '10%', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredFields.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--muted)' }}>
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
    </div>
  );
}
