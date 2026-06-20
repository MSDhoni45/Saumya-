-- Add owner notification WhatsApp phone to businesses
ALTER TABLE public.businesses
  ADD COLUMN IF NOT EXISTS notify_whatsapp_phone TEXT;

COMMENT ON COLUMN public.businesses.notify_whatsapp_phone
  IS 'Owner personal WhatsApp number (E.164) to receive X lead notifications.';
