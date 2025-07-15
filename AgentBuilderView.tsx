import React, { useState, useCallback } from 'react';
import type { AgentConfig, ChatMessage } from '../types';
import { runAgentStream } from '../services/geminiService';
import BuilderPanel from './BuilderPanel';
import InteractionPanel from './InteractionPanel';

const AgentBuilderView: React.FC = () => {
  const [agentConfig, setAgentConfig] = useState<AgentConfig | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreateAgent = (config: AgentConfig) => {
    setAgentConfig(config);
    setMessages([
      {
        role: 'model',
        content: `Hello! I am ${config.name}. How can I assist you based on my configured instructions?`,
      },
    ]);
    setError(null);
    setIsLoading(false);
  };

  const handleSendMessage = useCallback(async (userInput: string) => {
    if (!agentConfig) {
      setError("Please create an agent before starting a conversation.");
      return;
    }

    const newUserMessage: ChatMessage = { role: 'user', content: userInput };
    const updatedMessages = [...messages, newUserMessage];
    
    setMessages(updatedMessages);
    setIsLoading(true);
    setError(null);

    try {
      let toolCallMessageSetter: ((msg: string | null) => void) | null = null;
      const onToolCall = (name: string) => {
        toolCallMessageSetter?.(`🤖 Using tool: ${name}...`);
      };

      const stream = await runAgentStream(
        agentConfig,
        updatedMessages,
        onToolCall,
        (setter) => { toolCallMessageSetter = setter; }
      );
      
      toolCallMessageSetter?.(null);
      
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
          .filter((web): web is { uri: string; title: string } => !!(web?.uri));
        
        if (sources.length > 0) {
          setMessages(prev => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1].sources = sources.map(s => ({...s, title: s.title || s.uri}));
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
    }
  }, [agentConfig, messages]);

  return (
    <div className="flex flex-col md:flex-row h-full">
        <BuilderPanel onCreateAgent={handleCreateAgent} />
        <InteractionPanel
          agentConfig={agentConfig}
          messages={messages}
          isLoading={isLoading}
          error={error}
          onSendMessage={handleSendMessage}
        />
    </div>
  );
};

export default AgentBuilderView;
