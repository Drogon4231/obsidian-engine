"""
Shared era classification module — single source of truth.
Used by: scheduler.py, 11_youtube_uploader.py, 12_analytics_agent.py, supabase_client.py
"""

ERA_KEYWORDS = {
    "ancient_rome":   ["roman", "caesar", "emperor", "legion", "nero", "claudius", "augustus", "senate"],
    "ancient_egypt":  ["egypt", "pharaoh", "pyramid", "cleopatra", "nile", "hieroglyph", "tutankhamun"],
    "medieval":       ["medieval", "knight", "crusade", "plague", "castle", "inquisition", "feudal"],
    "ancient_greece": ["greek", "greece", "athens", "sparta", "alexander", "troy", "socrates"],
    "colonial":       ["colonial", "revolution", "conquest", "independence", "british raj"],
    "indian_history": ["india", "mughal", "maratha", "delhi", "rajput", "ashoka", "maurya", "gupta"],
    "modern":         ["world war", "nazi", "holocaust", "cold war", "vietnam", "soviet", "atomic"],
}


def classify_era(topic: str) -> str:
    """Classify a topic string into an era using keyword matching.

    Scores all eras by number of keyword hits and returns the best match.
    This prevents broad keywords like 'empire' from overshadowing specific ones.
    """
    t = topic.lower()
    scores = {}
    for era, keywords in ERA_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in t)
        if hits > 0:
            scores[era] = hits
    if not scores:
        return "other"
    return max(scores, key=scores.get)
