export interface QualificationField {
  key: string;
  label: string;
  required: boolean;
}

export interface AiAgent {
  id: string;
  business_id: string;
  name: string;
  agent_type: "sales" | "support" | "follow_up";
  persona: string;
  provider: "openai" | "anthropic";
  model: string;
  temperature: number;
  qualification_fields: QualificationField[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateAgentRequest {
  name: string;
  agent_type: "sales" | "support" | "follow_up";
  persona?: string;
  provider: "openai" | "anthropic";
  model: string;
  temperature: number;
  qualification_fields: QualificationField[];
  is_active: boolean;
}

export type UpdateAgentRequest = Partial<Omit<CreateAgentRequest, "agent_type">>;

export interface TestMessage {
  role: "user" | "assistant";
  content: string;
}

export interface TestRequest {
  message: string;
  history: TestMessage[];
  known_lead_fields: Record<string, string>;
}

export interface RetrievedChunk {
  document_id: string;
  title: string;
  content: string;
  similarity: number;
}

export interface TestResponse {
  reply: string;
  extracted_lead_fields: Record<string, string>;
  retrieved_chunks: RetrievedChunk[];
  prompt_tokens: number | null;
  completion_tokens: number | null;
  latency_ms: number;
}
