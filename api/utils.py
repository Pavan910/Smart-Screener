"""
Shared utilities for Smart-Screener v5.0
Handles AI calls, JSON parsing, caching, and common functions.
"""

import os
import re
import json
import hashlib
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from functools import wraps

# Google Gemini SDK
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Simple in-memory cache for serverless (resets on cold start)
_cache: Dict[str, Dict[str, Any]] = {}


def get_ai_config() -> Optional[Dict[str, str]]:
    """Get AI provider configuration from environment."""
    # Prioritize Google Gemini for best accuracy and cost efficiency
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    print(f"[AI Config] GEMINI: {bool(gemini_key)}, OPENAI: {bool(os.environ.get('OPENAI_API_KEY', ''))}, MISTRAL: {bool(os.environ.get('MISTRAL_API_KEY', ''))}, GROQ: {bool(os.environ.get('GROQ_API_KEY', ''))}")
    if gemini_key:
        return {
            'provider': 'gemini',
            'api_key': gemini_key,
            'base_url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent',
            'model': 'gemini-3.6-flash',
            'supports_json_mode': True
        }

    # Fallback to OpenAI GPT-4o
    openai_key = os.environ.get('OPENAI_API_KEY', '')
    if openai_key:
        return {
            'provider': 'openai',
            'api_key': openai_key,
            'base_url': 'https://api.openai.com/v1/chat/completions',
            'model': 'gpt-4o',
            'supports_json_mode': True
        }

    # Fallback to Mistral (free tier, works with serverless)
    mistral_key = os.environ.get('MISTRAL_API_KEY', '')
    if mistral_key:
        return {
            'provider': 'mistral',
            'api_key': mistral_key,
            'base_url': 'https://api.mistral.ai/v1/chat/completions',
            'model': 'mistral-small-latest',
            'supports_json_mode': True
        }

    # Fallback to Groq if no other keys
    groq_key = os.environ.get('GROQ_API_KEY', '')
    if groq_key:
        return {
            'provider': 'groq',
            'api_key': groq_key,
            'base_url': 'https://api.groq.com/openai/v1/chat/completions',
            'model': 'openai/gpt-oss-120b',
            'supports_json_mode': False
        }

    return None


def call_ai(
    prompt: str,
    system_prompt: str = "You are an expert technical recruiter and resume analyst. Extract information accurately and return valid JSON.",
    max_tokens: int = 3000,
    temperature: float = 0.1,
    use_json_mode: bool = True
) -> Optional[str]:
    """
    Call AI provider with automatic fallback on failure.

    Args:
        prompt: User prompt to send
        system_prompt: System instruction
        max_tokens: Maximum response tokens
        temperature: Response temperature (lower = more deterministic)
        use_json_mode: Whether to use JSON response format

    Returns:
        AI response text or None on failure
    """
    # Try providers in order until one works
    providers_to_try = _get_all_configs()

    for config in providers_to_try:
        result = _call_single_provider(config, prompt, system_prompt, max_tokens, temperature, use_json_mode)
        if result:
            return result
        print(f"[AI] {config['provider']} failed, trying next provider...")

    print("[AI] All providers failed")
    return None


def _get_all_configs():
    """Get all available AI provider configs in priority order."""
    configs = []

    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    if gemini_key:
        configs.append({
            'provider': 'gemini',
            'api_key': gemini_key,
            'base_url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent',
            'model': 'gemini-3.6-flash',
            'supports_json_mode': True
        })

    openai_key = os.environ.get('OPENAI_API_KEY', '')
    if openai_key:
        configs.append({
            'provider': 'openai',
            'api_key': openai_key,
            'base_url': 'https://api.openai.com/v1/chat/completions',
            'model': 'gpt-4o',
            'supports_json_mode': True
        })

    mistral_key = os.environ.get('MISTRAL_API_KEY', '')
    if mistral_key:
        configs.append({
            'provider': 'mistral',
            'api_key': mistral_key,
            'base_url': 'https://api.mistral.ai/v1/chat/completions',
            'model': 'mistral-small-latest',
            'supports_json_mode': True
        })

    groq_key = os.environ.get('GROQ_API_KEY', '')
    if groq_key:
        configs.append({
            'provider': 'groq',
            'api_key': groq_key,
            'base_url': 'https://api.groq.com/openai/v1/chat/completions',
            'model': 'openai/gpt-oss-120b',
            'supports_json_mode': False
        })

    return configs


