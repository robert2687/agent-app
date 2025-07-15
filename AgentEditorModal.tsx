import React, { useState, useEffect } from 'react';
import type { Agent } from '../types';

interface AgentEditorModalProps {
    agent: Agent | null;
    onSave: (agent: Agent) => void;
    onClose: () => void;
}

const defaultJson = (content: object) => JSON.stringify(content, null, 2);

const defaultInputSchema = { type: "object", properties: { query: { type: "string" } } };
const defaultOutputSchema = { type: "object", properties: { result: { type: "string" } } };

const AgentEditorModal: React.FC<AgentEditorModalProps> = ({ agent, onSave, onClose }) => {
    const [formData, setFormData] = useState<Omit<Agent, 'agent_id'>>({
        name: '',
        description: '',
        role_type: 'Generic Agent',
        goal: '',
        persona_instructions: '',
        tools_capabilities: [],
        memory_access: { short_term: true, long_term_knowledge_base: null },
        input_schema: defaultInputSchema,
        output_schema: defaultOutputSchema,
        priority: 10,
    });
    
    const [inputSchemaStr, setInputSchemaStr] = useState(defaultJson(defaultInputSchema));
    const [outputSchemaStr, setOutputSchemaStr] = useState(defaultJson(defaultOutputSchema));
    const [jsonError, setJsonError] = useState({ input: false, output: false });
    const [toolsStr, setToolsStr] = useState('');

    useEffect(() => {
        if (agent) {
            setFormData({
                name: agent.name,
                description: agent.description,
                role_type: agent.role_type,
                goal: agent.goal,
                persona_instructions: agent.persona_instructions,
                tools_capabilities: agent.tools_capabilities,
                memory_access: agent.memory_access,
                input_schema: agent.input_schema,
                output_schema: agent.output_schema,
                priority: agent.priority,
            });
            setInputSchemaStr(defaultJson(agent.input_schema));
            setOutputSchemaStr(defaultJson(agent.output_schema));
            setToolsStr(agent.tools_capabilities.join(', '));
        }
    }, [agent]);
    
    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: name === 'priority' ? parseInt(value, 10) || 0 : value }));
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        let parsedInput, parsedOutput;
        let hasError = false;
        
        try { parsedInput = JSON.parse(inputSchemaStr); setJsonError(p => ({...p, input: false})); } catch (err) { hasError = true; setJsonError(p => ({...p, input: true})); }
        try { parsedOutput = JSON.parse(outputSchemaStr); setJsonError(p => ({...p, output: false})); } catch (err) { hasError = true; setJsonError(p => ({...p, output: true})); }
        
        if (hasError) return;

        const finalAgent: Agent = {
            agent_id: agent?.agent_id || crypto.randomUUID(),
            ...formData,
            input_schema: parsedInput,
            output_schema: parsedOutput,
            tools_capabilities: toolsStr.split(',').map(t => t.trim()).filter(Boolean),
        };
        onSave(finalAgent);
    };

    return (
        <div className="fixed inset-0 bg-black/70 z-40 flex justify-center items-center animate-fade-in">
            <div className="bg-gray-800 rounded-lg shadow-2xl w-full max-w-4xl h-[90vh] flex flex-col">
                <header className="p-4 border-b border-gray-700 flex justify-between items-center flex-shrink-0">
                    <h2 className="text-xl font-bold">{agent ? 'Edit Agent' : 'Create New Agent'}</h2>
                    <button onClick={onClose} className="p-2 rounded-full hover:bg-gray-700">
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                </header>
                <form onSubmit={handleSubmit} className="flex-1 p-6 space-y-4 overflow-y-auto">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <input name="name" value={formData.name} onChange={handleChange} placeholder="Agent Name" required className="form-input" />
                        <input name="role_type" value={formData.role_type} onChange={handleChange} placeholder="Role Type (e.g., Data Retrieval Agent)" required className="form-input" />
                    </div>
                    <textarea name="goal" value={formData.goal} onChange={handleChange} placeholder="Primary Goal" required rows={2} className="form-input" />
                    <textarea name="persona_instructions" value={formData.persona_instructions} onChange={handleChange} placeholder="Persona & System Instructions" required rows={4} className="form-input font-mono text-sm" />
                    
                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-1">Tools (comma-separated)</label>
                        <input type="text" value={toolsStr} onChange={e => setToolsStr(e.target.value)} placeholder="e.g. web_search, calculator" className="form-input" />
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                       <div>
                            <label className="block text-sm font-medium text-gray-300 mb-1">Input Schema (JSON)</label>
                            <textarea value={inputSchemaStr} onChange={e => setInputSchemaStr(e.target.value)} rows={8} className={`form-input font-mono text-xs ${jsonError.input ? 'border-red-500' : ''}`} />
                            {jsonError.input && <p className="text-red-400 text-xs mt-1">Invalid JSON</p>}
                       </div>
                       <div>
                            <label className="block text-sm font-medium text-gray-300 mb-1">Output Schema (JSON)</label>
                            <textarea value={outputSchemaStr} onChange={e => setOutputSchemaStr(e.target.value)} rows={8} className={`form-input font-mono text-xs ${jsonError.output ? 'border-red-500' : ''}`} />
                             {jsonError.output && <p className="text-red-400 text-xs mt-1">Invalid JSON</p>}
                       </div>
                    </div>
                </form>
                <footer className="p-4 border-t border-gray-700 flex-shrink-0 flex justify-end">
                    <button type="button" onClick={handleSubmit} className="px-6 py-2 bg-indigo-600 rounded-lg hover:bg-indigo-700 font-semibold">
                        {agent ? 'Save Changes' : 'Create Agent'}
                    </button>
                </footer>
            </div>
            <style>{`.form-input { width: 100%; padding: 0.75rem; color: #E5E7EB; background-color: #1F2937; border: 1px solid #4B5563; border-radius: 0.5rem; transition: all 0.2s; } .form-input:focus { ring: 2px; border-color: #6366F1; outline: none; }`}</style>
        </div>
    );
};

export default AgentEditorModal;
