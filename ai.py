"""
OmniCore — AI Service & BuildPilot
OpenRouter-powered intent detection and project blueprint generation.
The AI layer is fully modular — replacing OpenRouter requires
changing only this module, not any business logic elsewhere.

BuildPilot workflow:
  User Input → Intent Detection → Search Engine → Dataset Ranking →
  Solution Pack Matching → Blueprint Generation → Code Examples
"""
import json
import logging
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import Dataset, SearchHistory, User
from utils import Timer, success_response
from auth import get_current_user_optional

logger = logging.getLogger("omnicore.ai")


# ── Search Engine ─────────────────────────────────────────────────────────────
# Unified search engine shared by BuildPilot and Data Explorer.

def search_datasets(
    query: str,
    db: Session,
    limit: int = 10,
    domain_filter: Optional[str] = None,
) -> list[Dataset]:
    """
    Search datasets by keyword against name, description, tags, category, domain.
    Results are ranked by a combination of:
      - Keyword relevance (exact match > partial match)
      - Quality score
      - Popularity
    """
    if not query.strip():
        q = db.query(Dataset).filter_by(is_active=True)
        if domain_filter:
            q = q.filter(Dataset.domain == domain_filter)
        return q.order_by(Dataset.popularity.desc()).limit(limit).all()

    terms = query.lower().split()

    all_datasets = db.query(Dataset).filter_by(is_active=True).all()
    scored: list[tuple[float, Dataset]] = []

    for ds in all_datasets:
        if domain_filter and ds.domain != domain_filter:
            continue

        score = 0.0
        search_text = (
            ds.name.lower() + " " +
            ds.description.lower() + " " +
            ds.domain.lower() + " " +
            ds.category.lower() + " " +
            ds.tags.lower()
        )

        for term in terms:
            if term in ds.name.lower():
                score += 10.0          # Strong match in name
            if term in ds.category.lower():
                score += 5.0           # Match in category
            if term in ds.tags.lower():
                score += 4.0           # Match in tags
            if term in ds.domain.lower():
                score += 3.0           # Match in domain
            if term in ds.description.lower():
                score += 2.0           # Match in description
            if term in search_text:
                score += 1.0           # General presence

        # Boost by quality and popularity
        score += ds.quality_score * 0.5
        score += min(ds.popularity / 1000, 5.0)

        if score > 0:
            scored.append((score, ds))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [ds for _, ds in scored[:limit]]


# ── OpenRouter AI Client ──────────────────────────────────────────────────────

class AIProvider:
    """
    Modular AI provider interface.
    Currently implemented for OpenRouter using the OpenAI-compatible API.
    Swap provider by replacing this class — no other code changes required.
    """

    def __init__(self):
        self._base_url = settings.OPENROUTER_BASE_URL
        self._api_key = settings.OPENROUTER_API_KEY
        self._model = settings.OPENROUTER_MODEL
        self._client = httpx.Client(timeout=60)

    def _is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.startswith("sk-"))

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 2000) -> str:
        """Send a chat completion request and return the assistant message content."""
        if not self._is_configured():
            raise ValueError("OPENROUTER_API_KEY is not configured.")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://omnicore.dev",
            "X-Title": "OmniCore BuildPilot",
        }
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = self._client.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise ValueError("AI provider returned no choices.")

        return choices[0]["message"]["content"].strip()

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass


# Singleton provider — instantiated once, reused across requests
_ai_provider = AIProvider()


# ── BuildPilot Prompts ────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are BuildPilot, the AI assistant powering OmniCore — a Developer Data Infrastructure Platform.

Your job is to analyze what a developer is building and return a structured JSON project blueprint.

CRITICAL RULES:
1. Return ONLY valid JSON. No markdown, no explanations, no code blocks.
2. Never invent dataset names. Only use slugs from the provided dataset list.
3. Be specific and actionable. Generic advice is useless.
4. The blueprint must feel like a senior developer wrote it.
5. Estimated integration time should be realistic, not optimistic.

