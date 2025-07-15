import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AIAgentDigitalTwin, getDefaultTwinState } from '../services/digitalTwinService';
import type { DigitalTwinState, IAI_Agent_DigitalTwin } from '../types';
import { Spinner } from './ui/Spinner';

const Accordion: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => {
    const [isOpen, setIsOpen] = useState(false);
    return (
        <div className="border border-gray-700 rounded-lg">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex justify-between items-center p-3 bg-gray-700/50 hover:bg-gray-700 transition-colors"
            >
                <h3 className="font-semibold text-gray-200">{title}</h3>
                <svg className={`w-5 h-5 transform transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
            </button>
            {isOpen && <div className="p-3 bg-gray-800/50">{children}</div>}
        </div>
    );
};

const DigitalTwinView: React.FC = () => {
    const [twin, setTwin] = useState<IAI_Agent_DigitalTwin | null>(null);
    const [twinState, setTwinState] = useState<DigitalTwinState | null>(null);
    const [configDraft, setConfigDraft] = useState<string>(JSON.stringify(getDefaultTwinState(), null, 2));
    const [userInput, setUserInput] = useState<string>("Hello, what's the return policy?");
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const stateDisplayRef = useRef<HTMLDivElement>(null);
    const [log, setLog] = useState<{ role: 'user' | 'agent', content: string }[]>([]);

    useEffect(() => {
        handleInitializeOrUpdate();
    }, []);

    useEffect(() => {
        if(stateDisplayRef.current) {
            stateDisplayRef.current.classList.remove('animate-highlight');
            void stateDisplayRef.current.offsetWidth; // Trigger reflow
            stateDisplayRef.current.classList.add('animate-highlight');
        }
    }, [twinState]);

    const handleInitializeOrUpdate = useCallback(() => {
        try {
            setError(null);
            const parsedConfig = JSON.parse(configDraft);
            const newTwin = new AIAgentDigitalTwin(parsedConfig);
            setTwin(newTwin);
            const newTwinState = newTwin.getTwinState();
            setTwinState(newTwinState);
            setLog([]);
        } catch (e) {
            console.error("Config parse error:", e);
            setError("Invalid JSON configuration. Please check the syntax.");
        }
    }, [configDraft]);

    const handleProcessInteraction = useCallback(async (reward?: number) => {
        if (!twin || !userInput.trim()) return;
        setIsLoading(true);
        setError(null);
        setLog(prev => [...prev, { role: 'user', content: userInput }]);

        try {
            const feedback = reward !== undefined ? { reward } : undefined;
            const result = await twin.processInteraction(userInput, feedback);
            setTwinState(result.updatedState);
            setLog(prev => [...prev, { role: 'agent', content: result.output }]);
            setUserInput('');
        } catch (e) {
            console.error("Processing error:", e);
            const errorMessage = e instanceof Error ? e.message : 'An unknown error occurred.';
            setError(`Failed to process interaction: ${errorMessage}`);
        } finally {
            setIsLoading(false);
        }
    }, [twin, userInput]);

    const handleReset = useCallback(() => {
        if (!twin) return;
        setTwinState(twin.resetOperationalState());
        setLog([]);
        setError(null);
    }, [twin]);
    
    return (
        <div className="h-full flex flex-col md:flex-row bg-gray-900 text-gray-100">
            {/* --- CONFIGURATION PANEL --- */}
            <aside className="w-full md:w-1/2 lg:w-2/5 p-4 border-r border-gray-700 overflow-y-auto space-y-4">
                <h2 className="text-2xl font-bold text-white">Digital Twin Configuration</h2>
                <p className="text-sm text-gray-400">Define the agent's core components. Press 'Apply' to update the simulation.</p>
                <div className="space-y-2">
                     <button onClick={handleInitializeOrUpdate} className="w-full p-2 bg-indigo-600 hover:bg-indigo-700 rounded-md font-semibold transition-colors">Apply Configuration</button>
                     <button onClick={() => setConfigDraft(JSON.stringify(getDefaultTwinState(), null, 2))} className="w-full p-2 bg-gray-600 hover:bg-gray-700 rounded-md font-semibold transition-colors">Reset to Default</button>
                </div>
                {error && <div className="p-2 text-sm text-red-400 bg-red-900/50 rounded-md">{error}</div>}
                <textarea
                    value={configDraft}
                    onChange={e => setConfigDraft(e.target.value)}
                    className="w-full h-96 p-2 bg-gray-800 border border-gray-600 rounded-lg font-mono text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    spellCheck="false"
                />
            </aside>

            {/* --- INTERACTION & OBSERVATION PANEL --- */}
            <main className="flex-1 p-4 flex flex-col overflow-hidden">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-2xl font-bold text-white">Simulation Environment</h2>
                    <button onClick={handleReset} disabled={!twin} className="px-4 py-2 bg-gray-600 text-sm font-semibold rounded-lg hover:bg-gray-700 disabled:bg-gray-800 disabled:cursor-not-allowed">Reset State</button>
                </div>
                
                {/* Interaction Area */}
                <div className="bg-gray-800/50 p-4 rounded-lg space-y-3">
                    <div className="flex space-x-2">
                        <input
                            type="text"
                            value={userInput}
                            onChange={e => setUserInput(e.target.value)}
                            placeholder="Type user input..."
                            disabled={isLoading || !twin}
                            className="flex-1 p-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                        />
                        <button onClick={() => handleProcessInteraction()} disabled={isLoading || !twin || !userInput.trim()} className="px-4 py-2 bg-indigo-600 font-semibold rounded-lg hover:bg-indigo-700 disabled:bg-gray-600">
                            {isLoading ? <Spinner /> : "Process"}
                        </button>
                    </div>
                    <div className="flex items-center justify-end space-x-2">
                        <span className="text-xs text-gray-400">Provide RL Feedback (optional):</span>
                        <button onClick={() => handleProcessInteraction(1)} disabled={isLoading || !twin || !userInput.trim()} className="px-3 py-1 text-xs bg-green-600/50 hover:bg-green-600 rounded-md">Good [+1]</button>
                        <button onClick={() => handleProcessInteraction(0)} disabled={isLoading || !twin || !userInput.trim()} className="px-3 py-1 text-xs bg-gray-600/50 hover:bg-gray-600 rounded-md">Neutral [0]</button>
                        <button onClick={() => handleProcessInteraction(-1)} disabled={isLoading || !twin || !userInput.trim()} className="px-3 py-1 text-xs bg-red-600/50 hover:bg-red-600 rounded-md">Bad [-1]</button>
                    </div>
                </div>

                {/* Log and State */}
                <div className="flex-1 mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4 overflow-hidden">
                    {/* Log */}
                    <div className="flex flex-col bg-gray-800/50 rounded-lg p-4 overflow-hidden">
                         <h3 className="text-lg font-bold text-indigo-400 mb-2 flex-shrink-0">Interaction Log</h3>
                         <div className="flex-1 overflow-y-auto space-y-2 pr-2">
                            {log.map((entry, i) => (
                                <div key={i} className={`p-2 rounded-md text-sm ${entry.role === 'user' ? 'bg-indigo-900/50' : 'bg-gray-700/50'}`}>
                                    <span className={`font-bold ${entry.role === 'user' ? 'text-indigo-300' : 'text-gray-300'}`}>{entry.role === 'user' ? 'User' : 'Agent'}: </span>
                                    {entry.content}
                                </div>
                            ))}
                            {isLoading && <div className="p-2 flex justify-center"><Spinner /></div>}
                         </div>
                    </div>
                    {/* State Inspector */}
                    <div ref={stateDisplayRef} className="flex flex-col bg-gray-800/50 rounded-lg p-4 overflow-hidden">
                        <h3 className="text-lg font-bold text-indigo-400 mb-2 flex-shrink-0">State Inspector</h3>
                        {twinState && (
                            <div className="flex-1 overflow-y-auto">
                                <div className="bg-gray-900/70 p-2 rounded mb-2">
                                    <h4 className="font-semibold text-gray-300">Last Decision Path:</h4>
                                    <ul className="text-xs text-yellow-400 list-disc list-inside">
                                        {twinState.lastDecisionPath.map((path, i) => <li key={i}>{path}</li>)}
                                    </ul>
                                </div>
                                <pre className="text-xs w-full"><code>{JSON.stringify(twinState, null, 2)}</code></pre>
                            </div>
                        )}
                        {!twinState && <div className="text-center text-gray-500">Initialize agent to see state.</div>}
                    </div>
                </div>
            </main>
        </div>
    );
};

export default DigitalTwinView;