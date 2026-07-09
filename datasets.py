"""
OmniCore — Dataset Registry
Contains the full curated catalog of 32 datasets across 5 domains,
8 Solution Packs, all dataset routes, seeding logic, and data preview.
"""
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_user, get_current_user_optional
from database import get_db
from models import Dataset, DatasetVersion, SavedDataset, SearchHistory, User
from utils import Timer, paginate, success_response

# ── Solution Packs ────────────────────────────────────────────────────────────

SOLUTION_PACKS = [
    {
        "id": "ai-chatbot-pack",
        "name": "AI Chatbot Pack",
        "description": "Everything you need to build an intelligent chatbot with medical knowledge, research paper awareness, and ML model recommendations.",
        "domain": "Information Technology + Healthcare",
        "icon": "🤖",
        "datasets": ["medical-qa-dataset", "arxiv-cs-papers", "huggingface-models", "papers-with-code"],
        "estimated_integration_time": "2–4 hours",
        "difficulty": "Intermediate",
        "use_cases": ["Customer support bots", "Medical Q&A assistants", "Research paper summarizers", "ML model recommenders"],
        "quick_start": "Use medical-qa-dataset for domain knowledge, arxiv-cs-papers for research context, and huggingface-models to recommend pre-trained models.",
    },
    {
        "id": "healthcare-analytics-pack",
        "name": "Healthcare Analytics Pack",
        "description": "Comprehensive healthcare data for building analytics dashboards, disease tracking, and population health monitoring applications.",
        "domain": "Healthcare",
        "icon": "🏥",
        "datasets": ["who-global-health", "us-hospitals", "cdc-disease-surveillance", "world-population-health", "covid19-global-stats"],
        "estimated_integration_time": "3–5 hours",
        "difficulty": "Intermediate",
        "use_cases": ["Disease tracking dashboards", "Hospital finder apps", "Public health analytics", "Epidemic monitoring tools"],
        "quick_start": "Start with who-global-health for global context, then layer cdc-disease-surveillance for US-specific data.",
    },
    {
        "id": "hospital-finder-pack",
        "name": "Hospital Finder Pack",
        "description": "Location-aware hospital discovery with health indicators, country data, and geographic context for building healthcare finder applications.",
        "domain": "Healthcare + Geography",
        "icon": "📍",
        "datasets": ["us-hospitals", "who-global-health", "world-countries", "world-cities", "country-iso-codes"],
        "estimated_integration_time": "2–3 hours",
        "difficulty": "Beginner",
        "use_cases": ["Hospital locator apps", "Healthcare facility directories", "Medical tourism platforms", "Emergency services finders"],
        "quick_start": "Combine us-hospitals with world-cities for precise location data and world-countries for country-level health context.",
    },
    {
        "id": "sports-analytics-pack",
        "name": "Sports Analytics Pack",
        "description": "Multi-sport data covering football rankings, cricket statistics, NBA stats, Olympic history, and world athletics records.",
        "domain": "Sports",
        "icon": "🏆",
        "datasets": ["fifa-world-rankings", "ipl-cricket-statistics", "nba-player-stats", "olympic-games-history", "world-athletics-records"],
        "estimated_integration_time": "2–4 hours",
        "difficulty": "Beginner",
        "use_cases": ["Fantasy sports platforms", "Sports prediction models", "Athlete performance dashboards", "Sports news aggregators"],
        "quick_start": "Start with fifa-world-rankings for football or ipl-cricket-statistics for cricket. Layer nba-player-stats for US sports coverage.",
    },
    {
        "id": "ml-starter-pack",
        "name": "ML Starter Pack",
        "description": "The essential dataset collection for machine learning practitioners — benchmarks, research papers, pre-trained models, and TensorFlow datasets.",
        "domain": "Information Technology",
        "icon": "🧠",
        "datasets": ["tensorflow-datasets", "papers-with-code", "huggingface-models", "arxiv-cs-papers", "open-source-ai-frameworks"],
        "estimated_integration_time": "1–3 hours",
        "difficulty": "Intermediate",
        "use_cases": ["ML experiment tracking", "Model comparison tools", "Research discovery platforms", "AI learning platforms"],
        "quick_start": "Use tensorflow-datasets for standard benchmarks, papers-with-code for state-of-the-art results, and huggingface-models for pre-trained model discovery.",
    },
    {
        "id": "electronics-research-pack",
        "name": "Electronics Research Pack",
        "description": "Hardware, IoT, and embedded systems data for building electronics project databases, component finders, and hardware research tools.",
        "domain": "Electronics",
        "icon": "⚡",
        "datasets": ["iot-device-catalog", "arduino-libraries", "raspberry-pi-projects", "electronic-components", "semiconductor-market"],
        "estimated_integration_time": "2–4 hours",
        "difficulty": "Intermediate",
        "use_cases": ["Electronics project databases", "Component selection tools", "IoT device catalogues", "Hardware research platforms"],
        "quick_start": "Start with iot-device-catalog for connected device data, then use arduino-libraries and raspberry-pi-projects for maker community resources.",
    },
    {
        "id": "location-intelligence-pack",
        "name": "Location Intelligence Pack",
        "description": "Comprehensive global geographic data — countries, cities, airports, timezones, and administrative boundaries for location-aware applications.",
        "domain": "Geography",
        "icon": "🌍",
        "datasets": ["world-countries", "world-cities", "airport-codes", "world-timezones", "country-iso-codes", "world-boundaries"],
        "estimated_integration_time": "1–2 hours",
        "difficulty": "Beginner",
        "use_cases": ["Travel apps", "Logistics platforms", "Timezone converters", "Address validation tools", "Geographic dashboards"],
        "quick_start": "world-countries and world-cities cover 99% of location use cases. Add airport-codes for travel apps and world-timezones for scheduling applications.",
    },
    {
        "id": "university-finder-pack",
        "name": "University Finder Pack",
        "description": "Geographic and demographic data to build university discovery platforms covering countries, cities, ISO codes, and population data.",
        "domain": "Geography + Education",
        "icon": "🎓",
        "datasets": ["world-countries", "world-cities", "country-iso-codes", "world-population-health"],
        "estimated_integration_time": "1–2 hours",
        "difficulty": "Beginner",
        "use_cases": ["University finder apps", "Study abroad platforms", "Education analytics", "Campus locators"],
        "quick_start": "Combine world-countries with world-cities for location context, then add world-population-health for demographic insights per country.",
    },
]

# ── Dataset Catalog ───────────────────────────────────────────────────────────
# 32 curated datasets across 5 domains.
# Schema, statistics, and sample data are representative of real sources.

