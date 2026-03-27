"""Tests for era_classifier.py — keyword-based historical era classification."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from intel.era_classifier import classify_era, ERA_KEYWORDS


class TestClassifyEra:
    def test_ancient_rome(self):
        assert classify_era("The Fall of Julius Caesar") == "ancient_rome"

    def test_ancient_rome_emperor(self):
        assert classify_era("Emperor Nero's Madness") == "ancient_rome"

    def test_ancient_egypt(self):
        assert classify_era("The Curse of Tutankhamun") == "ancient_egypt"

    def test_ancient_egypt_pharaoh(self):
        assert classify_era("Secrets of the Pharaoh") == "ancient_egypt"

    def test_medieval(self):
        assert classify_era("The Black Plague") == "medieval"

    def test_medieval_crusade(self):
        assert classify_era("The First Crusade") == "medieval"

    def test_ancient_greece(self):
        assert classify_era("The Battle of Sparta") == "ancient_greece"

    def test_ancient_greece_alexander(self):
        assert classify_era("Alexander the Great") == "ancient_greece"

    def test_colonial(self):
        assert classify_era("The American Revolution") == "colonial"

    def test_colonial_british_raj(self):
        assert classify_era("Life Under the British Raj") == "colonial"

    def test_indian_history(self):
        assert classify_era("The Mughal Empire") == "indian_history"

    def test_indian_history_maratha(self):
        assert classify_era("Rise of the Maratha Warriors") == "indian_history"

    def test_modern(self):
        assert classify_era("World War II Secrets") == "modern"

    def test_modern_cold_war(self):
        assert classify_era("The Cold War Espionage") == "modern"

    def test_other_unclassifiable(self):
        assert classify_era("Random Topic About Nothing") == "other"

    def test_empty_string(self):
        assert classify_era("") == "other"

    def test_case_insensitive(self):
        assert classify_era("CAESAR WAS BETRAYED") == "ancient_rome"
        assert classify_era("the pharaoh's tomb") == "ancient_egypt"

    def test_mughal_not_in_colonial(self):
        """Mughal should classify as indian_history, not colonial."""
        # colonial is checked before indian_history in dict order,
        # but mughal was removed from colonial keywords
        assert classify_era("Mughal Dynasty") == "indian_history"

    def test_no_keyword_overlap_causes_wrong_era(self):
        """India-specific topics should not classify as colonial."""
        result = classify_era("The Rajput Kingdoms of India")
        assert result == "indian_history"


class TestEraKeywords:
    def test_all_eras_have_keywords(self):
        for era, keywords in ERA_KEYWORDS.items():
            assert len(keywords) >= 2, f"Era '{era}' has too few keywords"

    def test_no_empty_keywords(self):
        for era, keywords in ERA_KEYWORDS.items():
            for kw in keywords:
                assert kw.strip(), f"Empty keyword in era '{era}'"

    def test_all_keywords_lowercase(self):
        for era, keywords in ERA_KEYWORDS.items():
            for kw in keywords:
                assert kw == kw.lower(), f"Keyword '{kw}' in era '{era}' is not lowercase"

    def test_mughal_only_in_indian_history(self):
        """Verify mughal doesn't appear in colonial after our fix."""
        for era, keywords in ERA_KEYWORDS.items():
            if era != "indian_history":
                assert "mughal" not in keywords, f"'mughal' found in '{era}' — should only be in indian_history"

    def test_empire_not_in_colonial(self):
        """'empire' is too generic — should not be in colonial keywords."""
        assert "empire" not in ERA_KEYWORDS.get("colonial", [])
