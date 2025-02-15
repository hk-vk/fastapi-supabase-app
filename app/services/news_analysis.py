from exa_py import Exa
import google.generativeai as genai
from datetime import datetime
from typing import Dict, Any
import os
from dotenv import load_dotenv
from deep_translator import GoogleTranslator
from langdetect import detect
from functools import lru_cache
import asyncio
from concurrent.futures import ThreadPoolExecutor
import aiohttp
from fastapi import BackgroundTasks
import hashlib
import json
from cachetools import TTLCache, cached

load_dotenv()

class NewsAnalysisService:
    def __init__(self):
        self.exa = Exa(api_key=os.getenv("EXA_API_KEY"))
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.translator = GoogleTranslator(source='ml', target='en')
        self.cache = TTLCache(maxsize=100, ttl=3600)  # Cache results for 1 hour
        self.executor = ThreadPoolExecutor(max_workers=3)  # Limit concurrent API calls
        
    @cached(cache=TTLCache(maxsize=1000, ttl=3600))
    def _get_cached_analysis(self, query_hash: str) -> Dict[str, Any]:
        """Cache analysis results using original query hash as key"""
        return self.cache.get(query_hash)

    def _cache_result(self, query_hash: str, result: Dict[str, Any]):
        """Store result in cache using original query hash"""
        self.cache[query_hash] = result

    @lru_cache(maxsize=128)
    def _translate_text(self, text: str) -> str:
        """Translate text from Malayalam to English"""
        try:
            return self.translator.translate(text)
        except Exception:
            return text

    async def _fetch_exa_results(self, query: str):
        """Async method to fetch Exa search results"""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor,
            lambda: self.exa.search_and_contents(
                query,
                text=True,
                num_results=7,
                type="auto",
                livecrawl="always",
                use_autoprompt=True
            )
        )

    async def _get_gemini_analysis(self, prompt: str):
        """Async method to get Gemini analysis"""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor,
            lambda: self.model.generate_content(prompt)
        )

    def _clean_json_response(self, text: str) -> Dict[str, Any]:
        """Clean and format the JSON response"""
        try:
            # Remove newlines, extra spaces, and backticks
            text = text.replace('\n', '').replace('`', '').strip()
            
            # Try to parse and re-stringify to ensure valid JSON
            json_obj = json.loads(text)
            cleaned_text = json.dumps(json_obj, separators=(',', ':'), ensure_ascii=False)
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            # If JSON parsing fails, return as a basic dict
            return {
                "ISFAKE": 1,
                "CONFIDENCE": 0.5,
                "EXPLANATION": "Failed to parse response: " + text.replace('\n', ' ').replace('`', '').replace('\\', '')
            }

    async def analyze_news(self, query: str, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        # Generate cache key from original Malayalam query
        original_query_hash = hashlib.md5(query.encode()).hexdigest()
        
        # Check cache first using original query hash
        cached_result = self._get_cached_analysis(original_query_hash)
        if (cached_result):
            return cached_result

        # Translate for analysis
        translated_query = self._translate_text(query)
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Fetch results asynchronously with translated query
        results = await self._fetch_exa_results(translated_query)
        
        content_docs = "\n\n".join([result.text for result in results.results])
        system_prompt = self._get_system_prompt(current_date)
        full_prompt = f"{system_prompt}\n\nDOCUMENTS TO ANALYZE:\n{content_docs}\n\nCLAIM TO VERIFY: {translated_query}"
        
        # Get analysis asynchronously
        response = await self._get_gemini_analysis(full_prompt)
        result = response.text
        
        # Clean and format the response
        result = self._clean_json_response(result)
        
        # Cache the result with original Malayalam query hash
        self._cache_result(original_query_hash, result)
        
        # Schedule cache cleanup in background
        background_tasks.add_task(self._cleanup_old_cache)
        
        return result

    def _cleanup_old_cache(self):
        """Clean up expired cache entries"""
        self.cache.expire()

    @lru_cache(maxsize=1)
    def _get_system_prompt(self, current_date: str) -> str:
        """Cache the system prompt as it rarely changes"""
        return f"""[ANALYSIS DATE: {current_date}]

You are an advanced AI assistant specialized in detecting fake news. Return result in compact JSON format without any newlines or extra spaces. Analysis timestamp: {current_date}.

VERIFICATION MATRIX:
always detect the tense of the sentences before any analysis
1. TEMPORAL ANALYSIS:
   | Claim Type | Verification Required |
   |------------|---------------------|
   | Past Events| Multiple sources + dates |
   | Present Claims | Live sources + official statements |
   | Future Predictions | Official announcements only |
   | Undated Claims | Source credibility check |

2. SOURCE CREDIBILITY SCORING:
   - Official Government Sources: 0.9-1.0
   - Mainstream Media: 0.7-0.9
   - Local News Outlets: 0.5-0.7
   - Social Media: 0.1-0.4
   - Anonymous Sources: 0.0-0.1

3. CRITICAL VERIFICATION RULES:
   A. Future Claims:
      - Require multiple confirmations
      - Must have specific dates/timelines
      - Need institutional backing

   B. Date-Specific Claims:
      - Cross-reference with official calendars
      - Verify against government announcements
      - Check historical patterns

   C. Event Verification:
      - Match with official calendars
      - Verify regional variations
      - Check historical patterns

4. LINGUISTIC ANALYSIS:
   - Check for temporal markers
   - Identify predictive language patterns
   - Analyze certainty indicators
   - Detect emotional manipulation

5. EVIDENCE WEIGHTING:
   | Evidence Type | Weight |
   |--------------|--------|
   | Official Documents | 1.0 |
   | Media Reports | 0.8 |
   | Expert Statements | 0.7 |
   | Public Records | 0.6 |
   | Social Media | 0.3 |

Output Format: Return a compact JSON object without newlines or extra whitespace in this exact format:
{{"ISFAKE":1,"CONFIDENCE":0.9,"EXPLANATION":"Brief explanation"}}

ISFAKE: [0 or 1]
CONFIDENCE: [score between 0-1]
EXPLANATION: [Structured analysis in just 200 words or less in professional way]"""