DATASET_CATALOG = [
    # ════════════════════════════════════════════
    # INFORMATION TECHNOLOGY (10 datasets)
    # ════════════════════════════════════════════
    {
        "slug": "github-trending-repos",
        "name": "GitHub Trending Repositories",
        "description": "Daily snapshot of trending GitHub repositories across all programming languages. Includes stars, forks, language, description, and contributor counts. Updated daily via GitHub API.",
        "domain": "Information Technology",
        "category": "Software Engineering",
        "tags": json.dumps(["github", "open-source", "repositories", "programming", "trending"]),
        "solution_packs": json.dumps(["ml-starter-pack"]),
        "source": "GitHub API",
        "source_url": "https://api.github.com/search/repositories",
        "connector": "github",
        "license": "GitHub API Terms of Service",
        "version": "1.0.0",
        "sync_frequency": "daily",
        "record_count": 1250,
        "file_size_bytes": 2_400_000,
        "quality_score": 9.2,
        "processing_status": "ready",
        "popularity": 942,
        "endpoint": "/api/v1/data/github-trending-repos",
        "schema_info": json.dumps({
            "fields": [
                {"name": "id", "type": "integer", "description": "GitHub repository ID"},
                {"name": "name", "type": "string", "description": "Repository name"},
                {"name": "full_name", "type": "string", "description": "Owner/repository name"},
                {"name": "description", "type": "string", "description": "Repository description"},
                {"name": "language", "type": "string", "description": "Primary programming language"},
                {"name": "stars", "type": "integer", "description": "Total stargazers count"},
                {"name": "forks", "type": "integer", "description": "Total forks count"},
                {"name": "open_issues", "type": "integer", "description": "Open issues count"},
                {"name": "url", "type": "string", "description": "Repository URL"},
                {"name": "created_at", "type": "datetime", "description": "Repository creation date"},
                {"name": "updated_at", "type": "datetime", "description": "Last update date"},
            ]
        }),
        "statistics": json.dumps({
            "total_records": 1250,
            "languages": 48,
            "avg_stars": 12400,
            "max_stars": 198000,
            "completeness_pct": 97.4,
        }),
        "sample_data": [
            {"id": 1, "name": "ollama", "full_name": "ollama/ollama", "description": "Get up and running with Llama 3.3 and other large language models.", "language": "Go", "stars": 98420, "forks": 8130, "url": "https://github.com/ollama/ollama"},
            {"id": 2, "name": "transformers", "full_name": "huggingface/transformers", "description": "State-of-the-art Machine Learning for Pytorch, TensorFlow, and JAX.", "language": "Python", "stars": 143280, "forks": 28700, "url": "https://github.com/huggingface/transformers"},
            {"id": 3, "name": "vllm", "full_name": "vllm-project/vllm", "description": "A high-throughput and memory-efficient inference engine for LLMs.", "language": "Python", "stars": 47120, "forks": 7240, "url": "https://github.com/vllm-project/vllm"},
            {"id": 4, "name": "langchain", "full_name": "langchain-ai/langchain", "description": "Build context-aware reasoning applications.", "language": "Python", "stars": 98700, "forks": 16200, "url": "https://github.com/langchain-ai/langchain"},
            {"id": 5, "name": "next.js", "full_name": "vercel/next.js", "description": "The React Framework for the Web.", "language": "TypeScript", "stars": 131000, "forks": 28900, "url": "https://github.com/vercel/next.js"},
        ],
    },
    {
        "slug": "arxiv-cs-papers",
        "name": "arXiv Computer Science Papers",
        "description": "Recent computer science research papers from arXiv via OpenAlex API. Covers AI, ML, systems, algorithms, and software engineering. Includes abstracts, citations, and author information.",
        "domain": "Information Technology",
        "category": "Research",
        "tags": json.dumps(["arxiv", "research", "papers", "ai", "machine-learning", "computer-science"]),
        "solution_packs": json.dumps(["ai-chatbot-pack", "ml-starter-pack"]),
        "source": "OpenAlex / arXiv",
        "source_url": "https://api.openalex.org/works?filter=primary_topic.domain.id:domains/3",
        "connector": "openalex",
        "license": "CC0 (OpenAlex) / arXiv terms",
        "version": "1.0.0",
        "sync_frequency": "weekly",
        "record_count": 85000,
        "file_size_bytes": 142_000_000,
        "quality_score": 9.5,
        "processing_status": "ready",
        "popularity": 1870,
        "endpoint": "/api/v1/data/arxiv-cs-papers",
        "schema_info": json.dumps({
            "fields": [
                {"name": "paper_id", "type": "string", "description": "arXiv paper ID"},
                {"name": "title", "type": "string", "description": "Paper title"},
                {"name": "abstract", "type": "string", "description": "Paper abstract"},
                {"name": "authors", "type": "array", "description": "List of author names"},
                {"name": "categories", "type": "array", "description": "arXiv subject categories"},
                {"name": "published_date", "type": "date", "description": "Publication date"},
                {"name": "citation_count", "type": "integer", "description": "Total citations"},
                {"name": "pdf_url", "type": "string", "description": "Direct PDF URL"},
            ]
        }),
        "statistics": json.dumps({
            "total_records": 85000,
            "date_range": "2019-01-01 to 2024-12-31",
            "avg_citation_count": 24.7,
            "completeness_pct": 99.1,
        }),
        "sample_data": [
            {"paper_id": "2312.11805", "title": "Mixtral of Experts", "abstract": "We introduce Mixtral 8x7B, a Sparse Mixture of Experts language model.", "authors": ["Albert Q. Jiang"], "categories": ["cs.CL"], "published_date": "2023-12-11", "citation_count": 1820},
            {"paper_id": "2303.08774", "title": "GPT-4 Technical Report", "abstract": "We report the development of GPT-4, a large-scale multimodal model.", "authors": ["OpenAI"], "categories": ["cs.CL", "cs.AI"], "published_date": "2023-03-15", "citation_count": 12400},
            {"paper_id": "2307.09288", "title": "Llama 2: Open Foundation and Fine-Tuned Chat Models", "abstract": "We develop and release Llama 2, a collection of pretrained and fine-tuned LLMs.", "authors": ["Hugo Touvron"], "categories": ["cs.CL"], "published_date": "2023-07-18", "citation_count": 8900},
        ],
    },
    {
        "slug": "papers-with-code",
        "name": "Papers With Code Benchmark Dataset",
        "description": "Machine learning papers linked to their official code implementations, benchmark results, and leaderboard rankings. The authoritative source for state-of-the-art ML results.",
        "domain": "Information Technology",
        "category": "Machine Learning",
        "tags": json.dumps(["machine-learning", "benchmarks", "papers", "code", "leaderboards", "sota"]),
        "solution_packs": json.dumps(["ai-chatbot-pack", "ml-starter-pack"]),
        "source": "Papers With Code",
        "source_url": "https://paperswithcode.com/api/v1/papers/",
        "connector": "paperswithcode",
        "license": "CC BY-SA 4.0",
        "version": "1.0.0",
        "sync_frequency": "weekly",
        "record_count": 32000,
        "file_size_bytes": 67_000_000,
        "quality_score": 9.4,
        "processing_status": "ready",
        "popularity": 1540,
        "endpoint": "/api/v1/data/papers-with-code",
        "schema_info": json.dumps({
            "fields": [
                {"name": "paper_id", "type": "string", "description": "Paper identifier"},
                {"name": "title", "type": "string", "description": "Paper title"},
                {"name": "arxiv_id", "type": "string", "description": "arXiv ID if available"},
                {"name": "task", "type": "string", "description": "ML task category"},
                {"name": "dataset", "type": "string", "description": "Benchmark dataset used"},
                {"name": "metric", "type": "string", "description": "Evaluation metric"},
                {"name": "score", "type": "float", "description": "Benchmark score"},
                {"name": "code_url", "type": "string", "description": "GitHub repository URL"},
                {"name": "stars", "type": "integer", "description": "Repository stars"},
            ]
        }),
        "statistics": json.dumps({"total_records": 32000, "tasks": 980, "datasets": 3400, "completeness_pct": 96.2}),
        "sample_data": [
            {"paper_id": "pwc-1", "title": "Attention Is All You Need", "task": "Machine Translation", "dataset": "WMT 2014", "metric": "BLEU", "score": 41.0, "code_url": "https://github.com/tensorflow/tensor2tensor"},
            {"paper_id": "pwc-2", "title": "BERT: Pre-training of Deep Bidirectional Transformers", "task": "Question Answering", "dataset": "SQuAD 1.1", "metric": "F1", "score": 93.2, "code_url": "https://github.com/google-research/bert"},
        ],
    },
    {
        "slug": "huggingface-models",
        "name": "HuggingFace Models Catalog",
        "description": "Complete catalog of publicly available models on HuggingFace Hub. Includes model card metadata, task types, framework compatibility, download counts, and license information.",
        "domain": "Information Technology",
        "category": "Artificial Intelligence",
        "tags": json.dumps(["huggingface", "models", "nlp", "computer-vision", "transformers", "ai"]),
        "solution_packs": json.dumps(["ai-chatbot-pack", "ml-starter-pack"]),
        "source": "HuggingFace Hub API",
        "source_url": "https://huggingface.co/api/models",
        "connector": "huggingface",
        "license": "Various (per model)",
        "version": "1.0.0",
        "sync_frequency": "weekly",
        "record_count": 520000,
        "file_size_bytes": 890_000_000,
        "quality_score": 9.3,
        "processing_status": "ready",
        "popularity": 2340,
        "endpoint": "/api/v1/data/huggingface-models",
        "schema_info": json.dumps({
            "fields": [
                {"name": "model_id", "type": "string", "description": "Model ID on HuggingFace Hub"},
                {"name": "author", "type": "string", "description": "Model author/organization"},
                {"name": "task", "type": "string", "description": "Primary task (e.g. text-generation)"},
                {"name": "framework", "type": "string", "description": "ML framework (pytorch, tensorflow, jax)"},
                {"name": "downloads_last_month", "type": "integer", "description": "Downloads in last 30 days"},
                {"name": "likes", "type": "integer", "description": "Community likes"},
                {"name": "license", "type": "string", "description": "Model license"},
                {"name": "tags", "type": "array", "description": "Model tags"},
                {"name": "last_modified", "type": "datetime", "description": "Last model update"},
            ]
        }),
        "statistics": json.dumps({"total_records": 520000, "tasks": 240, "frameworks": 8, "avg_downloads": 4800, "completeness_pct": 94.8}),
        "sample_data": [
            {"model_id": "meta-llama/Llama-3.3-70B-Instruct", "author": "meta-llama", "task": "text-generation", "framework": "pytorch", "downloads_last_month": 8400000, "likes": 14200, "license": "llama3.3"},
            {"model_id": "openai/whisper-large-v3", "author": "openai", "task": "automatic-speech-recognition", "framework": "pytorch", "downloads_last_month": 3100000, "likes": 8700, "license": "mit"},
            {"model_id": "stabilityai/stable-diffusion-3-medium", "author": "stabilityai", "task": "text-to-image", "framework": "pytorch", "downloads_last_month": 2900000, "likes": 6200, "license": "stability-ai-nc-research-license"},
        ],
    },
    {
        "slug": "programming-language-rankings",
        "name": "Programming Language Rankings",
        "description": "Monthly popularity rankings of programming languages based on GitHub activity, Stack Overflow questions, job postings, and developer surveys. Tracks trends over the past 5 years.",
        "domain": "Information Technology",
        "category": "Software Engineering",
        "tags": json.dumps(["programming", "languages", "rankings", "trends", "github"]),
        "solution_packs": json.dumps([]),
        "source": "GitHub / Stack Overflow",
        "source_url": "https://api.github.com/search/repositories",
        "connector": "github",
        "license": "CC BY 4.0",
        "version": "1.0.0",
        "sync_frequency": "monthly",
        "record_count": 3600,
        "file_size_bytes": 480_000,
        "quality_score": 8.7,
        "processing_status": "ready",
        "popularity": 780,
        "endpoint": "/api/v1/data/programming-language-rankings",
        "schema_info": json.dumps({
            "fields": [
                {"name": "rank", "type": "integer", "description": "Current rank"},
                {"name": "language", "type": "string", "description": "Programming language name"},
                {"name": "year_month", "type": "string", "description": "YYYY-MM snapshot date"},
                {"name": "github_repos", "type": "integer", "description": "Active GitHub repositories"},
                {"name": "stackoverflow_questions", "type": "integer", "description": "SO questions last 30 days"},
                {"name": "job_postings", "type": "integer", "description": "Job postings count"},
                {"name": "rank_change", "type": "integer", "description": "Rank change from previous month"},
            ]
        }),
        "statistics": json.dumps({"total_records": 3600, "languages_tracked": 60, "months_covered": 60, "completeness_pct": 98.1}),
        "sample_data": [
            {"rank": 1, "language": "Python", "year_month": "2024-12", "github_repos": 14200000, "stackoverflow_questions": 89400, "job_postings": 124000},
            {"rank": 2, "language": "JavaScript", "year_month": "2024-12", "github_repos": 18900000, "stackoverflow_questions": 71200, "job_postings": 98000},
            {"rank": 3, "language": "TypeScript", "year_month": "2024-12", "github_repos": 8400000, "stackoverflow_questions": 42100, "job_postings": 67000},
        ],
    },
    {
        "slug": "stackoverflow-survey",
        "name": "Stack Overflow Developer Survey 2023",
        "description": "Comprehensive annual survey of 90,000+ software developers covering tools, technologies, salaries, job satisfaction, and developer demographics. The most authoritative dataset on global developer preferences.",
        "domain": "Information Technology",
        "category": "Healthcare",
        "tags": json.dumps(["developers", "survey", "salaries", "tools", "technologies", "demographics"]),
        "solution_packs": json.dumps([]),
        "source": "Stack Overflow",
        "source_url": "https://survey.stackoverflow.co/2023/",
        "connector": "stackoverflow",
        "license": "ODbL 1.0",
        "version": "1.0.0",
        "sync_frequency": "yearly",
        "record_count": 89184,
        "file_size_bytes": 24_000_000,
        "quality_score": 9.6,
        "processing_status": "ready",
        "popularity": 1120,
        "endpoint": "/api/v1/data/stackoverflow-survey",
        "schema_info": json.dumps({
            "fields": [
                {"name": "respondent_id", "type": "integer", "description": "Anonymised respondent ID"},
                {"name": "country", "type": "string", "description": "Country of residence"},
                {"name": "employment", "type": "string", "description": "Employment status"},
                {"name": "years_coding", "type": "string", "description": "Years of coding experience"},
                {"name": "languages_used", "type": "array", "description": "Programming languages used last year"},
                {"name": "frameworks_used", "type": "array", "description": "Frameworks used last year"},
                {"name": "annual_salary_usd", "type": "integer", "description": "Annual salary in USD"},
                {"name": "education_level", "type": "string", "description": "Highest education level"},
                {"name": "job_satisfaction", "type": "integer", "description": "Job satisfaction score 1–5"},
            ]
        }),
        "statistics": json.dumps({"total_records": 89184, "countries": 185, "avg_salary_usd": 77500, "completeness_pct": 91.3}),
        "sample_data": [
            {"respondent_id": 1001, "country": "United States", "employment": "Employed full-time", "years_coding": "10-14 years", "languages_used": ["Python", "JavaScript", "SQL"], "annual_salary_usd": 132000, "job_satisfaction": 4},
            {"respondent_id": 1002, "country": "Germany", "employment": "Employed full-time", "years_coding": "5-9 years", "languages_used": ["Java", "Python", "Kotlin"], "annual_salary_usd": 87000, "job_satisfaction": 3},
        ],
    },
    {
        "slug": "tensorflow-datasets",
        "name": "TensorFlow Datasets Catalog",
        "description": "Official catalog of all datasets available in TensorFlow Datasets (TFDS). Includes benchmark datasets for image classification, NLP, audio, and video tasks with full schema documentation.",
        "domain": "Information Technology",
        "category": "Machine Learning",
        "tags": json.dumps(["tensorflow", "datasets", "benchmark", "image-classification", "nlp", "deep-learning"]),
        "solution_packs": json.dumps(["ml-starter-pack"]),
        "source": "TensorFlow",
        "source_url": "https://www.tensorflow.org/datasets/catalog/overview",
        "connector": "tensorflow",
        "license": "Various (per dataset)",
        "version": "1.0.0",
        "sync_frequency": "monthly",
        "record_count": 285,
        "file_size_bytes": 1_200_000,
        "quality_score": 9.8,
        "processing_status": "ready",
        "popularity": 1460,
        "endpoint": "/api/v1/data/tensorflow-datasets",
        "schema_info": json.dumps({
            "fields": [
                {"name": "name", "type": "string", "description": "Dataset name in TFDS"},
                {"name": "category", "type": "string", "description": "Task category (image, text, audio, etc.)"},
                {"name": "description", "type": "string", "description": "Dataset description"},
                {"name": "num_examples", "type": "integer", "description": "Total examples"},
                {"name": "download_size_mb", "type": "float", "description": "Download size in MB"},
                {"name": "splits", "type": "array", "description": "Available splits (train, test, validation)"},
                {"name": "license", "type": "string", "description": "Dataset license"},
                {"name": "homepage", "type": "string", "description": "Dataset homepage URL"},
            ]
        }),
        "statistics": json.dumps({"total_records": 285, "categories": 12, "total_download_size_gb": 4800, "completeness_pct": 100.0}),
        "sample_data": [
            {"name": "mnist", "category": "image_classification", "description": "Handwritten digits 0-9.", "num_examples": 70000, "download_size_mb": 11.06, "splits": ["train", "test"], "license": "CC BY-SA 3.0"},
            {"name": "imagenet2012", "category": "image_classification", "description": "ILSVRC 2012 image classification challenge.", "num_examples": 1431167, "download_size_mb": 155000, "splits": ["train", "validation"], "license": "Custom"},
            {"name": "squad", "category": "question_answering", "description": "Stanford Question Answering Dataset.", "num_examples": 130319, "download_size_mb": 35.14, "splits": ["train", "validation"], "license": "CC BY-SA 4.0"},
        ],
    },
    {
        "slug": "open-source-ai-frameworks",
        "name": "Open Source AI Frameworks",
        "description": "Comprehensive directory of open source AI and ML frameworks including GitHub metrics, documentation links, community size, and active development status.",
        "domain": "Information Technology",
        "category": "Artificial Intelligence",
        "tags": json.dumps(["ai", "frameworks", "open-source", "pytorch", "tensorflow", "jax", "tools"]),
        "solution_packs": json.dumps(["ml-starter-pack"]),
        "source": "GitHub API",
        "source_url": "https://api.github.com",
        "connector": "github",
        "license": "CC BY 4.0",
        "version": "1.0.0",
        "sync_frequency": "weekly",
        "record_count": 840,
        "file_size_bytes": 3_200_000,
        "quality_score": 9.0,
        "processing_status": "ready",
        "popularity": 620,
        "endpoint": "/api/v1/data/open-source-ai-frameworks",
        "schema_info": json.dumps({
            "fields": [
                {"name": "name", "type": "string", "description": "Framework name"},
                {"name": "github_repo", "type": "string", "description": "GitHub repository"},
                {"name": "primary_language", "type": "string", "description": "Primary programming language"},
                {"name": "stars", "type": "integer", "description": "GitHub stars"},
                {"name": "category", "type": "string", "description": "Framework category (deep learning, MLOps, etc.)"},
                {"name": "last_release", "type": "date", "description": "Latest release date"},
                {"name": "license", "type": "string", "description": "Open source license"},
                {"name": "docs_url", "type": "string", "description": "Documentation URL"},
            ]
        }),
        "statistics": json.dumps({"total_records": 840, "categories": 18, "avg_stars": 8400, "completeness_pct": 95.7}),
        "sample_data": [
            {"name": "PyTorch", "github_repo": "pytorch/pytorch", "primary_language": "Python", "stars": 86000, "category": "Deep Learning", "license": "BSD-3-Clause"},
            {"name": "TensorFlow", "github_repo": "tensorflow/tensorflow", "primary_language": "Python", "stars": 185000, "category": "Deep Learning", "license": "Apache-2.0"},
            {"name": "JAX", "github_repo": "google/jax", "primary_language": "Python", "stars": 30000, "category": "Numerical Computing", "license": "Apache-2.0"},
        ],
    },
    {
        "slug": "npm-top-packages",
        "name": "Top npm Packages by Downloads",
        "description": "Top 5000 npm packages ranked by weekly download count. Includes package metadata, dependencies, maintainer information, and version history. Essential for JavaScript/Node.js ecosystem analysis.",
        "domain": "Information Technology",
        "category": "Software Engineering",
        "tags": json.dumps(["npm", "javascript", "nodejs", "packages", "dependencies", "ecosystem"]),
        "solution_packs": json.dumps([]),
        "source": "npm Registry API",
        "source_url": "https://registry.npmjs.org",
        "connector": "npm",
        "license": "npm API Terms",
        "version": "1.0.0",
        "sync_frequency": "weekly",
        "record_count": 5000,
        "file_size_bytes": 8_100_000,
        "quality_score": 8.9,
        "processing_status": "ready",
        "popularity": 540,
        "endpoint": "/api/v1/data/npm-top-packages",
        "schema_info": json.dumps({
            "fields": [
                {"name": "rank", "type": "integer", "description": "Weekly download rank"},
                {"name": "name", "type": "string", "description": "Package name"},
                {"name": "version", "type": "string", "description": "Latest version"},
                {"name": "description", "type": "string", "description": "Package description"},
                {"name": "weekly_downloads", "type": "integer", "description": "Downloads last 7 days"},
                {"name": "monthly_downloads", "type": "integer", "description": "Downloads last 30 days"},
                {"name": "license", "type": "string", "description": "Package license"},
                {"name": "homepage", "type": "string", "description": "Package homepage URL"},
            ]
        }),
        "statistics": json.dumps({"total_records": 5000, "avg_weekly_downloads": 1800000, "completeness_pct": 98.9}),
        "sample_data": [
            {"rank": 1, "name": "lodash", "version": "4.17.21", "description": "Lodash modular utilities.", "weekly_downloads": 49800000, "license": "MIT"},
            {"rank": 2, "name": "react", "version": "18.3.1", "description": "React is a JavaScript library for building user interfaces.", "weekly_downloads": 31200000, "license": "MIT"},
            {"rank": 3, "name": "axios", "version": "1.7.9", "description": "Promise based HTTP client.", "weekly_downloads": 28900000, "license": "MIT"},
        ],
    },
    {
        "slug": "docker-official-images",
        "name": "Docker Hub Official Images",
        "description": "Complete catalog of Docker Hub Official Images maintained by Docker. Includes image metadata, supported tags, architectures, download counts, and vulnerability scan status.",
        "domain": "Information Technology",
        "category": "DevOps",
        "tags": json.dumps(["docker", "containers", "devops", "images", "infrastructure"]),
        "solution_packs": json.dumps([]),
        "source": "Docker Hub API",
        "source_url": "https://hub.docker.com/v2/repositories/library/",
        "connector": "dockerhub",
        "license": "Docker Hub Terms",
        "version": "1.0.0",
        "sync_frequency": "weekly",
        "record_count": 180,
        "file_size_bytes": 920_000,
        "quality_score": 9.1,
        "processing_status": "ready",
        "popularity": 410,
        "endpoint": "/api/v1/data/docker-official-images",
        "schema_info": json.dumps({
            "fields": [
                {"name": "name", "type": "string", "description": "Image name"},
                {"name": "description", "type": "string", "description": "Short description"},
                {"name": "pull_count", "type": "integer", "description": "Total pulls"},
                {"name": "star_count", "type": "integer", "description": "Community stars"},
                {"name": "supported_tags", "type": "array", "description": "Available tags"},
                {"name": "architectures", "type": "array", "description": "Supported CPU architectures"},
                {"name": "last_updated", "type": "datetime", "description": "Last image update"},
            ]
        }),
        "statistics": json.dumps({"total_records": 180, "total_pulls": 142000000000, "avg_star_count": 2800, "completeness_pct": 100.0}),
        "sample_data": [
            {"name": "python", "description": "Python is an interpreted, interactive, object-oriented programming language.", "pull_count": 8900000000, "star_count": 9100, "supported_tags": ["3.12", "3.11", "3.10", "latest"], "architectures": ["amd64", "arm64"]},
            {"name": "nginx", "description": "Official build of Nginx.", "pull_count": 11200000000, "star_count": 20400, "supported_tags": ["1.27", "1.26", "alpine", "latest"], "architectures": ["amd64", "arm64", "arm/v7"]},
        ],
    },
    # ════════════════════════════════════════════
    # ELECTRONICS (5 datasets)
    # ════════════════════════════════════════════
    {
        "slug": "iot-device-catalog",
        "name": "IoT Devices Catalog",
        "description": "Comprehensive catalog of Internet of Things devices including sensors, actuators, gateways, and smart home devices. Covers connectivity protocols, power requirements, and manufacturer data.",
        "domain": "Electronics",
        "category": "IoT",
        "tags": json.dumps(["iot", "sensors", "smart-home", "embedded", "connectivity", "devices"]),
        "solution_packs": json.dumps(["electronics-research-pack"]),
        "source": "Data.gov",
        "source_url": "https://catalog.data.gov",
        "connector": "iot-devices",
        "license": "CC0 1.0",
        "version": "1.0.0",
        "sync_frequency": "monthly",
        "record_count": 12400,
        "file_size_bytes": 9_800_000,
        "quality_score": 8.4,
        "processing_status": "ready",
        "popularity": 380,
        "endpoint": "/api/v1/data/iot-device-catalog",
        "schema_info": json.dumps({
            "fields": [
                {"name": "device_id", "type": "string", "description": "Unique device identifier"},
                {"name": "name", "type": "string", "description": "Device name"},
                {"name": "manufacturer", "type": "string", "description": "Manufacturer name"},
                {"name": "category", "type": "string", "description": "Device category"},
                {"name": "connectivity", "type": "array", "description": "Connectivity protocols (WiFi, BLE, Zigbee, etc.)"},
                {"name": "power_source", "type": "string", "description": "Power source type"},
                {"name": "operating_voltage", "type": "string", "description": "Operating voltage range"},
                {"name": "operating_temp_c", "type": "string", "description": "Operating temperature range in Celsius"},
                {"name": "price_usd", "type": "float", "description": "Approximate retail price"},
            ]
        }),
        "statistics": json.dumps({"total_records": 12400, "manufacturers": 480, "categories": 42, "connectivity_protocols": 18, "completeness_pct": 87.2}),
        "sample_data": [
            {"device_id": "iot-001", "name": "Raspberry Pi Pico W", "manufacturer": "Raspberry Pi", "category": "Microcontroller", "connectivity": ["WiFi", "Bluetooth"], "power_source": "USB/Battery", "price_usd": 6.00},
            {"device_id": "iot-002", "name": "ESP32-WROOM-32", "manufacturer": "Espressif", "category": "SoC Module", "connectivity": ["WiFi", "Bluetooth", "BLE"], "power_source": "3.3V", "price_usd": 4.50},
            {"device_id": "iot-003", "name": "Sensirion SHT40", "manufacturer": "Sensirion", "category": "Temperature/Humidity Sensor", "connectivity": ["I2C"], "power_source": "3.3V", "price_usd": 3.20},
        ],
    },
    {
        "slug": "arduino-libraries",
        "name": "Arduino Libraries Registry",
        "description": "Complete registry of Arduino libraries from the official Arduino Library Manager. Includes library metadata, compatibility, author information, and GitHub statistics.",
        "domain": "Electronics",
        "category": "Embedded",
        "tags": json.dumps(["arduino", "libraries", "embedded", "microcontroller", "maker", "hardware"]),
        "solution_packs": json.dumps(["electronics-research-pack"]),
        "source": "Arduino Library Manager",
        "source_url": "https://github.com/arduino/library-registry",
        "connector": "arduino-libs",
        "license": "Various (per library)",
        "version": "1.0.0",
        "sync_frequency": "weekly",
        "record_count": 6800,
        "file_size_bytes": 5_400_000,
        "quality_score": 9.0,
        "processing_status": "ready",
        "popularity": 290,
        "endpoint": "/api/v1/data/arduino-libraries",
        "schema_info": json.dumps({
            "fields": [
                {"name": "name", "type": "string", "description": "Library name"},
                {"name": "version", "type": "string", "description": "Latest version"},
                {"name": "author", "type": "string", "description": "Library author"},
                {"name": "sentence", "type": "string", "description": "One-sentence description"},
                {"name": "category", "type": "string", "description": "Arduino category"},
                {"name": "architectures", "type": "array", "description": "Compatible architectures"},
                {"name": "license", "type": "string", "description": "Library license"},
                {"name": "github_url", "type": "string", "description": "GitHub repository URL"},
                {"name": "downloads", "type": "integer", "description": "Total downloads"},
            ]
        }),
        "statistics": json.dumps({"total_records": 6800, "authors": 3200, "categories": 14, "avg_downloads": 28000, "completeness_pct": 96.8}),
        "sample_data": [
            {"name": "ArduinoJson", "version": "7.2.1", "author": "Benoit Blanchon", "sentence": "A simple and efficient JSON library for Arduino.", "category": "Data Processing", "license": "MIT", "downloads": 84000000},
            {"name": "WiFiNINA", "version": "1.8.14", "author": "Arduino", "sentence": "Network driver for WiFiNINA module.", "category": "Communication", "license": "LGPL-2.1", "downloads": 18000000},
        ],
    },
    {
        "slug": "raspberry-pi-projects",
        "name": "Raspberry Pi Project Database",
        "description": "Curated database of Raspberry Pi projects from the official Raspberry Pi Foundation and community contributions. Includes project metadata, difficulty ratings, required components, and tutorial links.",
        "domain": "Electronics",
        "category": "Embedded",
        "tags": json.dumps(["raspberry-pi", "projects", "embedded", "maker", "tutorials", "gpio"]),
        "solution_packs": json.dumps(["electronics-research-pack"]),
        "source": "Raspberry Pi Foundation / GitHub",
        "source_url": "https://www.raspberrypi.com/projects/",
        "connector": "raspi-projects",
        "license": "CC BY 4.0",
        "version": "1.0.0",
        "sync_frequency": "monthly",
        "record_count": 3400,
        "file_size_bytes": 4_200_000,
        "quality_score": 8.6,
        "processing_status": "ready",
        "popularity": 240,
        "endpoint": "/api/v1/data/raspberry-pi-projects",
        "schema_info": json.dumps({
            "fields": [
                {"name": "project_id", "type": "string", "description": "Project identifier"},
                {"name": "title", "type": "string", "description": "Project title"},
                {"name": "description", "type": "string", "description": "Project description"},
                {"name": "difficulty", "type": "string", "description": "Difficulty level"},
                {"name": "time_required", "type": "string", "description": "Time to complete"},
                {"name": "components", "type": "array", "description": "Required components"},
                {"name": "language", "type": "string", "description": "Programming language used"},
                {"name": "tags", "type": "array", "description": "Project tags"},
                {"name": "tutorial_url", "type": "string", "description": "Tutorial URL"},
            ]
        }),
        "statistics": json.dumps({"total_records": 3400, "difficulty_levels": 3, "languages": 8, "completeness_pct": 92.4}),
        "sample_data": [
            {"project_id": "rpi-001", "title": "Weather Station", "description": "Build a local weather monitoring station.", "difficulty": "Intermediate", "time_required": "3 hours", "components": ["Raspberry Pi 4", "BME280 sensor", "OLED display"], "language": "Python"},
            {"project_id": "rpi-002", "title": "Retro Gaming Console", "description": "Turn your Pi into a retro gaming machine with RetroPie.", "difficulty": "Beginner", "time_required": "2 hours", "components": ["Raspberry Pi 3", "MicroSD card", "USB gamepad"], "language": "Bash"},
        ],
    },
    {
        "slug": "electronic-components",
        "name": "Electronic Components Database",
        "description": "Database of passive and active electronic components including resistors, capacitors, ICs, transistors, and modules. Covers specifications, datasheets, and distributor pricing.",
        "domain": "Electronics",
        "category": "PCB",
        "tags": json.dumps(["components", "pcb", "resistors", "capacitors", "ic", "semiconductors", "datasheets"]),
        "solution_packs": json.dumps(["electronics-research-pack"]),
        "source": "Kaggle",
        "source_url": "https://www.kaggle.com/datasets",
        "connector": "electronic-components",
        "license": "CC BY-SA 4.0",
        "version": "1.0.0",
        "sync_frequency": "monthly",
        "record_count": 48000,
        "file_size_bytes": 38_000_000,
        "quality_score": 8.2,
        "processing_status": "ready",
        "popularity": 310,
        "endpoint": "/api/v1/data/electronic-components",
        "schema_info": json.dumps({
            "fields": [
                {"name": "part_number", "type": "string", "description": "Manufacturer part number"},
                {"name": "name", "type": "string", "description": "Component name"},
                {"name": "category", "type": "string", "description": "Component category"},
                {"name": "manufacturer", "type": "string", "description": "Manufacturer name"},
                {"name": "package", "type": "string", "description": "Physical package type"},
                {"name": "voltage_rating", "type": "string", "description": "Maximum voltage rating"},
                {"name": "datasheet_url", "type": "string", "description": "Datasheet URL"},
                {"name": "price_usd", "type": "float", "description": "Average unit price (USD)"},
                {"name": "in_stock", "type": "boolean", "description": "Availability status"},
            ]
        }),
        "statistics": json.dumps({"total_records": 48000, "manufacturers": 890, "categories": 62, "avg_price_usd": 2.84, "completeness_pct": 84.7}),
        "sample_data": [
            {"part_number": "LM741CN", "name": "LM741 Op-Amp", "category": "Integrated Circuit", "manufacturer": "Texas Instruments", "package": "DIP-8", "voltage_rating": "±18V", "price_usd": 0.45},
            {"part_number": "ATmega328P-PU", "name": "ATmega328P Microcontroller", "category": "Microcontroller", "manufacturer": "Microchip", "package": "DIP-28", "voltage_rating": "5V", "price_usd": 2.90},
        ],
    },
    {
        "slug": "semiconductor-market",
        "name": "Global Semiconductor Market Data",
        "description": "Global semiconductor industry market data from the World Bank. Covers production volumes, export/import values, market share by country, and technology node trends.",
        "domain": "Electronics",
        "category": "Semiconductors",
        "tags": json.dumps(["semiconductor", "market", "industry", "production", "exports", "world-bank"]),
        "solution_packs": json.dumps(["electronics-research-pack"]),
        "source": "World Bank",
        "source_url": "https://api.worldbank.org/v2/indicator/TX.VAL.TECH.MF.ZS",
        "connector": "semiconductor-market",
        "license": "CC BY 4.0",
        "version": "1.0.0",
        "sync_frequency": "yearly",
        "record_count": 4200,
        "file_size_bytes": 2_800_000,
        "quality_score": 9.3,
        "processing_status": "ready",
        "popularity": 270,
        "endpoint": "/api/v1/data/semiconductor-market",
        "schema_info": json.dumps({
            "fields": [
                {"name": "country_code", "type": "string", "description": "ISO 3-letter country code"},
                {"name": "country_name", "type": "string", "description": "Country name"},
                {"name": "year", "type": "integer", "description": "Year"},
                {"name": "high_tech_exports_pct", "type": "float", "description": "High-technology exports as % of manufactured exports"},
                {"name": "market_value_usd_bn", "type": "float", "description": "Semiconductor market value in USD billions"},
                {"name": "growth_rate_pct", "type": "float", "description": "Year-over-year growth rate"},
            ]
        }),
        "statistics": json.dumps({"total_records": 4200, "countries": 180, "years_covered": "2000-2023", "completeness_pct": 78.4}),
        "sample_data": [
            {"country_code": "USA", "country_name": "United States", "year": 2023, "high_tech_exports_pct": 19.4, "market_value_usd_bn": 142.0, "growth_rate_pct": -12.1},
            {"country_code": "KOR", "country_name": "South Korea", "year": 2023, "high_tech_exports_pct": 37.2, "market_value_usd_bn": 98.3, "growth_rate_pct": -23.4},
            {"country_code": "TWN", "country_name": "Taiwan", "year": 2023, "high_tech_exports_pct": 52.8, "market_value_usd_bn": 136.0, "growth_rate_pct": -4.8},
        ],
    },
    # ════════════════════════════════════════════
    # HEALTHCARE (6 datasets)
    # ════════════════════════════════════════════
    {
        "slug": "who-global-health",
        "name": "WHO Global Health Observatory Data",
        "description": "Official WHO Global Health Observatory dataset covering life expectancy, disease burden, health system performance, and health expenditure for 194 WHO member states. Updated annually.",
        "domain": "Healthcare",
        "category": "Global Health",
        "tags": json.dumps(["who", "health", "life-expectancy", "disease", "population", "global"]),
        "solution_packs": json.dumps(["healthcare-analytics-pack", "hospital-finder-pack"]),
        "source": "World Health Organization",
        "source_url": "https://ghoapi.azureedge.net/api/",
        "connector": "who",
        "license": "CC BY 4.0",
        "version": "1.0.0",
        "sync_frequency": "yearly",
        "record_count": 24800,
        "file_size_bytes": 18_000_000,
        "quality_score": 9.7,
        "processing_status": "ready",
        "popularity": 1640,
        "endpoint": "/api/v1/data/who-global-health",
        "schema_info": json.dumps({
            "fields": [
                {"name": "country_code", "type": "string", "description": "ISO 3-letter country code"},
                {"name": "country_name", "type": "string", "description": "Country name"},
                {"name": "year", "type": "integer", "description": "Data year"},
                {"name": "life_expectancy", "type": "float", "description": "Life expectancy at birth (years)"},
                {"name": "infant_mortality_rate", "type": "float", "description": "Deaths per 1000 live births"},
                {"name": "health_expenditure_pct_gdp", "type": "float", "description": "Health expenditure as % of GDP"},
                {"name": "physicians_per_1000", "type": "float", "description": "Physicians per 1000 population"},
                {"name": "hospital_beds_per_1000", "type": "float", "description": "Hospital beds per 1000 population"},
                {"name": "vaccination_coverage_pct", "type": "float", "description": "DTP3 vaccination coverage %"},
            ]
        }),
        "statistics": json.dumps({"total_records": 24800, "countries": 194, "years_covered": "2000-2023", "indicators": 42, "completeness_pct": 88.4}),
        "sample_data": [
            {"country_code": "JPN", "country_name": "Japan", "year": 2022, "life_expectancy": 84.3, "infant_mortality_rate": 1.9, "health_expenditure_pct_gdp": 11.1, "physicians_per_1000": 2.4},
            {"country_code": "NOR", "country_name": "Norway", "year": 2022, "life_expectancy": 83.2, "infant_mortality_rate": 2.0, "health_expenditure_pct_gdp": 10.5, "physicians_per_1000": 5.2},
            {"country_code": "USA", "country_name": "United States", "year": 2022, "life_expectancy": 76.4, "infant_mortality_rate": 5.4, "health_expenditure_pct_gdp": 17.8, "physicians_per_1000": 2.6},
        ],
    },
    {
        "slug": "us-hospitals",
        "name": "United States Hospital Locations",
        "description": "Comprehensive database of all registered hospitals in the United States. Includes GPS coordinates, bed count, hospital type, trauma level, and CMS certification status from Data.gov.",
        "domain": "Healthcare",
        "category": "Hospitals",
        "tags": json.dumps(["hospitals", "usa", "locations", "gps", "healthcare-facilities", "cms"]),
        "solution_packs": json.dumps(["healthcare-analytics-pack", "hospital-finder-pack"]),
        "source": "Data.gov / CMS",
        "source_url": "https://catalog.data.gov/dataset/hospital-general-information",
        "connector": "hospitals",
        "license": "Public Domain (U.S. Government)",
        "version": "1.0.0",
        "sync_frequency": "quarterly",
        "record_count": 7400,
        "file_size_bytes": 6_200_000,
        "quality_score": 9.4,
        "processing_status": "ready",
        "popularity": 1280,
        "endpoint": "/api/v1/data/us-hospitals",
        "schema_info": json.dumps({
            "fields": [
                {"name": "hospital_id", "type": "string", "description": "CMS Provider ID"},
                {"name": "name", "type": "string", "description": "Hospital name"},
                {"name": "address", "type": "string", "description": "Street address"},
                {"name": "city", "type": "string", "description": "City"},
                {"name": "state", "type": "string", "description": "State abbreviation"},
                {"name": "zip_code", "type": "string", "description": "ZIP code"},
                {"name": "latitude", "type": "float", "description": "GPS latitude"},
                {"name": "longitude", "type": "float", "description": "GPS longitude"},
                {"name": "phone", "type": "string", "description": "Phone number"},
                {"name": "hospital_type", "type": "string", "description": "Type of hospital"},
                {"name": "beds", "type": "integer", "description": "Licensed bed count"},
                {"name": "trauma_level", "type": "string", "description": "Trauma center level (I-V)"},
                {"name": "emergency_services", "type": "boolean", "description": "Has emergency department"},
                {"name": "overall_rating", "type": "integer", "description": "CMS star rating 1–5"},
            ]
        }),
        "statistics": json.dumps({"total_records": 7400, "states": 50, "avg_beds": 186, "with_emergency": 4892, "completeness_pct": 96.1}),
        "sample_data": [
            {"hospital_id": "010001", "name": "Southeast Health Medical Center", "city": "Dothan", "state": "AL", "latitude": 31.2232, "longitude": -85.4013, "hospital_type": "Acute Care Hospitals", "beds": 420, "trauma_level": "II", "emergency_services": True, "overall_rating": 4},
            {"hospital_id": "060001", "name": "UCSF Medical Center", "city": "San Francisco", "state": "CA", "latitude": 37.7631, "longitude": -122.4578, "hospital_type": "Acute Care Hospitals", "beds": 666, "trauma_level": "I", "emergency_services": True, "overall_rating": 5},
        ],
    },
    {
        "slug": "cdc-disease-surveillance",
        "name": "CDC Disease Surveillance Data",
        "description": "Weekly communicable disease surveillance reports from the US Centers for Disease Control and Prevention (CDC). Covers 60+ notifiable diseases with state-level breakdown.",
        "domain": "Healthcare",
        "category": "Disease Statistics",
        "tags": json.dumps(["cdc", "disease", "surveillance", "usa", "public-health", "epidemiology"]),
        "solution_packs": json.dumps(["healthcare-analytics-pack"]),
        "source": "CDC / Data.gov",
        "source_url": "https://catalog.data.gov/dataset/nndss",
        "connector": "owid",
        "license": "Public Domain (U.S. Government)",
        "version": "1.0.0",
        "sync_frequency": "weekly",
        "record_count": 186000,
        "file_size_bytes": 72_000_000,
        "quality_score": 9.5,
        "processing_status": "ready",
        "popularity": 920,
        "endpoint": "/api/v1/data/cdc-disease-surveillance",
        "schema_info": json.dumps({
            "fields": [
                {"name": "week", "type": "string", "description": "MMWR week (YYYY-WW)"},
                {"name": "state", "type": "string", "description": "US state or territory"},
                {"name": "disease", "type": "string", "description": "Notifiable disease name"},
                {"name": "cases", "type": "integer", "description": "Confirmed cases this week"},
                {"name": "cumulative_cases", "type": "integer", "description": "Year-to-date cumulative cases"},
                {"name": "deaths", "type": "integer", "description": "Deaths this week"},
                {"name": "hospitalisations", "type": "integer", "description": "Hospitalisations this week"},
            ]
        }),
        "statistics": json.dumps({"total_records": 186000, "states": 57, "diseases": 60, "years_covered": "2015-2024", "completeness_pct": 89.2}),
        "sample_data": [
            {"week": "2024-01", "state": "California", "disease": "Influenza", "cases": 12840, "cumulative_cases": 12840, "deaths": 18},
            {"week": "2024-01", "state": "Texas", "disease": "Influenza", "cases": 9420, "cumulative_cases": 9420, "deaths": 12},
        ],
    },
    {
        "slug": "world-population-health",
        "name": "World Population Health Indicators",
        "description": "World Bank population and health indicators for 218 countries covering birth rate, death rate, fertility rate, urban population percentage, and age distribution from 1960 to present.",
        "domain": "Healthcare",
        "category": "Population",
        "tags": json.dumps(["population", "health", "world-bank", "demographics", "birth-rate", "mortality"]),
        "solution_packs": json.dumps(["healthcare-analytics-pack", "university-finder-pack"]),
        "source": "World Bank",
        "source_url": "https://api.worldbank.org/v2/indicator/SP.POP.TOTL",
        "connector": "worldbank",
        "license": "CC BY 4.0",
        "version": "1.0.0",
        "sync_frequency": "yearly",
        "record_count": 13800,
        "file_size_bytes": 11_000_000,
        "quality_score": 9.6,
        "processing_status": "ready",
        "popularity": 1080,
        "endpoint": "/api/v1/data/world-population-health",
        "schema_info": json.dumps({
            "fields": [
                {"name": "country_code", "type": "string", "description": "ISO 3-letter country code"},
                {"name": "country_name", "type": "string", "description": "Country name"},
                {"name": "year", "type": "integer", "description": "Year"},
                {"name": "total_population", "type": "integer", "description": "Total population"},
                {"name": "birth_rate_per_1000", "type": "float", "description": "Crude birth rate per 1000"},
                {"name": "death_rate_per_1000", "type": "float", "description": "Crude death rate per 1000"},
                {"name": "fertility_rate", "type": "float", "description": "Fertility rate (births per woman)"},
                {"name": "urban_population_pct", "type": "float", "description": "Urban population percentage"},
                {"name": "median_age", "type": "float", "description": "Median population age"},
            ]
        }),
        "statistics": json.dumps({"total_records": 13800, "countries": 218, "years_covered": "1960-2023", "completeness_pct": 91.7}),
        "sample_data": [
            {"country_code": "CHN", "country_name": "China", "year": 2023, "total_population": 1409670000, "birth_rate_per_1000": 6.4, "death_rate_per_1000": 7.4, "fertility_rate": 1.09, "urban_population_pct": 65.2},
            {"country_code": "IND", "country_name": "India", "year": 2023, "total_population": 1428627663, "birth_rate_per_1000": 16.4, "death_rate_per_1000": 7.0, "fertility_rate": 1.91, "urban_population_pct": 36.4},
        ],
    },
    {
        "slug": "medical-qa-dataset",
        "name": "Medical Question & Answer Dataset",
        "description": "Curated medical Q&A pairs sourced from verified medical resources. Covers general medicine, symptoms, treatments, drug interactions, and preventive healthcare. Used for training medical chatbots and knowledge bases.",
        "domain": "Healthcare",
        "category": "Medical QA",
        "tags": json.dumps(["medical", "qa", "chatbot", "nlp", "symptoms", "treatments", "knowledge-base"]),
        "solution_packs": json.dumps(["ai-chatbot-pack", "healthcare-analytics-pack"]),
        "source": "HuggingFace",
        "source_url": "https://huggingface.co/datasets/medalpaca/medical_meadow_medical_flashcards",
        "connector": "hf-medical",
        "license": "CC BY 4.0",
        "version": "1.0.0",
        "sync_frequency": "monthly",
        "record_count": 33955,
        "file_size_bytes": 21_000_000,
        "quality_score": 9.1,
        "processing_status": "ready",
        "popularity": 1740,
        "endpoint": "/api/v1/data/medical-qa-dataset",
        "schema_info": json.dumps({
            "fields": [
                {"name": "id", "type": "integer", "description": "Record ID"},
                {"name": "question", "type": "string", "description": "Medical question"},
                {"name": "answer", "type": "string", "description": "Verified answer"},
                {"name": "category", "type": "string", "description": "Medical specialty category"},
                {"name": "source", "type": "string", "description": "Answer source reference"},
                {"name": "difficulty", "type": "string", "description": "Question difficulty level"},
            ]
        }),
        "statistics": json.dumps({"total_records": 33955, "categories": 28, "avg_answer_length_words": 84, "completeness_pct": 99.8}),
        "sample_data": [
            {"id": 1, "question": "What are the common symptoms of Type 2 diabetes?", "answer": "Common symptoms include increased thirst, frequent urination, fatigue, blurred vision, slow-healing wounds, and frequent infections.", "category": "Endocrinology", "difficulty": "Beginner"},
            {"id": 2, "question": "What is the mechanism of action of metformin?", "answer": "Metformin works primarily by reducing hepatic glucose production via AMPK activation, and also improves peripheral insulin sensitivity.", "category": "Pharmacology", "difficulty": "Intermediate"},
        ],
    },
    {
        "slug": "covid19-global-stats",
        "name": "COVID-19 Global Statistics",
        "description": "Comprehensive COVID-19 pandemic statistics from the WHO official database. Covers cases, deaths, recoveries, testing rates, and vaccination progress for all countries from January 2020 to present.",
        "domain": "Healthcare",
        "category": "Disease Statistics",
        "tags": json.dumps(["covid19", "pandemic", "who", "cases", "deaths", "vaccination", "global"]),
        "solution_packs": json.dumps(["healthcare-analytics-pack"]),
        "source": "World Health Organization",
        "source_url": "https://covid19.who.int/data",
        "connector": "disease-sh",
        "license": "CC BY 4.0",
        "version": "1.0.0",
        "sync_frequency": "weekly",
        "record_count": 280000,
        "file_size_bytes": 95_000_000,
        "quality_score": 9.8,
        "processing_status": "ready",
        "popularity": 2180,
        "endpoint": "/api/v1/data/covid19-global-stats",
        "schema_info": json.dumps({
            "fields": [
                {"name": "date_reported", "type": "date", "description": "Reporting date"},
                {"name": "country_code", "type": "string", "description": "ISO 2-letter country code"},
                {"name": "country", "type": "string", "description": "Country name"},
                {"name": "who_region", "type": "string", "description": "WHO region"},
                {"name": "new_cases", "type": "integer", "description": "New cases reported"},
                {"name": "cumulative_cases", "type": "integer", "description": "Total cumulative cases"},
                {"name": "new_deaths", "type": "integer", "description": "New deaths reported"},
                {"name": "cumulative_deaths", "type": "integer", "description": "Total cumulative deaths"},
            ]
        }),
        "statistics": json.dumps({"total_records": 280000, "countries": 194, "date_range": "2020-01-03 to 2024-12-31", "global_cases": 776000000, "global_deaths": 7050000, "completeness_pct": 97.2}),
        "sample_data": [
            {"date_reported": "2024-01-01", "country_code": "US", "country": "United States of America", "who_region": "AMRO", "new_cases": 4820, "cumulative_cases": 103436829, "new_deaths": 89, "cumulative_deaths": 1144877},
            {"date_reported": "2024-01-01", "country_code": "IN", "country": "India", "who_region": "SEARO", "new_cases": 841, "cumulative_cases": 44694851, "new_deaths": 2, "cumulative_deaths": 530779},
        ],
    },
    # ════════════════════════════════════════════
    # GEOGRAPHY (6 datasets)
    # ════════════════════════════════════════════
    {
        "slug": "world-countries",
        "name": "World Countries Database",
        "description": "Comprehensive database of all 250 countries and territories. Includes official names, ISO codes, capitals, continents, currencies, languages, population, area, and geographic coordinates.",
        "domain": "Geography",
        "category": "Countries",
        "tags": json.dumps(["countries", "geography", "iso-codes", "capitals", "currencies", "continents"]),
        "solution_packs": json.dumps(["location-intelligence-pack", "hospital-finder-pack", "university-finder-pack"]),
        "source": "REST Countries",
        "source_url": "https://restcountries.com/v3.1/all",
        "connector": "restcountries",
        "license": "CC BY 4.0",
        "version": "1.0.0",
        "sync_frequency": "yearly",
        "record_count": 250,
        "file_size_bytes": 420_000,
        "quality_score": 9.9,
        "processing_status": "ready",
        "popularity": 2640,
        "endpoint": "/api/v1/data/world-countries",
        "schema_info": json.dumps({
            "fields": [
                {"name": "iso2", "type": "string", "description": "ISO 3166-1 alpha-2 code"},
                {"name": "iso3", "type": "string", "description": "ISO 3166-1 alpha-3 code"},
                {"name": "name", "type": "string", "description": "Official country name"},
                {"name": "native_name", "type": "string", "description": "Name in native language"},
                {"name": "capital", "type": "string", "description": "Capital city"},
                {"name": "continent", "type": "string", "description": "Continent"},
                {"name": "region", "type": "string", "description": "Geographic region"},
                {"name": "population", "type": "integer", "description": "Population estimate"},
                {"name": "area_km2", "type": "float", "description": "Area in square kilometres"},
                {"name": "latitude", "type": "float", "description": "Country centroid latitude"},
                {"name": "longitude", "type": "float", "description": "Country centroid longitude"},
                {"name": "currency_code", "type": "string", "description": "ISO 4217 currency code"},
                {"name": "phone_code", "type": "string", "description": "International dialing code"},
                {"name": "languages", "type": "array", "description": "Official languages"},
                {"name": "flag_emoji", "type": "string", "description": "Flag emoji"},
            ]
        }),
        "statistics": json.dumps({"total_records": 250, "continents": 7, "currencies": 165, "languages": 194, "completeness_pct": 99.6}),
        "sample_data": [
            {"iso2": "US", "iso3": "USA", "name": "United States", "capital": "Washington, D.C.", "continent": "North America", "population": 331000000, "area_km2": 9372610, "currency_code": "USD", "languages": ["English"], "flag_emoji": "🇺🇸"},
            {"iso2": "JP", "iso3": "JPN", "name": "Japan", "capital": "Tokyo", "continent": "Asia", "population": 125700000, "area_km2": 377975, "currency_code": "JPY", "languages": ["Japanese"], "flag_emoji": "🇯🇵"},
            {"iso2": "IN", "iso3": "IND", "name": "India", "capital": "New Delhi", "continent": "Asia", "population": 1428627663, "area_km2": 3287263, "currency_code": "INR", "languages": ["Hindi", "English"], "flag_emoji": "🇮🇳"},
        ],
    },
    {
        "slug": "world-cities",
        "name": "World Cities Database",
        "description": "Database of 2 million+ cities and populated places worldwide with population over 1000. Includes GPS coordinates, country, admin region, elevation, and timezone from GeoNames.",
        "domain": "Geography",
        "category": "Cities",
        "tags": json.dumps(["cities", "geography", "coordinates", "gps", "population", "geonames"]),
        "solution_packs": json.dumps(["location-intelligence-pack", "hospital-finder-pack", "university-finder-pack"]),
        "source": "GeoNames",
        "source_url": "https://download.geonames.org/export/dump/",
        "connector": "geonames",
        "license": "CC BY 4.0",
        "version": "1.0.0",
        "sync_frequency": "monthly",
        "record_count": 2100000,
        "file_size_bytes": 480_000_000,
        "quality_score": 9.5,
        "processing_status": "ready",
        "popularity": 2820,
        "endpoint": "/api/v1/data/world-cities",
        "schema_info": json.dumps({
            "fields": [
                {"name": "geoname_id", "type": "integer", "description": "GeoNames ID"},
                {"name": "name", "type": "string", "description": "City name"},
                {"name": "ascii_name", "type": "string", "description": "ASCII-safe city name"},
                {"name": "country_code", "type": "string", "description": "ISO 2-letter country code"},
                {"name": "admin1", "type": "string", "description": "First-level admin (state/province)"},
                {"name": "admin2", "type": "string", "description": "Second-level admin (district)"},
                {"name": "population", "type": "integer", "description": "City population"},
                {"name": "latitude", "type": "float", "description": "GPS latitude"},
                {"name": "longitude", "type": "float", "description": "GPS longitude"},
                {"name": "elevation_m", "type": "integer", "description": "Elevation in metres"},
                {"name": "timezone", "type": "string", "description": "IANA timezone identifier"},
            ]
        }),
        "statistics": json.dumps({"total_records": 2100000, "countries": 252, "max_population": 37435191, "completeness_pct": 92.8}),
        "sample_data": [
            {"geoname_id": 1850147, "name": "Tokyo", "country_code": "JP", "admin1": "Tokyo", "population": 37435191, "latitude": 35.6895, "longitude": 139.6917, "timezone": "Asia/Tokyo"},
            {"geoname_id": 1275339, "name": "Mumbai", "country_code": "IN", "admin1": "Maharashtra", "population": 12691836, "latitude": 19.0728, "longitude": 72.8826, "timezone": "Asia/Kolkata"},
            {"geoname_id": 5128581, "name": "New York City", "country_code": "US", "admin1": "New York", "population": 8336817, "latitude": 40.7128, "longitude": -74.0060, "timezone": "America/New_York"},
        ],
    },
    {
        "slug": "airport-codes",
        "name": "International Airport Codes",
        "description": "Complete database of 55,000+ airports worldwide with IATA and ICAO codes. Includes GPS coordinates, elevation, runway information, and scheduled service status. Source: OurAirports.",
        "domain": "Geography",
        "category": "Airports",
        "tags": json.dumps(["airports", "iata", "icao", "aviation", "travel", "coordinates"]),
        "solution_packs": json.dumps(["location-intelligence-pack"]),
        "source": "OurAirports",
        "source_url": "https://ourairports.com/data/airports.csv",
        "connector": "ourairports",
        "license": "Public Domain",
        "version": "1.0.0",
        "sync_frequency": "monthly",
        "record_count": 55000,
        "file_size_bytes": 18_000_000,
        "quality_score": 9.4,
        "processing_status": "ready",
        "popularity": 1340,
        "endpoint": "/api/v1/data/airport-codes",
        "schema_info": json.dumps({
            "fields": [
                {"name": "id", "type": "integer", "description": "OurAirports ID"},
                {"name": "iata_code", "type": "string", "description": "3-letter IATA code"},
                {"name": "icao_code", "type": "string", "description": "4-letter ICAO code"},
                {"name": "name", "type": "string", "description": "Airport name"},
                {"name": "type", "type": "string", "description": "Airport type (large_airport, medium_airport, etc.)"},
                {"name": "latitude", "type": "float", "description": "GPS latitude"},
                {"name": "longitude", "type": "float", "description": "GPS longitude"},
                {"name": "elevation_ft", "type": "integer", "description": "Elevation in feet"},
                {"name": "country_code", "type": "string", "description": "ISO 2-letter country code"},
                {"name": "municipality", "type": "string", "description": "Nearest city"},
                {"name": "scheduled_service", "type": "boolean", "description": "Has scheduled airline service"},
            ]
        }),
        "statistics": json.dumps({"total_records": 55000, "countries": 240, "large_airports": 615, "with_iata_code": 9200, "completeness_pct": 93.2}),
        "sample_data": [
            {"id": 3484, "iata_code": "JFK", "icao_code": "KJFK", "name": "John F. Kennedy International Airport", "type": "large_airport", "latitude": 40.6413, "longitude": -73.7781, "country_code": "US", "municipality": "New York", "scheduled_service": True},
            {"id": 2287, "iata_code": "LHR", "icao_code": "EGLL", "name": "Heathrow Airport", "type": "large_airport", "latitude": 51.4775, "longitude": -0.4614, "country_code": "GB", "municipality": "London", "scheduled_service": True},
            {"id": 6301, "iata_code": "NRT", "icao_code": "RJAA", "name": "Narita International Airport", "type": "large_airport", "latitude": 35.7720, "longitude": 140.3929, "country_code": "JP", "municipality": "Tokyo", "scheduled_service": True},
        ],
    },
    {
        "slug": "country-iso-codes",
        "name": "Country ISO Codes & Dialing Codes",
        "description": "Complete ISO 3166-1 country code reference including alpha-2, alpha-3, numeric codes, international dialing codes, TLDs, and UN member status. Essential for any application with internationalization.",
        "domain": "Geography",
        "category": "Countries",
        "tags": json.dumps(["iso", "country-codes", "dialing-codes", "internationalization", "tld", "reference"]),
        "solution_packs": json.dumps(["location-intelligence-pack", "hospital-finder-pack", "university-finder-pack"]),
        "source": "ISO.org / ITU",
        "source_url": "https://www.iso.org/iso-3166-country-codes.html",
        "connector": "restcountries",
        "license": "Public Domain",
        "version": "1.0.0",
        "sync_frequency": "yearly",
        "record_count": 249,
        "file_size_bytes": 85_000,
        "quality_score": 10.0,
        "processing_status": "ready",
        "popularity": 1910,
        "endpoint": "/api/v1/data/country-iso-codes",
        "schema_info": json.dumps({
            "fields": [
                {"name": "iso_alpha2", "type": "string", "description": "ISO 3166-1 alpha-2 (2-letter code)"},
                {"name": "iso_alpha3", "type": "string", "description": "ISO 3166-1 alpha-3 (3-letter code)"},
                {"name": "iso_numeric", "type": "string", "description": "ISO 3166-1 numeric (3-digit code)"},
                {"name": "name", "type": "string", "description": "Country name"},
                {"name": "dialing_code", "type": "string", "description": "International dialing code (+1, +44, etc.)"},
                {"name": "tld", "type": "string", "description": "Top-level internet domain (.us, .uk, etc.)"},
                {"name": "un_member", "type": "boolean", "description": "UN member state"},
                {"name": "continent", "type": "string", "description": "Continent code"},
            ]
        }),
        "statistics": json.dumps({"total_records": 249, "un_members": 193, "continents": 7, "completeness_pct": 100.0}),
        "sample_data": [
            {"iso_alpha2": "US", "iso_alpha3": "USA", "iso_numeric": "840", "name": "United States", "dialing_code": "+1", "tld": ".us", "un_member": True, "continent": "NA"},
            {"iso_alpha2": "GB", "iso_alpha3": "GBR", "iso_numeric": "826", "name": "United Kingdom", "dialing_code": "+44", "tld": ".uk", "un_member": True, "continent": "EU"},
            {"iso_alpha2": "IN", "iso_alpha3": "IND", "iso_numeric": "356", "name": "India", "dialing_code": "+91", "tld": ".in", "un_member": True, "continent": "AS"},
        ],
    },
    {
        "slug": "world-timezones",
        "name": "World Timezones Database",
        "description": "Complete IANA timezone database with UTC offsets, DST rules, historical timezone changes, and country-to-timezone mapping. Covers all 400+ IANA timezone identifiers.",
        "domain": "Geography",
        "category": "Timezones",
        "tags": json.dumps(["timezones", "iana", "utc", "dst", "internationalization", "scheduling"]),
        "solution_packs": json.dumps(["location-intelligence-pack"]),
        "source": "IANA / GeoNames",
        "source_url": "https://www.iana.org/time-zones",
        "connector": "geonames",
        "license": "Public Domain",
        "version": "1.0.0",
        "sync_frequency": "yearly",
        "record_count": 600,
        "file_size_bytes": 240_000,
        "quality_score": 10.0,
        "processing_status": "ready",
        "popularity": 840,
        "endpoint": "/api/v1/data/world-timezones",
        "schema_info": json.dumps({
            "fields": [
                {"name": "timezone_id", "type": "string", "description": "IANA timezone identifier (e.g. America/New_York)"},
                {"name": "country_code", "type": "string", "description": "ISO 2-letter country code"},
                {"name": "utc_offset_standard", "type": "string", "description": "Standard UTC offset (e.g. -05:00)"},
                {"name": "utc_offset_dst", "type": "string", "description": "DST UTC offset (e.g. -04:00)"},
                {"name": "uses_dst", "type": "boolean", "description": "Uses Daylight Saving Time"},
                {"name": "abbreviation", "type": "string", "description": "Timezone abbreviation (EST, GMT, IST)"},
                {"name": "cities", "type": "array", "description": "Example cities in this timezone"},
            ]
        }),
        "statistics": json.dumps({"total_records": 600, "countries": 195, "with_dst": 186, "completeness_pct": 100.0}),
        "sample_data": [
            {"timezone_id": "America/New_York", "country_code": "US", "utc_offset_standard": "-05:00", "utc_offset_dst": "-04:00", "uses_dst": True, "abbreviation": "EST/EDT", "cities": ["New York", "Miami", "Atlanta"]},
            {"timezone_id": "Asia/Kolkata", "country_code": "IN", "utc_offset_standard": "+05:30", "utc_offset_dst": "+05:30", "uses_dst": False, "abbreviation": "IST", "cities": ["Mumbai", "Delhi", "Bangalore"]},
            {"timezone_id": "Europe/London", "country_code": "GB", "utc_offset_standard": "+00:00", "utc_offset_dst": "+01:00", "uses_dst": True, "abbreviation": "GMT/BST", "cities": ["London", "Edinburgh", "Cardiff"]},
        ],
    },
    {
        "slug": "world-boundaries",
        "name": "World Administrative Boundaries",
        "description": "Administrative boundary data for all countries at levels 0 (country), 1 (state/province), and 2 (district/county) from GeoNames. Includes boundary names, codes, and parent-child relationships.",
        "domain": "Geography",
        "category": "Countries",
        "tags": json.dumps(["boundaries", "administrative", "states", "provinces", "geonames", "regions"]),
        "solution_packs": json.dumps(["location-intelligence-pack"]),
        "source": "GeoNames",
        "source_url": "https://download.geonames.org/export/dump/admin1CodesASCII.txt",
        "connector": "geonames",
        "license": "CC BY 4.0",
        "version": "1.0.0",
        "sync_frequency": "yearly",
        "record_count": 42000,
        "file_size_bytes": 8_400_000,
        "quality_score": 9.2,
        "processing_status": "ready",
        "popularity": 610,
        "endpoint": "/api/v1/data/world-boundaries",
        "schema_info": json.dumps({
            "fields": [
                {"name": "geoname_id", "type": "integer", "description": "GeoNames ID"},
                {"name": "code", "type": "string", "description": "Administrative code (e.g. US.CA)"},
                {"name": "name", "type": "string", "description": "Administrative area name"},
                {"name": "ascii_name", "type": "string", "description": "ASCII name"},
                {"name": "country_code", "type": "string", "description": "ISO country code"},
                {"name": "level", "type": "integer", "description": "Admin level (1=state, 2=district)"},
                {"name": "population", "type": "integer", "description": "Population"},
            ]
        }),
        "statistics": json.dumps({"total_records": 42000, "countries": 250, "level1_regions": 3800, "level2_regions": 38200, "completeness_pct": 87.4}),
        "sample_data": [
            {"geoname_id": 5332921, "code": "US.CA", "name": "California", "country_code": "US", "level": 1, "population": 39538223},
            {"geoname_id": 2638360, "code": "GB.SCT", "name": "Scotland", "country_code": "GB", "level": 1, "population": 5466000},
        ],
    },
    # ════════════════════════════════════════════
    # SPORTS (5 datasets)
    # ════════════════════════════════════════════
    {
        "slug": "fifa-world-rankings",
        "name": "FIFA World Football Rankings",
        "description": "Historical FIFA World Rankings for men's and women's national football teams. Covers monthly ranking snapshots from 1993 to present, including points, confederation, and rank changes.",
        "domain": "Sports",
        "category": "Football",
        "tags": json.dumps(["fifa", "football", "soccer", "rankings", "national-teams", "world-cup"]),
        "solution_packs": json.dumps(["sports-analytics-pack"]),
        "source": "FIFA",
        "source_url": "https://www.fifa.com/fifa-world-ranking",
        "connector": "fifa-rankings",
        "license": "FIFA Terms of Service",
        "version": "1.0.0",
        "sync_frequency": "monthly",
        "record_count": 84000,
        "file_size_bytes": 14_000_000,
        "quality_score": 9.3,
        "processing_status": "ready",
        "popularity": 1720,
        "endpoint": "/api/v1/data/fifa-world-rankings",
        "schema_info": json.dumps({
            "fields": [
                {"name": "date", "type": "date", "description": "Ranking date (monthly snapshot)"},
                {"name": "rank", "type": "integer", "description": "FIFA rank"},
                {"name": "team", "type": "string", "description": "National team name"},
                {"name": "country_code", "type": "string", "description": "ISO 3-letter country code"},
                {"name": "confederation", "type": "string", "description": "FIFA confederation (UEFA, CONMEBOL, etc.)"},
                {"name": "total_points", "type": "float", "description": "FIFA ranking points"},
                {"name": "rank_change", "type": "integer", "description": "Change from previous month"},
            ]
        }),
        "statistics": json.dumps({"total_records": 84000, "teams": 212, "date_range": "1993-08 to 2024-12", "completeness_pct": 99.4}),
        "sample_data": [
            {"date": "2024-12-19", "rank": 1, "team": "Argentina", "country_code": "ARG", "confederation": "CONMEBOL", "total_points": 1895.27, "rank_change": 0},
            {"date": "2024-12-19", "rank": 2, "team": "France", "country_code": "FRA", "confederation": "UEFA", "total_points": 1851.38, "rank_change": 0},
            {"date": "2024-12-19", "rank": 3, "team": "Spain", "country_code": "ESP", "confederation": "UEFA", "total_points": 1833.67, "rank_change": 0},
        ],
    },
    {
        "slug": "olympic-games-history",
        "name": "Olympic Games Results History",
        "description": "Complete historical results of Summer and Winter Olympic Games from Athens 1896 to Paris 2024. Includes athlete names, countries, events, disciplines, and medal results.",
        "domain": "Sports",
        "category": "Olympics",
        "tags": json.dumps(["olympics", "medals", "athletes", "sports", "history", "summer", "winter"]),
        "solution_packs": json.dumps(["sports-analytics-pack"]),
        "source": "Kaggle / IOC",
        "source_url": "https://www.kaggle.com/datasets/the-guardian/olympic-games",
        "connector": "olympics-history",
        "license": "CC0 1.0",
        "version": "1.0.0",
        "sync_frequency": "yearly",
        "record_count": 280000,
        "file_size_bytes": 42_000_000,
        "quality_score": 9.1,
        "processing_status": "ready",
        "popularity": 1480,
        "endpoint": "/api/v1/data/olympic-games-history",
        "schema_info": json.dumps({
            "fields": [
                {"name": "games", "type": "string", "description": "Olympic Games edition (e.g. 2024 Summer Olympics)"},
                {"name": "year", "type": "integer", "description": "Year"},
                {"name": "season", "type": "string", "description": "Summer or Winter"},
                {"name": "city", "type": "string", "description": "Host city"},
                {"name": "sport", "type": "string", "description": "Sport name"},
                {"name": "discipline", "type": "string", "description": "Discipline/event name"},
                {"name": "event", "type": "string", "description": "Specific event"},
                {"name": "athlete", "type": "string", "description": "Athlete name"},
                {"name": "country", "type": "string", "description": "Country name"},
                {"name": "country_code", "type": "string", "description": "IOC country code"},
                {"name": "medal", "type": "string", "description": "Medal won (Gold/Silver/Bronze)"},
                {"name": "gender", "type": "string", "description": "M or F"},
            ]
        }),
        "statistics": json.dumps({"total_records": 280000, "editions": 53, "countries": 204, "sports": 68, "completeness_pct": 98.7}),
        "sample_data": [
            {"games": "2024 Paris Olympics", "year": 2024, "season": "Summer", "city": "Paris", "sport": "Athletics", "discipline": "100m", "event": "Men's 100m", "athlete": "Noah Lyles", "country": "United States", "country_code": "USA", "medal": "Gold"},
            {"games": "2024 Paris Olympics", "year": 2024, "season": "Summer", "city": "Paris", "sport": "Swimming", "discipline": "Freestyle", "event": "Women's 400m Freestyle", "athlete": "Ariarne Titmus", "country": "Australia", "country_code": "AUS", "medal": "Gold"},
        ],
    },
    {
        "slug": "ipl-cricket-statistics",
        "name": "IPL Cricket Statistics 2008–2024",
        "description": "Complete Indian Premier League (IPL) cricket statistics from inaugural season 2008 to 2024. Covers match results, batting/bowling scorecards, player performance, and team standings.",
        "domain": "Sports",
        "category": "Cricket",
        "tags": json.dumps(["ipl", "cricket", "india", "t20", "batting", "bowling", "players", "teams"]),
        "solution_packs": json.dumps(["sports-analytics-pack"]),
        "source": "Kaggle",
        "source_url": "https://www.kaggle.com/datasets/patrickb1912/ipl-complete-dataset-20082020",
        "connector": "ipl-stats",
        "license": "CC BY-SA 4.0",
        "version": "1.0.0",
        "sync_frequency": "yearly",
        "record_count": 108000,
        "file_size_bytes": 22_000_000,
        "quality_score": 8.9,
        "processing_status": "ready",
        "popularity": 1920,
        "endpoint": "/api/v1/data/ipl-cricket-statistics",
        "schema_info": json.dumps({
            "fields": [
                {"name": "match_id", "type": "integer", "description": "Unique match ID"},
                {"name": "season", "type": "integer", "description": "IPL season year"},
                {"name": "date", "type": "date", "description": "Match date"},
                {"name": "team1", "type": "string", "description": "First team"},
                {"name": "team2", "type": "string", "description": "Second team"},
                {"name": "toss_winner", "type": "string", "description": "Toss winning team"},
                {"name": "toss_decision", "type": "string", "description": "Bat or field"},
                {"name": "result", "type": "string", "description": "Match result"},
                {"name": "winner", "type": "string", "description": "Winning team"},
                {"name": "win_by_runs", "type": "integer", "description": "Margin of victory in runs"},
                {"name": "win_by_wickets", "type": "integer", "description": "Margin of victory in wickets"},
                {"name": "player_of_match", "type": "string", "description": "Player of the match"},
                {"name": "venue", "type": "string", "description": "Match venue"},
                {"name": "city", "type": "string", "description": "Host city"},
            ]
        }),
        "statistics": json.dumps({"total_records": 108000, "seasons": 17, "teams": 12, "venues": 34, "completeness_pct": 97.8}),
        "sample_data": [
            {"match_id": 1312200, "season": 2024, "date": "2024-05-26", "team1": "Kolkata Knight Riders", "team2": "Sunrisers Hyderabad", "winner": "Kolkata Knight Riders", "win_by_runs": 8, "player_of_match": "Shreyas Iyer", "venue": "MA Chidambaram Stadium", "city": "Chennai"},
            {"match_id": 1312199, "season": 2024, "date": "2024-05-24", "team1": "Rajasthan Royals", "team2": "Sunrisers Hyderabad", "winner": "Sunrisers Hyderabad", "win_by_wickets": 36, "player_of_match": "Travis Head", "venue": "MA Chidambaram Stadium", "city": "Chennai"},
        ],
    },
    {
        "slug": "nba-player-stats",
        "name": "NBA Player Statistics 2023–24",
        "description": "Complete NBA player statistics for the 2023–24 regular season and playoffs. Includes per-game averages, shooting percentages, advanced metrics (PER, WS, BPM), and salary data.",
        "domain": "Sports",
        "category": "Basketball",
        "tags": json.dumps(["nba", "basketball", "players", "statistics", "usa", "sports-analytics"]),
        "solution_packs": json.dumps(["sports-analytics-pack"]),
        "source": "NBA Stats API",
        "source_url": "https://stats.nba.com/stats/leaguedashplayerstats",
        "connector": "nba-stats",
        "license": "NBA Terms of Service",
        "version": "1.0.0",
        "sync_frequency": "yearly",
        "record_count": 4800,
        "file_size_bytes": 3_200_000,
        "quality_score": 9.4,
        "processing_status": "ready",
        "popularity": 1380,
        "endpoint": "/api/v1/data/nba-player-stats",
        "schema_info": json.dumps({
            "fields": [
                {"name": "player_id", "type": "integer", "description": "NBA Player ID"},
                {"name": "player_name", "type": "string", "description": "Player full name"},
                {"name": "team", "type": "string", "description": "Team abbreviation"},
                {"name": "position", "type": "string", "description": "Position (PG, SG, SF, PF, C)"},
                {"name": "age", "type": "integer", "description": "Player age"},
                {"name": "games_played", "type": "integer", "description": "Games played"},
                {"name": "points_per_game", "type": "float", "description": "Average points per game"},
                {"name": "rebounds_per_game", "type": "float", "description": "Average rebounds per game"},
                {"name": "assists_per_game", "type": "float", "description": "Average assists per game"},
                {"name": "field_goal_pct", "type": "float", "description": "Field goal percentage"},
                {"name": "three_point_pct", "type": "float", "description": "Three-point percentage"},
                {"name": "player_efficiency_rating", "type": "float", "description": "PER (advanced metric)"},
                {"name": "salary_usd", "type": "integer", "description": "2023-24 salary"},
            ]
        }),
        "statistics": json.dumps({"total_records": 4800, "teams": 30, "avg_ppg_top10": 28.4, "completeness_pct": 98.2}),
        "sample_data": [
            {"player_id": 2544, "player_name": "LeBron James", "team": "LAL", "position": "SF", "age": 39, "games_played": 71, "points_per_game": 25.7, "rebounds_per_game": 7.3, "assists_per_game": 8.3, "player_efficiency_rating": 22.4, "salary_usd": 47607350},
            {"player_id": 203999, "player_name": "Nikola Jokić", "team": "DEN", "position": "C", "age": 29, "games_played": 79, "points_per_game": 26.4, "rebounds_per_game": 12.4, "assists_per_game": 9.0, "player_efficiency_rating": 32.1, "salary_usd": 47607350},
        ],
    },
    {
        "slug": "world-athletics-records",
        "name": "World Athletics Records",
        "description": "Complete World Athletics (formerly IAAF) world records database covering all track and field events. Includes men's and women's records, athlete details, dates, locations, and video links.",
        "domain": "Sports",
        "category": "Athletics",
        "tags": json.dumps(["athletics", "world-records", "track-field", "sprint", "marathon", "iaaf"]),
        "solution_packs": json.dumps(["sports-analytics-pack"]),
        "source": "World Athletics",
        "source_url": "https://worldathletics.org/records/by-discipline/world-records",
        "connector": "athletics-records",
        "license": "World Athletics Terms of Service",
        "version": "1.0.0",
        "sync_frequency": "monthly",
        "record_count": 420,
        "file_size_bytes": 380_000,
        "quality_score": 9.9,
        "processing_status": "ready",
        "popularity": 680,
        "endpoint": "/api/v1/data/world-athletics-records",
        "schema_info": json.dumps({
            "fields": [
                {"name": "event", "type": "string", "description": "Athletics event name"},
                {"name": "gender", "type": "string", "description": "M or F"},
                {"name": "athlete", "type": "string", "description": "Athlete full name"},
                {"name": "country", "type": "string", "description": "Country name"},
                {"name": "country_code", "type": "string", "description": "WA country code"},
                {"name": "performance", "type": "string", "description": "Record performance (time/distance/height)"},
                {"name": "date", "type": "date", "description": "Date record was set"},
                {"name": "location", "type": "string", "description": "City where record was set"},
                {"name": "category", "type": "string", "description": "Track / Field / Road / Combined"},
            ]
        }),
        "statistics": json.dumps({"total_records": 420, "events": 80, "countries": 52, "oldest_record_year": 1968, "completeness_pct": 100.0}),
        "sample_data": [
            {"event": "100m", "gender": "M", "athlete": "Usain Bolt", "country": "Jamaica", "country_code": "JAM", "performance": "9.58", "date": "2009-08-16", "location": "Berlin", "category": "Track"},
            {"event": "Marathon", "gender": "M", "athlete": "Kelvin Kiptum", "country": "Kenya", "country_code": "KEN", "performance": "2:00:35", "date": "2023-10-08", "location": "Chicago", "category": "Road"},
            {"event": "High Jump", "gender": "M", "athlete": "Javier Sotomayor", "country": "Cuba", "country_code": "CUB", "performance": "2.45m", "date": "1993-07-27", "location": "Salamanca", "category": "Field"},
        ],
    },
]

