"""
community_engagement.py — Automated community engagement via Telegram recommendations.

Features:
  1. Comment curation: Identify top comment to pin + top 5 to heart, send Telegram
     messages with direct YouTube Studio links for manual action.
  2. Community post drafts: After each upload, generate a post draft and send via
     Telegram ready to copy-paste to the YouTube Community tab.
  3. Engagement timing: Track when comments peak, suggest optimal engagement times.

NO automated comment replies — all engagement is human-in-the-loop via Telegram.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"

PREFIX = "[Community]"


# ══════════════════════════════════════════════════════════════════════════════
# Comment Curation — find top comments for hearting/pinning
# ══════════════════════════════════════════════════════════════════════════════

def curate_comments(video_id: str, video_title: str = "") -> dict | None:
    """
    Fetch comments for a video, identify top comment to pin and top 5 to heart.
    Returns curation dict or None on failure.

    Should be called ~48h after upload when comments have accumulated.
    """
    comments = _fetch_comments_with_ids(video_id)
    if not comments:
        print(f"{PREFIX} No comments found for {video_id}")
        return None

    # Score comments: likes × 1.0 + length_bonus + question_bonus
    for c in comments:
        score = c["likes"] * 1.0
        text = c["text"].strip()
        # Bonus for substantive comments (40-500 chars)
        if 40 <= len(text) <= 500:
            score += 2
        # Bonus for questions (engagement drivers)
        if "?" in text:
            score += 1
        # Bonus for topic suggestions (community value)
        lower = text.lower()
        if any(phrase in lower for phrase in [
            "you should", "do a video", "please cover", "what about",
            "can you do", "would love to see",
        ]):
            score += 3
        # Penalty for very short comments
        if len(text) < 15:
            score -= 3
        # Penalty for all-caps (likely low quality)
        if text == text.upper() and len(text) > 10:
            score -= 2
        c["score"] = score

    ranked = sorted(comments, key=lambda c: c["score"], reverse=True)

    # Top comment to pin = highest scored, substantive (>30 chars)
    pin_candidate = None
    for c in ranked:
        if len(c["text"].strip()) >= 30:
            pin_candidate = c
            break

    # Top 5 to heart = next 5 highest scored (excluding pin candidate)
    heart_candidates = []
    for c in ranked:
        if pin_candidate and c["comment_id"] == pin_candidate["comment_id"]:
            continue
        heart_candidates.append(c)
        if len(heart_candidates) >= 5:
            break

    return {
        "video_id": video_id,
        "video_title": video_title,
        "total_comments": len(comments),
        "pin_candidate": pin_candidate,
        "heart_candidates": heart_candidates,
        "curated_at": datetime.now(timezone.utc).isoformat(),
    }


def _fetch_comments_with_ids(video_id: str, max_comments: int = 50) -> list[dict]:
    """Fetch comments including comment IDs (needed for YouTube Studio links)."""
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        TOKEN_FILE = BASE_DIR / "youtube_token.json"
        if not TOKEN_FILE.exists():
            # Fallback to API key
            api_key = os.environ.get("YOUTUBE_API_KEY")
            if not api_key:
                print(f"{PREFIX} No YouTube credentials available")
                return []
            youtube = build("youtube", "v3", developerKey=api_key)
        else:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_FILE, "w") as f:
                    f.write(creds.to_json())
            youtube = build("youtube", "v3", credentials=creds)

        comments = []
        next_page_token = None

        while len(comments) < max_comments:
            response = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(50, max_comments - len(comments)),
                order="relevance",
                textFormat="plainText",
                pageToken=next_page_token,
            ).execute()

            for item in response.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "comment_id": item["snippet"]["topLevelComment"]["id"],
                    "author": snippet.get("authorDisplayName", ""),
                    "text": snippet.get("textDisplay", ""),
                    "likes": snippet.get("likeCount", 0),
                    "published_at": snippet.get("publishedAt", ""),
                })

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        print(f"{PREFIX} Fetched {len(comments)} comments with IDs for {video_id}")
        return comments

    except Exception as e:
        print(f"{PREFIX} Error fetching comments: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Telegram Notifications — send curation recommendations
# ══════════════════════════════════════════════════════════════════════════════

def send_curation_telegram(curation: dict) -> bool:
    """
    Send comment curation recommendations to Telegram with YouTube Studio links.
    Returns True if sent successfully.
    """
    try:
        from server.notify import _tg
    except Exception:
        print(f"{PREFIX} Cannot import Telegram notifier")
        return False

    if not curation:
        return False

    video_id = curation["video_id"]
    title = curation.get("video_title", "")
    total = curation["total_comments"]

    # YouTube Studio comment management URL
    studio_url = f"https://studio.youtube.com/video/{video_id}/comments"

    lines = [
        f"*Comment Curation* — {total} comments",
        f"_{title}_" if title else "",
        "",
    ]

    # Pin recommendation
    pin = curation.get("pin_candidate")
    if pin:
        author = _escape_md(pin["author"])
        text = _escape_md(pin["text"][:150])
        likes = pin["likes"]
        lines.append("*PIN this comment:*")
        lines.append(f"  {author} ({likes} likes)")
        lines.append(f"  \"{text}\"")
        lines.append("")

    # Heart recommendations
    hearts = curation.get("heart_candidates", [])
    if hearts:
        lines.append(f"*HEART these {len(hearts)} comments:*")
        for i, h in enumerate(hearts, 1):
            author = _escape_md(h["author"])
            text = _escape_md(h["text"][:80])
            likes = h["likes"]
            lines.append(f"  {i}. {author} ({likes} likes) — \"{text}\"")
        lines.append("")

    lines.append(f"[Open YouTube Studio]({studio_url})")

    message = "\n".join(line for line in lines if line is not None)
    return _tg(message)


def _escape_md(text: str) -> str:
    """Escape Markdown special characters for Telegram."""
    for char in ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]:
        text = text.replace(char, f"\\{char}")
    return text


# ══════════════════════════════════════════════════════════════════════════════
# Community Post Drafts — generate after upload
# ══════════════════════════════════════════════════════════════════════════════

def draft_community_post(video_title: str, video_url: str, topic: str,
                         era: str = "", hook: str = "") -> dict:
    """
    Generate a community post draft for the YouTube Community tab.
    Returns dict with 'post_text' and 'poll_options'.
    """
    # Build a compelling community post
    post_lines = []

    # Opening hook
    if hook:
        # Use the video's hook line as the opening
        post_lines.append(hook[:200])
    else:
        post_lines.append("New deep dive just dropped.")

    post_lines.append("")
    post_lines.append(f"{video_title}")
    post_lines.append(video_url)
    post_lines.append("")

    # Engagement question based on topic
    questions = _generate_engagement_questions(topic, era)
    if questions:
        post_lines.append(questions[0])

    post_text = "\n".join(post_lines)

    # Poll suggestion
    poll_options = _generate_poll_options(topic, era)

    return {
        "post_text": post_text,
        "poll_options": poll_options,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _generate_engagement_questions(topic: str, era: str = "") -> list[str]:
    """Generate engagement questions based on the video topic."""
    topic_lower = topic.lower()

    # Era-specific questions
    if any(word in topic_lower for word in ["ancient", "roman", "greek", "egypt"]):
        return [
            "What part of this story surprised you the most? Drop it in the comments.",
            "Which ancient civilization do you think had the darkest secrets?",
        ]
    elif any(word in topic_lower for word in ["medieval", "dark age", "crusade", "plague"]):
        return [
            "Could you have survived this? Be honest.",
            "What medieval mystery should we investigate next?",
        ]
    elif any(word in topic_lower for word in ["war", "battle", "military", "soldier"]):
        return [
            "History is written by the victors. What do you think really happened?",
            "What's the most overlooked conflict in history?",
        ]
    elif any(word in topic_lower for word in ["conspiracy", "secret", "cover", "hidden"]):
        return [
            "Do you think the truth is still being hidden? Let us know below.",
            "What other cover-ups should we dig into?",
        ]
    elif any(word in topic_lower for word in ["murder", "death", "assassin", "poison"]):
        return [
            "Who do you think was really behind it? Drop your theory.",
            "What's the most suspicious death in history that no one talks about?",
        ]

    # Generic fallback
    return [
        "What part of this story shocked you the most?",
        "What dark chapter of history should we cover next?",
    ]


def _generate_poll_options(topic: str, era: str = "") -> list[str]:
    """Generate poll options for community engagement."""
    topic_lower = topic.lower()

    if any(word in topic_lower for word in ["murder", "death", "assassin", "poison"]):
        return [
            "Political rivals did it",
            "Family betrayal",
            "It was an accident / natural",
            "We'll never know the truth",
        ]
    elif any(word in topic_lower for word in ["conspiracy", "secret", "cover"]):
        return [
            "Definitely a cover-up",
            "Partly true, partly myth",
            "Just a coincidence",
            "The truth is even darker",
        ]
    elif any(word in topic_lower for word in ["war", "battle", "empire"]):
        return [
            "They were heroes",
            "They were villains",
            "Somewhere in between",
            "History got it completely wrong",
        ]

    # Generic poll
    return [
        "This blew my mind",
        "I already knew about this",
        "I need a Part 2",
        "Cover something even darker",
    ]


def send_community_post_telegram(draft: dict, video_title: str = "") -> bool:
    """Send community post draft to Telegram for manual posting."""
    try:
        from server.notify import _tg
    except Exception:
        print(f"{PREFIX} Cannot import Telegram notifier")
        return False

    post_text = draft.get("post_text", "")
    poll_options = draft.get("poll_options", [])

    lines = [
        "*Community Post Draft*",
        f"_{_escape_md(video_title)}_" if video_title else "",
        "",
        "Copy this to YouTube Community tab:",
        "",
        "```",
        post_text,
        "```",
    ]

    if poll_options:
        lines.append("")
        lines.append("*Suggested poll options:*")
        for i, opt in enumerate(poll_options, 1):
            lines.append(f"  {i}. {opt}")

    lines.append("")
    lines.append("_Post this within 1-2 hours of upload for best reach._")

    message = "\n".join(line for line in lines if line is not None)
    return _tg(message)


# ══════════════════════════════════════════════════════════════════════════════
# Engagement Timing Intelligence
# ══════════════════════════════════════════════════════════════════════════════

def analyze_comment_timing(video_id: str) -> dict | None:
    """
    Analyze when comments are posted to identify peak engagement windows.
    Returns timing analysis or None if insufficient data.
    """
    comments = _fetch_comments_with_ids(video_id, max_comments=50)
    if len(comments) < 5:
        return None

    # Parse timestamps and compute hours-since-upload
    hours = []
    for c in comments:
        published = c.get("published_at", "")
        if not published:
            continue
        try:
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            hours.append(dt.hour)
        except Exception:
            continue

    if not hours:
        return None

    # Find peak hours (UTC)
    hour_counts = Counter(hours)
    peak_hours = [h for h, _ in hour_counts.most_common(3)]

    return {
        "video_id": video_id,
        "total_analyzed": len(hours),
        "peak_hours_utc": peak_hours,
        "hour_distribution": dict(hour_counts),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_engagement_timing_summary(video_ids: list[str]) -> dict:
    """
    Aggregate timing data across multiple videos to find optimal engagement windows.
    """
    all_hours = Counter()
    videos_analyzed = 0

    for vid in video_ids:
        timing = analyze_comment_timing(vid)
        if timing:
            for hour, count in timing.get("hour_distribution", {}).items():
                all_hours[int(hour)] += count
            videos_analyzed += 1

    if not all_hours:
        return {"status": "insufficient_data", "videos_analyzed": 0}

    peak_hours = [h for h, _ in all_hours.most_common(3)]

    # Convert UTC hours to human-readable windows
    windows = []
    for h in peak_hours:
        end_h = (h + 2) % 24
        windows.append(f"{h:02d}:00-{end_h:02d}:00 UTC")

    return {
        "videos_analyzed": videos_analyzed,
        "peak_hours_utc": peak_hours,
        "recommended_windows": windows,
        "total_comments_analyzed": sum(all_hours.values()),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Pipeline Integration — orchestrator functions
# ══════════════════════════════════════════════════════════════════════════════

def run_post_upload(video_id: str, video_title: str, video_url: str,
                    topic: str, era: str = "", hook: str = "") -> dict:
    """
    Run immediately after upload: generate and send community post draft.
    Returns results dict.
    """
    results = {"status": "started"}

    # 1. Draft and send community post
    try:
        draft = draft_community_post(video_title, video_url, topic, era, hook)
        sent = send_community_post_telegram(draft, video_title)
        results["community_post"] = {
            "draft": draft,
            "telegram_sent": sent,
        }
        if sent:
            print(f"{PREFIX} Community post draft sent to Telegram")
    except Exception as e:
        print(f"{PREFIX} Community post draft failed: {e}")
        results["community_post"] = {"error": str(e)}

    results["status"] = "complete"
    return results


def run_48h_curation(video_id: str, video_title: str = "") -> dict:
    """
    Run ~48h after upload: curate comments and send recommendations.
    Called by the analytics agent during its daily run.
    Returns results dict.
    """
    results = {"status": "started"}

    # 1. Curate comments
    try:
        curation = curate_comments(video_id, video_title)
        if curation:
            sent = send_curation_telegram(curation)
            results["curation"] = {
                "total_comments": curation["total_comments"],
                "pin_candidate": curation["pin_candidate"]["author"] if curation.get("pin_candidate") else None,
                "heart_count": len(curation.get("heart_candidates", [])),
                "telegram_sent": sent,
            }
            if sent:
                print(f"{PREFIX} Comment curation sent to Telegram for {video_id}")

            # Save curation to outputs
            try:
                OUTPUTS_DIR.mkdir(exist_ok=True)
                out_path = OUTPUTS_DIR / f"comment_curation_{video_id}.json"
                out_path.write_text(json.dumps(curation, indent=2, ensure_ascii=False))
            except Exception:
                pass
        else:
            results["curation"] = {"status": "no_comments"}
    except Exception as e:
        print(f"{PREFIX} Comment curation failed: {e}")
        results["curation"] = {"error": str(e)}

    # 2. Engagement timing (only if we have data)
    try:
        timing = analyze_comment_timing(video_id)
        if timing:
            results["timing"] = timing
    except Exception as e:
        results["timing"] = {"error": str(e)}

    results["status"] = "complete"
    return results
