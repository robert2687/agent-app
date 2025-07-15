import React from 'react';
import type { WorkflowNode, Agent, DataSourceConfiguration } from '../types';

interface OrchestrationSidePanelProps {
    node: WorkflowNode | null;
    onEditAgent: (agent: Agent) => void;
    onDeleteNode: (id: string) => void;
}

const DetailItem: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
    <div>
        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{label}</h4>
        <div className="text-gray-200 text-sm">{children}</div>
    </div>
);

const OrchestrationSidePanel: React.FC<OrchestrationSidePanelProps> = ({ node, onEditAgent, onDeleteNode }) => {
    
    const renderNodeDetails = () => {
        if (!node) return null;

        if (node.type === 'Agent') {
            const agent = node.data as Agent;
            return (
                <div className="space-y-4">
                    <DetailItem label="Role">{agent.role_type}</DetailItem>
                    <DetailItem label="Goal"><p className="whitespace-pre-wrap">{agent.goal}</p></DetailItem>
                    <DetailItem label="Tools">{agent.tools_capabilities.join(', ') || 'None'}</DetailItem>
                    <DetailItem label="Input Schema"><pre className="text-xs p-2 bg-gray-900/50 rounded-md"><code>{JSON.stringify(agent.input_schema, null, 2)}</code></pre></DetailItem>
                    <DetailItem label="Output Schema"><pre className="text-xs p-2 bg-gray-900/50 rounded-md"><code>{JSON.stringify(agent.output_schema, null, 2)}</code></pre></DetailItem>
                </div>
            );
        }

        if (node.type === 'DataSource') {
            const ds = node.data as DataSourceConfiguration;
            return (
                <div className="space-y-4">
                    <DetailItem label="Source Type">{ds.source_type}</DetailItem>
                    <DetailItem label="Status">{ds.status}</DetailItem>
                    <DetailItem label="Description"><p className="whitespace-pre-wrap">{ds.description}</p></DetailItem>
                    <DetailItem label="Connection"><pre className="text-xs p-2 bg-gray-900/50 rounded-md"><code>{JSON.stringify(ds.connection_details, null, 2)}</code></pre></DetailItem>
                </div>
            );
        }

        return <DetailItem label="Info">This is a system node.</DetailItem>;
    };

    return (
        <aside className="w-96 bg-gray-800 border-l border-gray-700 flex flex-col">
            <header className="p-4 border-b border-gray-700 flex-shrink-0">
                <h3 className="text-lg font-bold text-white">Inspector</h3>
            </header>
            
            <div className="flex-1 p-4 overflow-y-auto">
                {node ? (
                    <div className="space-y-6 animate-fade-in">
                        <div className="flex justify-between items-center">
                            <h2 className="text-xl font-semibold text-indigo-400 truncate">{node.label}</h2>
                            <span className="text-xs font-mono px-2 py-1 bg-gray-700 rounded-full">{node.type}</span>
                        </div>
                        {renderNodeDetails()}
                    </div>
                ) : (
                    <div className="flex items-center justify-center h-full">
                        <div className="text-center text-gray-500">
                            <svg className="mx-auto h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 10l-2.5 2.5M10 10l2.5-2.5" /></svg>
                            <p className="mt-2 text-sm">Select a node to inspect its properties.</p>
                        </div>
                    </div>
                )}
            </div>
            
            {node && (
                <footer className="p-4 border-t border-gray-700 flex-shrink-0 flex gap-2">
                    {node.type === 'Agent' && (
                         <button onClick={() => onEditAgent(node.data as Agent)} className="flex-1 px-4 py-2 bg-indigo-600 rounded-lg hover:bg-indigo-700 font-semibold transition-colors">
                            Edit Agent
                        </button>
                    )}
                    <button onClick={() => onDeleteNode(node.id)} className="p-2 bg-red-800/50 hover:bg-red-800/80 rounded-lg text-red-300" title="Delete Node">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                </footer>
            )}
        </aside>
    );
};

export default OrchestrationSidePanel;
