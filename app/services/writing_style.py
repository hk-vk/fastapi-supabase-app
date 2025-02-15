import re
import numpy as np
from typing import Dict
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

class EnhancedMalayalamAnalyzer:
    def __init__(self):
        self.patterns = {
    'clickbait': {
        # Enhanced punctuation patterns
        r'[!]{3,}': 20,  # Triple exclamation for urgency [4][7]
        r'[?]{3,}': 20,  # Multiple question marks [1][4]
        r'\.{4,}': 15,   # Ellipsis for suspense [1][6]
        r'(\b★+|☆+\b)': 12,  # Star symbols for attention [3][9]

        # Compound phrase patterns
        r'(നിങ്ങൾ|താങ്കൾ)\s+(വിശ്വസിക്കാനാകില്ല|ഒരിക്കലും ചിന്തിച്ചിട്ടില്ല)': 30,  # You won't believe [9]
        r'(ഞെട്ടിക്കുന്ന|അത്ഭുത)\s+(വാർത്ത|സംഭവം)': 25,  # Shocking news/event [6][9]
        r'(രഹസ്യം|വെളിപ്പെടുത്തൽ)\s+[\w\s]+(\?|!)': 22,  # Secret revelations [1][4]

        # Viral content markers
        r'(വൈറൽ|ട്രെൻഡിംഗ്)\s+(വീഡിയോ|ഫോട്ടോ)': 18,  # Viral video/photo [6][9]
        r'പുതിയ\s+(വിവരം|അപ്ഡേറ്റ്)': 15,  # New information/update [9]
        r'\d+\s+(രഹസ്യങ്ങൾ|വഴിമുട്ടുകൾ)': 20,  # Numbered lists [4][7]

        # Emotional triggers
        r'(കരളറിഞ്ഞു|ഹൃദയവേദന)\s+[\w\s]+!': 25,  # Heartbreaking stories [9]
        r'(അടിയന്തര|ആപത്ത്)\s+[\w\s]+': 18,  # Emergency situations [6]
        r'(സംഭവം|കേസ്)\s+[\w\s]+(\?|!)': 15,  # Mystery events [1]

        # Question-based patterns
        r'എന്ത്?\s+(സംഭവിച്ചു|കാരണം)\??': 20,  # What happened? [7][9]
        r'എങ്ങനെ\s+[\w\s]+\?': 18,  # How...? questions [4]
        r'എന്തുകൊണ്ട്\s+[\w\s]+\?': 15,  # Why...? questions [9]

        # Numerical sensationalism
        r'\d+\s+(വർഷം|മാസം)\s+(മുമ്പ്|ശേഷം)': 12,  # X years/months ago [4][7]
        r'(\d+|\d+\+)\s+(പ്രതി|വ്യക്തി)': 15,  # Number of people involved [9]

        # Visual emphasis patterns
        r'(\b▁+|░+|▒+|▣+\b)': 10,  # Unicode block elements [3]
        r'(വായിച്ചു\s+നോക്കൂ|ക്ലിക്ക്\s+ചെയ്യൂ)': 25  # Call-to-action phrases [6][9]
    },
    'formal_markers': {
        # Official communication patterns
        r'(പ്രസ്താവന|വിശദീകരണം)\s+[\w\s]+': 20,  # Official statements [9]
        r'(റിപ്പോർട്ട്|സർക്കാർ)\s+[\w\s]+': 18,  # Government reports [6]
        r'(പരിശോധിച്ചു|സ്ഥിരീകരിച്ചു)\s+[\w\s]+': 15,  # Verified information [4]

        # Journalistic patterns
        r'(വാർത്താ\s+സ്രോതസ്സ്|ഉദ്ഘോഷിച്ചു)\b': 12,  # News sources [9]
        r'(സംഘടിപ്പിച്ചു|നടപ്പിലാക്കി)\b': 10,  # Organized/implemented [6]
        r'(അനുസരിച്ച്|പ്രകാരം)\s+[\w\s]+': 12  # According to... [1][4]
    }
}


    @lru_cache(maxsize=128)
    def normalize_score(self, score: float) -> float:
        return min(max(float(score), 0.0), 100.0)

    def analyze_writing_style(self, text: str) -> float:
        if not text.strip():
            return 0.0

        sentences = [s.strip() for s in text.split('.') if s.strip()]
        words = text.split()
        
        features = {
            'avg_sentence_length': np.mean([len(s.split()) for s in sentences]),
            'sentence_variance': np.var([len(s.split()) for s in sentences]),
            'lexical_diversity': len(set(words)) / len(words) if words else 0,
            'formal_markers': len(re.findall('|'.join(self.patterns['formal_markers'].keys()), text)),
            'clickbait_markers': len(re.findall('|'.join(self.patterns['clickbait'].keys()), text)),
            'punctuation_density': len(re.findall(r'[!?.]{2,}', text)) / len(sentences) if sentences else 0
        }

        style_score = (
            (1 - features['lexical_diversity']) * 25 +
            features['clickbait_markers'] * 8 +
            features['punctuation_density'] * 15 +
            (np.log1p(features['sentence_variance']) * 10) +
            (abs(20 - features['avg_sentence_length']) * 1.5) -
            (features['formal_markers'] * 0.8)
        )

        return self.normalize_score(100 - style_score)

    def analyze_text(self, text: str) -> Dict[str, float]:
        if not text.strip():
            return {
                'sensationalism': 0,
                'writingStyle': 0,
                'clickbait': 0
            }

        total_weight = 0
        text_length = len(text.split())
        
        for pattern, weight in self.patterns['clickbait'].items():
            matches = len(re.findall(pattern, text))
            total_weight += matches * weight * (1 + np.log1p(matches/text_length if text_length else 1))

        clickbait_score = total_weight * (1 + len(text)/(5000 if text else 1))
        writing_style = self.analyze_writing_style(text)

        return {
            'sensationalism': self.normalize_score(clickbait_score * 0.85),
            'writingStyle': 100-writing_style,
            'clickbait': self.normalize_score(clickbait_score)
        }

# Initialize singleton instance
malayalam_analyzer = EnhancedMalayalamAnalyzer()