The JSON structure you must return:
{
  "project_type": "string — concise project category (e.g. 'Hospital Finder', 'Sports Analytics Platform')",
  "detected_domain": "string — primary domain from: Information Technology, Electronics, Healthcare, Geography, Sports",
  "secondary_domains": ["array of secondary domains if applicable"],
  "summary": "string — 2-3 sentences describing what this project does and why these datasets help",
  "solution_pack": "string — recommended solution pack ID (null if none fits well)",
  "recommended_datasets": [
    {
      "slug": "dataset-slug",
      "reason": "why this specific dataset is recommended for this project",
      "usage": "how the developer should use this dataset in their app",
      "priority": "primary|secondary|optional"
    }
  ],
  "suggested_filters": ["list of useful query parameters or data filters for this use case"],
  "estimated_integration_time": "string (e.g. '3–5 hours')",
  "difficulty": "Beginner|Intermediate|Advanced",
  "quick_start": ["ordered list of 5–7 concrete steps to get started"],
  "code_examples": {
    "python": "complete working Python example using requests library",
    "javascript": "complete working JavaScript Fetch example",
    "fastapi": "complete FastAPI route that consumes OmniCore data",
    "express": "complete Express.js route that consumes OmniCore data",
    "curl": "complete cURL command example"
  }
}"""


def _build_user_prompt(user_input: str, available_datasets: list[dict]) -> str:
    dataset_list = json.dumps([
        {
            "slug": d["slug"],
            "name": d["name"],
            "domain": d["domain"],
            "category": d["category"],
            "tags": d["tags"],
        }
        for d in available_datasets
    ], indent=2)

    return f"""Developer says: "{user_input}"

Available datasets in OmniCore (ONLY use these slugs):
{dataset_list}

