import logging
import traceback
import os
import re
import requests
import pickle
import numpy as np
from urllib.parse import urlparse
import asyncio
from typing import Dict, List, Optional, Union
from pydantic import BaseModel

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class URLAnalysisResponse(BaseModel):
    url: str
    prediction: str
    prediction_probabilities: List[float]
    google_safe_browsing_flag: bool
    trusted: bool
    trust_score: float
    is_trustworthy: bool
    trust_reasons: List[str]
    final_decision: str

class URLAnalysisService:
    def __init__(self):
        self.trusted_domains = [
            # Major Malayalam News Sites
            "manoramaonline.com",
            "mathrubhumi.com",
            "madhyamam.com",
            "deshabhimani.com",
            "keralakaumudi.com",
            "deepika.com",
            "janmabhumidaily.com",
            "mangalam.com",
            "metrovaartha.com",
            "chandrikadaily.com",
            "sirajlive.com",
            "suprabhaatham.com",
            "thejasnews.com",
            "uttarandhra.com",
            "keralaonlinenews.com",
            "asianetnews.com",
            "twentyfournews.com",
            "reporterlive.com",
            "jaihindtv.in",
            "mediaonetvnews.in",
            "kvartha.com",
            
            # Regional/Local Malayalam News Sites
            "kottayamvartha.com",
            "ernakulamvartha.com",
            "thiruvananthapuramvartha.com",
            "kozhikodevartha.com",
            "wayanadvartha.com",
            "kannurvartha.com",
            "thrissurvartha.com",
            "piravomnews.com",
            "erumeli.com",
            
            # Major English News Sites
            "thehindu.com",
            "timesofindia.com",
            "indianexpress.com",
            "hindustantimes.com",
            "deccanchronicle.com",
            "dnaindia.com",
            "ndtv.com",
            "firstpost.com",
            "economictimes.indiatimes.com",
            "livemint.com",
            "telegraphindia.com",
            "scroll.in",
            "news18.com",
            "oneindia.com",
            "zeenews.india.com",
            "business-standard.com",
            "newindianexpress.com"
        ]
        self.model_path = "trained_model.pkl"
        self.google_api_key = os.getenv("GOOGLE_SAFE_BROWSING_API_KEY", "AIzaSyBkS78CJHZXLxzVWe-hCDxh-X-ADCgmMCc")

    def convert_numpy(self, o):
        if isinstance(o, np.integer):
            return int(o)
        elif isinstance(o, np.floating):
            return float(o)
        elif isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

    def is_trusted_url(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return any(trusted in domain for trusted in self.trusted_domains)

    def extract_features(self, url: str) -> Optional[List[float]]:
        logger.debug(f"Extracting features from: {url}")
        try:
            features = {}
            features['having_IP_Address'] = 1 if re.search(r'\d+\.\d+\.\d+\.\d+', url) else -1
            features['URL_Length'] = len(url)
            features['Shortining_Service'] = 1 if any(short in url.lower() for short in ['bit.ly', 'goo.gl', 'tinyurl']) else -1
            features['having_At_Symbol'] = 1 if "@" in url else -1
            features['double_slash_redirecting'] = 1 if re.search(r'https?://.+//', url) else -1

            additional_features = [
                'Prefix_Suffix', 'having_Sub_Domain', 'SSLfinal_State',
                'Domain_registeration_length', 'Favicon', 'port', 'HTTPS_token',
                'Request_URL', 'URL_of_Anchor', 'Links_in_tags', 'SFH',
                'Submitting_to_email', 'Abnormal_URL', 'Redirect', 'on_mouseover',
                'RightClick', 'popUpWidnow', 'Iframe', 'age_of_domain',
                'DNSRecord', 'web_traffic', 'Page_Rank', 'Google_Index',
                'Links_pointing_to_page', 'Statistical_report'
            ]
            for feat in additional_features:
                features[feat] = -1

            return [features[k] for k in sorted(features.keys())]
        except Exception as e:
            logger.error(f"Error extracting features: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    async def check_safe_browsing(self, url: str) -> Dict:
        logger.debug(f"Checking safe browsing for: {url}")
        try:
            endpoint = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
            params = {"key": self.google_api_key}
            payload = {
                "client": {
                    "clientId": "yeah-news-analyzer",
                    "clientVersion": "1.0"
                },
                "threatInfo": {
                    "threatTypes": [
                        "MALWARE",
                        "SOCIAL_ENGINEERING",
                        "POTENTIALLY_HARMFUL_APPLICATION",
                        "UNWANTED_SOFTWARE"
                    ],
                    "platformTypes": ["ANY_PLATFORM"],
                    "threatEntryTypes": ["URL"],
                    "threatEntries": [{"url": url}]
                }
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, params=params, json=payload) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Safe Browsing API error: {str(e)}")
            logger.error(traceback.format_exc())
            return {"error": "Safe Browsing check failed"}

    def score_url_trustworthiness(self, url_analysis: Dict) -> Dict:
        score = 0
        reasons = []

        if url_analysis.get('safe_browsing', {}).get('matches'):
            score -= 50
            reasons.append('Flagged by Google Safe Browsing')

        fakeness_prob = url_analysis.get('probabilities', [0, 0])[1]
        if fakeness_prob > 0.5:
            score -= int(fakeness_prob * 50)
            reasons.append(f'ML model confidence: {int(fakeness_prob * 100)}%')

        if url_analysis.get('is_trusted', False):
            score += 50
            reasons.append('Verified by trusted news database')

        trust_score = max(0, min(100, 50 + score))

        return {
            'trust_score': trust_score,
            'is_trustworthy': trust_score >= 50,
            'reasons': reasons
        }

    async def analyze_url(self, url: str) -> URLAnalysisResponse:
        logger.info(f"Analyzing URL: {url}")
        
        feature_vector = self.extract_features(url)
        if feature_vector is None:
            raise ValueError("Feature extraction failed.")

        if not os.path.exists(self.model_path):
            logger.error(f"Model file not found at {self.model_path}")
            raise FileNotFoundError(f"Model file not found at {self.model_path}")

        try:
            with open(self.model_path, "rb") as f:
                clf = pickle.load(f)
            prediction = int(clf.predict([feature_vector])[0])
            probabilities = [float(p) for p in clf.predict_proba([feature_vector])[0]]
        except Exception as e:
            logger.error(f"Error during ML prediction: {str(e)}")
            logger.error(traceback.format_exc())
            prediction = None
            probabilities = [0, 0]

        sb_result = await self.check_safe_browsing(url)
        sb_flag = bool(sb_result.get("matches"))

        trustworthiness = self.score_url_trustworthiness({
            'safe_browsing': sb_result,
            'probabilities': probabilities,
            'is_trusted': self.is_trusted_url(url)
        })

        final_decision = "URL appears Trustworthy"
        if sb_flag:
            final_decision = "URL is Untrustworthy (flagged by Google Safe Browsing)"
        elif probabilities[1] > 0.5:
            final_decision = "URL is Possibly Phishing/Spam (ML model high probability)"
        if self.is_trusted_url(url):
            final_decision = "Trusted URL (verified by trusted database)"

        return URLAnalysisResponse(
            url=url,
            prediction="Fake" if prediction == 1 else "Legitimate",
            prediction_probabilities=probabilities,
            google_safe_browsing_flag=sb_flag,
            trusted=self.is_trusted_url(url),
            trust_score=trustworthiness['trust_score'],
            is_trustworthy=trustworthiness['is_trustworthy'],
            trust_reasons=trustworthiness['reasons'],
            final_decision=final_decision
        ) 