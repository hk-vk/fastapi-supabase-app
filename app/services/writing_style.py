import re
import numpy as np
from typing import Dict, Tuple
from functools import lru_cache
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class EnhancedMalayalamAnalyzer:
    def __init__(self):
        self._compile_patterns()
        self.sentence_split_re = re.compile(r'[।॥?!.]|\s+\-\s+')

    def _compile_patterns(self) -> None:
        """Enhanced regex patterns for Malayalam clickbait detection"""
        self.compiled_patterns = {
            'clickbait': [
                # Enhanced exclamation patterns
                (re.compile(r'[!]{3,}'), 22),
                (re.compile(r'[?]{3,}'), 22),
                (re.compile(r'\.{4,}'), 18),
                
                # Symbol patterns
                (re.compile(r'(\b★+|☆+|✪+|✦+|❁+|♣+\b)'), 15),
                (re.compile(r'[\u2581-\u259F]'), 12),

                # Common clickbait phrases
                (re.compile(r'(നിങ്ങൾ|താങ്കൾ)\s+(വിശ്വസിക്കാനാകില്ല|ഒരിക്കലും ചിന്തിച്ചിട്ടില്ല)'), 35),
                (re.compile(r'(ഞെട്ടിക്കുന്ന|അത്ഭുത)\s+(വാർത്ത|സംഭവം|വിവരം)'), 28),
                (re.compile(r'(രഹസ്യം|വെളിപ്പെടുത്തൽ)\s+[\w\s]+(\?|!)'), 25),
                (re.compile(r'(വൈറൽ|ട്രെൻഡിംഗ്)\s+(വീഡിയോ|ഫോട്ടോ|റിയൽ)'), 22),
                (re.compile(r'പുതിയ\s+(വിവരം|അപ്ഡേറ്റ്|ഷോക്കിംഗ്)'), 20),
                (re.compile(r'\d+\s+(രഹസ്യങ്ങൾ|വഴിമുട്ടുകൾ|ഞെട്ടിക്കുന്ന\s+വസ്തുതകൾ)'), 25),

                # Emotional triggers
                (re.compile(r'(കരളറിഞ്ഞു|ഹൃദയവേദന)\s+[\w\s]+!'), 28),
                (re.compile(r'(അടിയന്തര|ആപത്ത്|അപകടം)\s+[\w\s]+'), 22),
                (re.compile(r'(സംഭവം|കേസ്)\s+[\w\s]+(\?|!)'), 18),

                # Question patterns
                (re.compile(r'എന്ത്?\s+(സംഭവിച്ചു|കാരണം)\??'), 25),
                (re.compile(r'എങ്ങനെ\s+[\w\s]+\?'), 20),
                (re.compile(r'എന്തുകൊണ്ട്\s+[\w\s]+\?'), 18),

                # Numerical sensationalism
                (re.compile(r'\d+\s+(വർഷം|മാസം|ആഴ്ച)\s+(മുമ്പ്|ശേഷം)'), 15),
                (re.compile(r'(\d+|\d+\+)\s+(പ്രതി|വ്യക്തി|രഹസ്യം)'), 18),

                # Newly added phrases
                (re.compile(r'(ഒറ്റവീട്ടിൽ|ഒരു\s+സ്ഥലത്ത്)\s+[\w\s]+!'), 25),
                (re.compile(r'ഇത്\s+നിങ്ങൾക്ക്\s+വിശ്വസിക്കാൻ\s+കഴിയില്ല!'), 30),
                (re.compile(r'(അടുത്തത്\s+എന്ത്|എന്താണ്\s+ശരി?)'), 22),
                (re.compile(r'(വായിച്ചു\s+നോക്കൂ|ക്ലിക്ക്\s+ചെയ്യൂ|ഷെയർ\s+ചെയ്യൂ)'), 28),
                (re.compile(r'(ചാനൽ\s+സബ്സ്ക്രൈബ്|നോട്ടിഫിക്കേഷൻ\s+ഓൺ)'), 18),
                (re.compile(r'(ഫ്രീ\s+ആയി|ഗിഫ്റ്റ്\s+എടുക്കൂ)'), 20),
                (re.compile(r'(ലൈക്\s+ചെയ്താൽ|ഷെയർ\s+ചെയ്താൽ)\s+[\w\s]+'), 15),
                (re.compile(r'(ഇത്രയും\s+സൗന്ദര്യം|ഇത്രയും\s+ഭയങ്കരം)'), 22),
                (re.compile(r'(അവസാനം\s+എന്തായി|അവസാനത്തെ\s+വാക്ക്)'), 18),
                (re.compile(r'(ഇനി\s+സമയം\s+ഇല്ല|ഉടൻ\s+കാണൂ)'), 20),
                (re.compile(r'(വീഡിയോ\s+കാണാതെ\s+പോകണ്ട|ഫുൾ\s+വീഡിയോ)'), 25),
                (re.compile(r'(എന്ത്\s+കണ്ടു|എന്ത്\s+പറഞ്ഞു)\s+[\w\s]+'), 15),
                (re.compile(r'(ഇത്\s+നിങ്ങളുടെ\s+പ്രിയപ്പെട്ട|ബന്ധുവിന്റെ)'), 18),
                (re.compile(r'(ചോദ്യം\s+ചെയ്താൽ|പ്രശ്നം\s+ഉണ്ടെങ്കിൽ)'), 12),
                (re.compile(r'(സർപ്രൈസ്\s+വീഡിയോ|ഷോക്കിംഗ്\s+വാർത്ത)'), 22),
                (re.compile(r'(എന്തുകൊണ്ട്\s+ഇങ്ങനെ|എങ്ങനെ\s+സാധ്യം)'), 18)
            ],
            'formal_markers': [
                # Official communication patterns
                (re.compile(r'(പ്രസ്താവന|വിശദീകരണം)\s+[\w\s]+'), 25),
                (re.compile(r'(റിപ്പോർട്ട്|സർക്കാർ)\s+[\w\s]+'), 22),
                (re.compile(r'(പരിശോധിച്ചു|സ്ഥിരീകരിച്ചു)\s+[\w\s]+'), 18),
                (re.compile(r'(വാർത്താ\s+സ്രോതസ്സ്|ഉദ്ഘോഷിച്ചു)\b'), 15),
                (re.compile(r'(സംഘടിപ്പിച്ചു|നടപ്പിലാക്കി)\b'), 12),
                (re.compile(r'(അനുസരിച്ച്|പ്രകാരം)\s+[\w\s]+'), 15),
                
                # New formal patterns
                (re.compile(r'(സർക്കാർ\s+അറിയിപ്പ്|ഔദ്യോഗിക\s+പ്രഖ്യാപനം)'), 20),
                (re.compile(r'(നിയമ\s+പ്രകാരം|ദേശീയ\s+നയം)'), 18),
                (re.compile(r'(പൊതുജന\s+ശ്രദ്ധയ്ക്ക്|വിജ്ഞാപനം)'), 15),
                (re.compile(r'(സുപ്രധാന\s+നിർദ്ദേശം|ഉത്തരവ്)'), 18),
                (re.compile(r'(ഭദ്രതാ\s+മാർഗ്ഗനിർദ്ദേശം|മുന്നറിയിപ്പ്)'), 15)
            ]
        }

    @lru_cache(maxsize=1024)
    def _preprocess_text(self, text: str) -> Tuple[tuple, tuple]:
        """Preprocess and cache text with enhanced normalization"""
        text = text.lower().replace('\u200d', '')  # Remove zero-width joiners
        sentences = [s.strip() for s in self.sentence_split_re.split(text) if s.strip()]
        words = re.findall(r'[\w\u0D00-\u0D7F]+', text, flags=re.UNICODE)
        return tuple(sentences), tuple(words)

    def _calculate_text_stats(self, sentences: tuple, words: tuple) -> Dict[str, float]:
        """Optimized text statistics calculation"""
        if not sentences or not words:
            return {'avg_sentence_length': 0, 'sentence_variance': 0, 'lexical_diversity': 0}
        
        lens = np.array([len(s.split()) for s in sentences])
        unique = len(set(words))
        
        return {
            'avg_sentence_length': float(np.mean(lens)),
            'sentence_variance': float(np.var(lens)),
            'lexical_diversity': unique / len(words)
        }

    def _analyze_patterns(self, text: str, pattern_type: str) -> Tuple[int, int]:
        """Optimized pattern matching with early exit"""
        total_score = 0
        match_count = 0
        
        for pattern, weight in self.compiled_patterns[pattern_type]:
            matches = pattern.findall(text)
            if matches:
                count = len(matches)
                total_score += weight * (1 + np.log1p(count))
                match_count += count
                
        return total_score, match_count

    def analyze_writing_style(self, text: str) -> float:
        """Enhanced style analysis with new patterns"""
        sentences, words = self._preprocess_text(text)
        stats = self._calculate_text_stats(sentences, words)
        
        formal_score, formal_matches = self._analyze_patterns(text, 'formal_markers')
        clickbait_score, clickbait_matches = self._analyze_patterns(text, 'clickbait')
        
        punctuation_density = (text.count('!') + text.count('?') + text.count('.')) / len(sentences) if sentences else 0
        
        style_score = (
            (1 - stats['lexical_diversity']) * 28 +
            clickbait_matches * 10 +
            punctuation_density * 18 +
            (np.log1p(stats['sentence_variance']) * 12) +
            (abs(18 - stats['avg_sentence_length']) * 2) -
            (formal_matches * 1.2)
        )
        
        return self._normalize_score(100 - style_score)

    def calculate_clickbait_score(self, text: str) -> float:
        """Updated clickbait scoring with new patterns"""
        total_score, match_count = self._analyze_patterns(text, 'clickbait')
        max_observed = 450  # Adjusted maximum based on new patterns
        normalized_score = (total_score / max_observed) * 100
        return self._normalize_score(normalized_score)

    @lru_cache(maxsize=1024)
    def _normalize_score(self, score: float) -> float:
        """Enhanced sigmoid normalization"""
        return 100 / (1 + np.exp(-0.12 * (score - 55)))

    def analyze_text(self, text: str) -> Dict[str, float]:
        """Main analysis entry point with validation"""
        if not isinstance(text, str) or len(text.strip()) < 10:
            return {
                'sensationalism': 0.0,
                'writingStyle': 0.0,
                'clickbait': 0.0
            }
        
        text = text[:5000]  # Maintain input size limit
        
        writing_style = self.analyze_writing_style(text)
        clickbait_score = self.calculate_clickbait_score(text)
        
        sensationalism = (clickbait_score * 0.75) + ((100 - writing_style) * 0.25)
        
        return {
            'sensationalism': self._normalize_score(sensationalism),
            'writingStyle': self._normalize_score(writing_style),
            'clickbait': self._normalize_score(clickbait_score)
        }

# Initialize analyzer
malayalam_analyzer = EnhancedMalayalamAnalyzer()
