
import React, { useState, useCallback } from 'react';
import { generateAgentResponseStream } from '../services/geminiService';
import { Spinner } from './ui/Spinner';

const AgentView: React.FC = () => {
    const [goal, setGoal] = useState<string>('Write a short, engaging blog post comparing the pros and cons of server-side rendering (SSR) vs. client-side rendering (CSR) for web development.');
    const [result, setResult] = useState<string>('');
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const handleExecuteGoal = useCallback(async (e: React.FormEvent) => {
        e.preventDefault();
        if (!goal.trim() || isLoading) return;

        setIsLoading(true);
        setError(null);
        setResult('');

        try {
            const stream = await generateAgentResponseStream(goal);
            
            let currentResponse = '';
            for await (const chunk of stream) {
                currentResponse += chunk.text;
                setResult(currentResponse);
            }
        } catch (err) {
            console.error(err);
            const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred.';
            setError(`Agent failed to execute: ${errorMessage}`);
        } finally {
            setIsLoading(false);
        }
    }, [goal, isLoading]);
    
    // Simple markdown to HTML conversion for headers, bold, and code.
    // Relies on `whitespace-pre-wrap` for lists and paragraphs.
    const formatAgentOutput = (text: string) => {
        const html = text
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/### (.*)/g, '<h3 class="text-xl font-semibold text-indigo-400 mt-6 mb-3">$1</h3>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/`([^`]+)`/g, '<code class="bg-gray-700 text-indigo-300 px-1.5 py-1 rounded-md font-mono text-sm">$1</code>');
        return { __html: html };
    };

    return (
        <div className="p-4 sm:p-6 md:p-8 h-full flex flex-col">
            <div className="text-center mb-6">
                <h2 className="text-3xl font-bold text-white">Task Execution Agent</h2>
                <p className="text-gray-400 mt-2">Give the agent a complex goal and watch it create a plan and execute it.</p>
            </div>

            <div className="w-full max-w-4xl mx-auto flex flex-col flex-1">
                <form onSubmit={handleExecuteGoal} className="space-y-4">
                    <div>
                        <label htmlFor="goal" className="block text-sm font-medium text-gray-300 mb-1">
                            Agent's Goal
                        </label>
                        <textarea
                            id="goal"
                            rows={3}
                            value={goal}
                            onChange={(e) => setGoal(e.target.value)}
                            placeholder="e.g., Plan a 3-day trip to Paris..."
                            disabled={isLoading}
                            className="w-full p-3 bg-gray-800 border border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none transition font-mono text-sm"
                        />
                    </div>
                    <div className="text-right">
                        <button
                            type="submit"
                            disabled={isLoading || !goal.trim()}
                            className="w-full sm:w-auto px-8 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors flex justify-center items-center sm:float-right"
                        >
                            {isLoading ? <Spinner /> : 'Execute Task'}
                        </button>
                    </div>
                </form>

                <div className="flex-1 mt-6">
                    {isLoading && !result && (
                        <div className="flex justify-center items-center h-full">
                           <div className="text-center">
                               <Spinner size="lg"/>
                               <p className="mt-4 text-gray-400">Agent is starting up...</p>
                           </div>
                        </div>
                    )}

                    {error && (
                        <div className="text-center p-4 my-4 text-sm text-red-400 bg-red-900/50 rounded-md">
                            {error}
                        </div>
                    )}

                    {(result || isLoading) && (
                        <div className="bg-gray-800/50 rounded-lg p-6 animate-fade-in space-y-6">
                            <div 
                                className="whitespace-pre-wrap text-gray-300 font-sans"
                                dangerouslySetInnerHTML={formatAgentOutput(result)}
                            ></div>
                            {isLoading && <Spinner />}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AgentView;
