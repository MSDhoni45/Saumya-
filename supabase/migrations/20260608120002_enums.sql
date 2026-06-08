-- =============================================================================
-- WhatsAgent AI — Migration 02: Enumerated types
-- =============================================================================

-- Organizations / billing
create type public.organization_plan as enum ('trial', 'starter', 'pro', 'enterprise');
create type public.subscription_status as enum ('active', 'past_due', 'canceled');

-- Membership
create type public.member_role as enum ('owner', 'admin', 'agent');
create type public.member_status as enum ('invited', 'active', 'removed');

-- Shared connection status (WhatsApp + Google Calendar)
create type public.connection_status as enum ('connected', 'disconnected', 'error');

-- Conversations & messaging
create type public.conversation_status as enum ('open', 'snoozed', 'closed');
create type public.agent_owner_type as enum ('ai', 'human');
create type public.message_direction as enum ('inbound', 'outbound');
create type public.message_sender_type as enum ('contact', 'ai_agent', 'human_agent', 'system');
create type public.message_type as enum ('text', 'image', 'document', 'audio', 'video', 'template', 'interactive');
create type public.message_status as enum ('sent', 'delivered', 'read', 'failed');

-- Knowledge base
create type public.kb_source_type as enum ('pdf', 'docx', 'url');
create type public.kb_document_status as enum ('pending', 'processing', 'ready', 'failed');

-- AI agents
create type public.ai_agent_type as enum ('sales', 'follow_up', 'support');
create type public.model_provider as enum ('openai', 'anthropic');

-- CRM / leads
create type public.lead_stage as enum ('new', 'qualified', 'contacted', 'won', 'lost');
create type public.lead_source as enum ('whatsapp', 'manual', 'import');
create type public.lead_activity_type as enum ('stage_change', 'note', 'message', 'appointment', 'system');

-- Appointments / calendar
create type public.calendar_provider as enum ('google');
create type public.appointment_status as enum ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show');
create type public.creation_source as enum ('ai_agent', 'manual');

-- Follow-up agent
create type public.follow_up_trigger as enum ('lead_created', 'no_response_24h', 'stage_changed', 'manual');
create type public.follow_up_channel as enum ('whatsapp');
create type public.enrollment_status as enum ('active', 'completed', 'exited', 'paused');
