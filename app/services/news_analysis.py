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
        # Initialize caches
        self.memory_cache = TTLCache(maxsize=100, ttl=3600)  # 1 hour TTL
        self.disk_cache = CacheDB()
        
        # Initialize thread pool with optimal size for connection handling
        self.executor = ThreadPoolExecutor(
            max_workers=min(32, (os.cpu_count() or 1) + 4),
            thread_name_prefix="analyzer"
        )
        
        # Initialize API clients
        exa_api_key = os.getenv("EXA_API_KEY")
        if not exa_api_key:
            raise ValueError("EXA_API_KEY not found in environment variables")
        self.exa = Exa(exa_api_key)
        
        # Initialize Gemini
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        genai.configure(api_key=google_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Initialize translator with persistent connection
        self.translator = GoogleTranslator(source='auto', target='en')

    async def get_session(self):
        """Get the shared HTTP session"""
        if not self._session:
            self._session = await get_http_session()
        return self._session

    async def cleanup(self):
        """Cleanup resources properly"""
        try:
            # Shutdown thread pool gracefully
            self.executor.shutdown(wait=True)
            
            # Clear caches
            self.memory_cache.clear()
            self.disk_cache.clear_db()
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

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
        """Optimized async method to fetch Exa search results for English content"""
        try:
            session = await self.get_session()
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self.executor,
                lambda: self.exa.search_and_contents(
                    query,
                     text = {

                    "max_characters": 2000

                 }, 
                    num_results=8,
                    type="keyword",
                    use_autoprompt=True,
                    livecrawl="always",
                )
            )
        except Exception as e:
            logger.error(f"English search error: {str(e)}")
            return None

    async def _fetch_malayalam_results(self, query: str):
        """Optimized async method to fetch Exa search results for Malayalam content"""
        try:
            session = await self.get_session()
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self.executor,
                lambda: self.exa.search_and_contents(
                    query,
                     text = {

                    "max_characters": 2000

                 },
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
               not isinstance(json_obj.get("EXPLANATION_EN"), str) or \
               not isinstance(json_obj.get("EXPLANATION_ML"), str):
                raise ValueError("Invalid field types")

            # Normalize values
            json_obj["ISFAKE"] = 1 if json_obj["ISFAKE"] not in [0, 1] else json_obj["ISFAKE"]
            json_obj["CONFIDENCE"] = max(0.0, min(1.0, float(json_obj["CONFIDENCE"])))
            
            # Ensure explanations are not empty
            if not json_obj["EXPLANATION_EN"].strip():
                json_obj["EXPLANATION_EN"] = "Analysis completed, but no detailed explanation available."
            if not json_obj["EXPLANATION_ML"].strip():
                json_obj["EXPLANATION_ML"] = "വിശകലനം പൂർത്തിയായി, പക്ഷേ വിശദീകരണം ലഭ്യമല്ല."

            return json_obj
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            logger.error(f"JSON cleaning error: {str(e)}", exc_info=True)
            return {
                "ISFAKE": 1,
                "CONFIDENCE": 0.5,
                "EXPLANATION_EN": "System error: Failed to analyze response. Please try again.",
                "EXPLANATION_ML": "സിസ്റ്റം പിശക്: പ്രതികരണം വിശകലനം ചെയ്യുന്നതിൽ പരാജയം. ദയവായി വീണ്ടും ശ്രമിക്കുക."
            }

    async def analyze_news(self, query: str, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        if not query or len(query.strip()) == 0:
            return {
                "ISFAKE": 1,
                "CONFIDENCE": 1.0,
                "EXPLANATION_EN": "Please provide some content for analysis.",
                "EXPLANATION_ML": "വിശകലനത്തിനായി ഉള്ളടക്കം നൽകുക."
            }

        # Generate cache key with version for prompt updates
        prompt_version = "v3"  # Updated version for bilingual support
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
                
                if not any(r for r in results if not isinstance(r, Exception)):
                    error_response = {
                        "ISFAKE": 1,
                        "CONFIDENCE": 0.9,
                        "EXPLANATION_EN": "No reliable information found about this claim.",
                        "EXPLANATION_ML": "ഈ അവകാശവാദത്തെക്കുറിച്ച് വിശ്വസനീയമായ വിവരങ്ങളൊന്നും കണ്ടെത്താനായില്ല."
                    }
                    return error_response

            except asyncio.TimeoutError:
                logger.error("Search timeout")
                return {
                    "ISFAKE": 1,
                    "CONFIDENCE": 0.8,
                    "EXPLANATION_EN": "Search timeout. Please try again.",
                    "EXPLANATION_ML": "തിരയൽ സമയപരിധി കഴിഞ്ഞു. ദയവായി വീണ്ടും ശ്രമിക്കുക."
                }

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
                    "EXPLANATION_EN": "No reliable information found about this claim.",
                    "EXPLANATION_ML": "ഈ അവകാശവാദത്തെക്കുറിച്ച് വിശ്വസനീയമായ വിവരങ്ങളൊന്നും കണ്ടെത്താനായില്ല."
                }
                return error_response

            # Enhanced content processing
            content_docs = []
            total_sources = len(results)
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
            - Total Sources: {total_sources}
            - Recent Sources (≤7d): {recent_sources}
            - Credible Sources: {credible_sources}
            - Analysis Date: {current_date}
            - Original Language: {"Malayalam" if detect(query) == "ml" else "English"}
            
            DOCUMENTS TO ANALYZE:
            {chr(10).join(content_docs)}
            
            CLAIM TO VERIFY: {translated_query}
            ORIGINAL CLAIM: {query}
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
                    "EXPLANATION_EN": "Analysis timeout. Please try again.",
                    "EXPLANATION_ML": "വിശകലന സമയം കഴിഞ്ഞു. ദയവായി വീണ്ടും ശ്രമിക്കുക."
                }

            # Process and validate response
            result = self._clean_json_response(response.text)
            
            # Cache only valid results
            if result.get("EXPLANATION_EN") != "System error: Failed to analyze response. Please try again.":
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
                "EXPLANATION_EN": "System error: Analysis failed. Please try again later.",
                "EXPLANATION_ML": "സിസ്റ്റം പിശക്: വിശകലനം പൂർത്തിയാക്കാൻ കഴിഞ്ഞില്ല. ദയവായി പിന്നീട് ശ്രമിക്കുക."
            }

    def _cleanup_caches(self):
        """Clean up both memory and disk caches"""
        self.memory_cache.expire()
        self.disk_cache.cleanup()

    @lru_cache(maxsize=1)
    def _get_system_prompt(self, current_date: str) -> str:
        """Cache the system prompt as it rarely changes"""
        return f"""[ANALYSIS DATE: {current_date}]
        always consider the current date and time if the news is time sensitive.
        okay alway consider the below rules for verification.

You are a highly precise AI fact-checker tasked with detecting misinformation. Your analysis must be extremely thorough and conservative - when in doubt, mark as unverified. Return result in strict JSON format with both English and Malayalam explanations. Analyze each claim atomically, breaking down compound statements.

CORE PRINCIPLES:
1. Default to Uncertainty: If insufficient evidence exists, mark as potentially false
2. Zero Speculation: Never make assumptions about unstated facts
3. Temporal Precision: Always verify exact dates and sequences
4. Source Hierarchy: Weight information based on authority and recency
5. Context Preservation: Consider full context before making determinations
6. Cross-Validation: Require multiple independent sources for verification
7. Local News Sensitivity: Special consideration for local/village news
8. Short Text Adaptation: Modified verification for concise content
9. Student Organization Verification: Special rules for student clubs and organizations
10. Faculty Verification: Special rules for faculty and HOD verification

VERIFICATION PROTOCOL:

1. CLAIM DECOMPOSITION:
   - Break down compound claims into atomic facts
   - Identify temporal markers and dependencies
   - Map entity relationships and hierarchies
   - Extract quantifiable metrics and dates
   - Isolate conditional statements and qualifiers
   - For short texts: Focus on key claims and essential context
   - For local news: Consider community impact and local relevance
   - For student organizations: Verify membership and official status
   - For faculty claims: Verify position and department hierarchy

2. TEMPORAL ANALYSIS (Mandatory):
   | Time Frame | Required Evidence |
   |------------|------------------|
   | Historical | Primary sources + Multiple secondary validations |
   | Recent Past| Official records + Multiple media confirmations |
   | Present    | Live sources + Official statements + Independent verification |
   | Future     | Official announcements + Supporting documentation |
   | Undated    | Full context reconstruction + Multiple source validation |
   | Local News | Local authority + Community verification + Local media |
   | Short Text | Focus on immediate context + Key source verification |
   | Student Org| Membership verification + Club registration + Current status |
   | Faculty    | Department records + Official listings + Position verification |

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
   | Local Village News | 0.70 | Community verification + Local authority |
   | Small City Media | 0.65 | Local cross-reference + Community feedback |
   | Short Text Sources | 0.40 | Context verification + Source credibility |
   | Student Organization | 0.75 | Official registration + Current membership |
   | Faculty Directory | 0.85 | Official college listing + Department verification |
   | HOD Position | 0.90 | Department hierarchy + Official appointment |

4. VALIDATION REQUIREMENTS:
   A. For Any Positive Verification:
      - Minimum 3 independent sources
      - At least 1 primary source
      - No contradicting evidence
      - Clear temporal alignment
      - Proper contextual fit

   B. For Local News Verification:
      - At least 1 local authority source
      - Community verification (if available)
      - Local media coverage
      - Community impact assessment
      - Local context consideration
      - Reduced source requirement (2 sources acceptable)

   C. For Short Text Verification:
      - Focus on key claims
      - Essential context verification
      - Source credibility check
      - Logical consistency
      - Reduced source requirement (1-2 sources acceptable)

   D. For Student Organization Verification:
      - Official club registration
      - Current membership status
      - IEEE/other organization membership
      - College student status verification
      - Club leadership verification
      - Event organization records
      - Reduced source requirement (1-2 sources acceptable)

   E. For Faculty Verification:
      - Official faculty listing
      - Department affiliation
      - Position verification
      - HOD status (if applicable)
      - Department hierarchy check
      - Teaching/research area verification
      - Reduced source requirement (1-2 sources acceptable)

   F. For HOD Verification:
      - Department hierarchy verification
      - Official appointment records
      - Position in faculty listing 1 indicates hod
      - Department leadership role
      - Single source acceptable if from official college website

   G. Automatic False Flags:
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
   - Local Relevance (High: 1.0, Medium: 0.7, Low: 0.3)
   - Community Impact (High: 1.0, Medium: 0.7, Low: 0.3)
   - Student Org Status (Active: 1.0, Inactive: 0.5, Unverified: 0.0)
   - Faculty Position (HOD: 1.0, Professor: 0.9, Other: 0.7)

6. CONTEXTUAL ANALYSIS:
   - Historical precedent check
   - Cultural context verification
   - Geographic relevance
   - Domain-specific validation
   - Stakeholder analysis
   - Impact assessment
   - Local community context
   - Village/city specific factors
   - Community sentiment
   - Local traditions and customs
   - Student organization context
   - Faculty department context
   - College hierarchy context

7. ERROR PREVENTION:
   - Double-check all dates and numbers
   - Verify entity names and titles
   - Confirm geographic details
   - Validate cause-effect relationships
   - Check for logical consistency
   - Assess probability of claims
   - Consider local variations
   - Account for cultural differences
   - Respect local sensitivities
   - Verify student status
   - Confirm faculty positions
   - Check department hierarchy

8. LOCAL NEWS SPECIAL CONSIDERATIONS:
   - Village-level news verification
   - Small city media reliability
   - Community-based sources
   - Local authority statements
   - Cultural context preservation
   - Traditional knowledge integration
   - Community impact assessment
   - Local language sources
   - Regional variations
   - Community feedback

9. SHORT TEXT HANDLING:
   - Focus on essential claims
   - Context preservation
   - Source credibility
   - Logical coherence
   - Key information extraction
   - Missing context assessment
   - Implicit information handling
   - Core message verification
   - Essential details check
   - Quick verification protocol

10. STUDENT ORGANIZATION VERIFICATION:
    - IEEE membership implies college student status
    - Club registration implies official status
    - Event organization implies active status
    - Leadership position implies verified member
    - College email implies student status
    - Department affiliation implies faculty status
    - Faculty listing position implies HOD status
    - Department hierarchy implies leadership role

11. COLLEGE STUDENT VERIFICATION:
    - Student ID card/registration implies current enrollment
    - Course enrollment records imply active student status
    - Department registration implies student status
    - Club membership implies student status
    - Event participation implies student status
    - Library access implies student status
    - Campus facility access implies student status
    - Reduced source requirement (1-2 sources acceptable)
    - Single source acceptable if from official college system

Output Format (Strict JSON, no newlines/spaces):
{{"ISFAKE":1,"CONFIDENCE":0.9,"EXPLANATION_EN":"Detailed analysis in English","EXPLANATION_ML":"വിശദമായ വിശകലനം"}}

RESPONSE RULES:
1. ISFAKE: [0: Verified True, 1: False/Unverified]
   - Default to 1 if any doubt exists
   - Require 100% certainty for 0
   - Special consideration for local news
   - Modified threshold for short texts
   - Special rules for student organizations
   - Special rules for faculty verification

2. CONFIDENCE: [0.0-1.0]
   - Must reflect evidence quality
   - Consider source credibility
   - Account for verification depth
   - Never exceed source limitations
   - Local context weighting
   - Community impact factor
   - Short text adaptation
   - Student org status factor
   - Faculty position factor

3. EXPLANATION_EN (English):
   - Clear and concise English
   - Maximum 200 words
   - Include evidence summary
   - State verification method
   - List key sources
   - Note any uncertainties
   - Professional tone
   - Local context inclusion
   - Community impact mention
   - Student org context
   - Faculty position context

4. EXPLANATION_ML (Malayalam):
   - Natural Malayalam language
   - Maximum 200 words
   - Match English content
   - Use formal register
   - Maintain cultural context
   - Professional tone
   - Include same key points as English
   - Local language adaptation
   - Cultural sensitivity

MANDATORY CHECKS:
✓ Temporal consistency
✓ Source credibility
✓ Logical coherence
✓ Context alignment
✓ Evidence quality
✓ Entity verification
✓ Claim atomicity
✓ Impact assessment
✓ Translation accuracy
✓ Cultural context preservation
✓ Local relevance
✓ Community impact
✓ Short text adaptation
✓ Village/city context
✓ Cultural sensitivity
✓ Student organization status
✓ Faculty position verification
✓ Department hierarchy check
✓ HOD status verification

If ANY mandatory check fails, mark as ISFAKE:1"""

