# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Conversational SLO (Service Level Objective) Manager that uses AWS Bedrock Claude Sonnet 4.5 to analyze natural language queries about service reliability and orchestrate data fetching from multiple sources (ClickHouse, Watermelon API, etc.).

**Key Features:**
- Natural language intent classification → automated data source selection
- Intent enrichment for comprehensive responses
- Multi-source data aggregation (Java stats, behavior patterns)
- Time range resolution with automatic index granularity
- Currently CLI-based (FastAPI in requirements for future REST API)

## Development Commands

### Environment Setup
```bash
# Python 3.12 or higher recommended
source venv/bin/activate
pip install -r requirements.txt
```

### Running the System

**Orchestrator (Primary Entry Point)**
```bash
python orchestrator.py
# Interactive CLI: takes queries, returns aggregated data from all sources
```

**Example Usage (Programmatic)**
```bash
python example_usage.py
# Demonstrates: basic queries, exports, raw data access, error handling
```

**Testing Individual Components**
```bash
# Intent classifier only (no data fetching)
cd intent_classifier && python intent_classifier.py

# Test time resolution
cd utils && python time_range_resolver.py
cd intent_classifier && python timestamp.py

# Test adapters
cd context_adapter && python memory_adapter.py
cd context_adapter && python java_stats.py
```

### Module Imports

**From orchestrator/external scripts:**
```python
from intent_classifier import IntentClassifier, TimestampResolver
from context_adapter import fetch_api_data, transform_to_llm_format
from context_adapter import fetch_behavior_service_memory, transform_behavior_memory
from utils import resolve_time_range_from_query, resolve_time_range
```

**Within modules:** Use relative imports (e.g., `from timestamp import TimestampResolver`)

## Architecture

### End-to-End Flow

```
User Query
    ↓
Orchestrator (orchestrator.py)
    ↓
Intent Classifier (AWS Bedrock Claude 4.5)
    ├─ Extracts: primary_intent, secondary_intents, entities
    ├─ Enrichment: Adds related intents via enrichment_rules.yaml
    ├─ Mapping: Maps intents → data_sources via intent_categories.yaml
    └─ Time Resolution: Converts time_range → UTC timestamps + index
    ↓
Adapter Routing (based on data_sources)
    ├─ java_stats_api → Watermelon API (SLO metrics, health, burn rate)
    ├─ clickhouse → Behavior memory (patterns, anomalies)
    ├─ postgres → (not yet implemented)
    └─ opensearch → (not yet implemented)
    ↓
Response Aggregation
    └─ Returns: {classification, time_resolution, data, metadata}
```

### Core Components

**1. Intent Classification** (`intent_classifier/intent_classifier.py`)
- Sends query to AWS Bedrock Claude Sonnet 4.5
- Extracts primary_intent, secondary_intents, entities (service, time_range, comparison_range)
- Maps intents to data sources using `intent_categories.yaml`
- Applies enrichment rules from `enrichment_rules.yaml`
- Returns classification + timestamp_resolution + data_sources list

