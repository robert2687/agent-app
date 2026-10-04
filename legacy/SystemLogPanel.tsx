import React from 'react';
import type { SystemLogEntry } from '../types';

interface SystemLogPanelProps {
    logEntries: SystemLogEntry[];
}

const LEVEL_COLORS = {
    info: 'text-gray-400',
    warn: 'text-yellow-400',
    error: 'text-red-400',
};

const SystemLogPanel: React.FC<SystemLogPanelProps> = ({ logEntries }) => {
    return (
        <div className="h-40 bg-gray-900 border-t border-gray-700 flex flex-col flex-shrink-0">
            <header className="px-4 py-1 border-b border-gray-700">
                <h4 className="text-sm font-semibold text-gray-300">System Log</h4>
            </header>
            <div className="flex-1 p-2 overflow-y-auto font-mono text-xs">
                {logEntries.length === 0 && <p className="text-gray-500">Log is empty. Actions will be recorded here.</p>}
                {logEntries.map(entry => (
                    <div key={entry.id} className={`flex gap-2 ${LEVEL_COLORS[entry.level]}`}>
                        <span className="text-gray-500 flex-shrink-0">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                        <p className="flex-grow whitespace-pre-wrap">{entry.message}</p>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default SystemLogPanel;
