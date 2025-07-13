# Model Update: Switch to Kimi K2 for Better Performance

## Change Required
Replace all references to GPT-3.5 with the **MoonshotAI Kimi K2** model in the domain enrichment tool.

## Why This Change?
- **Better for tool use**: Kimi K2 is specifically optimized for agentic capabilities and tool use
- **Larger context**: 66K tokens vs GPT-3.5's smaller context window
- **Superior reasoning**: Excels at reasoning tasks, perfect for company disambiguation
- **More generous limits**: 66.3M tokens available vs limited free tier

## Specific Code Changes Needed

### 1. Update Model Name in API Calls
**Replace this:**
```python
"model": "openai/gpt-3.5-turbo"
```

**With this:**
```python
"model": "moonshotai/kimi-k2"
```

### 2. Update Metadata References
**Replace this:**
```python
"ai_model_used": "openai/gpt-3.5-turbo"
```

**With this:**
```python
"ai_model_used": "moonshotai/kimi-k2"
```

### 3. Update Comments and Documentation
Replace any comments or variable names that reference GPT-3.5 with Kimi K2.

### 4. Optimize for Larger Context Window
Since Kimi K2 has 66K context, you can:
- Include more search results in the AI analysis (increase from 15 to 25-30 results)
- Add more detailed search result content (increase content truncation from 200 to 400 characters)
- Include additional context in prompts

**Update this section:**
```python
# Old: Limited context for GPT-3.5
for result in search_results[:15]:  # Limit to avoid token limits
    formatted_results.append({
        "title": result.get('title', ''),
        "url": result.get('url', ''),
        "content": result.get('content', '')[:200]  # Truncate content
    })
```

**To this:**
```python
# New: Leverage Kimi K2's larger context window
for result in search_results[:25]:  # More results with larger context
    formatted_results.append({
        "title": result.get('title', ''),
        "url": result.get('url', ''),
        "content": result.get('content', '')[:400]  # More detailed content
    })
```

### 5. Enhanced Prompt for Better Results
Since Kimi K2 is optimized for reasoning, you can make the prompt more detailed:

```python
prompt = f"""
You are an expert AI assistant specialized in company research and domain identification. 

TASK: Analyze search results to find the PRIMARY business website domain.

Company: {company_name}
Address: {address.get('city', '')}, {address.get('state', '')} {address.get('zip', '')}

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
```

## Testing the Change
After making these updates, test with the same companies to ensure Kimi K2 provides better results:

```bash
python cli.py "ABB Ltd" "Zurich, Switzerland"  # Should clearly identify abb.com
python cli.py "Apple Inc" "Cupertino, CA"      # Should reliably find apple.com
```

## Expected Improvements
- Better disambiguation of ambiguous company names
- More accurate domain identification
- Improved confidence scoring
- Better handling of edge cases

Make these changes and the tool should perform significantly better at identifying the correct company domains!