**2. Orchestrator** (`orchestrator.py`)
- Main entry point coordinating full pipeline
- Routes to appropriate adapters based on data_sources
- Aggregates responses into unified JSON structure
- Handles errors gracefully (adapter failures don't crash system)
- Default app_id: 31854 (hardcoded, can be made configurable)

**3. Context Adapters** (`context_adapter/`)
- **`java_stats.py`**: Watermelon API for real-time SLO metrics
  - Requires: start_time_ms, end_time_ms, username, password, application_id, index
  - Returns: Error budget, latency P95, health status, burn rate
  - Keycloak auth → Bearer token → API call

- **`memory_adapter.py`**: ClickHouse for behavior patterns
  - Requires: start_time, end_time, app_id, sid (optional)
  - Returns: Baseline states, pattern types, confidence scores
  - Direct ClickHouse SQL queries with 30s timeout

**4. Time Range Resolution** (`intent_classifier/timestamp.py`, `utils/time_range_resolver.py`)
- Two implementations:
  - `timestamp.py`: Static patterns (today, yesterday, last_7_days, past_N_days)
  - `time_range_resolver.py`: Dynamic NLP parsing with dateparser
- Converts string → UTC milliseconds + determines index granularity:
  - HOURLY: ≤3 days
  - DAILY: >3 days
- Min duration: 5 minutes, Max: 2 years

### Intent Categories (9 Categories)

- **STATE**: Current status (health, alerts, incidents)
- **TREND**: Changes over time (drift, comparison, burn rate)
- **PATTERN**: Recurring behavior (seasonality, time-based anomalies)
- **CAUSE**: Root cause analysis (config drift, failures)
- **IMPACT**: Blast radius (customer impact, affected services)
- **ACTION**: Remediation (mitigation, runbook, rollback)
- **PREDICT**: Future risk (failure prediction, capacity)
- **OPTIMIZE**: Performance tuning (bottlenecks, query optimization)
- **EVIDENCE**: Audit trail (timeline, change history)

Each category contains multiple specific intents (50+ total) defined in `intent_categories.yaml`.

### Data Sources

| Source | Status | Description | Config Location |
|--------|--------|-------------|-----------------|
| `java_stats_api` | ✅ Implemented | Real-time SLO metrics from Watermelon API | Keycloak auth in .env |
| `clickhouse` | ✅ Implemented | Historical behavior patterns and AI memory | Credentials in code |
| `postgres` | ⏳ Planned | SLO definitions, alerts, incidents | Not implemented |
| `opensearch` | ⏳ Planned | Logs, traces, full-text search | Not implemented |

## Configuration Files

### YAML Configs (`intent_classifier/`)

**`intent_categories.yaml`**
- Defines all 50+ intents with descriptions, examples
- Maps each intent to required data_sources
- Used to build LLM system prompt dynamically
- LLM returns ONLY intent classification (not data sources)

**`enrichment_rules.yaml`**
- Maps primary intents → secondary intents
- Example: ROOT_CAUSE_SINGLE → adds UNDERCURRENTS_TREND + MITIGATION_STEPS
- Creates comprehensive responses without explicit user request

**`data_sources.yaml`**
- Defines data source capabilities, timeouts, connection settings
- Not currently used at runtime (static config reference)

### Environment Variables (`.env`)

**Required:**
```bash
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-5-20250929-v1:0
MAX_TOKENS=500
TEMPERATURE=0.0
```

**Optional (defaults provided):**
```bash
JAVA_STATS_USERNAME=wmadmin
JAVA_STATS_PASSWORD=your_password
```

## Key Design Patterns

### Declarative Intent-to-Data-Source Mapping
- Intents specify required data_sources in YAML
- LLM only classifies intent + extracts entities
- Code maps intents → data sources (prevents LLM hallucination)
- Ensures reliable data source selection

### Two-Stage Time Resolution
- LLM extracts time_range as string ("past_10_days")
- Python converts to exact UTC timestamps
- Separates intent understanding from timestamp math

### Auto-Enrichment
- Query: "Why is payment-api failing?"
- Primary: ROOT_CAUSE_SINGLE
- Enriched: + UNDERCURRENTS_TREND + MITIGATION_STEPS
- Pulls comprehensive data automatically

### Adapter Isolation
- Each adapter is independent, can fail without crashing system
- Orchestrator aggregates available data
- Missing adapters marked as "not_implemented" in response

## Important Notes

### Using the Orchestrator
- **Main entry point:** `python orchestrator.py`
- Takes natural language query → returns aggregated JSON
- Currently supports 2 data sources: java_stats_api, clickhouse
- Default app_id: 31854 (single application for now)
- Supports both interactive CLI and programmatic usage

### Orchestrator Response Structure
```python
{
  "success": True,
  "query": "user query",
  "classification": {
    "primary_intent": "SERVICE_HEALTH",
    "secondary_intents": [],
    "enriched_intents": ["SERVICE_HEALTH", "UNDERCURRENTS_TREND"],
    "entities": {"service": "payment-api", "time_range": "past_7_days"}
  },
  "time_resolution": {
    "start_time": 1769691000000,  # Unix ms
    "end_time": 1770296000000,
    "index": "DAILY",
    "time_range": "past_7_days"
  },
  "data_sources_used": ["java_stats_api", "clickhouse"],
  "data": {
    "java_stats_api": {...},
    "clickhouse": {...}
  },
  "metadata": {
    "app_id": 31854,
    "service": "payment-api",
    "enrichment_applied": True
  }
}
```

### Credentials and Security
- AWS credentials in `.env` (required)
- Java Stats credentials in `.env` (optional, defaults provided)
- ClickHouse credentials hardcoded in `memory_adapter.py`:
  - URL: `http://ec2-47-129-241-41.ap-southeast-1.compute.amazonaws.com:8123`
  - Auth: `("wm_test", "Watermelon@123")`
- Never commit credential changes
- Consider migrating all hardcoded credentials to .env

### Testing Status
- **No formal unit tests** currently in the codebase
- Each module has standalone test functions (run files directly)
- Test manually by running individual components
- Example: `cd intent_classifier && python intent_classifier.py`

### Error Handling
- ClickHouse: 30s timeout, auth error detection
- Watermelon API: Token refresh, SSL warning suppression
- Missing YAML: Returns empty dict with error message
- LLM JSON: Handles extra text around JSON response

### Common Gotchas
- Intent classifier must run from `intent_classifier/` directory when standalone (YAML configs loaded from same dir)
- Timestamps always in milliseconds (not seconds)
- Index granularity auto-determined: HOURLY (≤3 days) or DAILY (>3 days)
- Service name extraction from query is best-effort (LLM may not always detect)
- Comparison ranges not yet fully implemented in orchestrator

### Future Enhancements
- Add postgres and opensearch adapters
- Make app_id configurable (currently hardcoded to 31854)
- Add caching layer for repeated queries
- Implement REST API using FastAPI (already in requirements.txt)
- Add retry logic for failed adapter calls
- Support comparison_range queries end-to-end
