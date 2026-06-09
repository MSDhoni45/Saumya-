/**
 * Mirrors `apps/api/app/schemas/whatsapp.py` — keep the literal unions in sync
 * with the backend's `Literal[...]` types and the `conversations`/`messages`
 * check constraints.
 */

export type ConversationStatus = "open" | "pending" | "handoff" | "closed";
export type SenderType = "contact" | "ai" | "agent" | "system";
export type MessageDirection = "inbound" | "outbound";
export type MessageType = "text" | "image" | "document" | "audio" | "video" | "template" | "location";
export type MessageDeliveryStatus = "queued" | "sent" | "delivered" | "read" | "failed";

export interface Conversation {
  id: string;
  business_id: string;
  whatsapp_account_id: string;
  contact_phone: string;
  contact_name: string | null;
  status: ConversationStatus;
  assigned_user_id: string | null;
  last_message_at: string | null;
  created_at: string;
  // Populated by the list endpoint via correlated subquery (not a DB column).
  last_message_content: string | null;
  last_sender_type: SenderType | null;
}

export interface Message {
  id: string;
  conversation_id: string;
  direction: MessageDirection;
  sender_type: SenderType;
  message_type: MessageType;
  content: string | null;
  media_url: string | null;
  status: MessageDeliveryStatus;
  created_at: string;
}

export type WhatsAppAccountStatus = "pending" | "connected" | "disconnected" | "error";

export interface WhatsAppAccount {
  id: string;
  business_id: string;
  display_name: string | null;
  phone_number: string;
  waba_id: string;
  phone_number_id: string;
  status: WhatsAppAccountStatus;
  connected_at: string | null;
  created_at: string;
}

export interface ConnectWhatsAppPayload {
  waba_id: string;
  phone_number_id: string;
  access_token: string;
  display_name?: string;
}

export interface ConversationUpdatePayload {
  status?: ConversationStatus;
  assigned_user_id?: string | null;
}

export interface SendMessageResult {
  message_id: string;
  whatsapp_message_id: string;
  status: string;
}