Return the project blueprint JSON now."""


# ── Fallback Blueprint (when AI is not configured) ────────────────────────────

def _generate_fallback_blueprint(
    user_input: str,
    matched_datasets: list[Dataset],
    solution_pack_id: Optional[str],
) -> dict:
    """
    Rule-based blueprint generator used when OpenRouter is not configured.
    Provides a useful response without requiring an AI key.
    """
    from datasets import SOLUTION_PACKS

    pack = next((p for p in SOLUTION_PACKS if p["id"] == solution_pack_id), None)
    domain = matched_datasets[0].domain if matched_datasets else "Information Technology"

    recommendations = []
    for i, ds in enumerate(matched_datasets[:6]):
        recommendations.append({
            "slug": ds.slug,
            "reason": f"{ds.name} provides {ds.category.lower()} data relevant to your project.",
            "usage": f"Query the {ds.endpoint} endpoint with your API key.",
            "priority": "primary" if i < 2 else ("secondary" if i < 4 else "optional"),
        })

    api_key_placeholder = "YOUR_OMNICORE_API_KEY"
    first_slug = matched_datasets[0].slug if matched_datasets else "world-countries"
    base_url = "https://your-backend.hf.space"

    return {
        "project_type": user_input[:80],
        "detected_domain": domain,
        "secondary_domains": [],
        "summary": f"Based on your description, OmniCore has identified {len(matched_datasets)} relevant dataset(s) that can power your application. Configure your OPENROUTER_API_KEY for AI-powered recommendations.",
        "solution_pack": solution_pack_id,
        "recommended_datasets": recommendations,
        "suggested_filters": ["country", "date", "limit", "page"],
        "estimated_integration_time": "2–4 hours",
        "difficulty": "Beginner",
        "quick_start": [
            "Register at OmniCore to get your universal API key.",
            f"Explore the recommended datasets in the Data Explorer.",
            f"Test your first API call in the API Console.",
            f"Copy the endpoint URL and API key into your application.",
            "Use the code examples below to make your first request.",
            "Add pagination (page, page_size) to handle large datasets.",
        ],
        "code_examples": {
            "python": f'''import requests

API_KEY = "{api_key_placeholder}"
BASE_URL = "{base_url}"

response = requests.get(
    f"{{BASE_URL}}/api/v1/datasets/{first_slug}/data",
    headers={{"Authorization": f"Bearer {{API_KEY}}"}},
    params={{"page": 1, "page_size": 20}}
)
data = response.json()
print(f"Retrieved {{data['count']}} records.")
for record in data["data"]:
    print(record)
''',
            "javascript": f'''const API_KEY = "{api_key_placeholder}";
const BASE_URL = "{base_url}";

const response = await fetch(
  `${{BASE_URL}}/api/v1/datasets/{first_slug}/data?page=1&page_size=20`,
  {{
    headers: {{
      "Authorization": `Bearer ${{API_KEY}}`
    }}
  }}
);

const data = await response.json();
console.log(`Retrieved ${{data.count}} records.`);
data.data.forEach(record => console.log(record));
''',
            "fastapi": f'''from fastapi import FastAPI
import httpx

app = FastAPI()
API_KEY = "{api_key_placeholder}"
BASE_URL = "{base_url}"

@app.get("/data")
async def get_data(page: int = 1, page_size: int = 20):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{{BASE_URL}}/api/v1/datasets/{first_slug}/data",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            params={{"page": page, "page_size": page_size}}
        )
    return response.json()
''',
            "express": f'''const express = require("express");
const axios = require("axios");
const app = express();

const API_KEY = "{api_key_placeholder}";
const BASE_URL = "{base_url}";

app.get("/data", async (req, res) => {{
  const {{ page = 1, page_size = 20 }} = req.query;
  const response = await axios.get(
    `${{BASE_URL}}/api/v1/datasets/{first_slug}/data`,
    {{
      headers: {{ Authorization: `Bearer ${{API_KEY}}` }},
      params: {{ page, page_size }}
    }}
  );
  res.json(response.data);
}});

app.listen(3001, () => console.log("Server running on port 3001"));
''',
            "curl": f'''curl -X GET \\
  "{base_url}/api/v1/datasets/{first_slug}/data?page=1&page_size=20" \\
  -H "Authorization: Bearer {api_key_placeholder}" \\
  -H "Accept: application/json"
''',
        },
    }


# ── BuildPilot Service ────────────────────────────────────────────────────────

def run_buildpilot(user_input: str, db: Session) -> dict:
    """
    Main BuildPilot service function.
    1. Search for relevant datasets
    2. Match a solution pack
    3. Call AI for structured blueprint (or use fallback)
    4. Return structured JSON blueprint
    """
    from datasets import DATASET_CATALOG, SOLUTION_PACKS

    # Step 1: Search for relevant datasets
    matched_datasets = search_datasets(user_input, db, limit=10)

    if not matched_datasets:
        # Broader fallback
        matched_datasets = db.query(Dataset).filter_by(is_active=True).order_by(
            Dataset.popularity.desc()
        ).limit(6).all()

    # Step 2: Match best Solution Pack
    solution_pack_id = _match_solution_pack(user_input, matched_datasets)

    # Step 3: Try AI, fall back to rule-based
    if _ai_provider._is_configured():
        try:
            available = [{
                "slug": d.slug, 
                "name": d.name, 
                "domain": d.domain, 
                "category": d.category, 
                "tags": d.tags_list
            } for d in matched_datasets]
            
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(user_input, available)},
            ]
            raw_response = _ai_provider.chat(messages, temperature=0.2, max_tokens=3000)

            # Parse JSON response
            blueprint = _parse_ai_response(raw_response)
            blueprint["_source"] = "ai"
            blueprint["solution_pack"] = solution_pack_id or blueprint.get("solution_pack")
            return blueprint
        except Exception as exc:
            logger.warning("AI call failed, using fallback: %s", exc)

    # Fallback
    blueprint = _generate_fallback_blueprint(user_input, matched_datasets, solution_pack_id)
    blueprint["_source"] = "fallback"
    return blueprint


def _parse_ai_response(raw: str) -> dict:
    """
    Parse the AI's JSON response. Strip any markdown fences if present.
    Raises ValueError if the response cannot be parsed.
    """
    # Remove markdown code fences if AI wraps response
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        stripped = "\n".join(lines[1:-1]).strip()
    return json.loads(stripped)


def _match_solution_pack(user_input: str, datasets: list[Dataset]) -> Optional[str]:
    """
    Rule-based solution pack matching.
    Scores each pack by how many keywords from user_input appear in pack description.
    """
    from datasets import SOLUTION_PACKS

    user_lower = user_input.lower()
    best_pack = None
    best_score = 0

    # Keyword hints for each pack
    pack_keywords = {
        "ai-chatbot-pack": ["chatbot", "chat", "ai", "assistant", "qa", "bot", "nlp"],
        "healthcare-analytics-pack": ["health", "medical", "disease", "hospital", "clinical", "patient"],
        "hospital-finder-pack": ["hospital", "clinic", "doctor", "healthcare", "finder", "locator"],
        "sports-analytics-pack": ["sport", "football", "cricket", "nba", "basketball", "olympic", "athlete"],
        "ml-starter-pack": ["machine learning", "ml", "deep learning", "neural", "model", "training", "dataset"],
        "electronics-research-pack": ["electronics", "iot", "arduino", "raspberry", "sensor", "circuit", "embedded"],
        "location-intelligence-pack": ["location", "geography", "map", "city", "country", "airport", "travel"],
        "university-finder-pack": ["university", "college", "education", "campus", "school", "student"],
    }

    for pack_id, keywords in pack_keywords.items():
        score = sum(1 for kw in keywords if kw in user_lower)
        if score > best_score:
            best_score = score
            best_pack = pack_id

    return best_pack if best_score >= 1 else None


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/buildpilot", tags=["BuildPilot"])


class BuildPilotRequest(BaseModel):
    input: str


@router.post("/analyze")
def analyze(
    body: BuildPilotRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    BuildPilot flagship endpoint.
    Accepts a natural language description of what the developer is building
    and returns a fully structured Project Blueprint.
    """
    if not body.input or len(body.input.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please describe what you are building (minimum 5 characters).",
        )

    if len(body.input) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Input too long. Please keep your description under 500 characters.",
        )

    with Timer() as t:
        blueprint = run_buildpilot(body.input.strip(), db)

        # Log search for analytics
        if current_user:
            sh = SearchHistory(
                user_id=current_user.id,
                query=f"[BuildPilot] {body.input[:200]}",
                results_count=len(blueprint.get("recommended_datasets", [])),
            )
            db.add(sh)
            db.commit()

    return success_response(
        data=blueprint,
        message="Project blueprint generated.",
        execution_time_ms=t.elapsed_ms,
    )


