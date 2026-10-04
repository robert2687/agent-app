import { GoogleGenAI, GenerateContentStream, Content, Type, Tool } from "@google/genai";
import type { ChatMessage, AgentConfig, AnalysisResult } from "../types";

// Ensure the API key is available from environment variables
if (!process.env.API_KEY) {
    throw new Error("API_KEY environment variable not set.");
}

export const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

// --- Tool Definitions ---
const calculatorTool: Tool = {
    functionDeclarations: [
        {
            name: "calculator",
            description: "A simple calculator that can perform addition, subtraction, multiplication, and division on two numbers.",
            parameters: {
                type: Type.OBJECT,
                properties: {
                    a: { type: Type.NUMBER, description: "The first number." },
                    b: { type: Type.NUMBER, description: "The second number." },
                    operation: { type: Type.STRING, enum: ["add", "subtract", "multiply", "divide"], description: "The operation to perform." }
                },
                required: ["a", "b", "operation"]
            }
        }
    ]
};

const functions = {
    calculator: ({ a, b, operation }: { a: number, b: number, operation: string }) => {
        switch (operation) {
            case "add": return a + b;
            case "subtract": return a - b;
            case "multiply": return a * b;
            case "divide": 
                if (b === 0) return "Error: Cannot divide by zero.";
                return a / b;
            default: return "Error: Unknown operation.";
        }
    }
};


/**
 * Runs the configured AI agent and generates a streaming response.
 * @param config The agent's configuration.
 * @param messages The full conversation history.
 * @param onToolCall A callback invoked when a tool is being called.
 * @param registerToolCallSetter A function to register a setter for the tool call message.
 * @returns A promise that resolves to a GenerateContentStream object.
 */
export async function runAgentStream(
    config: AgentConfig,
    messages: ChatMessage[],
    onToolCall: (name: string, args: any) => void,
    registerToolCallSetter: (setter: (message: string | null) => void) => void
): Promise<GenerateContentStream> {
    const contents: Content[] = messages.map(msg => ({
        role: msg.role,
        parts: [{ text: msg.content }],
    }));

    const tools: Tool[] = [];
    if (config.tools.useSearch) {
        tools.push({ googleSearch: {} });
    }
    if (config.tools.useCalculator) {
        tools.push(calculatorTool);
    }

    const model = 'gemini-2.5-flash';
    const apiConfig: any = {
        systemInstruction: config.systemInstruction,
        ...(tools.length > 0 && { tools }),
    };
    
    // The multi-step process is only required if the calculator is a potential tool.
    // Search grounding is handled by the model in a single step.
    if (config.tools.useCalculator) {
        const firstResponse = await ai.models.generateContent({
            model,
            contents,
            config: apiConfig,
        });

        const call = firstResponse.candidates?.[0]?.content?.parts?.[0]?.toolCalls?.[0];

        if (call) {
            onToolCall(call.name, call.args);
            // Call the function and get the result.
            const result = functions[call.name as keyof typeof functions](call.args);
            
            const toolResponseContent: Content[] = [
                {
                    role: 'model',
                    parts: [{ toolCalls: [call] }]
                },
                {
                    role: 'tool',
                    parts: [{ toolResponse: { name: call.name, response: { result } } }]
                }
            ];

            // Make the second call to get the final response, which can be streamed.
            return ai.models.generateContentStream({
                model,
                contents: [...contents, ...toolResponseContent],
                config: apiConfig
            });
        } else {
             // No tool call was made, but we used the non-streaming API.
             // We can wrap the response in a fake stream to keep the UI logic consistent.
            const text = firstResponse.text;
            const stream = (async function*() {
                yield { text };
            })() as unknown as GenerateContentStream;
            
            // Manually attach the response promise to match the real stream's behavior
            (stream as any).response = Promise.resolve(firstResponse);
            return stream;
        }
    }

    // Default behavior for agents without a calculator tool (e.g., search-only or no tools).
    return ai.models.generateContentStream({
        model,
        contents,
        config: apiConfig,
    });
}

/** For ChatView */
export async function generateChatResponseStream(
    messages: ChatMessage[],
    useSearch: boolean,
    useTools: boolean,
    onToolCall: (name: string, args: any) => void
): Promise<GenerateContentStream> {
    const config: AgentConfig = {
        name: 'Chat Assistant',
        systemInstruction: 'You are a helpful assistant.',
        tools: {
            useCalculator: useTools,
            useSearch: useSearch,
        }
    };
    // The 4th argument (registerToolCallSetter) is not used in the current implementation of runAgentStream,
    // but we pass a no-op function to satisfy the signature.
    return runAgentStream(config, messages, onToolCall, () => {});
}

/** For ImageView */
export async function generateImages(prompt: string): Promise<string[]> {
    const response = await ai.models.generateImages({
        model: 'imagen-3.0-generate-002',
        prompt: prompt,
        config: {
          numberOfImages: 4,
          outputMimeType: 'image/jpeg',
          aspectRatio: '1:1',
        },
    });

    return response.generatedImages.map(img => img.image.imageBytes);
}

/** For DataAnalysisView */
export async function analyzeData(csvData: string, question: string): Promise<AnalysisResult> {
    const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: `Analyze the following CSV data and answer the user's question.
        
        CSV Data:
        \`\`\`csv
        ${csvData}
        \`\`\`
        
        Question: ${question}`,
        config: {
            responseMimeType: 'application/json',
            responseSchema: {
                type: Type.OBJECT,
                properties: {
                    answer: {
                        type: Type.STRING,
                        description: "A direct, concise answer to the user's question based on the data."
                    },
                    summary: {
                        type: Type.STRING,
                        description: "A brief summary of the data analysis performed."
                    },
                    keyFindings: {
                        type: Type.ARRAY,
                        description: "A list of key findings or interesting observations from the data.",
                        items: { type: Type.STRING }
                    }
                },
                required: ["answer", "summary", "keyFindings"]
            }
        }
    });
    
    const jsonText = response.text.trim();
    return JSON.parse(jsonText) as AnalysisResult;
}

/** For AgentView */
export async function generateAgentResponseStream(goal: string): Promise<GenerateContentStream> {
    return ai.models.generateContentStream({
        model: 'gemini-2.5-flash',
        contents: goal,
        config: {
            systemInstruction: "You are a world-class agent that can break down a complex goal into a series of steps and then execute them. Provide a clear, well-structured response.",
        },
    });
}

/** For CodeEditorView */
export async function generateCodeSuggestion(code: string, instruction: string): Promise<{ newCode: string }> {
    const response = await ai.models.generateContent({
       model: "gemini-2.5-flash",
       contents: `Instruction: "${instruction}"\n\nCode:\n\`\`\`\n${code}\n\`\`\``,
       config: {
            systemInstruction: "You are an expert code assistant. Your task is to modify the user-provided code based on their instruction. You must return a JSON object containing the complete, modified code. Do not omit any part of the original code that was not meant to be changed. The user should be able to take your output and replace their entire file with it.",
            responseMimeType: "application/json",
            responseSchema: {
               type: Type.OBJECT,
               properties: {
                   newCode: {
                       type: Type.STRING,
                       description: "The full, modified source code."
                   }
               },
               required: ["newCode"]
           }
       },
    });
    
    const jsonText = response.text.trim();
    const result = JSON.parse(jsonText);
    
    if (result.newCode) {
      result.newCode = result.newCode.replace(/^```(tsx|jsx|javascript|typescript)?\n/,'').replace(/\n```$/,'');
    }

    return result as { newCode: string };
}