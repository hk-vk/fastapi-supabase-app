from exa_py import Exa
import google.generativeai as genai
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
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
from cachetools import TTLCache
import sqlite3
import pickle
from pathlib import Path

load_dotenv()

class CacheDB:
    def __init__(self, db_path: str = "analysis_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    query_hash TEXT PRIMARY KEY,
                    result BLOB,
                    timestamp TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON analysis_cache(timestamp)")

    def get(self, query_hash: str) -> Optional[Dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute(
                    "SELECT result FROM analysis_cache WHERE query_hash = ? AND timestamp > datetime('now', '-1 day')",
                    (query_hash,)
                ).fetchone()
                if result:
                    return pickle.loads(result[0])
        except Exception as e:
            print(f"Cache get error: {e}")
            return None
        return None

    def set(self, query_hash: str, result: Dict):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO analysis_cache (query_hash, result, timestamp) VALUES (?, ?, datetime('now'))",
                    (query_hash, pickle.dumps(result))
                )
        except Exception as e:
            print(f"Cache set error: {e}")

    def cleanup(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM analysis_cache WHERE timestamp < datetime('now', '-1 day')")
        except Exception as e:
            print(f"Cache cleanup error: {e}")

class NewsAnalysisService:
    def __init__(self):
        self.exa = Exa(api_key=os.getenv("EXA_API_KEY"))
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.translator = GoogleTranslator(source='auto', target='en')
        self.memory_cache = TTLCache(maxsize=100, ttl=80000000)  # 1 hour memory cache
        self.disk_cache = CacheDB()
        self.executor = ThreadPoolExecutor(max_workers=3)

    @lru_cache(maxsize=128)
    def _translate_text(self, text: str) -> str:
        """Translate text to English with language auto-detection"""
        try:
            source_lang = detect(text)
            if source_lang != 'en':
                return self.translator.translate(text)
            return text
        except Exception:
            return text

    async def _fetch_exa_results(self, query: str):
        """Async method to fetch Exa search results"""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor,
            lambda: self.exa.search_and_contents(
                query,
                text=True,
                num_results=7,  # Reduced for faster results
                type="auto",
                livecrawl="always",
                use_autoprompt=True
            )
        )

    async def _get_gemini_analysis(self, prompt: str):
        """Async method to get Gemini analysis with lower temperature"""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor,
            lambda: self.model.generate_content(
                prompt,
                generation_config={'temperature': 0.3}  
            )
        )

    def _clean_json_response(self, text: str) -> Dict[str, Any]:
        """Clean and format the JSON response"""
        try:
            # Remove newlines, extra spaces, and backticks
            text = text.replace('\n', '').replace('`', '').strip()
            json_obj = json.loads(text)
            return json_obj
        except json.JSONDecodeError:
            return {
                "ISFAKE": 1,
                "CONFIDENCE": 0.5,
                "EXPLANATION": "Failed to parse response: " + text[:200].replace('\n', ' ')
            }

    async def analyze_news(self, query: str, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        # Generate cache key
        query_hash = hashlib.md5(query.encode()).hexdigest()
        
        # Check memory cache first
        if result := self.memory_cache.get(query_hash):
            return result
            
        # Check disk cache
        if result := self.disk_cache.get(query_hash):
            # Store in memory cache for faster subsequent access
            self.memory_cache[query_hash] = result
            return result

        # Translate if needed
        translated_query = self._translate_text(query)
        
        # Fetch results asynchronously
        results = await self._fetch_exa_results(translated_query)
        content_docs = "\n\n".join([result.text for result in results.results])
        
        # Get analysis with current date
        current_date = datetime.now().strftime('%Y-%m-%d')
        system_prompt = self._get_system_prompt(current_date)
        full_prompt = f"{system_prompt}\n\nDOCUMENTS TO ANALYZE:\n{content_docs}\n\nCLAIM TO VERIFY: {translated_query}"
        
        response = await self._get_gemini_analysis(full_prompt)
        result = self._clean_json_response(response.text)
        
        # Cache the result in both memory and disk
        self.memory_cache[query_hash] = result
        self.disk_cache.set(query_hash, result)
        
        # Schedule cache cleanup in background
        background_tasks.add_task(self._cleanup_caches)
        
        return result

    def _cleanup_caches(self):
        """Clean up both memory and disk caches"""
        self.memory_cache.expire()
        self.disk_cache.cleanup()

    @lru_cache(maxsize=1)
    def _get_system_prompt(self, current_date: str) -> str:
        """Cache the system prompt as it rarely changes"""
        return f"""[ANALYSIS DATE: {current_date}]

You are an advanced AI assistant specialized in detecting fake news. Return result in compact JSON format without any newlines or extra spaces. Analysis timestamp: {current_date}.

VERIFICATION MATRIX:
always detect the tense of the sentences before any analysis. and read each and every word and compare it with the results
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
