import httpx
import json
import time
import logging
from typing import List, Dict, Optional
from models import CompanyRequest, DomainResponse
from searxng_client import SearXNGClient

logger = logging.getLogger(__name__)

class DomainEnrichmentService:
    def __init__(self, searxng_url: str, openrouter_api_key: str, ai_model: str = "moonshotai/kimi-k2"):
        self.searxng_client = SearXNGClient(searxng_url)
        self.openrouter_api_key = openrouter_api_key
        self.ai_model = ai_model
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def process_company_request(self, request: CompanyRequest) -> DomainResponse:
        """Main workflow to find company domain"""
        start_time = time.time()
        
        logger.info(f"Processing request for: {request.company_name}")
        
        # Step 1: Generate search queries
        search_queries = self.generate_search_queries(request.company_name, request.address)
        logger.debug(f"Generated {len(search_queries)} search queries")
        
        # Step 2: Search via SearXNG
        all_search_results = []
        for query in search_queries:
            results = await self.searxng_client.search(query)
            all_search_results.extend(results)
        
        logger.debug(f"Collected {len(all_search_results)} total search results")
        
        # Step 3: AI analysis of results
        domain_analysis = await self.analyze_results_with_ai(
            request.company_name, 
            request.address, 
            all_search_results
        )
        
        # Step 4: Verify domain if found
        verification_status = "no_domain_found"
        if domain_analysis.get('primary_domain'):
            verification_status = await self.verify_domain(domain_analysis['primary_domain'])
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return DomainResponse(
            primary_domain=domain_analysis.get('primary_domain'),
            confidence_score=domain_analysis.get('confidence_score', 0.0),
            search_queries_used=search_queries,
            domains_considered=domain_analysis.get('alternative_domains', []),
            verification_status=verification_status,
            processing_time_ms=processing_time,
            metadata={
                "company_name_normalized": self.normalize_company_name(request.company_name),
                "ai_model_used": self.ai_model,
                "search_results_count": len(all_search_results),
                "domain_status": verification_status,
                "reasoning": domain_analysis.get('reasoning', '')
            }
        )
    
    def generate_search_queries(self, company_name: str, address) -> List[str]:
        """Generate multiple search query variations"""
        normalized_name = self.normalize_company_name(company_name)
        city = address.city if hasattr(address, 'city') else address.get('city', '')
        state = address.state if hasattr(address, 'state') else address.get('state', '')
        
        queries = [
            f'"{normalized_name}" official website',
            f'"{normalized_name}" {city} {state} website',
            f'"{normalized_name}" headquarters website',
            f'"{normalized_name}" corporate site',
            f'{normalized_name} {city} company website',
            f'"{company_name}" official domain'
        ]
        
        # Remove duplicates and empty queries
        unique_queries = list(set([q for q in queries if q.strip()]))
        return unique_queries
    
    def normalize_company_name(self, name: str) -> str:
        """Clean up company name for better search results"""
        suffixes = ['Inc', 'Corp', 'Corporation', 'LLC', 'Ltd', 'Limited', 'Co', 'Company']
        normalized = name.strip()
        
        for suffix in suffixes:
            if normalized.endswith(f' {suffix}'):
                normalized = normalized[:-len(suffix)-1]
        
        return normalized.strip()
    
    async def analyze_results_with_ai(self, company_name: str, address, search_results: List[Dict]) -> Dict:
        """Use OpenRouter AI to analyze search results and identify primary domain"""
        
        if not search_results:
            return {
                "primary_domain": None, 
                "confidence_score": 0.0, 
                "reasoning": "No search results available",
                "alternative_domains": []
            }
        
        # Prepare search results for AI analysis
        formatted_results = []
        for result in search_results[:25]:  # Leverage Kimi K2's larger context window
            formatted_results.append({
                "title": result.get('title', ''),
                "url": result.get('url', ''),
                "content": result.get('content', '')[:400]  # More detailed content for Kimi K2
            })
        
        city = address.city if hasattr(address, 'city') else address.get('city', '')
        state = address.state if hasattr(address, 'state') else address.get('state', '')
        zip_code = getattr(address, 'zip', None) if hasattr(address, 'zip') else address.get('zip', '')
        
        prompt = f"""
You are an expert AI assistant specialized in company research and domain identification. 

TASK: Analyze search results to find the PRIMARY business website domain.

Company: {company_name}
Address: {city}, {state} {zip_code}

Search Results (analyze all thoroughly):
{json.dumps(formatted_results, indent=2)}

ANALYSIS REQUIREMENTS:
1. Identify the most likely PRIMARY business domain (not social media, news, or subsidiaries)
2. Look for official corporate websites matching company name AND location
3. Avoid regional subsidiaries unless clearly the primary entity
4. Consider domain authority, relevance, and geographic alignment
5. Be especially careful with common company names (e.g., distinguish "ABB" electronics vs "ABB" bank)

REASONING PROCESS:
- First, eliminate obviously irrelevant results
- Then, identify potential official domains
- Cross-reference company name variations with location
- Validate domain relevance to the specific company/address provided

Return ONLY a JSON object with this exact format:
{{
  "primary_domain": "example.com" or null,
  "confidence_score": 0.0-1.0,
  "reasoning": "Detailed explanation of selection process",
  "alternative_domains": ["other.com", "another.com"],
  "eliminated_results": ["why certain results were discarded"],
  "location_match": "how well the domain matches the provided address"
}}

Be conservative - if uncertain, return null for primary_domain rather than guessing.
"""

        try:
            logger.debug("Sending request to OpenRouter AI")
            response = await self.http_client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.ai_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 500
                }
            )
            
            if response.status_code == 200:
                ai_response = response.json()
                content = ai_response['choices'][0]['message']['content']
                logger.debug(f"AI response: {content}")
                
                # Parse JSON response
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse AI JSON response: {e}")
                    return {
                        "primary_domain": None, 
                        "confidence_score": 0.0, 
                        "reasoning": "Failed to parse AI response",
                        "alternative_domains": []
                    }
            else:
                logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                return {
                    "primary_domain": None, 
                    "confidence_score": 0.0, 
                    "reasoning": f"AI API error: {response.status_code}",
                    "alternative_domains": []
                }
                
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return {
                "primary_domain": None, 
                "confidence_score": 0.0, 
                "reasoning": f"Error: {str(e)}",
                "alternative_domains": []
            }
    
    async def verify_domain(self, domain: str) -> str:
        """Verify that domain is accessible and appears legitimate"""
        logger.debug(f"Verifying domain: {domain}")
        
        try:
            # Check HTTPS first
            response = await self.http_client.head(f"https://{domain}", timeout=10.0)
            
            if response.status_code < 400:
                return "verified"
            else:
                return "inaccessible"
                
        except:
            try:
                # Try HTTP if HTTPS fails
                response = await self.http_client.head(f"http://{domain}", timeout=10.0)
                if response.status_code < 400:
                    return "http_only"
                else:
                    return "inaccessible"
            except:
                return "unreachable"
    
    async def close(self):
        """Close HTTP clients"""
        await self.http_client.aclose()
        await self.searxng_client.close()