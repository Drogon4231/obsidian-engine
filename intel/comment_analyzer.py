"""
comment_analyzer.py — Audience intelligence from YouTube comments.

Fetches comments via YouTube Data API, analyzes sentiment and topic requests
via Claude Haiku, and produces structured intelligence for pipeline injection.

Usage:
    from comment_analyzer import get_audience_intelligence, get_comment_intelligence_block
    analysis = get_audience_intelligence("dQw4w9WgXcQ")
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"

# ── Optional dependency: YouTube API client ──────────────────────────────────
try:
    from googleapiclient.discovery import build as _yt_build
    _YOUTUBE_AVAILABLE = True
except ImportError:
    _yt_build = None
    _YOUTUBE_AVAILABLE = False

from core.agent_wrapper import call_agent

PREFIX = "[CommentAnalyzer]"


# ══════════════════════════════════════════════════════════════════════════════
# YouTube comment fetching
# ══════════════════════════════════════════════════════════════════════════════

def fetch_comments(video_id: str, max_comments: int = 100) -> list[dict]:
    """
    Fetch top-level comments for a YouTube video.

    Args:
        video_id: YouTube video ID (e.g., 'dQw4w9WgXcQ').
        max_comments: Maximum number of comments to retrieve.

    Returns:
        List of dicts: {author, text, likes, published_at}
    """
    if not _YOUTUBE_AVAILABLE:
        print(f"{PREFIX} google-api-python-client not installed — cannot fetch comments.")
        return []

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print(f"{PREFIX} YOUTUBE_API_KEY not set — cannot fetch comments.")
        return []

    try:
        youtube = _yt_build("youtube", "v3", developerKey=api_key)
    except Exception as e:
        print(f"{PREFIX} Failed to build YouTube client: {e}")
        return []

    comments = []
    next_page_token = None

    try:
        while len(comments) < max_comments:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, max_comments - len(comments)),
                order="relevance",
                textFormat="plainText",
                pageToken=next_page_token,
            )
            response = request.execute()

            for item in response.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "author": snippet.get("authorDisplayName", ""),
                    "text": snippet.get("textDisplay", ""),
                    "likes": snippet.get("likeCount", 0),
                    "published_at": snippet.get("publishedAt", ""),
                })

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        print(f"{PREFIX} Fetched {len(comments)} comments for video {video_id}")
        return comments

    except Exception as e:
        print(f"{PREFIX} Error fetching comments: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Sentiment analysis via Claude Haiku
# ══════════════════════════════════════════════════════════════════════════════

def analyze_sentiment(comments: list[dict]) -> dict:
    """
    Batch-analyze comment sentiment via Claude Haiku.

    Processes comments in batches of 20 and aggregates results.

    Returns:
        {overall_sentiment, top_topics_requested, criticisms, praise, controversy_flags}
    """
    if not comments:
        return {
            "overall_sentiment": "unknown",
            "top_topics_requested": [],
            "criticisms": [],
            "praise": [],
            "controversy_flags": [],
        }

    batch_size = 20
    batches = [comments[i:i + batch_size] for i in range(0, len(comments), batch_size)]

    all_results = []

    system_prompt = (
        "You are an audience intelligence analyst for a YouTube documentary channel "
        "called 'The Obsidian Archive' covering dark/suppressed history.\n\n"
        "Analyze the following batch of YouTube comments and return a JSON object with:\n"
        "- overall_sentiment: 'positive', 'negative', or 'mixed'\n"
        "- top_topics_requested: list of topics viewers are asking for\n"
        "- criticisms: list of specific complaints or negative feedback\n"
        "- praise: list of things viewers loved\n"
        "- controversy_flags: list of claims viewers dispute or debate\n\n"
        "Be specific and quote relevant comment excerpts when useful. Return valid JSON only."
    )

    for i, batch in enumerate(batches):
        comment_texts = "\n---\n".join(
            f"[{c.get('likes', 0)} likes] {c['text']}" for c in batch
        )
        user_prompt = f"Analyze these {len(batch)} comments:\n\n{comment_texts}"

        try:
            print(f"{PREFIX} Analyzing batch {i + 1}/{len(batches)}...")
            result = call_agent("comment_analyzer", system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=2000)
            if isinstance(result, dict):
                all_results.append(result)
        except Exception as e:
            print(f"{PREFIX} Error analyzing batch {i + 1}: {e}")

    # Aggregate results across batches
    return _aggregate_sentiment(all_results)


def _aggregate_sentiment(results: list[dict]) -> dict:
    """Merge sentiment results from multiple batches."""
    if not results:
        return {
            "overall_sentiment": "unknown",
            "top_topics_requested": [],
            "criticisms": [],
            "praise": [],
            "controversy_flags": [],
        }

    sentiments = [r.get("overall_sentiment", "mixed") for r in results]
    pos = sentiments.count("positive")
    neg = sentiments.count("negative")
    if pos > neg * 2:
        overall = "positive"
    elif neg > pos * 2:
        overall = "negative"
    else:
        overall = "mixed"

    topics = []
    criticisms = []
    praise = []
    controversy = []

    for r in results:
        topics.extend(r.get("top_topics_requested", []))
        criticisms.extend(r.get("criticisms", []))
        praise.extend(r.get("praise", []))
        controversy.extend(r.get("controversy_flags", []))

    # Deduplicate topics by rough similarity
    topic_counter = Counter(t.lower().strip() for t in topics if t)
    unique_topics = [topic for topic, _ in topic_counter.most_common(15)]

    return {
        "overall_sentiment": overall,
        "top_topics_requested": unique_topics,
        "criticisms": criticisms[:20],
        "praise": praise[:20],
        "controversy_flags": controversy[:15],
    }


# ══════════════════════════════════════════════════════════════════════════════
# Topic request extraction
# ══════════════════════════════════════════════════════════════════════════════

def extract_topic_requests(comments: list[dict]) -> list[dict]:
    """
    Mine comments for topic suggestions using keyword patterns.

    Looks for phrases like 'you should cover', 'do a video on', 'what about',
    'please make', etc.

    Returns:
        List of {topic, frequency, sample_comments} sorted by frequency.
    """
    request_patterns = [
        r"you should (?:cover|do|make|talk about|look into)\s+(.+)",
        r"do a (?:video|episode|documentary) (?:on|about)\s+(.+)",
        r"what about\s+(.+?)[\?\!\.]*$",
        r"please (?:make|do|cover)\s+(.+)",
        r"can you (?:do|cover|make a video (?:on|about))\s+(.+)",
        r"would love (?:to see|a video (?:on|about))\s+(.+)",
        r"(?:cover|explore|investigate)\s+(.+?)(?:\s+next| please|!|\?|$)",
    ]

    matches = []
    for comment in comments:
        text = comment.get("text", "").strip()
        for pattern in request_patterns:
            found = re.findall(pattern, text, re.IGNORECASE)
            for match in found:
                topic = match.strip().rstrip(".!?")
                if len(topic) > 3 and len(topic) < 200:
                    matches.append({
                        "topic": topic,
                        "source_comment": text[:200],
                        "likes": comment.get("likes", 0),
                    })

    # Aggregate by rough topic similarity
    topic_groups = {}
    for m in matches:
        key = m["topic"].lower().strip()
        if key not in topic_groups:
            topic_groups[key] = {
                "topic": m["topic"],
                "frequency": 0,
                "total_likes": 0,
                "sample_comments": [],
            }
        topic_groups[key]["frequency"] += 1
        topic_groups[key]["total_likes"] += m["likes"]
        if len(topic_groups[key]["sample_comments"]) < 3:
            topic_groups[key]["sample_comments"].append(m["source_comment"])

    # Sort by frequency, then by total likes
    sorted_topics = sorted(
        topic_groups.values(),
        key=lambda x: (x["frequency"], x["total_likes"]),
        reverse=True,
    )

    print(f"{PREFIX} Extracted {len(sorted_topics)} topic requests from comments")
    return sorted_topics[:25]


# ══════════════════════════════════════════════════════════════════════════════
# Full pipeline
# ══════════════════════════════════════════════════════════════════════════════

def get_audience_intelligence(video_id: str) -> dict:
    """
    Full comment analysis pipeline: fetch → analyze → extract.

    Saves results to outputs/comment_analysis_{video_id}.json.

    Returns:
        Summary dict with sentiment, topics, and metadata.
    """
    print(f"{PREFIX} Starting audience intelligence for video {video_id}...")

    comments = fetch_comments(video_id)
    if not comments:
        print(f"{PREFIX} No comments found — returning empty analysis.")
        return {"video_id": video_id, "status": "no_comments", "comment_count": 0}

    sentiment = analyze_sentiment(comments)
    topic_requests = extract_topic_requests(comments)

    analysis = {
        "video_id": video_id,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "comment_count": len(comments),
        "sentiment": sentiment,
        "topic_requests": topic_requests,
        "status": "complete",
    }

    # Save to outputs
    OUTPUTS_DIR.mkdir(exist_ok=True)
    output_file = OUTPUTS_DIR / f"comment_analysis_{video_id}.json"
    try:
        output_file.write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
        print(f"{PREFIX} Saved analysis to {output_file}")
    except Exception as e:
        print(f"{PREFIX} Warning: could not save analysis file: {e}")

    return analysis


def get_comment_intelligence_block(video_ids: list[str]) -> str:
    """
    Aggregate comment intelligence across multiple videos into a formatted
    string suitable for injection into agent prompts.

    Args:
        video_ids: List of YouTube video IDs to analyze.

    Returns:
        Formatted intelligence string, or '' if no data available.
    """
    all_topics = []
    all_criticisms = []
    all_praise = []
    sentiments = []

    for vid in video_ids:
        # Try loading cached analysis first
        cached = OUTPUTS_DIR / f"comment_analysis_{vid}.json"
        if cached.exists():
            try:
                data = json.loads(cached.read_text())
            except Exception:
                data = get_audience_intelligence(vid)
        else:
            data = get_audience_intelligence(vid)

        if data.get("status") != "complete":
            continue

        sentiment = data.get("sentiment", {})
        sentiments.append(sentiment.get("overall_sentiment", "unknown"))
        all_topics.extend(sentiment.get("top_topics_requested", []))
        all_criticisms.extend(sentiment.get("criticisms", []))
        all_praise.extend(sentiment.get("praise", []))

    if not sentiments:
        return ""

    # Deduplicate topics
    topic_counter = Counter(t.lower().strip() for t in all_topics if t)
    top_topics = [t for t, _ in topic_counter.most_common(10)]

    lines = [
        "## Audience Comment Intelligence",
        f"Videos analyzed: {len(video_ids)}",
        f"Overall sentiment: {', '.join(set(sentiments))}",
        "",
        "### Most Requested Topics:",
    ]
    for t in top_topics:
        lines.append(f"  - {t}")

    if all_criticisms[:5]:
        lines.append("\n### Common Criticisms:")
        for c in all_criticisms[:5]:
            lines.append(f"  - {c}")

    if all_praise[:5]:
        lines.append("\n### What Viewers Love:")
        for p in all_praise[:5]:
            lines.append(f"  - {p}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def run(video_id: str) -> dict:
    """Main entry point. Returns analysis dict."""
    return get_audience_intelligence(video_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze YouTube comments for audience intelligence.")
    parser.add_argument("video_id", help="YouTube video ID to analyze")
    parser.add_argument("--max-comments", type=int, default=100, help="Max comments to fetch")
    args = parser.parse_args()

    result = run(args.video_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
