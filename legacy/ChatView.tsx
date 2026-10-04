import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ChatMessage, Source } from '../types';
import { generateChatResponseStream } from '../services/geminiService';
import { Spinner } from './ui/Spinner';

const MessageBubble: React.FC<{ message: ChatMessage }> = ({ message }) => {
    const isModel = message.role === 'model';
    const bubbleClasses = isModel
        ? 'bg-gray-700 text-gray-200 self-start rounded-tr-xl rounded-bl-xl rounded-br-xl'
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
                                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 flex-shrink-0 text-gray-400 group-hover:text-indigo-300" viewBox="0 0 20 20" fill="currentColor">
                                          <path fillRule="evenodd" d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0l-1.5-1.5a2 2 0 112.828-2.828l1.5 1.5a.5.5 0 00.707 0l3.001-3a.5.5 0 00-.708-.707l-3 3a2 2 0 01-2.828 0l-1.5-1.5a2 2 0 112.828-2.828l3-3a2 2 0 012.828 2.828l-3 3a2 2 0 01-2.828 0l-1.5-1.5a.5.5 0 00-.707.707l1.5 1.5z" clipRule="evenodd" />
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

const Toggle: React.FC<{label: string, enabled: boolean, onChange: (enabled: boolean) => void}> = ({label, enabled, onChange}) => (
    <div className="flex items-center justify-end gap-2">
        <label htmlFor={`${label}-toggle`} className="text-sm font-medium text-gray-300 cursor-pointer select-none">
            {label}
        </label>
        <button
            type="button"
            id={`${label}-toggle`}
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

const ChatView: React.FC = () => {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [useSearch, setUseSearch] = useState(false);
    const [useTools, setUseTools] = useState(false);
    const [toolCallMessage, setToolCallMessage] = useState<string | null>(null);

    const chatContainerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        setMessages([{ role: 'model', content: "Hello! How can I help you today? Ask me anything, or toggle on 'Search the web' for up-to-date info or 'Use Tools' for calculations!" }]);
    }, []);

    useEffect(() => {
        if (chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
        }
    }, [messages, toolCallMessage]);

    const handleSendMessage = useCallback(async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const newUserMessage: ChatMessage = { role: 'user', content: input };
        const updatedMessages = [...messages, newUserMessage];
        
        setMessages(updatedMessages);
        setInput('');
        setIsLoading(true);
        setError(null);
        setToolCallMessage(null);

        try {
            const onToolCall = (name: string, args: any) => {
                 setToolCallMessage(`🤖 Using tool: ${name}...`);
            };

            const stream = await generateChatResponseStream(updatedMessages, useSearch, useTools, onToolCall);
            
            setToolCallMessage(null); // Clear tool message once stream starts
            
            let currentResponse = '';
            setMessages(prev => [...prev, { role: 'model', content: '' }]);

            for await (const chunk of stream) {
                currentResponse += chunk.text;
                setMessages(prev => {
                    const newMessages = [...prev];
                    newMessages[newMessages.length - 1].content = currentResponse;
                    return newMessages;
                });
            }
            
            const finalResponse = await stream.response;
            const metadata = finalResponse?.candidates?.[0]?.groundingMetadata;
            if (metadata?.groundingChunks && metadata.groundingChunks.length > 0) {
              const sources = metadata.groundingChunks
                .map(chunk => chunk.web)
                .filter((web): web is { uri: string; title: string } => !!(web?.uri && web.title))
              
              if (sources.length > 0) {
                setMessages(prev => {
                  const newMessages = [...prev];
                  newMessages[newMessages.length - 1].sources = sources;
                  return newMessages;
                });
              }
            }
        } catch (err) {
            console.error(err);
            const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred.';
            setError(`Sorry, something went wrong: ${errorMessage}`);
            setMessages(prev => [...prev, { role: 'model', content: `Error: ${errorMessage}` }]);
        } finally {
            setIsLoading(false);
            setToolCallMessage(null);
        }
    }, [input, isLoading, messages, useSearch, useTools]);

    return (
        <div className="flex flex-col h-full p-4 bg-gray-900">
            <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4 rounded-lg bg-gray-800/50">
                {messages.map((msg, index) => (
                    <MessageBubble key={index} message={msg} />
                ))}
                {(isLoading || toolCallMessage) && (
                  <div className="flex justify-start mb-4">
                    <div className="p-4 max-w-xl lg:max-w-3xl bg-gray-700 text-gray-200 self-start rounded-tr-xl rounded-bl-xl rounded-br-xl shadow-md flex items-center gap-3">
                      <Spinner />
                      <span>{toolCallMessage || 'Thinking...'}</span>
                    </div>
                  </div>
                )}
            </div>
            {error && <div className="p-2 my-2 text-sm text-red-400 bg-red-900/50 rounded-md">{error}</div>}
            
            <div className="mt-4">
              <div className="flex items-center justify-end gap-4 mb-2 pr-1">
                <Toggle label="Search the web" enabled={useSearch} onChange={setUseSearch} />
                <Toggle label="Use Tools" enabled={useTools} onChange={setUseTools} />
              </div>
              <form onSubmit={handleSendMessage} className="flex items-center space-x-2">
                  <input
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      placeholder="Type your message here..."
                      disabled={isLoading}
                      className="flex-1 p-3 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none transition"
                  />
                  <button
                      type="submit"
                      disabled={isLoading || !input.trim()}
                      className="px-6 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
                  >
                      {isLoading ? <Spinner /> : 'Send'}
                  </button>
              </form>
            </div>
        </div>
    );
};

export default ChatView;