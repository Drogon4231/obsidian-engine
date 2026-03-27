"""Tests for intel/community_engagement.py — comment curation, post drafts, timing."""

from unittest.mock import patch

from intel.community_engagement import (
    curate_comments,
    draft_community_post,
    send_curation_telegram,
    send_community_post_telegram,
    analyze_comment_timing,
    compute_engagement_timing_summary,
    run_post_upload,
    run_48h_curation,
    _escape_md,
    _generate_engagement_questions,
    _generate_poll_options,
)


# ══════════════════════════════════════════════════════════════════════════════
# Comment Curation
# ══════════════════════════════════════════════════════════════════════════════

class TestCurateComments:
    """Test comment scoring and ranking logic."""

    def _mock_comments(self):
        return [
            {"comment_id": "c1", "author": "Alice", "text": "This was absolutely incredible, the research depth is amazing!", "likes": 15, "published_at": "2026-03-20T10:00:00Z"},
            {"comment_id": "c2", "author": "Bob", "text": "First!", "likes": 2, "published_at": "2026-03-20T09:00:00Z"},
            {"comment_id": "c3", "author": "Charlie", "text": "You should do a video on the Tunguska event, that would be perfect for this channel", "likes": 8, "published_at": "2026-03-20T12:00:00Z"},
            {"comment_id": "c4", "author": "Diana", "text": "What was the source for the claim about the missing documents?", "likes": 5, "published_at": "2026-03-20T14:00:00Z"},
            {"comment_id": "c5", "author": "Eve", "text": "ok", "likes": 0, "published_at": "2026-03-20T15:00:00Z"},
            {"comment_id": "c6", "author": "Frank", "text": "The narration style reminds me of old History Channel docs, in the best way possible", "likes": 10, "published_at": "2026-03-20T11:00:00Z"},
            {"comment_id": "c7", "author": "Grace", "text": "LMAO THIS IS SO FAKE", "likes": 1, "published_at": "2026-03-20T16:00:00Z"},
        ]

    @patch("intel.community_engagement._fetch_comments_with_ids")
    def test_pin_candidate_is_top_substantive(self, mock_fetch):
        mock_fetch.return_value = self._mock_comments()
        result = curate_comments("test123", "Test Video")
        assert result is not None
        # Pin should be a substantive comment (>=30 chars), highest score
        pin = result["pin_candidate"]
        assert pin is not None
        assert len(pin["text"]) >= 30
        # Alice has 15 likes + length bonus = top scorer
        assert pin["author"] == "Alice"

    @patch("intel.community_engagement._fetch_comments_with_ids")
    def test_heart_candidates_exclude_pin(self, mock_fetch):
        mock_fetch.return_value = self._mock_comments()
        result = curate_comments("test123")
        pin_id = result["pin_candidate"]["comment_id"]
        heart_ids = [c["comment_id"] for c in result["heart_candidates"]]
        assert pin_id not in heart_ids

    @patch("intel.community_engagement._fetch_comments_with_ids")
    def test_heart_candidates_max_5(self, mock_fetch):
        mock_fetch.return_value = self._mock_comments()
        result = curate_comments("test123")
        assert len(result["heart_candidates"]) <= 5

    @patch("intel.community_engagement._fetch_comments_with_ids")
    def test_topic_suggestion_gets_bonus(self, mock_fetch):
        mock_fetch.return_value = self._mock_comments()
        result = curate_comments("test123")
        # Charlie's comment has "you should do a video" → bonus
        hearts = result["heart_candidates"]
        charlie = next((c for c in hearts if c["author"] == "Charlie"), None)
        # Charlie should rank high despite fewer likes than Frank
        assert charlie is not None

    @patch("intel.community_engagement._fetch_comments_with_ids")
    def test_short_comments_penalized(self, mock_fetch):
        mock_fetch.return_value = self._mock_comments()
        result = curate_comments("test123")
        # Short comments should rank lower than substantive ones
        bob_score = next(c["score"] for c in result["heart_candidates"] + [result["pin_candidate"]] if c["author"] == "Bob")
        frank_score = next(c["score"] for c in result["heart_candidates"] + [result["pin_candidate"]] if c["author"] == "Frank")
        # Frank (substantive, 10 likes) should outscore Bob ("First!", 2 likes)
        assert frank_score > bob_score

    @patch("intel.community_engagement._fetch_comments_with_ids")
    def test_no_comments_returns_none(self, mock_fetch):
        mock_fetch.return_value = []
        result = curate_comments("test123")
        assert result is None

    @patch("intel.community_engagement._fetch_comments_with_ids")
    def test_all_caps_penalized(self, mock_fetch):
        mock_fetch.return_value = self._mock_comments()
        result = curate_comments("test123")
        # All-caps comment should score lower than substantive ones with similar likes
        all_scored = [result["pin_candidate"]] + result["heart_candidates"]
        grace_score = next(c["score"] for c in all_scored if c["author"] == "Grace")
        diana_score = next(c["score"] for c in all_scored if c["author"] == "Diana")
        # Diana (5 likes, question) should outscore Grace (1 like, all caps)
        assert diana_score > grace_score


