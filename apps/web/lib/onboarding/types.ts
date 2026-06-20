export type OnboardingStep = 1 | 2 | 3 | 4 | 5 | 6;

export const STEP_META: { step: OnboardingStep; title: string; description: string }[] = [
  { step: 1, title: "Business details", description: "Tell us about your business" },
  { step: 2, title: "Connect WhatsApp", description: "Link your WhatsApp Business account" },
  { step: 3, title: "Knowledge base", description: "Upload documents your AI can reference" },
  { step: 4, title: "Configure AI agent", description: "Set your agent's persona and goals" },
  { step: 5, title: "Test your agent", description: "Send a test message before going live" },
  { step: 6, title: "Go live", description: "Review and activate" },
];

// ---------------------------------------------------------------------------
// Business
// ---------------------------------------------------------------------------

export interface BusinessDetail {
  id: string;
  name: string;
  industry: string | null;
  timezone: string;
  onboarding_completed: boolean;
  notify_whatsapp_phone: string | null;
  created_at: string;
  updated_at: string;
}

export interface BusinessUpdatePayload {
  name?: string;
  industry?: string | null;
  timezone?: string;
  onboarding_completed?: boolean;
  notify_whatsapp_phone?: string | null;
}

// ---------------------------------------------------------------------------
// Knowledge base
// ---------------------------------------------------------------------------

export interface KbDocument {
  id: string;
  knowledge_base_id: string;
  title: string;
  source_type: string;
  source_url: string | null;
  content: string;
  status: string;
  created_at: string;
}

export interface KnowledgeBase {
  id: string;
  business_id: string;
  name: string;
  description: string | null;
  documents: KbDocument[];
  created_at: string;
  updated_at: string;
}

export interface CreateKbPayload {
  name: string;
  description?: string;
}

export interface AddDocumentPayload {
  title: string;
  content: string;
  source_type?: string;
  source_url?: string;
}

// ---------------------------------------------------------------------------
// Agent (mirrors existing types from agents.py)
// ---------------------------------------------------------------------------

export interface QualificationField {
  key: string;
  label: string;
  required: boolean;
}

export interface AgentCreatePayload {
  name: string;
  agent_type: "sales" | "support" | "follow_up";
  persona: string;
  provider: "openai" | "anthropic";
  model: string;
  temperature: number;
  qualification_fields: QualificationField[];
  is_active: boolean;
}

export interface AgentDetail {
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

// ---------------------------------------------------------------------------
// Agent test
// ---------------------------------------------------------------------------

export interface TestMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AgentTestPayload {
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

export interface AgentTestResult {
  reply: string;
  extracted_lead_fields: Record<string, string>;
  retrieved_chunks: RetrievedChunk[];
  prompt_tokens: number | null;
  completion_tokens: number | null;
  latency_ms: number;
}
