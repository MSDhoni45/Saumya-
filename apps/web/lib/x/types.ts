export interface XAccount {
  id: string;
  business_id: string;
  x_user_id: string;
  username: string;
  display_name: string | null;
  is_active: boolean;
  token_expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface XPost {
  id: string;
  business_id: string;
  x_account_id: string;
  content: string;
  thread_tweets: { text: string }[];
  tweet_ids: string[];
  status: "draft" | "scheduled" | "posted" | "failed";
  scheduled_at: string | null;
  posted_at: string | null;
  error_message: string | null;
  engagement: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export interface PaginatedXPosts {
  items: XPost[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface XLeadSearch {
  id: string;
  business_id: string;
  name: string;
  keywords: string[];
  exclude_keywords: string[];
  min_followers: number;
  language: string;
  is_active: boolean;
  auto_dm_enabled: boolean;
  auto_dm_threshold: number;
  last_run_at: string | null;
  created_at: string;
}

export interface XOutreach {
  id: string;
  business_id: string;
  lead_id: string | null;
  x_user_id: string;
  username: string;
  display_name: string | null;
  profile_bio: string | null;
  followers_count: number | null;
  tweet_text: string | null;
  ai_score: number | null;
  ai_score_reason: string | null;
  outreach_message: string | null;
  status: "pending" | "reviewed" | "sent" | "dm_sent" | "replied" | "converted" | "skipped";
  sent_at: string | null;
  dm_sent_at: string | null;
  reply_text: string | null;
  replied_at: string | null;
  created_at: string;
}

export interface PaginatedXOutreach {
  items: XOutreach[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface XAnalytics {
  outreach: {
    total: number;
    by_status: Record<string, number>;
    avg_score: number | null;
    sent_last_7d: number;
    dm_sent_last_7d: number;
    replied: number;
  };
  posts: {
    total: number;
    by_status: Record<string, number>;
  };
  searches: {
    total: number;
    active: number;
  };
  top_leads: {
    username: string;
    display_name: string | null;
    ai_score: number | null;
    status: string;
    followers_count: number | null;
  }[];
}
