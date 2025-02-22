from exa_py import Exa
import google.generativeai as genai
from datetime import datetime, timedelta, timezone
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
import logging
from fastapi import HTTPException
from app.core.http_client import get_http_session
from dateutil import parser
import pytz

logger = logging.getLogger(__name__)

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

    def clear_db(self):
        """Clear the entire analysis cache database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM analysis_cache")
                conn.commit()
        except Exception as e:
            print(f"Cache clear error: {e}")

class NewsAnalysisService:
    def __init__(self):
        self._session = None
        self._translate_session = None
        # Initialize caches
        self.memory_cache = TTLCache(maxsize=100, ttl=3600)  # 1 hour TTL
        self.disk_cache = CacheDB()
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        # Initialize API clients
        exa_api_key = os.getenv("EXA_API_KEY")
        if not exa_api_key:
            raise ValueError("EXA_API_KEY not found in environment variables")
        self.exa = Exa(exa_api_key)
        
        # Initialize Gemini
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Initialize translator
        self.translator = GoogleTranslator(source='auto', target='en')

    async def get_session(self):
        """Get or create the HTTP session"""
        if not self._session:
            self._session = await get_http_session()
        return self._session

    async def get_translate_session(self):
        """Get or create the translation HTTP session"""
        if not self._translate_session:
            self._translate_session = await get_http_session()
        return self._translate_session

    async def cleanup(self):
        """No cleanup needed as session is managed by http_client"""
        pass

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

    async def _fetch_english_results(self, query: str):
        """Async method to fetch Exa search results for English content"""
        try:
            return await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.exa.search_and_contents(
                    query,
                    text=True,
                    num_results=8,
                    type="auto",
                    use_autoprompt=True,
                    livecrawl="always",
                )
            )
        except Exception as e:
            logger.error(f"English search error: {str(e)}")
            return None

    async def _fetch_malayalam_results(self, query: str):
        """Async method to fetch Exa search results for Malayalam content"""
        try:
            return await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.exa.search_and_contents(
                    query,
                    text=True,
                    num_results=7,
                    type="keyword",
                    use_autoprompt=True,
                    livecrawl="always",
                )
            )
        except Exception as e:
            logger.error(f"Malayalam search error: {str(e)}")
            return None

    async def _get_gemini_analysis(self, prompt: str):
        """Async method to get Gemini analysis with minimal temperature for maximum accuracy"""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor,
            lambda: self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.1,  # Reduced temperature for more deterministic output
                    'top_p': 0.1,        # Lower top_p for more focused sampling
                    'top_k': 1           # Minimal top_k for most likely outputs only
                }
            )
        )

    def _clean_json_response(self, text: str) -> Dict[str, Any]:
        """Clean and format the JSON response with enhanced validation"""
        try:
            # Remove common formatting issues
            text = text.strip()
            text = text.replace('\n', '').replace('`', '').replace('json', '')
            text = text.replace('```', '').replace('json', '')
            
            # Find the first { and last } to extract valid JSON
            start = text.find('{')
            end = text.rfind('}')
            if start == -1 or end == -1:
                raise json.JSONDecodeError("No JSON object found", text, 0)
            
            json_str = text[start:end + 1]
            json_obj = json.loads(json_str)

            # Validate required fields and types
            if not isinstance(json_obj.get("ISFAKE"), (int, float)) or \
               not isinstance(json_obj.get("CONFIDENCE"), (int, float)) or \
               not isinstance(json_obj.get("EXPLANATION"), str):
                raise ValueError("Invalid field types")

            # Normalize values
            json_obj["ISFAKE"] = 1 if json_obj["ISFAKE"] not in [0, 1] else json_obj["ISFAKE"]
            json_obj["CONFIDENCE"] = max(0.0, min(1.0, float(json_obj["CONFIDENCE"])))
            
            # Ensure explanation is not empty
            if not json_obj["EXPLANATION"].strip():
                json_obj["EXPLANATION"] = "വിശകലനം പൂർത്തിയായി, പക്ഷേ വിശദീകരണം ലഭ്യമല്ല."

            return json_obj
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            logger.error(f"JSON cleaning error: {str(e)}", exc_info=True)
            return {
                "ISFAKE": 1,
                "CONFIDENCE": 0.5,
                "EXPLANATION": "പ്രതികരണം വിശകലനം ചെയ്യുന്നതിൽ പിശക്. ദയവായി വീണ്ടും ശ്രമിക്കുക."
            }

    async def analyze_news(self, query: str, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        if not query or len(query.strip()) < 5:
            return {
                "ISFAKE": 1,
                "CONFIDENCE": 1.0,
                "EXPLANATION": "വിശകലനത്തിനായി കുറഞ്ഞത് 5 അക്ഷരങ്ങളെങ്കിലും ആവശ്യമാണ്."
            }

        # Generate cache key with version for prompt updates
        prompt_version = "v2"
        query_hash = hashlib.md5(f"{query}{prompt_version}".encode()).hexdigest()
        
        # Check memory cache first
        if result := self.memory_cache.get(query_hash):
            return result
            
        # Check disk cache
        if result := self.disk_cache.get(query_hash):
            # Store in memory cache for faster subsequent access
            self.memory_cache[query_hash] = result
            return result

        try:
            translated_query = self._translate_text(query)
            if not translated_query:
                raise ValueError("Translation failed")

            try:
                # Fetch results from both English and Malayalam sources concurrently
                english_task = self._fetch_english_results(translated_query)
                malayalam_task = self._fetch_malayalam_results(query)
                results = await asyncio.gather(english_task, malayalam_task, return_exceptions=True)
                
                # Process and combine results
                combined_results = []
                for result in results:
                    if isinstance(result, Exception):
                        logger.warning(f"Search failed: {str(result)}")
                        continue
                    if result and hasattr(result, 'results'):
                        combined_results.extend(result.results)
                
                # Remove duplicates and create Results object
                seen_urls = set()
                unique_results = []
                for result in combined_results:
                    if result.url not in seen_urls:
                        seen_urls.add(result.url)
                        unique_results.append(result)
                
                class Results:
                    def __init__(self, results_list):
                        self.results = results_list
                    def __len__(self):
                        return len(self.results)

                results = Results(unique_results[:10])
                
                if not results or len(results) == 0:
                    error_response = {
                        "ISFAKE": 1,
                        "CONFIDENCE": 0.9,
                        "EXPLANATION": "ഈ അവകാശവാദത്തെക്കുറിച്ച് വിശ്വസനീയമായ വിവരങ്ങളൊന്നും കണ്ടെത്താനായില്ല."
                    }
                    return error_response

            except asyncio.TimeoutError:
                logger.error("Search timeout")
                return {
                    "ISFAKE": 1,
                    "CONFIDENCE": 0.8,
                    "EXPLANATION": "തിരയൽ സമയപരിധി കഴിഞ്ഞു. ദയവായി വീണ്ടും ശ്രമിക്കുക."
                }

            # Enhanced content processing
            content_docs = []
            total_sources = len(results) if results else 0
            recent_sources = 0
            credible_sources = 0

            if total_sources > 0:
                for result in results.results:
                    if result.text:
                        content_docs.append(f"SOURCE: {result.url}\nCONTENT: {result.text}")
                        
                        # Count recent sources (within last 7 days)
                        if result.published_date:
                            try:
                                published_date = parser.parse(result.published_date)
                                # Convert naive datetime to timezone-aware
                                if published_date.tzinfo is None:
                                    published_date = published_date.replace(tzinfo=timezone.utc)
                                current_time = datetime.now(timezone.utc)
                                if (current_time - published_date).days <= 7:
                                    recent_sources += 1
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Failed to parse date: {result.published_date}", exc_info=True)
                        
                        # Basic credibility check based on domain
                        if any(domain in result.url for domain in ['.gov', '.edu', '.org', 'news.', 'times.']):
                            credible_sources += 1

            # Prepare analysis context
            current_date = datetime.now().strftime('%Y-%m-%d')
            system_prompt = self._get_system_prompt(current_date)
            
            analysis_context = f"""
            CLAIM METADATA:
            - Total Sources Found: {total_sources}
            - Recent Sources (≤7d): {recent_sources}
            - Credible Sources: {credible_sources}
            - Analysis Date: {current_date}
            
            DOCUMENTS TO ANALYZE:
            {chr(10).join(content_docs)}
            
            CLAIM TO VERIFY: {translated_query}
            """

            # Get analysis with enhanced error handling
            try:
                response = await asyncio.wait_for(
                    self._get_gemini_analysis(f"{system_prompt}\n\n{analysis_context}"),
                    timeout=45.0
                )
            except asyncio.TimeoutError:
                return {
                    "ISFAKE": 1,
                    "CONFIDENCE": 1.0,
                    "EXPLANATION": "വിശകലന സമയം കഴിഞ്ഞു. ദയവായി വീണ്ടും ശ്രമിക്കുക."
                }

            # Process and validate response
            result = self._clean_json_response(response.text)
            
            # Validate result structure
            if not all(k in result for k in ["ISFAKE", "CONFIDENCE", "EXPLANATION"]):
                result = {
                    "ISFAKE": 1,
                    "CONFIDENCE": 1.0,
                    "EXPLANATION": "സിസ്റ്റം പിശക്: അപൂർണ്ണമായ വിശകലനം. ദയവായി പിന്നീട് ശ്രമിക്കുക."
                }
            
            # Cache valid results
            if result.get("EXPLANATION") != "സിസ്റ്റം പിശക്: അപൂർണ്ണമായ വിശകലനം. ദയവായി പിന്നീട് ശ്രമിക്കുക.":
                self.memory_cache[query_hash] = result
                self.disk_cache.set(query_hash, result)
            
            # Schedule cache cleanup in background
            background_tasks.add_task(self._cleanup_caches)
            
            return result

        except Exception as e:
            logger.error(f"Analysis error: {str(e)}", exc_info=True)
            return {
                "ISFAKE": 1,
                "CONFIDENCE": 1.0,
                "EXPLANATION": "സിസ്റ്റം പിശക്: വിശകലനം പൂർത്തിയാക്കാൻ കഴിഞ്ഞില്ല. ദയവായി പിന്നീട് ശ്രമിക്കുക."
            }

    def _cleanup_caches(self):
        """Clean up both memory and disk caches"""
        self.memory_cache.expire()
        self.disk_cache.cleanup()

    @lru_cache(maxsize=1)
    def _get_system_prompt(self, current_date: str) -> str:
        """Cache the system prompt as it rarely changes"""
        return f"""[ANALYSIS DATE: {current_date}]

