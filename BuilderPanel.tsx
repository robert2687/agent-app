import React, { useState } from 'react';
import type { AgentConfig } from '../types';

interface BuilderPanelProps {
  onCreateAgent: (config: AgentConfig) => void;
}

const Toggle: React.FC<{label: string, enabled: boolean, onChange: (enabled: boolean) => void}> = ({label, enabled, onChange}) => (
    <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-gray-300 select-none">
            {label}
        </label>
        <button
            type="button"
            onClick={() => onChange(!enabled)}
            role="switch"
            aria-checked={enabled}
            className={`${
                enabled ? 'bg-indigo-600' : 'bg-gray-600'
            } relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-900`}
        >
            <span
                aria-hidden="true"
                className={`${
                    enabled ? 'translate-x-5' : 'translate-x-0'
                } pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out`}
            />
        </button>
    </div>
);


const BuilderPanel: React.FC<BuilderPanelProps> = ({ onCreateAgent }) => {
  const [name, setName] = useState('Math Tutor');
  const [systemInstruction, setSystemInstruction] = useState('You are a friendly and patient math tutor for high school students. You must use the calculator tool for any calculations.');
  const [useCalculator, setUseCalculator] = useState(true);
  const [useSearch, setUseSearch] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onCreateAgent({
      name,
      systemInstruction,
      tools: { useCalculator, useSearch },
    });
  };

  return (
    <aside className="w-full md:w-96 lg:w-1/3 bg-gray-800 p-4 border-r border-gray-700 overflow-y-auto">
      <div className="sticky top-0 p-1">
        <h2 className="text-xl font-bold text-white mb-4">Agent Configuration</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="agent-name" className="block text-sm font-medium text-gray-300 mb-1">
              Agent Name
            </label>
            <input
              id="agent-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Travel Planner"
              className="w-full p-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none transition"
              required
            />
          </div>
          <div>
            <label htmlFor="system-instruction" className="block text-sm font-medium text-gray-300 mb-1">
              Persona & Instructions
            </label>
            <textarea
              id="system-instruction"
              rows={8}
              value={systemInstruction}
              onChange={(e) => setSystemInstruction(e.target.value)}
              placeholder="Define the agent's role and behavior..."
              className="w-full p-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none transition font-mono text-sm"
              required
            />
          </div>
          <div className="space-y-3 p-3 bg-gray-900/50 rounded-lg">
             <h3 className="font-semibold text-gray-200">Tools</h3>
             <Toggle label="Enable Calculator" enabled={useCalculator} onChange={setUseCalculator} />
             <Toggle label="Enable Web Search" enabled={useSearch} onChange={setUseSearch} />
          </div>
          <div>
            <button
              type="submit"
              className="w-full px-6 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 disabled:bg-gray-600 transition-colors"
            >
              Create Agent
            </button>
          </div>
        </form>
      </div>
    </aside>
  );
};

export default BuilderPanel;