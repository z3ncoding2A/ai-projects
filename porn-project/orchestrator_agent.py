#!/usr/bin/env python3
"""
orchestrator_agent.py
Autonomous Scraper & Pipeline Orchestrator built with the Google Antigravity SDK.

Responsibilities:
- Audits video library health & missing assets
- Orchestrates multi-page scraping & asset downloading
- Automatically repairs expired/missing thumbnails via fallback cascades
- Semantic classification & categorization of newly scraped media
- Periodic health checks and pipeline self-annealing
"""

import os
import sys
import json
import asyncio
import logging
from typing import Optional

from google.antigravity import Agent, LocalAgentConfig, ToolContext
from google.antigravity.triggers import every, TriggerContext

# Project directory
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_FILE = os.path.join(ROOT_DIR, "videos.json")
CATEGORIES_FILE = os.path.join(ROOT_DIR, "categories.json")
CATEGORIES_SCHEMA_FILE = os.path.join(ROOT_DIR, "categories-schema.json")
BLACKLIST_FILE = os.path.join(ROOT_DIR, "blacklist.txt")

# Import deterministic execution tool functions
from execution.scraper_pipeline import run_audit, run_scrape, run_verify_thumbs, load_json, save_json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# ── Custom Tool Functions for Antigravity Agent ──────────────────────────────

def audit_catalog_health() -> str:
    """Audits the video catalog database and returns health metrics.

    Returns:
        JSON string containing total videos, categorized count, uncategorized count,
        missing local thumbnails count, and overall health score.
    """
    report = run_audit()
    return json.dumps(report, indent=2)

def scrape_new_videos(target_url: str = "https://www.pornhub.com/users/z3ncoding/videos/recent", max_pages: int = 1) -> str:
    """Scrapes new videos from the specified user profile or tag search URL.

    Args:
        target_url: The profile or tag URL to scrape.
        max_pages: Number of pages of results to scrape (default 1).

    Returns:
        Summary JSON with counts of newly scraped, added, and updated videos.
    """
    result = run_scrape(target_url=target_url, max_pages=max_pages, auto_save=True)
    return json.dumps(result, indent=2)

def repair_missing_thumbnails(limit: int = 50) -> str:
    """Repairs and downloads missing or broken video thumbnails using multi-stage fallbacks.

    Args:
        limit: Maximum number of thumbnails to repair in this batch (default 50).

    Returns:
        JSON summary of verified and repaired thumbnails.
    """
    result = run_verify_thumbs(limit=limit)
    return json.dumps(result, indent=2)

def get_category_schema() -> str:
    """Retrieves the active hierarchical category taxonomy and schema.

    Returns:
        JSON list of category nodes with id, name, icon, and description.
    """
    schema = load_json(CATEGORIES_SCHEMA_FILE, [])
    return json.dumps(schema, indent=2)

def apply_video_category(viewkey: str, category_id: str) -> str:
    """Assigns a category to a specific video in categories.json.

    Args:
        viewkey: The unique identifier of the video.
        category_id: The target category ID (e.g. 'public', 'most', 'explode', etc.).

    Returns:
        Status confirmation string.
    """
    categories = load_json(CATEGORIES_FILE, {})
    if category_id == 'none':
        if viewkey in categories:
            del categories[viewkey]
    else:
        categories[viewkey] = category_id
    save_json(CATEGORIES_FILE, categories)
    return f"Successfully assigned video {viewkey} to category '{category_id}'."

def generate_library_dossier() -> str:
    """Generates an executive summary markdown report of the library catalog status.

    Returns:
        Markdown-formatted library status dossier.
    """
    audit = run_audit()
    categories = load_json(CATEGORIES_FILE, {})
    schema = load_json(CATEGORIES_SCHEMA_FILE, [])

    schema_names = {node["id"]: node.get("name", node["id"]) for node in schema}

    # Count distribution
    cat_counts = {}
    for cat in categories.values():
        name = schema_names.get(cat, cat)
        cat_counts[name] = cat_counts.get(name, 0) + 1

    lines = [
        "# Video Library Status Dossier",
        f"- **Total Catalog Items**: {audit.get('total_videos', 0):,}",
        f"- **Categorized Videos**: {audit.get('categorized_count', 0):,}",
        f"- **Uncategorized Videos**: {audit.get('uncategorized_count', 0):,}",
        f"- **Blacklisted Items**: {audit.get('blacklisted_count', 0):,}",
        f"- **Missing Local Thumbnails**: {audit.get('missing_local_thumbnails', 0):,}",
        f"- **Library Health Score**: {audit.get('health_score', 'N/A')}",
        "",
        "## Category Distribution",
    ]
    for cat_name, count in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"- **{cat_name}**: {count:,} videos")

    return "\n".join(lines)