def _call_single_provider(config, prompt, system_prompt, max_tokens, temperature, use_json_mode):
    """Call a single AI provider and return result or None on failure."""
    try:
        provider = config['provider']
        print(f"[AI] Trying {provider}...")

        # Handle Gemini API (different format)
        if provider == 'gemini':
            return _call_gemini(config, prompt, system_prompt, max_tokens, temperature, use_json_mode)

        # Handle OpenAI-compatible APIs (OpenAI, Mistral, Groq)
        request_body = {
            "model": config['model'],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # Use JSON mode for OpenAI (ensures valid JSON output)
        if use_json_mode and config.get('supports_json_mode') and provider == 'openai':
            request_body["response_format"] = {"type": "json_object"}

        data = json.dumps(request_body).encode('utf-8')

        req = urllib.request.Request(
            config['base_url'],
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config["api_key"]}',
                'User-Agent': 'SmartScreener/1.0'
            }
        )

        # Increased timeout for complex extractions
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            content = result['choices'][0]['message']['content'].strip()
            print(f"[AI] {config['provider']} ({config['model']}): {len(content)} chars")
            return content

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode('utf-8')
        except:
            pass
        print(f"[AI] {config['provider']} HTTP Error {e.code}: {e.reason} - {error_body[:200]}")
        return None
    except urllib.error.URLError as e:
        print(f"[AI] {config['provider']} URL Error: {e.reason}")
        return None
    except Exception as e:
        print(f"[AI] {config['provider']} Error: {type(e).__name__}: {e}")
        return None


def _call_gemini(
    config: Dict[str, str],
    prompt: str,
    system_prompt: str,
    max_tokens: int,
    temperature: float,
    use_json_mode: bool
) -> Optional[str]:
    """
    Call Google Gemini API using official SDK.

    The SDK properly handles both AIza... and AQ... key formats.
    """
    if not GENAI_AVAILABLE:
        print("[AI] Gemini SDK not available, install google-genai")
        return None

    try:
        # Initialize client with API key
        client = genai.Client(api_key=config['api_key'])

        # Combine system prompt and user prompt
        full_prompt = f"{system_prompt}\n\n{prompt}"

        # Build generation config using SDK types
        from google.genai import types

        gen_config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        # Enable JSON mode
        if use_json_mode:
            gen_config.response_mime_type = "application/json"

        # Call the API
        print(f"[AI] Calling Gemini {config['model']}...")
        response = client.models.generate_content(
            model=config['model'],
            contents=full_prompt,
            config=gen_config
        )

        if response and response.text:
            content = response.text.strip()
            print(f"[AI] {config['provider']} ({config['model']}): {len(content)} chars")
            return content

        print("[AI] Gemini: No content in response")
        return None

    except Exception as e:
        import traceback
        print(f"[AI] Gemini Error: {type(e).__name__}: {e}")
        print(f"[AI] Traceback: {traceback.format_exc()}")
        return None