# ══════════════════════════════════════════════════════════════════════════════
# Community Post Drafts
# ══════════════════════════════════════════════════════════════════════════════

class TestDraftCommunityPost:
    def test_basic_draft(self):
        draft = draft_community_post(
            video_title="The Lost City of Z",
            video_url="https://youtube.com/watch?v=abc123",
            topic="The Lost City of Z",
        )
        assert "post_text" in draft
        assert "poll_options" in draft
        assert "The Lost City of Z" in draft["post_text"]
        assert "youtube.com" in draft["post_text"]
        assert len(draft["poll_options"]) >= 3

    def test_hook_included_when_provided(self):
        draft = draft_community_post(
            video_title="Test",
            video_url="https://youtube.com/watch?v=x",
            topic="test",
            hook="In 1347, a ship arrived carrying more than cargo.",
        )
        assert "1347" in draft["post_text"]

    def test_murder_topic_gets_specific_poll(self):
        draft = draft_community_post(
            video_title="The Assassination of Caesar",
            video_url="https://youtube.com/watch?v=x",
            topic="The Assassination of Julius Caesar",
        )
        # Should get murder-specific poll options
        poll_lower = [o.lower() for o in draft["poll_options"]]
        assert any("rivals" in o or "betrayal" in o or "accident" in o for o in poll_lower)

    def test_conspiracy_topic_poll(self):
        draft = draft_community_post(
            video_title="The Secret of X",
            video_url="https://youtube.com/watch?v=x",
            topic="The Secret Government Cover-Up",
        )
        poll_lower = [o.lower() for o in draft["poll_options"]]
        assert any("cover" in o or "myth" in o for o in poll_lower)


class TestEngagementQuestions:
    def test_ancient_topic(self):
        qs = _generate_engagement_questions("The Fall of Ancient Rome")
        assert len(qs) >= 1
        assert any("ancient" in q.lower() or "surprised" in q.lower() for q in qs)

    def test_medieval_topic(self):
        qs = _generate_engagement_questions("The Black Plague of Medieval Europe")
        assert len(qs) >= 1

    def test_generic_fallback(self):
        qs = _generate_engagement_questions("Something completely unrelated")
        assert len(qs) >= 1


class TestPollOptions:
    def test_always_returns_options(self):
        opts = _generate_poll_options("Random Topic")
        assert len(opts) >= 3

    def test_war_topic(self):
        opts = _generate_poll_options("The Battle of Thermopylae")
        assert len(opts) >= 3


# ══════════════════════════════════════════════════════════════════════════════
# Telegram Sending
# ══════════════════════════════════════════════════════════════════════════════

class TestTelegramSending:
    @patch("server.notify._tg", return_value=True)
    def test_send_curation(self, mock_tg):
        curation = {
            "video_id": "abc123",
            "video_title": "Test Video",
            "total_comments": 42,
            "pin_candidate": {"author": "Alice", "text": "Great video!", "likes": 10, "comment_id": "c1"},
            "heart_candidates": [
                {"author": "Bob", "text": "Amazing", "likes": 5, "comment_id": "c2"},
            ],
            "curated_at": "2026-03-20T10:00:00Z",
        }
        result = send_curation_telegram(curation)
        assert result is True

    @patch("server.notify._tg", return_value=True)
    def test_send_community_post(self, mock_tg):
        draft = {
            "post_text": "New video!\nCheck it out",
            "poll_options": ["Option A", "Option B", "Option C"],
        }
        result = send_community_post_telegram(draft, "Test Video")
        assert result is True

    def test_send_curation_none_returns_false(self):
        result = send_curation_telegram(None)
        assert result is False


