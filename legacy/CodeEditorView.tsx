
import React, { useState, useCallback } from 'react';
import { generateCodeSuggestion } from '../services/geminiService';
import { Spinner } from './ui/Spinner';

const initialCode = `import React, { useState } from 'react';

const SimpleComponent = () => {
  return (
    <div className="p-4 border rounded-lg">
      <h1 className="text-xl font-bold">My Component</h1>
      <p>This is a simple React component.</p>
    </div>
  );
};

export default SimpleComponent;
`;

const CodeEditorView: React.FC = () => {
    const [code, setCode] = useState<string>(initialCode);
    const [instruction, setInstruction] = useState<string>("Add a state variable 'count' initialized to 0, and two buttons to increment and decrement it.");
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const handleSuggest = useCallback(async (e: React.FormEvent) => {
        e.preventDefault();
        if (!instruction.trim() || isLoading) return;

        setIsLoading(true);
        setError(null);

        try {
            const result = await generateCodeSuggestion(code, instruction);
            setCode(result.newCode);
        } catch (err) {
            console.error(err);
            const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred.';
            setError(`Failed to get suggestion: ${errorMessage}`);
        } finally {
            setIsLoading(false);
        }
    }, [code, instruction, isLoading]);

    return (
        <div className="p-4 sm:p-6 md:p-8 h-full flex flex-col">
            <div className="text-center mb-6">
                <h2 className="text-3xl font-bold text-white">AI Code Assistant</h2>
                <p className="text-gray-400 mt-2">Write or paste your code, then tell the AI what changes to make.</p>
            </div>

            <div className="w-full max-w-6xl mx-auto flex flex-col flex-1 gap-6">
                <div className="flex-1 flex flex-col">
                    <label htmlFor="code-editor" className="block text-sm font-medium text-gray-300 mb-1">
                        Code Editor
                    </label>
                    <textarea
                        id="code-editor"
                        value={code}
                        onChange={(e) => setCode(e.target.value)}
                        placeholder="Your code here..."
                        disabled={isLoading}
                        className="w-full flex-1 p-3 bg-gray-800 border border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none transition font-mono text-sm resize-none"
                        spellCheck="false"
                    />
                </div>
                
                <form onSubmit={handleSuggest} className="space-y-3">
                     <div>
                        <label htmlFor="instruction" className="block text-sm font-medium text-gray-300 mb-1">
                            Instruction
                        </label>
                        <textarea
                            id="instruction"
                            rows={2}
                            value={instruction}
                            onChange={(e) => setInstruction(e.target.value)}
                            placeholder="e.g., Refactor this into a function component..."
                            disabled={isLoading}
                            className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none transition"
                        />
                    </div>
                    <div className="flex justify-end items-center gap-4">
                         {error && (
                            <div className="text-sm text-red-400 text-left flex-1">
                                {error}
                            </div>
                        )}
                        <button
                            type="submit"
                            disabled={isLoading || !instruction.trim()}
                            className="w-full sm:w-auto px-8 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors flex justify-center items-center"
                        >
                            {isLoading ? <Spinner /> : 'Generate Code'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default CodeEditorView;