# ── Periodic Background Check Trigger ────────────────────────────────────────

async def periodic_library_health_check(ctx: TriggerContext):
    """Periodic trigger that evaluates catalog health every 30 minutes."""
    logging.info("TRIGGER: Evaluating catalog health...")
    audit = run_audit()
    if audit.get("missing_local_thumbnails", 0) > 0:
        logging.info(f"TRIGGER: Found {audit['missing_local_thumbnails']} missing thumbnails. Repairing...")
        run_verify_thumbs(limit=30)

# ── Antigravity Agent Configuration ──────────────────────────────────────────

SYSTEM_INSTRUCTIONS = """You are the Autonomous Scraper & Pipeline Orchestrator for the z3ncoding Video Library workstation.

Your responsibilities:
1. Orchestrate scraping pipelines to discover and ingest new video metadata.
2. Ensure catalog integrity: verify thumbnails, repair missing assets using fallbacks, and check stream links.
3. Categorize uncategorized media accurately using the category schema.
4. Provide structured, actionable status dossiers and health reports.

When executing tasks:
- Always check catalog health first via `audit_catalog_health`.
- If missing thumbnails are found, invoke `repair_missing_thumbnails`.
- Report clear, transparent metrics on new imports and catalog state.
"""

def create_orchestrator_agent(enable_periodic_trigger: bool = False) -> Agent:
    triggers = []
    if enable_periodic_trigger:
        triggers.append(every(1800, periodic_library_health_check))

    config = LocalAgentConfig(
        system_instructions=SYSTEM_INSTRUCTIONS,
        tools=[
            audit_catalog_health,
            scrape_new_videos,
            repair_missing_thumbnails,
            get_category_schema,
            apply_video_category,
            generate_library_dossier,
        ],
        triggers=triggers,
    )
    return Agent(config=config)

# ── Runner ───────────────────────────────────────────────────────────────────

async def run_autonomous_cycle():
    """Runs a single end-to-end autonomous audit and repair cycle."""
    print("\n🚀 Starting Autonomous Pipeline Cycle with Google Antigravity SDK...\n")
    async with create_orchestrator_agent(enable_periodic_trigger=False) as agent:
        prompt = (
            "Please perform a complete audit of the video library catalog. "
            "If there are any missing thumbnails, repair a batch of them. "
            "Then output an executive summary dossier of the library status."
        )
        print(f"User Prompt: {prompt}\n")
        response = await agent.chat(prompt)
        async for chunk in response:
            print(chunk, end="", flush=True)
        print("\n\n[✓] Autonomous Pipeline Cycle Completed.")

async def run_interactive_mode():
    """Starts an interactive REPL with the Antigravity Orchestrator Agent."""
    print("\n⚡ Starting Interactive Antigravity Orchestrator Shell (Type 'exit' to quit)...\n")
    async with create_orchestrator_agent(enable_periodic_trigger=False) as agent:
        while True:
            try:
                user_input = input("\nOrchestrator> ").strip()
                if not user_input or user_input.lower() in ('exit', 'quit'):
                    break
                response = await agent.chat(user_input)
                print("\nAgent: ", end="")
                async for chunk in response:
                    print(chunk, end="", flush=True)
                print()
            except (KeyboardInterrupt, EOFError):
                break

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Antigravity Scraper & Pipeline Orchestrator")
    parser.add_argument("--interactive", action="store_true", help="Run interactive conversational shell")
    args = parser.parse_args()

    if args.interactive:
        asyncio.run(run_interactive_mode())
    else:
        asyncio.run(run_autonomous_cycle())
