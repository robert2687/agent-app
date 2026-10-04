import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { Message as MessageType, Role } from '../types';
import UserIcon from './icons/UserIcon';
import ErrorIcon from './icons/ErrorIcon';
import AgentIcon from './AgentIcon';
import CodeBlock from './CodeBlock';

interface MessageProps {
    message: MessageType;
}

const Message: React.FC<MessageProps> = ({ message }) => {
    const isUser = message.role === Role.USER;
    const isError = message.role === Role.ERROR;
    const hasImages = message.imageUrls && message.imageUrls.length > 0;

    const wrapperClasses = `flex items-start gap-3 my-4 ${isUser ? 'justify-end' : 'justify-start'}`;
    
    const bubbleClasses = `max-w-xl lg:max-w-2xl xl:max-w-3xl rounded-2xl shadow-lg ${
        isUser
            ? 'bg-blue-600 text-white rounded-br-lg'
            : isError
            ? 'bg-red-800 text-red-100 rounded-bl-lg'
            : 'bg-slate-700 text-slate-200 rounded-bl-lg'
    } ${hasImages ? 'p-2 bg-slate-800/50' : 'px-5 py-3'}`;
    
    const icon = isUser ? <UserIcon /> : isError ? <ErrorIcon /> : <AgentIcon agent={message.agent} />;

    return (
        <div className={wrapperClasses}>
            {!isUser && <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center mt-1">{icon}</div>}
            <div className={bubbleClasses}>
                {hasImages ? (
                    <div className={`grid gap-2 ${message.imageUrls.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
                        {message.imageUrls.map((url, index) => (
                             <a href={url} target="_blank" rel="noopener noreferrer" key={index} className="block rounded-lg overflow-hidden">
                                <img 
                                    src={url} 
                                    alt={`AI generated image ${index + 1}`} 
                                    className="w-full h-full object-cover aspect-square transition-transform duration-300 hover:scale-105"
                                    aria-label={`AI generated image ${index + 1}`}
                                />
                            </a>
                        ))}
                    </div>
                ) : (
                     <div className="prose prose-invert prose-sm max-w-none">
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypeHighlight]}
                            components={{
                                pre: (props) => <CodeBlock {...props} />
                            }}
                        >
                            {message.content}
                        </ReactMarkdown>
                    </div>
                )}
            </div>
            {isUser && <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-800 flex items-center justify-center mt-1">{icon}</div>}
        </div>
    );
};

export default Message;