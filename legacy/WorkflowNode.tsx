import React from 'react';
import type { WorkflowNode, WorkflowNodeType, Agent, DataSourceConfiguration } from '../../types';

const NODE_STYLES: Record<WorkflowNodeType, { bg: string; border: string; icon: JSX.Element; }> = {
    DataSource: {
        bg: 'bg-sky-900/50',
        border: 'border-sky-400',
        icon: <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 14.25h13.5m-13.5 0a3 3 0 0 1-3-3V7.5a3 3 0 0 1 3-3h13.5a3 3 0 0 1 3 3v3.75a3 3 0 0 1-3 3m-13.5 0-1.125-1.125" />
    },
    Agent: {
        bg: 'bg-indigo-900/50',
        border: 'border-indigo-400',
        icon: <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
    },
    Input: {
        bg: 'bg-green-900/50',
        border: 'border-green-400',
        icon: <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
    },
    Output: {
        bg: 'bg-amber-900/50',
        border: 'border-amber-400',
        icon: <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
    },
    Tool: {
        bg: 'bg-slate-900/50',
        border: 'border-slate-400',
        icon: <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75a4.5 4.5 0 0 1-4.884 4.484c-1.076-.091-2.264.071-2.95.904l-7.152 8.684a2.548 2.548 0 1 1-3.586-3.586l8.684-7.152c.833-.686.995-1.874.904-2.95a4.5 4.5 0 0 1 6.336-6.336Z" />
    }
};

interface WorkflowNodeProps {
    node: WorkflowNode;
    isSelected: boolean;
    onMouseDown: (e: React.MouseEvent) => void;
    onHandleMouseDown: (e: React.MouseEvent, nodeId: string, handle: 'left' | 'right') => void;
    onHandleMouseUp: (e: React.MouseEvent, nodeId: string, handle: 'left' | 'right') => void;
}

export const WorkflowNodeComponent: React.FC<WorkflowNodeProps> = ({ node, isSelected, onMouseDown, onHandleMouseDown, onHandleMouseUp }) => {
    const style = NODE_STYLES[node.type];
    const data = node.data;

    const renderDescription = () => {
        switch (node.type) {
            case 'DataSource':
                return `Type: ${(data as DataSourceConfiguration).source_type}`;
            case 'Agent':
                return (data as Agent).role_type || (data as Agent).description;
            case 'Input':
            case 'Output':
                return 'System Node';
            default:
                return `ID: ${node.id}`;
        }
    };

    return (
        <div
            onMouseDown={onMouseDown}
            className={`absolute ${style.bg} border-2 ${isSelected ? 'ring-2 ring-offset-2 ring-offset-gray-800 ring-indigo-400' : style.border} rounded-lg shadow-xl cursor-grab active:cursor-grabbing text-white w-56 h-24 p-3 flex flex-col justify-between transition-all duration-150 ease-in-out hover:shadow-2xl hover:scale-105`}
            style={{ left: `${node.position.x}px`, top: `${node.position.y}px` }}
        >
            <div className="flex items-center gap-2">
                <svg className={`w-5 h-5 flex-shrink-0 ${style.border.replace('border-','text-')}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    {style.icon}
                </svg>
                <div className="font-bold truncate">{node.label}</div>
            </div>
            <div className="text-xs text-gray-400 truncate">
                {renderDescription()}
            </div>

            {/* Connection Handles */}
            <div 
                className="absolute -left-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-gray-400 border-2 border-gray-900 hover:bg-indigo-400 cursor-crosshair z-10"
                onMouseDown={(e) => onHandleMouseDown(e, node.id, 'left')}
                onMouseUp={(e) => onHandleMouseUp(e, node.id, 'left')}
            ></div>
            <div 
                className="absolute -right-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-gray-400 border-2 border-gray-900 hover:bg-indigo-400 cursor-crosshair z-10"
                onMouseDown={(e) => onHandleMouseDown(e, node.id, 'right')}
                 onMouseUp={(e) => onHandleMouseUp(e, node.id, 'right')}
            ></div>
        </div>
    );
};
