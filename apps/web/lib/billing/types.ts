export type PlanId = "free" | "starter" | "growth" | "agency";
export type SubscriptionStatus = "active" | "trialing" | "past_due" | "cancelled" | "paused";
export type PaymentProvider = "stripe" | "razorpay";

export interface Plan {
  id: PlanId;
  name: string;
  description: string;
  message_limit: number | null;
  price_usd_cents: number;
  price_inr_paise: number;
  is_current: boolean;
}

export interface Subscription {
  id: string;
  business_id: string;
  plan: PlanId;
  status: SubscriptionStatus;
  payment_provider: PaymentProvider | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  trial_ends_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Usage {
  business_id: string;
  plan: PlanId;
  message_limit: number | null;
  message_count: number;
  period_start: string | null;
  period_end: string | null;
  percent_used: number | null;
}

export type CheckoutPlanId = Exclude<PlanId, "free">;

export interface CheckoutRequest {
  plan: CheckoutPlanId;
  provider: PaymentProvider;
  success_url?: string;
  cancel_url?: string;
}

export interface StripeCheckoutResponse {
  provider: "stripe";
  checkout_url: string;
}

export interface RazorpayCheckoutResponse {
  provider: "razorpay";
  razorpay_subscription_id: string;
  razorpay_key_id: string;
  amount: number;
  currency: string;
  business_name: string;
}

export type CheckoutResponse = StripeCheckoutResponse | RazorpayCheckoutResponse;

export interface CancelResponse {
  cancel_at_period_end: boolean;
  current_period_end: string | null;
  message: string;
}
