"""AI-powered lead scoring and outreach message generation for X leads.

Takes a raw X profile + tweet and returns:
  - a 0-100 quality score
  - a one-line reason
  - a personalised outreach reply draft (≤280 chars) suitable for posting as
    a reply to the prospect's tweet
"""

import json
import logging
from typing import Any

from app.services.llm_provider import generate_raw_completion

logger = logging.getLogger(__name__)

# Agency context injected into every scoring prompt so the LLM understands
# what Influnexus offers and what a good lead looks like.
_AGENCY_CONTEXT = """
Influnexus is a creative agency that also builds AI automation systems.
Services offered:
- Social media content creation & management
- Brand identity & graphic design
- AI agents for customer support, lead gen, and workflow automation
- Marketing automation (email, WhatsApp, X/Twitter)
- Video production & editing

Ideal client: A business owner, marketer, or founder who:
- Mentions needing help with social media, content, branding, or marketing
- Is frustrated with manual repetitive tasks and needs automation
- Is scaling a brand or agency and needs creative support
- Has 100+ followers (shows real presence, not spam)
"""

_SCORING_PROMPT = """You are a lead qualification assistant for Influnexus creative agency.

{agency_context}

Analyse this X (Twitter) profile and tweet, then respond in JSON only.

Profile:
- Username: @{username}
- Display name: {display_name}
- Bio: {bio}
- Followers: {followers}
- Following: {following}

Tweet they posted:
"{tweet_text}"

Respond with exactly this JSON structure:
{{
  "score": <integer 0-100>,
  "reason": "<one sentence explaining the score>",
  "outreach_message": "<a friendly, natural reply to their tweet, under 240 chars, that starts a conversation — do NOT pitch immediately, ask a helpful question or offer a quick insight related to their pain point>"
}}

Score guide:
- 80-100: Clear pain point matching Influnexus services, active user, good follower count
- 60-79: Likely relevant, some signals but not explicit
- 40-59: Tangentially relevant, might be interested
- 0-39: Low relevance — wrong audience, spam account, or no clear need
"""


async def score_and_draft_outreach(
    *,
    username: str,
    display_name: str | None,
    bio: str | None,
    followers: int | None,
    following: int | None,
    tweet_text: str,
    provider: str = "anthropic",
    model: str = "claude-haiku-4-5-20251001",
) -> dict[str, Any]:
    """Score a prospect and generate a personalised outreach message.

    Uses a cheap/fast model (Haiku) since this runs at volume for every
    discovered tweet — accuracy matters more than reasoning depth here.

    Returns dict with keys: score (int), reason (str), outreach_message (str).
    Falls back to score=0 on LLM error so callers can still store the row.
    """
    prompt = _SCORING_PROMPT.format(
        agency_context=_AGENCY_CONTEXT,
        username=username,
        display_name=display_name or "Unknown",
        bio=bio or "No bio",
        followers=followers or 0,
        following=following or 0,
        tweet_text=tweet_text,
    )

    try:
        raw = await generate_raw_completion(
            prompt=prompt,
            provider=provider,
            model=model,
            temperature=0.3,
            max_tokens=400,
        )
        result = json.loads(raw)
        return {
            "score": int(result.get("score", 0)),
            "reason": str(result.get("reason", "")),
            "outreach_message": str(result.get("outreach_message", "")),
        }
    except Exception:
        logger.exception("Failed to score X lead @%s — defaulting to score=0", username)
        return {"score": 0, "reason": "Scoring failed", "outreach_message": ""}


async def generate_content_ideas(
    *,
    business_name: str,
    services: list[str],
    count: int = 5,
    provider: str = "anthropic",
    model: str = "claude-haiku-4-5-20251001",
) -> list[dict[str, str]]:
    """Generate tweet/thread ideas for Influnexus content marketing.

    Returns list of dicts with keys: type ('tweet'|'thread'), content (str),
    hook (str — first line designed to stop the scroll).
    """
    prompt = f"""You are a social media strategist for {business_name}, a creative agency that also builds AI automation systems.

Services: {', '.join(services)}

Generate {count} high-performing X (Twitter) content ideas. Mix single tweets and thread starters.
Focus on: showing results, behind-the-scenes automation demos, client wins, tips that demonstrate expertise.

Respond with a JSON array of objects, each with:
- "type": "tweet" or "thread"
- "hook": the opening line (must stop the scroll)
- "content": full tweet text OR the first 3 tweets of a thread (separated by "---")

JSON array only, no other text."""

    try:
        raw = await generate_raw_completion(
            prompt=prompt,
            provider=provider,
            model=model,
            temperature=0.7,
            max_tokens=1200,
        )
        ideas = json.loads(raw)
        return ideas if isinstance(ideas, list) else []
    except Exception:
        logger.exception("Failed to generate content ideas")
        return []
