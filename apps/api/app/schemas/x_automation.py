import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# X Account
# ---------------------------------------------------------------------------


class XAccountConnectRequest(BaseModel):
    x_user_id: str
    username: str
    display_name: str | None = None
    access_token: str
    refresh_token: str | None = None
    token_expires_at: datetime | None = None


class XAccountResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    business_id: uuid.UUID
    x_user_id: str
    username: str
    display_name: str | None
    is_active: bool
    token_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# X Posts
# ---------------------------------------------------------------------------


class ThreadTweet(BaseModel):
    text: str = Field(..., max_length=280)


class XPostCreateRequest(BaseModel):
    x_account_id: uuid.UUID
    content: str = Field(..., max_length=280, description="First tweet text (used for single tweets too)")
    thread_tweets: list[ThreadTweet] = Field(
        default_factory=list,
        description="If set, post as a thread. First item = content above; remaining items are replies.",
    )
    scheduled_at: datetime | None = None


class XPostResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    business_id: uuid.UUID
    x_account_id: uuid.UUID
    content: str
    thread_tweets: list[dict]
    tweet_ids: list[str]
    status: str
    scheduled_at: datetime | None
    posted_at: datetime | None
    error_message: str | None
    engagement: dict
    created_at: datetime
    updated_at: datetime


class PaginatedXPosts(BaseModel):
    items: list[XPostResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# X Lead Searches
# ---------------------------------------------------------------------------


class XLeadSearchCreateRequest(BaseModel):
    name: str = Field(..., max_length=100)
    keywords: list[str] = Field(..., min_length=1)
    exclude_keywords: list[str] = Field(default_factory=list)
    min_followers: int = Field(100, ge=0)
    language: str = Field("en", max_length=5)


class XLeadSearchResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    business_id: uuid.UUID
    name: str
    keywords: list[str]
    exclude_keywords: list[str]
    min_followers: int
    language: str
    is_active: bool
    last_run_at: datetime | None
    created_at: datetime


# ---------------------------------------------------------------------------
# X Outreach
# ---------------------------------------------------------------------------


class XOutreachResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    business_id: uuid.UUID
    lead_id: uuid.UUID | None
    x_user_id: str
    username: str
    display_name: str | None
    profile_bio: str | None
    followers_count: int | None
    tweet_text: str | None
    ai_score: int | None
    ai_score_reason: str | None
    outreach_message: str | None
    status: str
    sent_at: datetime | None
    created_at: datetime


class XOutreachUpdateRequest(BaseModel):
    status: str | None = None
    outreach_message: str | None = None


class PaginatedXOutreach(BaseModel):
    items: list[XOutreachResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# Content ideas
# ---------------------------------------------------------------------------


class ContentIdeasRequest(BaseModel):
    business_name: str = Field(default="Influnexus")
    services: list[str] = Field(
        default_factory=lambda: [
            "Social media management",
            "Brand design",
            "AI automation",
            "Marketing strategy",
        ]
    )
    count: int = Field(5, ge=1, le=10)


class ContentIdeaResponse(BaseModel):
    type: str
    hook: str
    content: str
