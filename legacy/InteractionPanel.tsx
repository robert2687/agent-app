import React, { useState, useRef, useEffect, useCallback } from 'react';
import type { ChatMessage, AgentConfig, Source } from '../types';
import { Spinner } from './ui/Spinner';

const MessageBubble: React.FC<{ message: ChatMessage }> = ({ message }) => {
    const isModel = message.role === 'model';
    const bubbleClasses = isModel
        ? 'bg-gray-700/50 text-gray-200 self-start rounded-tr-xl rounded-bl-xl rounded-br-xl'
        : 'bg-indigo-600 text-white self-end rounded-tl-xl rounded-bl-xl rounded-br-xl';
    
    const containerClasses = isModel ? 'flex justify-start' : 'flex justify-end';

    const formatContent = (text: string) => {
      let formattedText = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code class="bg-gray-800 text-indigo-300 px-1 py-0.5 rounded">$1</code>');
      return { __html: formattedText };
    };

    return (
        <div className={`${containerClasses} mb-4`}>
            <div className={`p-4 max-w-xl lg:max-w-3xl ${bubbleClasses} shadow-md`}>
                <div className="text-base whitespace-pre-wrap" dangerouslySetInnerHTML={formatContent(message.content)}></div>
                {message.sources && message.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-600/50">
                        <h4 className="text-xs font-semibold text-gray-400 mb-2">Sources:</h4>
                        <ul className="space-y-1">
                            {message.sources.map((source, index) => (
                                <li key={index}>
                                    <a
                                        href={source.uri}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-indigo-400 hover:text-indigo-300 text-sm flex items-center gap-1.5 group"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                                          <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" /><path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
                                        </svg>
                                        <span className="truncate group-hover:underline">{source.title || new URL(source.uri).hostname}</span>
                                    </a>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
};

interface InteractionPanelProps {
    agentConfig: AgentConfig | null;
    messages: ChatMessage[];
    isLoading: boolean;
    error: string | null;
    onSendMessage: (input: string) => Promise<void>;
}

const InteractionPanel: React.FC<InteractionPanelProps> = ({ agentConfig, messages, isLoading, error, onSendMessage }) => {
    const [input, setInput] = useState('');
    const [toolCallMessage, setToolCallMessage] = useState<string | null>(null);
    const chatContainerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
        }
    }, [messages, toolCallMessage]);

    const handleFormSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;
        onSendMessage(input);
        setInput('');
    };
    
    const isChatDisabled = !agentConfig;

    return (
        <main className="flex-1 flex flex-col p-4 bg-gray-900">
            <header className="mb-4">
                <h2 className="text-xl font-semibold text-white">
                    {agentConfig ? `Chat with: ${agentConfig.name}` : 'Awaiting Agent...'}
                </h2>
                <p className="text-sm text-gray-400">
                    {agentConfig ? 'Your agent is ready.' : 'Configure and create an agent to begin.'}
                </p>
            </header>

            <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4 rounded-lg bg-gray-800/50">
                {isChatDisabled && (
                    <div className="flex items-center justify-center h-full">
                        <div className="text-center text-gray-500">
                            <svg xmlns="http://www.w3.org/2000/svg" className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5-2.5-7S3 7 3 7a8 8 0 0014.657 11.657z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.879 16.121A3 3 0 1014.12 11.88a3 3 0 00-4.242 4.242z" />
                            </svg>
                            <p className="mt-2">Use the builder to create an AI agent.</p>
                        </div>
                    </div>
                )}
                {messages.map((msg, index) => (
                    <MessageBubble key={index} message={msg} />
                ))}
                {isLoading && (
                  <div className="flex justify-start mb-4">
                    <div className="p-4 max-w-xl lg:max-w-3xl bg-gray-700/50 text-gray-200 self-start rounded-tr-xl rounded-bl-xl rounded-br-xl shadow-md flex items-center gap-3">
                      <Spinner />
                      <span>{toolCallMessage || 'Thinking...'}</span>
                    </div>
                  </div>
                )}
            </div>
            {error && <div className="p-2 my-2 text-sm text-red-400 bg-red-900/50 rounded-md">{error}</div>}
            
            <div className="mt-4">
              <form onSubmit={handleFormSubmit} className="flex items-center space-x-2">
                  <input
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      placeholder={isChatDisabled ? "Create an agent to start chatting" : "Type your message here..."}
                      disabled={isLoading || isChatDisabled}
                      className="flex-1 p-3 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none transition disabled:opacity-50"
                  />
                  <button
                      type="submit"
                      disabled={isLoading || !input.trim() || isChatDisabled}
                      className="px-6 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
                  >
                      {isLoading ? <Spinner /> : 'Send'}
                  </button>
              </form>
            </div>
        </main>
    );
};

export default InteractionPanel;