import React, { useState, useMemo, useCallback } from 'react';
import './SecurityTab.css';

/* ================================================================
   Risk Level Definitions
   ================================================================ */
const RISK_CONFIG = {
    critical: { label: 'Critical', color: '#dc2626', bg: '#fef2f2', border: '#fecaca', icon: '🔴' },
    high:     { label: 'High',     color: '#ea580c', bg: '#fff7ed', border: '#fed7aa', icon: '🟠' },
    medium:   { label: 'Medium',   color: '#d97706', bg: '#fffbeb', border: '#fde68a', icon: '🟡' },
    low:      { label: 'Low',      color: '#6b7280', bg: '#f9fafb', border: '#e5e7eb', icon: '🟢' },
};

const RULE_TYPES = [
    { value: 'managed_policy_name', label: 'Managed Policy Name' },
    { value: 'inline_policy_action', label: 'Inline Policy Action' },
];

const MATCH_TYPES = [
    { value: 'exact', label: 'Exact' },
    { value: 'wildcard', label: 'Wildcard' },
];

const RISK_LEVELS = [
    { value: 'critical', label: 'Critical' },
    { value: 'high', label: 'High' },
    { value: 'medium', label: 'Medium' },
    { value: 'low', label: 'Low' },
];

/* ================================================================
   SecurityTab — Main Component
   ================================================================ */