def parse_ai_json(response: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Parse JSON from AI response, handling markdown code blocks.

    Args:
        response: Raw AI response text

    Returns:
        Parsed JSON dictionary or None
    """
    if not response:
        return None

    try:
        # Remove markdown code blocks
        content = re.sub(r'^```(?:json)?\s*', '', response.strip())
        content = re.sub(r'\s*```$', '', content)
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON object from response
    try:
        match = re.search(r'\{[\s\S]*\}', response)
        if match:
            return json.loads(match.group(0))
    except json.JSONDecodeError:
        pass

    # Try to extract JSON array
    try:
        match = re.search(r'\[[\s\S]*\]', response)
        if match:
            return json.loads(match.group(0))
    except json.JSONDecodeError:
        pass

    print(f"[JSON] Failed to parse: {response[:200]}...")
    return None


def generate_hash(text: str) -> str:
    """Generate MD5 hash of text for caching/deduplication."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def cache_key(prefix: str, *args) -> str:
    """Generate cache key from prefix and arguments."""
    content = prefix + "|" + "|".join(str(a) for a in args)
    return generate_hash(content)


def get_cached(key: str) -> Optional[Any]:
    """Get value from cache if exists and not expired."""
    if key in _cache:
        entry = _cache[key]
        if entry.get('expires_at', 0) > datetime.now().timestamp():
            print(f"[Cache] Hit: {key[:16]}...")
            return entry.get('value')
        else:
            del _cache[key]
    return None


def set_cached(key: str, value: Any, ttl_seconds: int = 3600) -> None:
    """Set value in cache with TTL."""
    _cache[key] = {
        'value': value,
        'expires_at': datetime.now().timestamp() + ttl_seconds
    }
    print(f"[Cache] Set: {key[:16]}... (TTL: {ttl_seconds}s)")


def cached(ttl_seconds: int = 3600):
    """Decorator for caching function results."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key = cache_key(func.__name__, *args, *kwargs.values())

            # Check cache
            result = get_cached(key)
            if result is not None:
                return result

            # Call function and cache result
            result = func(*args, **kwargs)
            if result is not None:
                set_cached(key, result, ttl_seconds)

            return result
        return wrapper
    return decorator


def clean_text(text: str) -> str:
    """Clean and normalize text for processing."""
    if not text:
        return ""

    # Replace various unicode whitespace with regular space
    text = re.sub(r'[\u00a0\u2000-\u200b\u2028\u2029\u202f\u205f\u3000]', ' ', text)

    # Replace multiple whitespace with single space
    text = re.sub(r'[ \t]+', ' ', text)

    # Clean up multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove leading/trailing whitespace from lines
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()


def extract_email(text: str) -> str:
    """Extract email address from text."""
    match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return match.group(0).lower() if match else ""


def extract_phone(text: str) -> str:
    """Extract phone number from text (supports multiple formats)."""
    patterns = [
        r'\+91[\s\-]?\d{5}[\s\-]?\d{5}',      # Indian: +91-XXXXX-XXXXX
        r'\+91[\s\-]?\d{10}',                   # Indian: +91-XXXXXXXXXX
        r'\+1[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}',  # US: +1-XXX-XXX-XXXX
        r'\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}',  # US: (XXX) XXX-XXXX
        r'[6-9]\d{9}',                          # Indian mobile: XXXXXXXXXX
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return re.sub(r'[\s\-\(\)]', '', match.group(0))

    return ""


def extract_linkedin(text: str) -> str:
    """Extract LinkedIn URL from text."""
    match = re.search(r'linkedin\.com/in/([a-zA-Z0-9\-_]+)', text, re.I)
    if match:
        return f"https://linkedin.com/in/{match.group(1)}"
    return ""


def extract_github(text: str) -> str:
    """Extract GitHub URL from text."""
    match = re.search(r'github\.com/([a-zA-Z0-9\-_]+)', text, re.I)
    if match:
        return f"https://github.com/in/{match.group(1)}"
    return ""


def calculate_months_between(start: str, end: str) -> int:
    """
    Calculate months between two date strings.

    Args:
        start: Start date (YYYY-MM or YYYY)
        end: End date (YYYY-MM, YYYY, or "Present")

    Returns:
        Number of months between dates
    """
    current_year = datetime.now().year
    current_month = datetime.now().month

    def parse_date(date_str: str) -> tuple:
        """Parse date string to (year, month) tuple."""
        if not date_str or date_str.lower() in ['present', 'current', 'now']:
            return (current_year, current_month)

        # Try YYYY-MM format
        match = re.match(r'(\d{4})[-/](\d{1,2})', date_str)
        if match:
            return (int(match.group(1)), int(match.group(2)))

        # Try just YYYY
        match = re.match(r'(\d{4})', date_str)
        if match:
            return (int(match.group(1)), 6)  # Assume mid-year

        return (current_year, current_month)

    start_year, start_month = parse_date(start)
    end_year, end_month = parse_date(end)

    # Validate years
    if start_year < 1980 or start_year > current_year + 1:
        return 0
    if end_year < 1980 or end_year > current_year + 1:
        return 0

    months = (end_year - start_year) * 12 + (end_month - start_month)
    return max(0, months)


def truncate_text(text: str, max_length: int = 4000, suffix: str = "...") -> str:
    """Truncate text to max length, preserving word boundaries."""
    if len(text) <= max_length:
        return text

    truncated = text[:max_length - len(suffix)]
    # Try to break at word boundary
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.8:
        truncated = truncated[:last_space]

    return truncated + suffix


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer."""
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp value between min and max."""
    return max(min_val, min(max_val, value))
