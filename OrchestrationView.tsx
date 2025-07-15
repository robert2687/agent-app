import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { WorkflowNode, DataSourceConfiguration, Agent, WorkflowConnection, SystemLogEntry } from '../types';
import { WorkflowNodeComponent } from './ui/WorkflowNode';
import AgentEditorModal from './AgentEditorModal';
import OrchestrationSidePanel from './OrchestrationSidePanel';
import SystemLogPanel from './SystemLogPanel';

const DATA_SOURCE_STORAGE_KEY = 'ai_app_suite_data_sources';
const AGENT_STORAGE_KEY = 'ai_app_suite_agents';
const WORKFLOW_STORAGE_KEY = 'ai_app_suite_workflow';

const useLocalStorage = <T,>(key: string, initialValue: T): [T, React.Dispatch<React.SetStateAction<T>>] => {
    const [storedValue, setStoredValue] = useState<T>(() => {
        try {
            const item = window.localStorage.getItem(key);
            return item ? JSON.parse(item) : initialValue;
        } catch (error) {
            console.error(error);
            return initialValue;
        }
    });

    const setValue: React.Dispatch<React.SetStateAction<T>> = (value) => {
        try {
            const valueToStore = value instanceof Function ? value(storedValue) : value;
            setStoredValue(valueToStore);
            window.localStorage.setItem(key, JSON.stringify(valueToStore));
        } catch (error) {
            console.error(error);
        }
    };
    return [storedValue, setValue];
};

