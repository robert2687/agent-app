import React, { useState, useEffect, useMemo } from 'react';
import { DataSourceConfiguration, DataSourceType, DataSourceStatus } from '../types';

const STORAGE_KEY = 'ai_app_suite_data_sources';

const defaultJson = (content: object = {}) => JSON.stringify(content, null, 2);

const StatusBadge: React.FC<{ status: DataSourceStatus }> = ({ status }) => {
    const statusClasses = {
        [DataSourceStatus.Active]: 'bg-green-500/20 text-green-400',
        [DataSourceStatus.Inactive]: 'bg-gray-500/20 text-gray-400',
        [DataSourceStatus.Error]: 'bg-red-500/20 text-red-400',
    };
    return (
        <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusClasses[status]}`}>
            {status}
        </span>
    );
};

const JsonTextArea: React.FC<{ value: string; onChange: (value: string) => void; error: boolean; rows?: number; disabled?: boolean; }> = 
({ value, onChange, error, rows = 4, disabled = false }) => (
    <>
        <textarea
            value={value}
            onChange={e => onChange(e.target.value)}
            disabled={disabled}
            rows={rows}
            className={`w-full p-2 bg-gray-800 border ${error ? 'border-red-500' : 'border-gray-600'} rounded-lg font-mono text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none transition resize-y`}
            spellCheck="false"
        />
        {error && <p className="text-red-400 text-xs mt-1">Must be valid JSON.</p>}
    </>
);

const DataSourceEditor: React.FC<{
    source: Partial<DataSourceConfiguration>;
    onSave: (data: Omit<DataSourceConfiguration, 'source_id' | 'created_at' | 'last_updated_at'>) => void;
    onCancel: () => void;
}> = ({ source, onSave, onCancel }) => {
    const [name, setName] = useState(source.name || '');
    const [description, setDescription] = useState(source.description || '');
    const [sourceType, setSourceType] = useState(source.source_type || DataSourceType.API);
    const [interval, setInterval] = useState(source.collection_interval_seconds ?? '');
    
    const [connDetails, setConnDetails] = useState(defaultJson(source.connection_details));
    const [parsingRules, setParsingRules] = useState(defaultJson(source.parsing_rules));
    const [normRules, setNormRules] = useState(defaultJson(source.normalization_rules));
    
    const [jsonError, setJsonError] = useState({ conn: false, parse: false, norm: false });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        
        let parsedConn, parsedParse, parsedNorm;
        let hasError = false;
        
        try { parsedConn = JSON.parse(connDetails); setJsonError(p => ({...p, conn: false})); } catch (err) { hasError = true; setJsonError(p => ({...p, conn: true})); }
        try { parsedParse = JSON.parse(parsingRules); setJsonError(p => ({...p, parse: false})); } catch (err) { hasError = true; setJsonError(p => ({...p, parse: true})); }
        try { parsedNorm = JSON.parse(normRules); setJsonError(p => ({...p, norm: false})); } catch (err) { hasError = true; setJsonError(p => ({...p, norm: true})); }
        
        if (hasError) return;

        onSave({
            name,
            description,
            source_type: sourceType,
            status: source.status || DataSourceStatus.Inactive,
            collection_interval_seconds: interval === '' ? null : Number(interval),
            connection_details: parsedConn,
            parsing_rules: parsedParse,
            normalization_rules: parsedNorm
        });
    };
    
    return (
        <form onSubmit={handleSubmit} className="p-6 bg-gray-800/50 rounded-lg space-y-6 animate-fade-in">
            <h2 className="text-2xl font-bold text-white">{source.source_id ? 'Edit Data Source' : 'Create New Data Source'}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1">Name</label>
                    <input type="text" value={name} onChange={e => setName(e.target.value)} required className="form-input" />
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1">Source Type</label>
                    <select value={sourceType} onChange={e => setSourceType(e.target.value as DataSourceType)} className="form-input">
                        {Object.values(DataSourceType).map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                </div>
            </div>
            <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Description</label>
                <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} className="form-input" />
            </div>
            <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Collection Interval (seconds)</label>
                <input type="number" value={interval} onChange={e => setInterval(e.target.value)} placeholder="Leave blank if not applicable" className="form-input" />
            </div>
            <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Connection Details (JSON)</label>
                <JsonTextArea value={connDetails} onChange={setConnDetails} error={jsonError.conn} />
            </div>
            <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Parsing Rules (JSON)</label>
                <JsonTextArea value={parsingRules} onChange={setParsingRules} error={jsonError.parse} />
            </div>
            <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Normalization Rules (JSON)</label>
                <JsonTextArea value={normRules} onChange={setNormRules} error={jsonError.norm} />
            </div>
            <div className="flex justify-end gap-4">
                <button type="button" onClick={onCancel} className="px-4 py-2 bg-gray-600 rounded-lg hover:bg-gray-700">Cancel</button>
                <button type="submit" className="px-4 py-2 bg-indigo-600 rounded-lg hover:bg-indigo-700 font-semibold">Save Configuration</button>
            </div>
        </form>
    );
};

const DataSourceViewer: React.FC<{ 
    source: DataSourceConfiguration; 
    onEdit: () => void; 
    onDelete: () => void;
    onSetStatus: (status: DataSourceStatus) => void;
}> = ({ source, onEdit, onDelete, onSetStatus }) => {
    return (
        <div className="p-6 bg-gray-800/50 rounded-lg space-y-6 animate-fade-in">
            <div className="flex justify-between items-start">
                <div>
                    <h2 className="text-2xl font-bold text-white">{source.name}</h2>
                    <p className="text-gray-400">{source.description}</p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                    <StatusBadge status={source.status} />
                    <button onClick={onEdit} className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-md">
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" /><path fillRule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clipRule="evenodd" /></svg>
                    </button>
                </div>
            </div>
            <div className="flex flex-wrap gap-2">
                {source.status !== DataSourceStatus.Active && <button onClick={() => onSetStatus(DataSourceStatus.Active)} className="px-3 py-1 text-sm bg-green-600/50 hover:bg-green-600 rounded-md">Activate</button>}
                {source.status !== DataSourceStatus.Inactive && <button onClick={() => onSetStatus(DataSourceStatus.Inactive)} className="px-3 py-1 text-sm bg-gray-600/50 hover:bg-gray-600 rounded-md">Deactivate</button>}
                <button onClick={onDelete} className="px-3 py-1 text-sm bg-red-600/50 hover:bg-red-600 rounded-md">Delete</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div className="bg-gray-900/50 p-3 rounded-lg">
                    <p className="text-gray-400 font-medium">Source ID</p>
                    <p className="text-gray-200 font-mono text-xs">{source.source_id}</p>
                </div>
                <div className="bg-gray-900/50 p-3 rounded-lg">
                    <p className="text-gray-400 font-medium">Source Type</p>
                    <p className="text-gray-200">{source.source_type}</p>
                </div>
                <div className="bg-gray-900/50 p-3 rounded-lg">
                    <p className="text-gray-400 font-medium">Collection Interval</p>
                    <p className="text-gray-200">{source.collection_interval_seconds ? `${source.collection_interval_seconds}s` : 'N/A'}</p>
                </div>
                 <div className="bg-gray-900/50 p-3 rounded-lg">
                    <p className="text-gray-400 font-medium">Created At</p>
                    <p className="text-gray-200">{new Date(source.created_at).toLocaleString()}</p>
                </div>
                <div className="bg-gray-900/50 p-3 rounded-lg">
                    <p className="text-gray-400 font-medium">Last Updated</p>
                    <p className="text-gray-200">{new Date(source.last_updated_at).toLocaleString()}</p>
                </div>
            </div>
            <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Connection Details</label>
                <pre className="p-3 bg-gray-900/50 rounded-lg text-xs font-mono"><code>{defaultJson(source.connection_details)}</code></pre>
            </div>
            <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Parsing Rules</label>
                <pre className="p-3 bg-gray-900/50 rounded-lg text-xs font-mono"><code>{defaultJson(source.parsing_rules)}</code></pre>
            </div>
            <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Normalization Rules</label>
                <pre className="p-3 bg-gray-900/50 rounded-lg text-xs font-mono"><code>{defaultJson(source.normalization_rules)}</code></pre>
            </div>
        </div>
    );
}

const DataSourceManagerView: React.FC = () => {
    const [sources, setSources] = useState<DataSourceConfiguration[]>([]);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [isEditing, setIsEditing] = useState<boolean>(false);

    useEffect(() => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) setSources(JSON.parse(stored));
        } catch (e) {
            console.error("Failed to load data sources:", e);
        }
    }, []);

    const saveSources = (newSources: DataSourceConfiguration[]) => {
        setSources(newSources);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(newSources));
    };

    const handleSave = (data: Omit<DataSourceConfiguration, 'source_id' | 'created_at' | 'last_updated_at'>) => {
        if (isEditing && selectedId) {
            const updated = sources.map(s => s.source_id === selectedId ? { ...s, ...data, last_updated_at: new Date().toISOString() } : s);
            saveSources(updated);
        } else {
            const newSource: DataSourceConfiguration = { ...data, source_id: crypto.randomUUID(), created_at: new Date().toISOString(), last_updated_at: new Date().toISOString() };
            saveSources([...sources, newSource]);
            setSelectedId(newSource.source_id);
        }
        setIsEditing(false);
    };

    const handleDelete = (id: string) => {
        if (window.confirm("Are you sure you want to delete this data source? This cannot be undone.")) {
            saveSources(sources.filter(s => s.source_id !== id));
            if (selectedId === id) setSelectedId(null);
        }
    };
    
    const handleSetStatus = (id: string, status: DataSourceStatus) => {
        saveSources(sources.map(s => s.source_id === id ? { ...s, status, last_updated_at: new Date().toISOString() } : s));
    };

    const selectedSource = useMemo(() => sources.find(s => s.source_id === selectedId), [sources, selectedId]);

    return (
        <div className="flex flex-col md:flex-row h-full">
            <aside className="w-full md:w-1/3 lg:w-1/4 p-4 border-r border-gray-700 overflow-y-auto">
                <h2 className="text-xl font-bold text-white mb-4">Data Sources</h2>
                <button onClick={() => { setSelectedId(null); setIsEditing(true); }} className="w-full mb-4 px-4 py-2 bg-indigo-600 rounded-lg hover:bg-indigo-700 font-semibold transition-colors">
                    Create New Source
                </button>
                <ul className="space-y-2">
                    {sources.map(s => (
                        <li key={s.source_id}>
                            <button onClick={() => { setSelectedId(s.source_id); setIsEditing(false); }} className={`w-full text-left p-3 rounded-lg transition-colors ${selectedId === s.source_id && !isEditing ? 'bg-indigo-900/50' : 'hover:bg-gray-800'}`}>
                                <p className="font-semibold text-gray-200 truncate">{s.name}</p>
                                <div className="flex justify-between items-center mt-1">
                                    <p className="text-xs text-gray-400">{s.source_type}</p>
                                    <StatusBadge status={s.status} />
                                </div>
                            </button>
                        </li>
                    ))}
                </ul>
            </aside>
            <main className="flex-1 p-4 md:p-6 overflow-y-auto">
                {isEditing && (
                    <DataSourceEditor 
                        source={selectedSource || {}} 
                        onSave={handleSave} 
                        onCancel={() => setIsEditing(false)} 
                    />
                )}
                {!isEditing && selectedSource && (
                    <DataSourceViewer 
                        source={selectedSource} 
                        onEdit={() => setIsEditing(true)}
                        onDelete={() => handleDelete(selectedSource.source_id)}
                        onSetStatus={(status) => handleSetStatus(selectedSource.source_id, status)}
                    />
                )}
                {!isEditing && !selectedSource && (
                     <div className="flex justify-center items-center h-full">
                        <div className="text-center text-gray-500">
                             <svg xmlns="http://www.w3.org/2000/svg" className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V7M3 7l9 5 9-5M3 7l-2.5 1.5a1 1 0 000 1.75l17 10a1 1 0 001 0l2.5-1.5" /></svg>
                            <p className="mt-4 text-lg">Select a data source to view its details, or create a new one.</p>
                        </div>
                    </div>
                )}
            </main>
            <style>{`.form-input { width: 100%; padding: 0.5rem; background-color: #374151; border: 1px solid #4B5563; border-radius: 0.5rem; transition: all 0.2s; } .form-input:focus { ring: 2px; ring-color: #6366F1; outline: none; }`}</style>
        </div>
    );
};

export default DataSourceManagerView;
