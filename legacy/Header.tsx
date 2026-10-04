import React from 'react';
import { Agent } from '../types';
import AgentSelector from './AgentSelector';

interface HeaderProps {
    activeAgent: Agent;
    onAgentChange: (agent: Agent) => void;
}

const Header: React.FC<HeaderProps> = ({ activeAgent, onAgentChange }) => {
    return (
        <header className="bg-slate-800/50 backdrop-blur-sm border-b border-slate-700 p-4 shadow-md z-10">
            <div className="max-w-4xl mx-auto flex items-center justify-between">
                <h1 className="text-xl font-bold text-slate-100">AI Agent System</h1>
                <AgentSelector activeAgent={activeAgent} onAgentChange={onAgentChange} />
            </div>
        </header>
    );
};

export default Header;