# ══════════════════════════════════════════════════════════════════════════════
# Engagement Timing
# ══════════════════════════════════════════════════════════════════════════════

class TestEngagementTiming:
    @patch("intel.community_engagement._fetch_comments_with_ids")
    def test_analyze_timing(self, mock_fetch):
        # Comments at various hours
        mock_fetch.return_value = [
            {"comment_id": f"c{i}", "author": f"User{i}", "text": "comment",
             "likes": 0, "published_at": f"2026-03-20T{h:02d}:00:00Z"}
            for i, h in enumerate([14, 14, 14, 15, 15, 20])
        ]
        result = analyze_comment_timing("vid123")
        assert result is not None
        assert 14 in result["peak_hours_utc"]

    @patch("intel.community_engagement._fetch_comments_with_ids")
    def test_insufficient_comments(self, mock_fetch):
        mock_fetch.return_value = [
            {"comment_id": "c1", "author": "A", "text": "hi", "likes": 0, "published_at": "2026-03-20T10:00:00Z"},
        ]
        result = analyze_comment_timing("vid123")
        assert result is None

    @patch("intel.community_engagement.analyze_comment_timing")
    def test_timing_summary(self, mock_timing):
        mock_timing.side_effect = [
            {"video_id": "v1", "total_analyzed": 10, "peak_hours_utc": [14, 15], "hour_distribution": {14: 5, 15: 3, 20: 2}},
            {"video_id": "v2", "total_analyzed": 8, "peak_hours_utc": [14, 16], "hour_distribution": {14: 4, 16: 3, 10: 1}},
        ]
        result = compute_engagement_timing_summary(["v1", "v2"])
        assert result["videos_analyzed"] == 2
        assert 14 in result["peak_hours_utc"]  # Most common across both


# ══════════════════════════════════════════════════════════════════════════════
# Pipeline Integration
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    @patch("server.notify._tg", return_value=True)
    def test_run_post_upload(self, mock_tg):
        result = run_post_upload(
            video_id="abc123",
            video_title="The Lost City",
            video_url="https://youtube.com/watch?v=abc123",
            topic="The Lost City of Z",
        )
        assert result["status"] == "complete"
        assert "community_post" in result
        assert result["community_post"]["telegram_sent"] is True

    @patch("intel.community_engagement._fetch_comments_with_ids")
    @patch("server.notify._tg", return_value=True)
    def test_run_48h_curation(self, mock_tg, mock_fetch):
        mock_fetch.return_value = [
            {"comment_id": "c1", "author": "Alice", "text": "This documentary was absolutely incredible, the depth of research really shows", "likes": 20, "published_at": "2026-03-20T10:00:00Z"},
            {"comment_id": "c2", "author": "Bob", "text": "You should cover the Dyatlov Pass incident next", "likes": 8, "published_at": "2026-03-20T12:00:00Z"},
            {"comment_id": "c3", "author": "Charlie", "text": "Amazing work as always, subscribed!", "likes": 5, "published_at": "2026-03-20T14:00:00Z"},
            {"comment_id": "c4", "author": "Diana", "text": "What sources did you use for the third segment?", "likes": 3, "published_at": "2026-03-20T15:00:00Z"},
            {"comment_id": "c5", "author": "Eve", "text": "The narration gave me chills, especially the ending", "likes": 12, "published_at": "2026-03-20T11:00:00Z"},
            {"comment_id": "c6", "author": "Frank", "text": "Good", "likes": 0, "published_at": "2026-03-20T16:00:00Z"},
        ]
        result = run_48h_curation("abc123", "Test Video")
        assert result["status"] == "complete"
        assert "curation" in result
        assert result["curation"]["telegram_sent"] is True


# ══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ══════════════════════════════════════════════════════════════════════════════

class TestHelpers:
    def test_escape_md(self):
        assert "\\*bold\\*" == _escape_md("*bold*")
        assert "\\_italic\\_" == _escape_md("_italic_")
        assert "hello world" == _escape_md("hello world")

    def test_escape_md_brackets(self):
        assert "\\[link\\]" == _escape_md("[link]")
