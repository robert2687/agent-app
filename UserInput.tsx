import React, { useState, KeyboardEvent, useRef, useEffect } from 'react';
import { Agent } from '../types';
import SendIcon from './icons/SendIcon';

interface UserInputProps {
    onSendMessage: (text: string) => void;
    isLoading: boolean;
    activeAgent: Agent;
}

const agentPlaceholders: Record<Agent, string> = {
    [Agent.Default]: "Type a message or /imagine <prompt>...",
    [Agent.SystemsArchitect]: "e.g., I want to build an AI fitness trainer",
    [Agent.BehavioralModeler]: "e.g., Design a personality for a witty trivia host AI",
    [Agent.DigitalTwin]: "e.g., Model the cash flow for a small coffee shop",
    [Agent.ApiIntegration]: "e.g., Write a function to get the weather for Paris",
};

const UserInput: React.FC<UserInputProps> = ({ onSendMessage, isLoading, activeAgent }) => {
    const [text, setText] = useState('');
    const textAreaRef = useRef<HTMLTextAreaElement>(null);

    const handleSend = () => {
        if (text.trim() && !isLoading) {
            onSendMessage(text);
            setText('');
        }
    };

    const handleKeyPress = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    useEffect(() => {
        const textArea = textAreaRef.current;
        if (textArea) {
            textArea.style.height = 'auto';
            const scrollHeight = textArea.scrollHeight;
            textArea.style.height = `${scrollHeight}px`;
        }
    }, [text]);

    return (
        <footer className="bg-slate-800/70 backdrop-blur-sm border-t border-slate-700 p-4">
            <div className="max-w-4xl mx-auto flex items-start gap-4">
                <textarea
                    ref={textAreaRef}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder={agentPlaceholders[activeAgent] || "Type a message..."}
                    className="flex-1 bg-slate-900 border border-slate-600 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none transition-all duration-200 disabled:opacity-50"
                    rows={1}
                    style={{ maxHeight: '200px' }}
                    disabled={isLoading}
                    aria-label="Chat input"
                />
                <button
                    onClick={handleSend}
                    disabled={isLoading || !text.trim()}
                    className="bg-blue-600 text-white rounded-full p-3 hover:bg-blue-500 disabled:bg-slate-600 disabled:cursor-not-allowed transition-colors duration-200 flex-shrink-0 self-end"
                    aria-label="Send message"
                >
                    <SendIcon />
                </button>
            </div>
        </footer>
    );
};

export default UserInput;