const OrchestrationView: React.FC = () => {
    const [nodes, setNodes] = useLocalStorage<WorkflowNode[]>(`${WORKFLOW_STORAGE_KEY}_nodes`, []);
    const [connections, setConnections] = useLocalStorage<WorkflowConnection[]>(`${WORKFLOW_STORAGE_KEY}_connections`, []);
    const [agents, setAgents] = useLocalStorage<Agent[]>(AGENT_STORAGE_KEY, []);
    
    const [log, setLog] = useState<SystemLogEntry[]>([]);
    const [isEditorOpen, setIsEditorOpen] = useState(false);
    const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

    const [draggingNode, setDraggingNode] = useState<{ id: string; offset: { x: number, y: number } } | null>(null);
    const [connecting, setConnecting] = useState<{ sourceId: string; sourceHandle: 'left' | 'right', startPos: {x: number, y: number}, currentPos: {x: number, y: number} } | null>(null);
    const canvasRef = useRef<HTMLDivElement>(null);

    const addLog = useCallback((message: string, level: 'info' | 'warn' | 'error' = 'info') => {
        setLog(prev => [{ id: crypto.randomUUID(), timestamp: new Date().toISOString(), level, message }, ...prev].slice(0, 100));
    }, []);
    
    // Load initial nodes from data sources and agents on first render
    useEffect(() => {
        const dataSources: DataSourceConfiguration[] = JSON.parse(localStorage.getItem(DATA_SOURCE_STORAGE_KEY) || '[]');
        const storedAgents: Agent[] = JSON.parse(localStorage.getItem(AGENT_STORAGE_KEY) || '[]');

        const existingNodeIds = new Set(nodes.map(n => n.id));
        const newNodes: WorkflowNode[] = [];

        dataSources.forEach(ds => {
            if (!existingNodeIds.has(ds.source_id)) {
                newNodes.push({ id: ds.source_id, type: 'DataSource', label: ds.name, position: { x: 50, y: 50 + newNodes.length * 120 }, data: ds });
            }
        });

        storedAgents.forEach(agent => {
            if (!existingNodeIds.has(agent.agent_id)) {
                newNodes.push({ id: agent.agent_id, type: 'Agent', label: agent.name, position: { x: 350, y: 50 + newNodes.length * 120 }, data: agent });
            }
        });
        
        if (newNodes.length > 0) {
            setNodes(prev => [...prev, ...newNodes]);
            addLog(`Discovered and loaded ${newNodes.length} new components.`);
        }
    }, []); // Runs only once


    const handleMouseMove = useCallback((e: React.MouseEvent) => {
        if (!canvasRef.current) return;
        const rect = canvasRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        if (draggingNode) {
            setNodes(prev => prev.map(n => n.id === draggingNode.id ? { ...n, position: { x: x - draggingNode.offset.x, y: y - draggingNode.offset.y } } : n));
        } else if (connecting) {
            setConnecting(prev => prev ? {...prev, currentPos: {x,y}} : null);
        }
    }, [draggingNode, connecting, setNodes]);

    const handleMouseUp = useCallback(() => {
        setDraggingNode(null);
        setConnecting(null);
    }, []);
    
    const handleNodeMouseDown = (e: React.MouseEvent, id: string) => {
        const node = nodes.find(n => n.id === id);
        if (!node) return;
        const offsetX = e.nativeEvent.offsetX;
        const offsetY = e.nativeEvent.offsetY;
        setDraggingNode({ id, offset: { x:offsetX, y:offsetY } });
        setSelectedNodeId(id);
    };
    
    const handleHandleMouseDown = (e: React.MouseEvent, nodeId: string, handle: 'left' | 'right') => {
        e.stopPropagation();
        const node = nodes.find(n => n.id === nodeId);
        if(!node || !canvasRef.current) return;

        const rect = canvasRef.current.getBoundingClientRect();
        const handleX = node.position.x + (handle === 'left' ? -8 : 224); // width of node is 224px (w-56)
        const handleY = node.position.y + 48; // half height of node is 48 (h-24)
        setConnecting({ sourceId: nodeId, sourceHandle: handle, startPos: {x: handleX, y:handleY}, currentPos: {x: e.clientX - rect.left, y: e.clientY - rect.top}});
    };

    const handleHandleMouseUp = (e: React.MouseEvent, targetNodeId: string, targetHandle: 'left' | 'right') => {
        e.stopPropagation();
        if (connecting && connecting.sourceId !== targetNodeId) {
            const newConnection: WorkflowConnection = {
                id: crypto.randomUUID(),
                sourceId: connecting.sourceId,
                targetId: targetNodeId,
                sourceHandle: connecting.sourceHandle,
                targetHandle: targetHandle
            };
            setConnections(prev => [...prev, newConnection]);
            addLog(`Connected '${nodes.find(n=>n.id === connecting.sourceId)?.label}' to '${nodes.find(n=>n.id===targetNodeId)?.label}'.`);
        }
        setConnecting(null);
    };

    const handleSaveAgent = (agent: Agent) => {
        const isNew = !agents.some(a => a.agent_id === agent.agent_id);
        const updatedAgents = isNew ? [...agents, agent] : agents.map(a => a.agent_id === agent.agent_id ? agent : a);
        setAgents(updatedAgents);

        if (isNew) {
            setNodes(prev => [...prev, { id: agent.agent_id, type: 'Agent', label: agent.name, position: { x: 400, y: 150 }, data: agent }]);
            addLog(`Created new agent: ${agent.name}.`, 'info');
        } else {
            setNodes(prev => prev.map(n => n.id === agent.agent_id ? { ...n, label: agent.name, data: agent } : n));
            addLog(`Updated agent: ${agent.name}.`, 'info');
        }
        setIsEditorOpen(false);
        setEditingAgent(null);
    };
    
    const handleOpenEditor = (agent: Agent | null) => {
        setEditingAgent(agent);
        setIsEditorOpen(true);
    };

    const selectedNode = useMemo(() => nodes.find(n => n.id === selectedNodeId), [nodes, selectedNodeId]);

    return (
        <div className="h-full flex flex-col bg-gray-900 text-gray-100 relative">
             {isEditorOpen && (
                <AgentEditorModal
                    agent={editingAgent}
                    onSave={handleSaveAgent}
                    onClose={() => setIsEditorOpen(false)}
                />
            )}

            <div className="flex-1 flex overflow-hidden">
                <main className="flex-1 flex flex-col">
                    <div className="flex-shrink-0 p-4 border-b border-gray-700 flex justify-between items-center">
                         <div>
                            <h2 className="text-xl font-bold text-white">Orchestration Canvas</h2>
                            <p className="text-sm text-gray-400">Design and connect your agentic workflows.</p>
                        </div>
                        <button onClick={() => handleOpenEditor(null)} className="px-4 py-2 bg-indigo-600 rounded-lg hover:bg-indigo-700 font-semibold transition-colors flex items-center gap-2">
                             <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" /></svg>
                            Add Agent
                        </button>
                    </div>

                    <div 
                        ref={canvasRef}
                        className="flex-1 bg-gray-800/50 border-r border-gray-700 overflow-hidden relative"
                        onMouseMove={handleMouseMove}
                        onMouseUp={handleMouseUp}
                        onMouseLeave={handleMouseUp}
                    >
                        <svg width="100%" height="100%" className="absolute inset-0">
                            <defs>
                                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                                    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(75, 85, 99, 0.5)" strokeWidth="0.5"/>
                                </pattern>
                            </defs>
                            <rect width="100%" height="100%" fill="url(#grid)" />
                            {/* Render connections */}
                            {connections.map(conn => {
                                const sourceNode = nodes.find(n => n.id === conn.sourceId);
                                const targetNode = nodes.find(n => n.id === conn.targetId);
                                if (!sourceNode || !targetNode) return null;
                                const sourceX = sourceNode.position.x + (conn.sourceHandle === 'left' ? 0 : 224);
                                const sourceY = sourceNode.position.y + 48;
                                const targetX = targetNode.position.x + (conn.targetHandle === 'left' ? 0 : 224);
                                const targetY = targetNode.position.y + 48;
                                const d = `M ${sourceX} ${sourceY} C ${sourceX + 100} ${sourceY}, ${targetX - 100} ${targetY}, ${targetX} ${targetY}`;
                                return <path key={conn.id} d={d} stroke="#9CA3AF" strokeWidth="2" fill="none" />;
                            })}
                             {/* Render connecting line */}
                            {connecting && <path d={`M ${connecting.startPos.x} ${connecting.startPos.y} L ${connecting.currentPos.x} ${connecting.currentPos.y}`} stroke="#A5B4FC" strokeWidth="2" fill="none" strokeDasharray="5,5" />}
                        </svg>

                        <div className="relative w-full h-full">
                            {nodes.map(node => (
                                <WorkflowNodeComponent 
                                    key={node.id} 
                                    node={node} 
                                    isSelected={node.id === selectedNodeId}
                                    onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                                    onHandleMouseDown={handleHandleMouseDown}
                                    onHandleMouseUp={handleHandleMouseUp}
                                />
                            ))}
                        </div>
                    </div>
                     <SystemLogPanel logEntries={log} />
                </main>
                <OrchestrationSidePanel 
                    node={selectedNode}
                    onEditAgent={(agent) => handleOpenEditor(agent)}
                    onDeleteNode={(id) => {
                        setNodes(prev => prev.filter(n => n.id !== id));
                        setConnections(prev => prev.filter(c => c.sourceId !== id && c.targetId !== id));
                        addLog(`Deleted node ${nodes.find(n=>n.id===id)?.label}.`, 'warn');
                    }}
                />
            </div>
        </div>
    );
};

export default OrchestrationView;