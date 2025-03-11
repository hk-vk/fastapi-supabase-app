import re
import string
from typing import Dict, List, Tuple, Optional, Set
from functools import lru_cache
import numpy as np
from collections import Counter
import logging
import os
import gc

# Configure logging for production environment
logger = logging.getLogger(__name__)

# Singleton pattern for analyzer to reduce memory usage
_ANALYZER_INSTANCE = None

def get_analyzer() -> 'EnhancedMalayalamAnalyzer':
    """Factory function for analyzer instance with singleton pattern"""
    global _ANALYZER_INSTANCE
    if _ANALYZER_INSTANCE is None:
        _ANALYZER_INSTANCE = EnhancedMalayalamAnalyzer()
    return _ANALYZER_INSTANCE

class EnhancedMalayalamAnalyzer:
    """Enhanced analyzer for Malayalam text with improved pattern recognition"""
    
    def __init__(self):
        # Initialize pattern dictionaries
        self.patterns = {}
        self.weights = {}
        # Malayalam Unicode range
        self.malayalam_range = re.compile(r'[\u0D00-\u0D7F]')
        self._compile_patterns()
        # Force garbage collection after initialization
        gc.collect()
        logger.info("Malayalam text analyzer initialized for production")
    
    def _compile_patterns(self) -> None:
        """Compile patterns for Malayalam text analysis"""
        # Clickbait patterns - both Malayalam and transliterated
        self.patterns['clickbait'] = [
            # Sensational Malayalam words
            (r'അത്ഭുതകരമായ|അദ്ഭുതം|വിസ്മയകരം', 25),  # Amazing/wonderful
            (r'ഞെട്ടിക്കുന്ന|ഞെട്ടിപ്പിക്കുന്ന|ഞെട്ടൽ', 30),  # Shocking
            (r'വിശ്വസിക്കാനാവില്ല|അവിശ്വസനീയം', 25),  # Unbelievable
            (r'രഹസ്യം|രഹസ്യങ്ങൾ|ഗൂഢരഹസ്യം', 20),  # Secret/secrets
            (r'വൈറൽ|തരംഗമാകുന്ന|ട്രെൻഡിംഗ്', 15),  # Viral/trending
            
            # Question patterns (common in Malayalam clickbait)
            (r'നിങ്ങൾക്കറിയാമോ\?|എന്തുകൊണ്ട്\?|എങ്ങനെ\?', 20),  # Did you know?/Why?/How?
            
            # Numerical clickbait in Malayalam
            (r'\d+ കാര്യങ്ങൾ|\d+ വഴികൾ|\d+ രഹസ്യങ്ങൾ', 25),  # N things/ways/secrets
            
            # Urgency patterns in Malayalam
            (r'ഉടൻ|ഇപ്പോൾ തന്നെ|ഇന്ന്|ഈ നിമിഷം', 20),  # Now/immediately/today
            (r'അവസാന അവസരം|സമയം തീരുന്നതിന് മുമ്പ്', 25),  # Last chance/before time runs out
            
            # Common Malayalam clickbait phrases
            (r'നിങ്ങൾ ഇത് കണ്ടോ|നിങ്ങൾ അറിയേണ്ടത്', 25),  # You must see this/You need to know
            (r'ഇതാണ് യഥാർത്ഥ|ഇതാണ് സത്യം', 20),  # This is the real/This is the truth
            
            # Transliterated clickbait (Malayalam written in English)
            (r'njettikkuna|athbhutham|vishwasikkaan kazhiyilla', 15),
            (r'viral|trending|rahasyam|shock', 15),
            
            # English clickbait (common in Malayalam media)
            (r'shocking|amazing|unbelievable|must see', 15),
            (r'won\'t believe|never seen|exclusive|revealed', 15),
        ]
        
        # Writing style patterns - formal vs informal Malayalam
        self.patterns['writing_style'] = [
            # Formal Malayalam connectors
            (r'അതിനാൽ|ആയതിനാൽ|അതിന്റെ ഫലമായി', 15),  # Therefore/as a result
            (r'എന്നിരുന്നാലും|എന്നാൽ|എങ്കിലും', 10),  # However/nevertheless
            
            # Academic/research terms in Malayalam
            (r'പഠനം|ഗവേഷണം|നിരീക്ഷണം|വിശകലനം', 15),  # Study/research/observation/analysis
            
            # Balanced presentation in Malayalam
            (r'ഒരുവശത്ത്|മറുവശത്ത്|എന്നാൽ|മറിച്ച്', 10),  # On one hand/on the other hand
            
            # Citation patterns in Malayalam
            (r'അനുസരിച്ച്|പ്രകാരം|അഭിപ്രായത്തിൽ', 15),  # According to/as per
            
            # Complex Malayalam sentence structures
            (r'എന്നത് കൊണ്ട് അർത്ഥമാക്കുന്നത്|എന്നതിനർത്ഥം', 20),  # Which means that
            
            # Statistical references in Malayalam
            (r'ശതമാനം|അനുപാതം|കണക്കനുസരിച്ച്', 15),  # Percentage/ratio/according to statistics
            
            # Objective tone markers in Malayalam
            (r'വസ്തുതകൾ|യാഥാർത്ഥ്യം|വസ്തുനിഷ്ഠമായി', 15),  # Facts/reality/objectively
        ]
        
        # Sensationalism patterns specific to Malayalam news
        self.patterns['sensationalism'] = [
            # Emotional language in Malayalam
            (r'ദുരന്തം|ദുരിതം|ദുഃഖം|വേദന', 25),  # Tragedy/suffering/sorrow/pain
            (r'ഭീകരം|ഭയാനകം|ഭീതി|ഭയം', 25),  # Terrible/frightening/fear
            
            # Exaggeration in Malayalam
            (r'എക്കാലത്തെയും|ഏറ്റവും വലിയ|ചരിത്രത്തിലെ ആദ്യം', 20),  # All-time/biggest/first in history
            
            # Dramatic language in Malayalam
            (r'അടിമറിച്ചു|തകർത്തു|തച്ചുടച്ചു', 20),  # Overthrown/shattered/smashed
            
            # Conflict words in Malayalam
            (r'സംഘർഷം|യുദ്ധം|പോരാട്ടം|ഏറ്റുമുട്ടൽ', 20),  # Conflict/war/struggle/clash
            
            # Scandal/controversy in Malayalam
            (r'വിവാദം|ആരോപണം|കുംഭകോണം|അഴിമതി', 25),  # Controversy/allegation/scam/corruption
        ]
        
        # Compile all patterns for performance
        for pattern_type in self.patterns:
            compiled_patterns = []
            for pattern, weight in self.patterns[pattern_type]:
                try:
                    compiled_patterns.append((re.compile(pattern, re.IGNORECASE), weight))
                except re.error as e:
                    logger.error(f"Failed to compile pattern '{pattern}': {e}")
            self.patterns[pattern_type] = compiled_patterns

    @lru_cache(maxsize=512)  # Reduced cache size for production
    def _preprocess_text(self, text: str) -> Tuple[tuple, tuple]:
        """Preprocess text for analysis with Malayalam support"""
        try:
            # Split into sentences (supporting Malayalam punctuation)
            sentences = re.split(r'[.!?।॥\u0964\u0965]+', text)
            sentences = tuple(s.strip() for s in sentences if len(s.strip()) > 0)
            
            # Split into words (supporting Malayalam characters)
            words = re.findall(r'[\w\u0D00-\u0D7F]+', text.lower())
            words = tuple(words)
            
            return sentences, words
        except Exception as e:
            logger.error(f"Error preprocessing text: {e}")
            return tuple(), tuple()

    def _calculate_text_stats(self, sentences: tuple, words: tuple) -> Dict[str, float]:
        """Calculate text statistics with Malayalam considerations"""
        try:
            if not sentences or not words:
                return {"avg_sentence_length": 0, "lexical_diversity": 0}
            
            avg_sentence_length = len(words) / len(sentences)
            
            # Lexical diversity (unique words / total words)
            unique_words = len(set(words))
            lexical_diversity = unique_words / len(words) if words else 0
            
            return {
                "avg_sentence_length": avg_sentence_length,
                "lexical_diversity": lexical_diversity
            }
        except Exception as e:
            logger.error(f"Error calculating text stats: {e}")
            return {"avg_sentence_length": 0, "lexical_diversity": 0}

    def _analyze_patterns(self, text: str, pattern_type: str) -> Tuple[int, int]:
        """Analyze text for patterns with Malayalam support"""
        try:
            if pattern_type not in self.patterns:
                return 0, 0
                
            total_score = 0
            match_count = 0
            
            # Check if text contains Malayalam characters
            has_malayalam = bool(self.malayalam_range.search(text))
            
            for pattern, weight in self.patterns[pattern_type]:
                matches = pattern.findall(text)
                if matches:
                    # Adjust weight for Malayalam content
                    adjusted_weight = weight * 1.2 if has_malayalam else weight
                    match_count += len(matches)
                    total_score += len(matches) * adjusted_weight
                    
            return total_score, match_count
        except Exception as e:
            logger.error(f"Error analyzing patterns: {e}")
            return 0, 0

    def analyze_writing_style(self, text: str) -> float:
        """Analyze writing style quality with Malayalam support"""
        try:
            sentences, words = self._preprocess_text(text)
            
            # Get basic text statistics
            stats = self._calculate_text_stats(sentences, words)
            
            # Analyze for formal writing patterns
            style_score, style_count = self._analyze_patterns(text, 'writing_style')
            
            # Factor in sentence length (adjusted for Malayalam)
            length_factor = min(100, stats["avg_sentence_length"] * 5)
            
            # Factor in lexical diversity
            diversity_factor = min(100, stats["lexical_diversity"] * 200)
            
            # Check Malayalam content ratio
            malayalam_chars = sum(1 for c in text if '\u0D00' <= c <= '\u0D7F')
            malayalam_ratio = malayalam_chars / len(text) if text else 0
            
            # Adjust scoring for Malayalam text
            if malayalam_ratio > 0.3:
                # Malayalam text typically has longer sentences
                length_factor *= 0.8
                # Adjust for Malayalam morphological richness
                diversity_factor *= 1.2
            
            # Combined quality score
            combined_score = (
                (style_score * 0.5) + 
                (length_factor * 0.25) + 
                (diversity_factor * 0.25)
            )
            
            # Higher score means more formal/quality writing
            return self._normalize_score(combined_score)
        except Exception as e:
            logger.error(f"Error analyzing writing style: {e}")
            return 50.0  # Return neutral score on error

    def calculate_clickbait_score(self, text: str) -> float:
        """Calculate clickbait score with enhanced Malayalam support"""
        try:
            total_score, match_count = self._analyze_patterns(text, 'clickbait')
            
            # Check if text contains Malayalam characters
            has_malayalam = bool(self.malayalam_range.search(text))
            
            # Adjust max observed value based on language
            max_observed = 500 if has_malayalam else 400
            
            # Calculate score with length penalty
            text_length = len(text)
            length_factor = 1.0
            if text_length > 1000:
                length_factor = 0.8  # Reduce score for very long texts
            
            normalized_score = (total_score / max_observed) * 100 * length_factor
            return self._normalize_score(normalized_score)
        except Exception as e:
            logger.error(f"Error calculating clickbait score: {e}")
            return 0.0  # Return low score on error

    @lru_cache(maxsize=256)  # Reduced cache size for production
    def _normalize_score(self, score: float) -> float:
        """Normalize score to 0-100 range using sigmoid function"""
        try:
            # Sigmoid normalization centered at 50
            normalized = 100 / (1 + np.exp(-0.1 * (score - 50)))
            return max(0, min(100, normalized))
        except Exception as e:
            logger.error(f"Error normalizing score: {e}")
            return 50.0  # Return neutral score on error

    def analyze_text(self, text: str) -> Dict[str, float]:
        """Main analysis function returning the required parameters"""
        try:
            # Input validation
            if not isinstance(text, str):
                logger.warning("Non-string input provided to analyze_text")
                return {
                    'sensationalism': 0.0,
                    'writingStyle': 0.0,
                    'clickbait': 0.0
                }
            
            # Process even short text
            if not text.strip():
                logger.debug("Empty text provided for analysis")
                return {
                    'sensationalism': 0.0,
                    'writingStyle': 0.0,
                    'clickbait': 0.0
                }
            
            # Limit text length for performance and memory usage
            text = text[:3000]  # Reduced from 5000 for production
            
            # Check Malayalam content
            has_malayalam = bool(self.malayalam_range.search(text))
            
            # Calculate writing style score (higher = better quality)
            writing_style = self.analyze_writing_style(text)
            
            # Calculate clickbait score
            clickbait_score = self.calculate_clickbait_score(text)
            
            # Calculate sensationalism directly or from patterns
            if has_malayalam:
                # For Malayalam text, use dedicated sensationalism patterns
                sens_score, _ = self._analyze_patterns(text, 'sensationalism')
                max_sens = 400  # Adjusted for Malayalam
                sensationalism = (sens_score / max_sens) * 100
                # Blend with clickbait for comprehensive score
                sensationalism = (sensationalism * 0.6) + (clickbait_score * 0.4)
            else:
                # For non-Malayalam, derive from clickbait and inverse of writing style
                sensationalism = (clickbait_score * 0.7) + ((100 - writing_style) * 0.3)
            
            # Return the same format as the original implementation
            return {
                'sensationalism': self._normalize_score(sensationalism),
                'writingStyle': self._normalize_score(writing_style),
                'clickbait': self._normalize_score(clickbait_score)
            }
        except Exception as e:
            logger.error(f"Error in analyze_text: {e}", exc_info=True)
            # Return neutral values on error for graceful degradation
            return {
                'sensationalism': 0.0,
                'writingStyle': 0.0,
                'clickbait': 0.0
            }

# Initialize singleton instance at module load time
_ANALYZER_INSTANCE = get_analyzer()

# Add health check function for monitoring
def health_check() -> Dict[str, bool]:
    """Health check function for monitoring"""
    try:
        # Simple test to verify analyzer is working
        result = _ANALYZER_INSTANCE.analyze_text("This is a test sentence.")
        return {
            "status": "healthy",
            "analyzer_initialized": _ANALYZER_INSTANCE is not None,
            "test_analysis_successful": all(k in result for k in ['sensationalism', 'writingStyle', 'clickbait'])
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

__all__ = ['get_analyzer', 'health_check']
