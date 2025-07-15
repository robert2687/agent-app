import type { DigitalTwinState, IAI_Agent_DigitalTwin } from '../types';
import { ai } from './geminiService';
import type { Content } from '@google/genai';


// --- Helper Functions (as per design) ---

function updateContextFromInput(context: Record<string, any>, input: string): Record<string, any> {
    context['input'] = input;
    context['inputLength'] = input.length;
    context['isQuestion'] = input.includes('?');
    context['sentiment'] = input.includes('great') || input.includes('good') ? 'positive' : (input.includes('bad') || input.includes('terrible') ? 'negative' : 'neutral');
    return context;
}

function retrieveRelevantMemory(twinState: DigitalTwinState, query: string): string {
    const relevantEntries = twinState.memory.longTermMemory.entries.filter(entry =>
        entry.content.toLowerCase().includes(query.toLowerCase())
    );
    return relevantEntries.length > 0 ? relevantEntries[0].content : "";
}

function evaluateCondition(condition: string, context: Record<string, any>): boolean {
    try {
        // Safe evaluation by exposing only the 'context' object.
        const func = new Function('context', `with(context) { return ${condition}; }`);
        return func(context);
    } catch (e) {
        console.error(`Error evaluating condition "${condition}":`, e);
        return false;
    }
}

async function invokeLLM(twinState: DigitalTwinState, templateName: string, vars: Record<string, any>): Promise<string> {
    const template = twinState.promptEngineering.templates.find(t => t.name === templateName);
    if (!template) return `Error: Prompt template '${templateName}' not found.`;

    let prompt = template.template;
    for (const key of Object.keys(vars)) {
        prompt = prompt.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), String(vars[key] ?? ''));
    }

    try {
        const contents: Content[] = [{ role: 'user', parts: [{ text: prompt }] }];
        // Use the twin's description as the system instruction.
        const systemInstruction = twinState.description; 
        
        const response = await ai.models.generateContent({
            model: twinState.promptEngineering.llmConfig.modelName,
            contents: contents,
            config: {
                systemInstruction,
                temperature: twinState.promptEngineering.llmConfig.temperature,
                maxOutputTokens: twinState.promptEngineering.llmConfig.maxTokens,
                topP: twinState.promptEngineering.llmConfig.topP,
            }
        });

        return response.text;
    } catch (error) {
        console.error(`Error invoking LLM for template ${templateName}:`, error);
        const errorMessage = error instanceof Error ? error.message : String(error);
        return `(Error calling LLM: ${errorMessage})`;
    }
}


function simulateToolUse(toolName: string, args: Record<string, any>): string {
    if (toolName === 'calculator') {
        const { operation, num1, num2 } = args;
        if (operation === 'add') return String(num1 + num2);
        if (operation === 'multiply') return String(num1 * num2);
    }
    return `Simulated result for tool '${toolName}' with args: ${JSON.stringify(args)}.`;
}


async function processAgentInteraction(
    twinState: DigitalTwinState,
    input: string,
    environmentFeedback?: { reward?: number; }
): Promise<{ updatedState: DigitalTwinState; output: string }> {
    let state = JSON.parse(JSON.stringify(twinState)); // Work on a copy

    state.currentInput = input;
    state.lastDecisionPath = [];
    state.currentStateContext = updateContextFromInput(state.currentStateContext, input);
    state.memory.shortTermMemory.push({ timestamp: Date.now(), role: 'user', content: input, sentiment: state.currentStateContext['sentiment'] });

    let agentResponse = "";
    let decisionMade = false;
    
    // Phase 2: Memory Retrieval
    let relevantMemory = retrieveRelevantMemory(state, input);
    if (relevantMemory) {
        state.currentStateContext['relevantMemory'] = relevantMemory;
        state.lastDecisionPath.push('Memory_Retrieval');
    }

    // Phase 3: Decision Logic
    const sortedRules = [...state.decisionLogic.rules].sort((a, b) => b.priority - a.priority);
    for (const rule of sortedRules) {
        if (evaluateCondition(rule.condition, state.currentStateContext)) {
            state.lastDecisionPath.push(`Decision_Rule: ${rule.name}`);
            switch (rule.actionType) {
                case 'LLM_CALL':
                    agentResponse = await invokeLLM(state, rule.actionPayload.promptName, { ...rule.actionPayload.vars, ...state.currentStateContext });
                    break;
                case 'FIXED_RESPONSE':
                    agentResponse = rule.actionPayload as string;
                    break;
                case 'TOOL_USE':
                    agentResponse = simulateToolUse(rule.actionPayload.toolName, rule.actionPayload.args);
                    break;
                default:
                    agentResponse = `Rule triggered unhandled action: ${rule.actionType}`;
            }
            decisionMade = true;
            break;
        }
    }

    // Phase 5: Default Fallback
    if (!decisionMade) {
        state.lastDecisionPath.push('Default_LLM_Fallback');
        agentResponse = await invokeLLM(state, "default_response", { ...state.currentStateContext });
    }

    // Phase 6: Post-processing & State Update
    state.currentOutput = agentResponse;
    state.memory.shortTermMemory.push({ timestamp: Date.now(), role: 'agent', content: agentResponse });
    state.performanceMetrics.totalInteractions++;

    // Phase 7: RL Feedback
    if (state.reinforcementLearning.enabled && environmentFeedback) {
        state.lastDecisionPath.push(`Reinforcement_Learning_Feedback (Reward: ${environmentFeedback.reward})`);
        // Here you would add the experience to a buffer and potentially train
    }

    return { updatedState: state, output: agentResponse };
}