@router.get("/examples")
def get_examples():
    """Return example BuildPilot prompts to inspire developers."""
    return success_response(
        data=[
            "I'm building a Hospital Finder application for patients.",
            "I'm building an AI chatbot for medical questions.",
            "I'm building a Sports Analytics platform for cricket fans.",
            "I'm building a University Finder for international students.",
            "I'm building a real-time IoT device monitoring dashboard.",
            "I'm building a machine learning experiment tracker.",
            "I'm building a global weather and timezone converter app.",
            "I'm building a COVID-19 dashboard with country comparisons.",
            "I'm building an electronics component search engine.",
            "I'm building an Olympic Games history explorer.",
        ],
        message="Example BuildPilot prompts.",
    )


@router.get("/search")
def buildpilot_search(
    q: str,
    limit: int = 8,
    db: Session = Depends(get_db),
):
    """
    Lightweight dataset search endpoint for the BuildPilot UI.
    Returns matching datasets without invoking the AI.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required.")

    with Timer() as t:
        results = search_datasets(q, db, limit=limit)

    return success_response(
        data=[ds.to_dict(include_provenance=False) for ds in results],
        count=len(results),
        execution_time_ms=t.elapsed_ms,
    )


# ── API Console Endpoint ──────────────────────────────────────────────────────

console_router = APIRouter(prefix="/console", tags=["API Console"])


class ConsoleRequest(BaseModel):
    endpoint: str
    method: str = "GET"
    params: Optional[dict] = None
    api_key: str


@console_router.post("/execute")
def execute_console(body: ConsoleRequest, db: Session = Depends(get_db)):
    """
    Proxy endpoint for the API Console.
    Executes a request against OmniCore's own API internally
    and returns the response with timing metadata.
    """
    # Validate method
    if body.method.upper() not in ("GET",):
        raise HTTPException(status_code=400, detail="Only GET is supported in the API Console.")

    # Validate the endpoint targets /api/v1/
    if not body.endpoint.startswith("/api/v1/"):
        raise HTTPException(
            status_code=400,
            detail="Endpoint must start with /api/v1/",
        )

    # Validate API key
    import hashlib
    from models import APIKey
    key_hash = hashlib.sha256(body.api_key.encode()).hexdigest()
    api_key_rec = db.query(APIKey).filter_by(key_hash=key_hash, is_active=True).first()
    if not api_key_rec:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    start = time.perf_counter()

    # Make internal HTTP request
    try:
        with httpx.Client(timeout=30) as client:
            url = f"http://localhost:8000{body.endpoint}"
            resp = client.get(
                url,
                params=body.params or {},
                headers={"Authorization": f"Bearer {body.api_key}"},
            )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return success_response(
            data={
                "status_code": resp.status_code,
                "response_body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
                "response_time_ms": elapsed_ms,
                "endpoint": body.endpoint,
                "method": body.method.upper(),
                "code_snippets": _generate_code_snippets(body.endpoint, body.api_key, body.params),
            },
            execution_time_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return success_response(
            data={
                "status_code": 500,
                "response_body": {"error": str(exc)},
                "response_time_ms": elapsed_ms,
                "endpoint": body.endpoint,
                "method": body.method.upper(),
                "code_snippets": _generate_code_snippets(body.endpoint, body.api_key, body.params),
            },
            execution_time_ms=elapsed_ms,
        )


def _generate_code_snippets(endpoint: str, api_key: str, params: Optional[dict]) -> dict:
    """Generate ready-to-use code snippets for the API Console."""
    base_url = "https://your-backend.hf.space"
    display_key = api_key[:12] + "..."
    param_str = "&".join(f"{k}={v}" for k, v in (params or {}).items())
    full_url = f"{base_url}{endpoint}" + (f"?{param_str}" if param_str else "")
    params_repr_py = repr(params) if params else "{}"
    params_repr_js = json.dumps(params) if params else "null"

    return {
        "curl": f'curl -X GET \\\n  "{full_url}" \\\n  -H "Authorization: Bearer {display_key}" \\\n  -H "Accept: application/json"',
        "python": f'''import requests

response = requests.get(
    "{base_url}{endpoint}",
    headers={{"Authorization": "Bearer {display_key}"}},
    params={params_repr_py}
)
data = response.json()
print(data)
''',
        "javascript": f'''const response = await fetch(
  "{full_url}",
  {{
    headers: {{
      "Authorization": "Bearer {display_key}"
    }}
  }}
);
const data = await response.json();
console.log(data);
''',
        "fastapi": f'''import httpx
from fastapi import FastAPI

app = FastAPI()

@app.get("/proxy")
async def proxy_data():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "{base_url}{endpoint}",
            headers={{"Authorization": "Bearer {display_key}"}},
            params={params_repr_py}
        )
    return response.json()
''',
        "express": f'''const axios = require("axios");

app.get("/proxy", async (req, res) => {{
  const response = await axios.get("{full_url}", {{
    headers: {{ Authorization: "Bearer {display_key}" }}
  }});
  res.json(response.data);
}});
''',
    }


# ── Dashboard Routes ──────────────────────────────────────────────────────────

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@dashboard_router.get("/")
def get_dashboard(
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Return full dashboard data for the authenticated user."""
    from auth import get_current_user
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required.")

    with Timer() as t:
        from models import APIKey, SavedDataset, SearchHistory, UsageStat

        api_keys = db.query(APIKey).filter_by(user_id=current_user.id, is_active=True).order_by(APIKey.created_at.desc()).all()
        saved = db.query(SavedDataset).filter_by(user_id=current_user.id).order_by(SavedDataset.saved_at.desc()).limit(10).all()
        recent_searches = db.query(SearchHistory).filter_by(user_id=current_user.id).order_by(SearchHistory.searched_at.desc()).limit(10).all()
        usage_stats = db.query(UsageStat).filter_by(user_id=current_user.id).order_by(UsageStat.created_at.desc()).limit(50).all()

        total_api_calls = sum(k.usage_count for k in api_keys)
        total_datasets = db.query(Dataset).filter_by(is_active=True).count()

    return success_response(
        data={
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "username": current_user.username,
                "member_since": current_user.created_at.isoformat() + "Z",
                "last_login": current_user.last_login.isoformat() + "Z" if current_user.last_login else None,
            },
            "stats": {
                "total_api_calls": total_api_calls,
                "active_api_keys": len(api_keys),
                "saved_datasets": len(saved),
                "total_available_datasets": total_datasets,
            },
            "api_keys": [
                {
                    "id": k.id,
                    "name": k.name,
                    "key_prefix": k.key_prefix,
                    "usage_count": k.usage_count,
                    "last_used": k.last_used.isoformat() + "Z" if k.last_used else None,
                    "created_at": k.created_at.isoformat() + "Z",
                }
                for k in api_keys
            ],
            "saved_datasets": [
                {
                    "dataset_id": s.dataset_id,
                    "dataset": s.dataset.to_dict(include_provenance=False) if s.dataset else None,
                    "saved_at": s.saved_at.isoformat() + "Z",
                }
                for s in saved
            ],
            "recent_searches": [
                {
                    "query": sh.query,
                    "results_count": sh.results_count,
                    "searched_at": sh.searched_at.isoformat() + "Z",
                }
                for sh in recent_searches
            ],
            "recent_usage": [
                {
                    "endpoint": u.endpoint,
                    "response_time_ms": u.response_time_ms,
                    "status_code": u.status_code,
                    "created_at": u.created_at.isoformat() + "Z",
                }
                for u in usage_stats
            ],
        },
        execution_time_ms=t.elapsed_ms,
    )