You are a highly precise AI fact-checker tasked with detecting misinformation. Your analysis must be extremely thorough and conservative - when in doubt, mark as unverified. Return result in strict JSON format. Analyze each claim atomically, breaking down compound statements.

CORE PRINCIPLES:
1. Default to Uncertainty: If insufficient evidence exists, mark as potentially false
2. Zero Speculation: Never make assumptions about unstated facts
3. Temporal Precision: Always verify exact dates and sequences
4. Source Hierarchy: Weight information based on authority and recency
5. Context Preservation: Consider full context before making determinations
6. Cross-Validation: Require multiple independent sources for verification

VERIFICATION PROTOCOL:

1. CLAIM DECOMPOSITION:
   - Break down compound claims into atomic facts
   - Identify temporal markers and dependencies
   - Map entity relationships and hierarchies
   - Extract quantifiable metrics and dates
   - Isolate conditional statements and qualifiers

2. TEMPORAL ANALYSIS (Mandatory):
   | Time Frame | Required Evidence |
   |------------|------------------|
   | Historical | Primary sources + Multiple secondary validations |
   | Recent Past| Official records + Multiple media confirmations |
   | Present    | Live sources + Official statements + Independent verification |
   | Future     | Official announcements + Supporting documentation |
   | Undated    | Full context reconstruction + Multiple source validation |

