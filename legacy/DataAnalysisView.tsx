import React, { useState, useCallback } from 'react';
import { analyzeData } from '../services/geminiService';
import type { AnalysisResult } from '../types';
import { Spinner } from './ui/Spinner';

const placeholderCsv = `City,Country,Population
New York,USA,8400000
London,UK,8900000
Tokyo,Japan,14000000
`;

const DataAnalysisView: React.FC = () => {
    const [csvData, setCsvData] = useState<string>(placeholderCsv);
    const [question, setQuestion] = useState<string>('Which city has the highest population?');
    const [result, setResult] = useState<AnalysisResult | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const handleAnalyze = useCallback(async (e: React.FormEvent) => {
        e.preventDefault();
        if (!csvData.trim() || !question.trim() || isLoading) return;

        setIsLoading(true);
        setError(null);
        setResult(null);

        try {
            const analysisResult = await analyzeData(csvData, question);
            setResult(analysisResult);
        } catch (err) {
            console.error(err);
            const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred.';
            setError(`Failed to get analysis: ${errorMessage}`);
        } finally {
            setIsLoading(false);
        }
    }, [csvData, question, isLoading]);

    return (
        <div className="p-4 sm:p-6 md:p-8 h-full flex flex-col">
            <div className="text-center mb-6">
                <h2 className="text-3xl font-bold text-white">Data Analysis Agent</h2>
                <p className="text-gray-400 mt-2">Paste your CSV data, ask a question, and get an AI-powered analysis.</p>
            </div>

            <div className="w-full max-w-4xl mx-auto flex flex-col flex-1">
                <form onSubmit={handleAnalyze} className="space-y-4">
                    <div>
                        <label htmlFor="csv-data" className="block text-sm font-medium text-gray-300 mb-1">
                            CSV Data
                        </label>
                        <textarea
                            id="csv-data"
                            rows={8}
                            value={csvData}
                            onChange={(e) => setCsvData(e.target.value)}
                            placeholder="Paste your CSV data here..."
                            disabled={isLoading}
                            className="w-full p-3 bg-gray-800 border border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none transition font-mono text-sm"
                        />
                    </div>
                    <div>
                        <label htmlFor="question" className="block text-sm font-medium text-gray-300 mb-1">
                            Your Question
                        </label>
                        <input
                            id="question"
                            type="text"
                            value={question}
                            onChange={(e) => setQuestion(e.target.value)}
                            placeholder="e.g., What is the average value?"
                            disabled={isLoading}
                            className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none transition"
                        />
                    </div>
                    <div className="text-right">
                        <button
                            type="submit"
                            disabled={isLoading || !csvData.trim() || !question.trim()}
                            className="w-full sm:w-auto px-8 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors flex justify-center items-center sm:float-right"
                        >
                            {isLoading ? <Spinner /> : 'Analyze Data'}
                        </button>
                    </div>
                </form>

                <div className="flex-1 mt-6">
                    {isLoading && (
                        <div className="flex justify-center items-center h-full">
                           <div className="text-center">
                               <Spinner size="lg"/>
                               <p className="mt-4 text-gray-400">Analyzing data... the agent is thinking.</p>
                           </div>
                        </div>
                    )}

                    {error && (
                        <div className="text-center p-4 my-4 text-sm text-red-400 bg-red-900/50 rounded-md">
                            {error}
                        </div>
                    )}

                    {result && (
                        <div className="bg-gray-800/50 rounded-lg p-6 animate-fade-in space-y-6">
                            <div>
                                <h3 className="text-lg font-semibold text-indigo-400 mb-2">Direct Answer</h3>
                                <p className="text-gray-200 text-xl">{result.answer}</p>
                            </div>
                            
                            <div className="pt-6 border-t border-gray-700">
                                <h3 className="text-lg font-semibold text-indigo-400 mb-2">Summary</h3>
                                <p className="text-gray-300">{result.summary}</p>
                            </div>
                            
                            <div className="pt-6 border-t border-gray-700">
                                <h3 className="text-lg font-semibold text-indigo-400 mb-2">Key Findings</h3>
                                <ul className="list-disc list-inside space-y-2 text-gray-300">
                                    {result.keyFindings.map((finding, index) => (
                                        <li key={index}>{finding}</li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default DataAnalysisView;