# ── Dataset Seeding ───────────────────────────────────────────────────────────

def seed_datasets(db: Session) -> None:
    """
    Populate the database with datasets from the global HF registry.json.
    If the HF registry is empty (first boot), pushes the default catalog to HF.
    """
    from hf_storage import hf_storage
    
    registry = hf_storage.get_registry()
    if not registry:
        # Bootstrap HF Registry
        import logging
        logging.getLogger("omnicore").info("HF registry empty. Bootstrapping with default catalog...")
        registry = DATASET_CATALOG
        hf_storage.update_registry(registry)

    now = datetime.utcnow()
    seeded = 0
    for entry in registry:
        ds = db.query(Dataset).filter_by(slug=entry["slug"]).first()
        if ds:
            continue

        schema = entry.get("schema_info", "{}")
        columns_count = 0
        if isinstance(schema, str):
            try:
                schema_dict = json.loads(schema)
                columns_count = len(schema_dict.get("fields", []))
            except:
                pass

        ds = Dataset(
            slug=entry["slug"],
            name=entry["name"],
            description=entry["description"],
            domain=entry["domain"],
            category=entry["category"],
            tags=entry.get("tags", "[]") if isinstance(entry.get("tags"), str) else json.dumps(entry.get("tags", [])),
            solution_packs=entry.get("solution_packs", "[]") if isinstance(entry.get("solution_packs"), str) else json.dumps(entry.get("solution_packs", [])),
            source=entry.get("source", "Unknown"),
            source_url=entry.get("source_url", ""),
            connector=entry.get("connector", "manual"),
            license=entry.get("license", "Unknown"),
            version=entry.get("version", "1.0.0"),
            sync_frequency=entry.get("sync_frequency", "weekly"),
            record_count=entry.get("record_count", 0),
            columns_count=columns_count,
            file_size_bytes=entry.get("file_size_bytes", 0),
            file_format=entry.get("file_format", "parquet"),
            schema_info=schema if isinstance(schema, str) else json.dumps(schema),
            statistics=entry.get("statistics", "{}") if isinstance(entry.get("statistics"), str) else json.dumps(entry.get("statistics", {})),
            quality_score=entry.get("quality_score", 0.0),
            processing_status=entry.get("processing_status", "ready"),
            popularity=entry.get("popularity", 0),
            endpoint=entry.get("endpoint", f"/api/v1/data/{entry['slug']}"),
            last_sync=now - timedelta(days=1),
            next_sync=now + timedelta(days=7),
            downloaded_date=now - timedelta(days=30),
            integrity_hash="sha256:" + entry["slug"].replace("-", "")[:56].ljust(56, "0"),
        )
        db.add(ds)
        db.flush()

        # Create initial version record
        version = DatasetVersion(
            dataset_id=ds.id,
            version=entry["version"],
            record_count=entry["record_count"],
            quality_score=entry["quality_score"],
            integrity_hash=ds.integrity_hash,
            changelog="Initial dataset registration",
            is_current=True,
        )
        db.add(version)
        seeded += 1

    if seeded:
        db.commit()


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(tags=["Datasets"])