3. SOURCE CREDIBILITY MATRIX:
   | Source Type | Weight | Required Validation |
   |-------------|--------|-------------------|
   | Official Government | 0.95 | Cross-reference with related agencies |
   | International Bodies | 0.90 | Verify against member state data |
   | Primary Documents | 0.85 | Authentication check + Context verification |
   | Academic Journals | 0.80 | Peer review status + Citation analysis |
   | Major News Agencies | 0.75 | Multiple source confirmation |
   | Regional Media | 0.60 | Local authority verification |
   | Expert Statements | 0.50 | Credential verification + Conflict check |
   | Social Media | 0.20 | Extensive corroboration required |
   | Anonymous | 0.10 | Multiple independent verifications |

4. VALIDATION REQUIREMENTS:
   A. For Any Positive Verification:
      - Minimum 3 independent sources
      - At least 1 primary source
      - No contradicting evidence
      - Clear temporal alignment
      - Proper contextual fit

   B. Automatic False Flags:
      - Single source claims
      - Contradictory evidence
      - Temporal inconsistencies
      - Missing crucial context
      - Unverified entities
      - Logical impossibilities

5. EVIDENCE QUALITY METRICS:
   - Recency (≤24h: 1.0, ≤7d: 0.8, ≤30d: 0.6, >30d: 0.4)
   - Directness (Primary: 1.0, Secondary: 0.7, Tertiary: 0.4)
   - Corroboration (Multiple: 1.0, Single: 0.5, None: 0.0)
   - Authority (Official: 1.0, Expert: 0.8, Public: 0.4)
   - Completeness (Full: 1.0, Partial: 0.6, Limited: 0.3)

6. CONTEXTUAL ANALYSIS:
   - Historical precedent check
   - Cultural context verification
   - Geographic relevance
   - Domain-specific validation
   - Stakeholder analysis
   - Impact assessment

7. ERROR PREVENTION:
   - Double-check all dates and numbers
   - Verify entity names and titles
   - Confirm geographic details
   - Validate cause-effect relationships
   - Check for logical consistency
   - Assess probability of claims

Output Format (Strict JSON, no newlines/spaces):
{{"ISFAKE":1,"CONFIDENCE":0.9,"EXPLANATION":"വിശദമായ വിശകലനം"}}

RESPONSE RULES:
1. ISFAKE: [0: Verified True, 1: False/Unverified]
   - Default to 1 if any doubt exists
   - Require 100% certainty for 0

2. CONFIDENCE: [0.0-1.0]
   - Must reflect evidence quality
   - Consider source credibility
   - Account for verification depth
   - Never exceed source limitations

3. EXPLANATION:
   - Malayalam language only
   - Maximum 200 words
   - Include evidence summary
   - State verification method
   - List key sources
   - Note any uncertainties
   - Professional tone

MANDATORY CHECKS:
✓ Temporal consistency
✓ Source credibility
✓ Logical coherence
✓ Context alignment
✓ Evidence quality
✓ Entity verification
✓ Claim atomicity
✓ Impact assessment

If ANY mandatory check fails, mark as ISFAKE:1"""