export class AIAgentDigitalTwin implements IAI_Agent_DigitalTwin {
    private state: DigitalTwinState;

    constructor(initialState: DigitalTwinState) {
        this.state = JSON.parse(JSON.stringify(initialState));
    }

    configureAgent(config: Partial<DigitalTwinState>): DigitalTwinState {
        this.state = { ...this.state, ...config };
        return this.getTwinState();
    }

    async processInteraction(input: string, environmentFeedback?: { reward?: number; }): Promise<{ output: string; updatedState: DigitalTwinState }> {
        const { updatedState, output } = await processAgentInteraction(this.state, input, environmentFeedback);
        this.state = updatedState;
        return { output, updatedState: this.getTwinState() };
    }

    getTwinState(): DigitalTwinState {
        return JSON.parse(JSON.stringify(this.state));
    }

    resetOperationalState(): DigitalTwinState {
        const pristineState = getDefaultTwinState();
        this.state.currentInput = undefined;
        this.state.currentOutput = undefined;
        this.state.currentStateContext = {};
        this.state.lastDecisionPath = [];
        this.state.memory.shortTermMemory = [];
        this.state.performanceMetrics = pristineState.performanceMetrics;
        return this.getTwinState();
    }
}

export function getDefaultTwinState(): DigitalTwinState {
    return {
        id: "CustomerSupportBot-v2-default",
        name: "SupportPro Agent",
        description: "A digital twin of a customer support agent.",
        promptEngineering: {
            templates: [
                { name: "default_response", template: "You are a helpful AI assistant. The user said: {{input}}. The relevant context is: {{relevantMemory}}", variables: ["input", "relevantMemory"] },
                { name: "greeting_response", template: "You are a friendly agent. Say hello to the user.", variables: [] },
                { name: "name_inquiry_response", template: "Politely state your name.", variables: [] }
            ],
            llmConfig: { modelName: "gemini-2.5-flash", temperature: 0.7, maxTokens: 256, topP: 1.0 }
        },
        decisionLogic: {
            rules: [
                { name: "Greeting Rule", condition: "context.input.toLowerCase().includes('hello') || context.input.toLowerCase().includes('hi')", actionType: "LLM_CALL", actionPayload: { promptName: "greeting_response" }, priority: 10 },
                { name: "Name Inquiry Rule", condition: "context.input.toLowerCase().includes('what is your name')", actionType: "LLM_CALL", actionPayload: { promptName: "name_inquiry_response" }, priority: 10 },
                { name: "Negative Sentiment Rule", condition: "context.sentiment === 'negative'", actionType: "FIXED_RESPONSE", actionPayload: "I'm sorry to hear you're having trouble. Let me see how I can help.", priority: 5 }
            ]
        },
        reinforcementLearning: { enabled: false, currentExperienceBuffer: [] },
        planning: { enabled: false },
        memory: {
            shortTermMemory: [],
            longTermMemory: {
                entries: [
                    { id: "mem1", content: "The return policy is 30 days for a full refund.", metadata: { topic: "refunds" } }
                ]
            }
        },
        currentStateContext: {},
        lastDecisionPath: [],
        performanceMetrics: { totalInteractions: 0, successfulInteractions: 0, avgResponseTimeMs: 0 }
    };
}
