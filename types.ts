// This type is deprecated in favor of the more detailed `Agent` type.
export interface AgentConfig {
  name: string;
  systemInstruction: string;
  tools: {
    useCalculator: boolean;
    useSearch: boolean;
  };
}

export interface Source {
  title: string;
  uri: string;
}

export interface ChatMessage {
  role: 'user' | 'model';
  content: string;
  sources?: Source[];
}

export interface AnalysisResult {
  answer: string;
  summary: string;
  keyFindings: string[];
}

// --- AI Digital Twin Types ---

export interface PromptTemplate {
    name: string;
    template: string;
    variables: string[];
}

export interface LLMConfig {
    modelName: string;
    temperature: number;
    maxTokens: number;
    topP: number;
}

export interface DecisionRule {
    name: string;
    condition: string;
    actionType: 'LLM_CALL' | 'FIXED_RESPONSE' | 'PLAN_EXECUTION' | 'MEMORY_QUERY' | 'TOOL_USE';
    actionPayload: any;
    priority: number;
}

export interface RLModelParameters {
    stateSpace: { name: string; dimensions: Record<string, string>; };
    actionSpace: { name: string; actions: string[]; };
    rewardFunction: { description: string; logic: string; };
    learnedPolicyWeights: Record<string, number>;
    explorationRate: number;
    learningRate: number;
    discountFactor: number;
}

export interface PlanningAction {
    name: string;
    preconditions: string[];
    effects: string[];
    actionType: 'LLM_CALL' | 'TOOL_USE' | 'INTERNAL_OPERATION';
    payload?: any;
}

export interface LongTermMemoryEntry {
    id: string;
    content: string;
    embedding?: number[];
    metadata?: Record<string, any>;
}

export interface ShortTermMemoryEntry {
    timestamp: number;
    role: 'user' | 'agent';
    content: string;
    sentiment?: string;
    keywords?: string[];
}

export interface DigitalTwinState {
    id: string;
    name: string;
    description: string;
    promptEngineering: {
        templates: PromptTemplate[];
        llmConfig: LLMConfig;
    };
    decisionLogic: {
        rules: DecisionRule[];
    };
    reinforcementLearning: {
        enabled: boolean;
        modelParams?: RLModelParameters;
        currentExperienceBuffer: Array<{
            state: Record<string, any>;
            action: string;
            reward: number;
            nextState: Record<string, any>;
        }>;
    };
    planning: {
        enabled: boolean;
        availableActions?: PlanningAction[];
        currentGoal?: string;
        activePlan?: string[];
        planExecutionState?: 'IDLE' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';
    };
    memory: {
        shortTermMemory: ShortTermMemoryEntry[];
        longTermMemory: {
            entries: LongTermMemoryEntry[];
            vectorDBConfig?: { endpoint: string; collection: string; };
        };
    };
    currentInput?: string;
    currentOutput?: string;
    currentStateContext: Record<string, any>;
    lastDecisionPath: string[];
    performanceMetrics: {
        totalInteractions: number;
        successfulInteractions: number;
        avgResponseTimeMs: number;
    };
}

export interface IAI_Agent_DigitalTwin {
    configureAgent(config: Partial<DigitalTwinState>): DigitalTwinState;
    processInteraction(input: string, environmentFeedback?: { reward?: number; success?: boolean; failure?: boolean; }): Promise<{ output: string; updatedState: DigitalTwinState }>;
    getTwinState(): DigitalTwinState;
    resetOperationalState(): DigitalTwinState;
}

// --- Data Source Configuration Types ---

export enum DataSourceType {
  API = 'API',
  Sensor = 'Sensor',
  WebScrape = 'WebScrape',
  UserInput = 'UserInput',
  RealtimeStream = 'RealtimeStream'
}

export enum DataSourceStatus {
  Active = 'Active',
  Inactive = 'Inactive',
  Error = 'Error'
}

export interface DataSourceConfiguration {
  source_id: string; // UUID
  name: string;
  description: string;
  source_type: DataSourceType;
  status: DataSourceStatus;
  created_at: string; // ISO timestamp
  last_updated_at: string; // ISO timestamp
  collection_interval_seconds: number | null;
  connection_details: Record<string, any>;
  parsing_rules: Record<string, any>;
  normalization_rules: Record<string, any>;
}

// --- Professional Agent Definition ---
export interface Agent {
    agent_id: string; // UUID
    name: string;
    description: string;
    role_type: string;
    goal: string;
    persona_instructions: string; // System prompt
    tools_capabilities: string[];
    memory_access: {
        short_term: boolean;
        long_term_knowledge_base: string | null;
    };
    input_schema: Record<string, any>; // JSON Schema object
    output_schema: Record<string, any>; // JSON Schema object
    priority: number;
}

// --- Orchestration Types ---

export type WorkflowNodeType = 'DataSource' | 'Agent' | 'Input' | 'Output' | 'Tool';

export interface WorkflowNode {
  id: string;
  type: WorkflowNodeType;
  label: string;
  position: { x: number; y: number; };
  data: DataSourceConfiguration | Agent | Record<string, any>;
}

export interface WorkflowConnection {
  id: string;
  sourceId: string;
  targetId: string;
  sourceHandle: 'right' | 'left';
  targetHandle: 'right' | 'left';
}

// --- System Log Types ---
export interface SystemLogEntry {
    id: string;
    timestamp: string;
    level: 'info' | 'warn' | 'error';
    message: string;
}