export default function SecurityTab({
    permissionSetsData,
    riskPolicies,
    riskSource,
    onSaveRiskPolicies,
    loading,
}) {
    const permissionSets = permissionSetsData?.permission_sets || [];

    /* ---- Risk overview stats ---- */
    const riskStats = useMemo(() => {
        const counts = { critical: 0, high: 0, medium: 0, low: 0 };
        permissionSets.forEach(ps => {
            const level = ps.risk_level || 'low';
            counts[level] = (counts[level] || 0) + 1;
        });
        return counts;
    }, [permissionSets]);

    const totalPS = permissionSets.length;

    /* ---- Flagged permission sets list ---- */
    const flaggedPS = useMemo(() => {
        return permissionSets
            .filter(ps => ps.risk_level && ps.risk_level !== 'low')
            .sort((a, b) => {
                const order = { critical: 0, high: 1, medium: 2, low: 3 };
                return (order[a.risk_level] || 3) - (order[b.risk_level] || 3);
            });
    }, [permissionSets]);

    /* ---- Rule editor state ---- */
    const [editingRules, setEditingRules] = useState(null);
    const [saving, setSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState(null);

    const currentRules = editingRules || riskPolicies?.rules || [];

    const startEditing = useCallback(() => {
        setEditingRules([...(riskPolicies?.rules || [])]);
        setSaveMessage(null);
    }, [riskPolicies]);

    const cancelEditing = () => {
        setEditingRules(null);
        setSaveMessage(null);
    };

    const addRule = () => {
        setEditingRules(prev => [
            ...(prev || []),
            { type: 'managed_policy_name', pattern: '', match: 'exact', risk: 'medium', reason: '' },
        ]);
    };

    const updateRule = (index, field, value) => {
        setEditingRules(prev => {
            const updated = [...prev];
            updated[index] = { ...updated[index], [field]: value };
            return updated;
        });
    };

    const deleteRule = (index) => {
        setEditingRules(prev => prev.filter((_, i) => i !== index));
    };

    const saveRules = async () => {
        setSaving(true);
        setSaveMessage(null);
        try {
            await onSaveRiskPolicies({ version: 1, rules: editingRules });
            setSaveMessage({ type: 'success', text: `Saved ${editingRules.length} rules. Run a new crawl to apply risk scoring.` });
            setEditingRules(null);
        } catch (err) {
            setSaveMessage({ type: 'error', text: err.message || 'Failed to save rules' });
        } finally {
            setSaving(false);
        }
    };

    const resetToDefaults = () => {
        if (window.confirm('Reset all rules to industry-standard defaults? This will discard any custom rules.')) {
            // Fetch defaults from API will happen on save — for now clear editing
            setEditingRules(null);
            onSaveRiskPolicies(null); // null signals "delete custom, use defaults"
            setSaveMessage({ type: 'success', text: 'Reset to defaults. Run a new crawl to apply.' });
        }
    };

    if (loading) {
        return (
            <div className="security-container">
                <div className="security-loading">
                    <div className="security-loading__spinner" />
                    Loading security data…
                </div>
            </div>
        );
    }

    return (
        <div className="security-container">
            {/* Risk Overview Stats */}
            <section className="security-stats">
                {Object.entries(RISK_CONFIG).map(([level, config]) => (
                    <div
                        className={`security-stat-card security-stat-card--${level}`}
                        key={level}
                    >
                        <div className="security-stat-card__icon">{config.icon}</div>
                        <div className="security-stat-card__content">
                            <span className="security-stat-card__value">{riskStats[level]}</span>
                            <span className="security-stat-card__label">{config.label} Risk</span>
                        </div>
                    </div>
                ))}
            </section>

            {/* Flagged Permission Sets */}
            <section className="security-panel">
                <div className="security-panel__header">
                    <div>
                        <h3 className="security-panel__title">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                                <line x1="12" y1="9" x2="12" y2="13" />
                                <line x1="12" y1="17" x2="12.01" y2="17" />
                            </svg>
                            Flagged Permission Sets
                        </h3>
                        <p className="security-panel__subtitle">
                            {flaggedPS.length} of {totalPS} permission sets flagged ({totalPS - flaggedPS.length} low risk)
                        </p>
                    </div>
                </div>
                <div className="security-panel__body">
                    {flaggedPS.length === 0 ? (
                        <p className="security-panel__empty">No flagged permission sets. All permission sets are low risk.</p>
                    ) : (
                        <table className="security-flagged-table">
                            <thead>
                                <tr>
                                    <th>Risk</th>
                                    <th>Permission Set</th>
                                    <th>Reasons</th>
                                </tr>
                            </thead>
                            <tbody>
                                {flaggedPS.map((ps, i) => {
                                    const config = RISK_CONFIG[ps.risk_level] || RISK_CONFIG.low;
                                    return (
                                        <tr key={ps.arn || i}>
                                            <td>
                                                <span
                                                    className="risk-badge"
                                                    style={{
                                                        background: config.bg,
                                                        color: config.color,
                                                        border: `1px solid ${config.border}`,
                                                    }}
                                                >
                                                    {config.icon} {config.label}
                                                </span>
                                            </td>
                                            <td>
                                                <span className="security-ps-name">{ps.name}</span>
                                                <span className="security-ps-arn">{ps.arn}</span>
                                            </td>
                                            <td>
                                                <ul className="security-reasons">
                                                    {(ps.risk_reasons || []).map((r, j) => (
                                                        <li key={j}>
                                                            <code className="security-reason__rule">{r.rule}</code>
                                                            <span className="security-reason__text">{r.reason}</span>
                                                        </li>
                                                    ))}
                                                </ul>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    )}
                </div>
            </section>

            {/* Risk Policy Editor */}
            <section className="security-panel">
                <div className="security-panel__header">
                    <div>
                        <h3 className="security-panel__title">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                            </svg>
                            Risk Policy Rules
                        </h3>
                        <p className="security-panel__subtitle">
                            {currentRules.length} rules · Source: {riskSource === 'custom' ? 'Custom (saved)' : 'Industry defaults'}
                        </p>
                    </div>
                    <div className="security-panel__actions">
                        {editingRules === null ? (
                            <button className="security-btn security-btn--primary" onClick={startEditing}>
                                <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                                    <path d="M12.854 0.146a.5.5 0 00-.707 0L10.5 1.793 14.207 5.5l1.647-1.646a.5.5 0 000-.708l-3-3zM13.5 6.207L9.793 2.5 3.5 8.793V12.5h3.707l6.293-6.293z"/>
                                    <path d="M1 13.5A1.5 1.5 0 002.5 15h11a1.5 1.5 0 001.5-1.5v-6a.5.5 0 00-1 0v6a.5.5 0 01-.5.5h-11a.5.5 0 01-.5-.5v-11a.5.5 0 01.5-.5H9a.5.5 0 000-1H2.5A1.5 1.5 0 001 2.5v11z"/>
                                </svg>
                                Edit Rules
                            </button>
                        ) : (
                            <>
                                <button className="security-btn security-btn--success" onClick={saveRules} disabled={saving}>
                                    {saving ? 'Saving…' : 'Save Rules'}
                                </button>
                                <button className="security-btn security-btn--ghost" onClick={cancelEditing}>
                                    Cancel
                                </button>
                            </>
                        )}
                        <button className="security-btn security-btn--ghost" onClick={resetToDefaults}>
                            Reset to Defaults
                        </button>
                    </div>
                </div>

                {saveMessage && (
                    <div className={`security-message security-message--${saveMessage.type}`}>
                        {saveMessage.text}
                    </div>
                )}

                <div className="security-panel__body security-panel__body--scroll">
                    <table className="security-rules-table">
                        <thead>
                            <tr>
                                <th style={{ width: 180 }}>Type</th>
                                <th style={{ width: 200 }}>Pattern</th>
                                <th style={{ width: 100 }}>Match</th>
                                <th style={{ width: 100 }}>Risk Level</th>
                                <th>Reason</th>
                                {editingRules !== null && <th style={{ width: 50 }}></th>}
                            </tr>
                        </thead>
                        <tbody>
                            {currentRules.map((rule, i) => (
                                <tr key={i}>
                                    <td>
                                        {editingRules !== null ? (
                                            <select value={rule.type} onChange={e => updateRule(i, 'type', e.target.value)}>
                                                {RULE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                                            </select>
                                        ) : (
                                            <span className="security-rule-type">{RULE_TYPES.find(t => t.value === rule.type)?.label || rule.type}</span>
                                        )}
                                    </td>
                                    <td>
                                        {editingRules !== null ? (
                                            <input
                                                type="text"
                                                value={rule.pattern}
                                                onChange={e => updateRule(i, 'pattern', e.target.value)}
                                                placeholder="e.g., AdministratorAccess"
                                            />
                                        ) : (
                                            <code className="security-rule-pattern">{rule.pattern}</code>
                                        )}
                                    </td>
                                    <td>
                                        {editingRules !== null ? (
                                            <select value={rule.match} onChange={e => updateRule(i, 'match', e.target.value)}>
                                                {MATCH_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                                            </select>
                                        ) : (
                                            <span className="security-rule-match">{rule.match}</span>
                                        )}
                                    </td>
                                    <td>
                                        {editingRules !== null ? (
                                            <select value={rule.risk} onChange={e => updateRule(i, 'risk', e.target.value)}>
                                                {RISK_LEVELS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                                            </select>
                                        ) : (
                                            <span
                                                className="risk-badge risk-badge--sm"
                                                style={{
                                                    background: RISK_CONFIG[rule.risk]?.bg,
                                                    color: RISK_CONFIG[rule.risk]?.color,
                                                    border: `1px solid ${RISK_CONFIG[rule.risk]?.border}`,
                                                }}
                                            >
                                                {RISK_CONFIG[rule.risk]?.label || rule.risk}
                                            </span>
                                        )}
                                    </td>
                                    <td>
                                        {editingRules !== null ? (
                                            <input
                                                type="text"
                                                value={rule.reason}
                                                onChange={e => updateRule(i, 'reason', e.target.value)}
                                                placeholder="Why is this risky?"
                                            />
                                        ) : (
                                            <span className="security-rule-reason">{rule.reason}</span>
                                        )}
                                    </td>
                                    {editingRules !== null && (
                                        <td>
                                            <button
                                                className="security-btn security-btn--danger security-btn--icon"
                                                onClick={() => deleteRule(i)}
                                                title="Delete rule"
                                            >
                                                ✕
                                            </button>
                                        </td>
                                    )}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {editingRules !== null && (
                        <button className="security-btn security-btn--add" onClick={addRule}>
                            + Add Rule
                        </button>
                    )}
                </div>
            </section>
        </div>
    );
}

/* ================================================================
   Reusable RiskBadge component — exported for other tabs
   ================================================================ */
export function RiskBadge({ level, showLabel = true }) {
    const config = RISK_CONFIG[level] || RISK_CONFIG.low;
    if (level === 'low') return null; // Don't show badge for low risk

    return (
        <span
            className="risk-badge risk-badge--sm"
            style={{
                background: config.bg,
                color: config.color,
                border: `1px solid ${config.border}`,
            }}
            title={`${config.label} risk`}
        >
            {config.icon}{showLabel ? ` ${config.label}` : ''}
        </span>
    );
}