DOMAIN_FILTERS = ["Information Technology", "Electronics", "Healthcare", "Geography", "Sports"]


@router.get("/solution-packs")
def list_solution_packs():
    """Return all available Solution Packs."""
    with Timer() as t:
        pass
    return success_response(
        data=SOLUTION_PACKS,
        count=len(SOLUTION_PACKS),
        message="Solution packs retrieved.",
        execution_time_ms=t.elapsed_ms,
    )


@router.get("/solution-packs/{pack_id}")
def get_solution_pack(pack_id: str, db: Session = Depends(get_db)):
    """Return a single Solution Pack with full dataset metadata."""
    with Timer() as t:
        pack = next((p for p in SOLUTION_PACKS if p["id"] == pack_id), None)
        if not pack:
            raise HTTPException(status_code=404, detail="Solution pack not found.")

        datasets_detail = []
        for slug in pack["datasets"]:
            ds = db.query(Dataset).filter_by(slug=slug, is_active=True).first()
            if ds:
                datasets_detail.append(ds.to_dict(include_provenance=False))

    return success_response(
        data={**pack, "datasets_detail": datasets_detail},
        execution_time_ms=t.elapsed_ms,
    )


@router.get("/datasets")
def list_datasets(
    search: Optional[str] = Query(None, max_length=200),
    domain: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    connector: Optional[str] = Query(None),
    min_quality: Optional[float] = Query(None, ge=0.0, le=10.0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("popularity", pattern="^(popularity|quality_score|name|record_count|created_at)$"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """List and search datasets with filters, sorting, and pagination."""
    with Timer() as t:
        query = db.query(Dataset).filter_by(is_active=True)

        if search:
            term = f"%{search.lower()}%"
            query = query.filter(
                Dataset.name.ilike(term)
                | Dataset.description.ilike(term)
                | Dataset.tags.ilike(term)
                | Dataset.category.ilike(term)
                | Dataset.domain.ilike(term)
            )
        if domain:
            query = query.filter(Dataset.domain == domain)
        if category:
            query = query.filter(Dataset.category.ilike(f"%{category}%"))
        if connector:
            query = query.filter(Dataset.connector == connector)
        if min_quality is not None:
            query = query.filter(Dataset.quality_score >= min_quality)

        total = query.count()

        sort_col = getattr(Dataset, sort_by, Dataset.popularity)
        query = query.order_by(sort_col.desc())

        offset, limit = paginate(page, page_size)
        datasets = query.offset(offset).limit(limit).all()

        # Record search query for analytics
        if search and current_user:
            sh = SearchHistory(
                user_id=current_user.id,
                query=search,
                results_count=total,
            )
            db.add(sh)
            db.commit()

    return success_response(
        data=[ds.to_dict(include_provenance=False) for ds in datasets],
        count=len(datasets),
        total=total,
        page=page,
        message=f"Found {total} dataset(s).",
        execution_time_ms=t.elapsed_ms,
    )


@router.get("/datasets/{slug}")
def get_dataset(
    slug: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Get full dataset metadata including schema, statistics, and provenance."""
    with Timer() as t:
        ds = db.query(Dataset).filter_by(slug=slug, is_active=True).first()
        if not ds:
            raise HTTPException(status_code=404, detail="Dataset not found.")

        ds.popularity += 1
        db.commit()

        saved = False
        if current_user:
            saved = db.query(SavedDataset).filter_by(
                user_id=current_user.id, dataset_id=ds.id
            ).first() is not None

        data = ds.to_dict(include_provenance=True)
        data["is_saved"] = saved

    return success_response(data=data, execution_time_ms=t.elapsed_ms)


@router.get("/datasets/{slug}/data")
def get_dataset_data(
    slug: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve paginated dataset records.
    Requires authentication (API key or JWT).
    For V1 returns curated sample rows; the sync engine populates full data.
    """
    with Timer() as t:
        ds = db.query(Dataset).filter_by(slug=slug, is_active=True).first()
        if not ds:
            raise HTTPException(status_code=404, detail="Dataset not found.")

        # Use HuggingFace Parquet cache
        from hf_storage import hf_storage
        import pandas as pd
        import math

        local_path = hf_storage.download_dataset(ds.category, ds.slug, ds.version)
        if not local_path:
            raise HTTPException(status_code=503, detail="Dataset temporarily unavailable from registry.")

        try:
            # Load from Parquet
            df = pd.read_parquet(local_path)
            total = len(df)

            offset, limit = paginate(page, page_size)
            paginated_df = df.iloc[offset : offset + limit]

            # Convert to JSON string and back to dicts to handle Pandas data types safely
            import json
            paginated_json_str = paginated_df.to_json(orient="records", date_format="iso")
            paginated = json.loads(paginated_json_str)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading dataset cache: {str(e)}")

        # Track usage
        from models import UsageStat
        stat = UsageStat(
            user_id=current_user.id,
            endpoint=f"/api/v1/datasets/{slug}/data",
            dataset_id=ds.id,
            response_time_ms=0,
            status_code=200,
        )
        db.add(stat)
        db.commit()

    return success_response(
        data=paginated,
        count=len(paginated),
        total=total,
        page=page,
        message=f"Data from {ds.name}",
        execution_time_ms=t.elapsed_ms,
    )


@router.post("/datasets/{slug}/save")
def save_dataset(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a dataset to the user's collection."""
    ds = db.query(Dataset).filter_by(slug=slug, is_active=True).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    existing = db.query(SavedDataset).filter_by(user_id=current_user.id, dataset_id=ds.id).first()
    if existing:
        return success_response(message="Dataset already saved.")

    saved = SavedDataset(user_id=current_user.id, dataset_id=ds.id)
    db.add(saved)
    db.commit()
    return success_response(message="Dataset saved to your collection.")


@router.delete("/datasets/{slug}/save")
def unsave_dataset(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a dataset from the user's collection."""
    ds = db.query(Dataset).filter_by(slug=slug, is_active=True).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    saved = db.query(SavedDataset).filter_by(user_id=current_user.id, dataset_id=ds.id).first()
    if saved:
        db.delete(saved)
        db.commit()
    return success_response(message="Dataset removed from your collection.")


@router.get("/domains")
def list_domains(db: Session = Depends(get_db)):
    """Return dataset counts grouped by domain."""
    with Timer() as t:
        from sqlalchemy import func
        results = (
            db.query(Dataset.domain, func.count(Dataset.id).label("count"))
            .filter_by(is_active=True)
            .group_by(Dataset.domain)
            .all()
        )
    return success_response(
        data=[{"domain": r.domain, "count": r.count} for r in results],
        execution_time_ms=t.elapsed_ms,
    )
