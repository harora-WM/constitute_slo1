# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Conversational SLO (Service Level Objective) Manager that uses AWS Bedrock Claude Sonnet 4.5 to analyze natural language queries about service reliability and orchestrate data fetching from multiple sources with intelligent pattern detection.

**Key Features:**
- Natural language intent classification → automated data source selection
- Intent-based pattern query routing (7 specialized pattern types)
- Service name → Service ID resolution with fuzzy matching
- Multi-source data aggregation (Java stats, behavior patterns)
- Time range resolution with automatic index granularity
- Pattern-specific ClickHouse queries (drift, seasonal, volume-driven, etc.)
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
# Interactive CLI with intent routing and service matching
```

**Generate Service Mapping**
```bash
python fetch_services.py
# Fetches all services from ClickHouse → generates services.yaml
# Run this when services change or for initial setup
```

**Test Service Matching**
```bash
python utils/service_matcher.py "dashboard-stats"
# Tests fuzzy matching of service names to service IDs
```

**Testing Individual Components**
```bash
# Intent classifier
cd intent_classifier && python intent_classifier.py

# Time resolution
cd utils && python time_range_resolver.py

# Adapters
cd context_adapter && python memory_adapter.py
cd context_adapter && python java_stats.py

# Intent-based queries
cd context_adapter && python intent_based_queries.py

# Integration examples
python example_intent_integration.py
python example_service_matching.py
python example_java_stats_intents.py  # Test intent-based java_stats functions
```

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
Service Resolution (if service mentioned)
    └─ ServiceMatcher: Fuzzy match service name → service_id from services.yaml
    ↓
Adapter Routing (based on data_sources)
    ├─ java_stats_api → Watermelon API (SLO metrics, health, burn rate + service_id)
    └─ clickhouse → Intent-based pattern queries
         ├─ UNDERCURRENTS_TREND → sudden_spike, sudden_drop, drift_up, drift_down
         ├─ CAPACITY_RISK → volume_driven patterns
         ├─ SEASONALITY_PATTERN → weekly patterns (grouped by day)
         ├─ TIME_WINDOW_ANOMALY → daily patterns (grouped by hour)
         ├─ RECURRING_INCIDENT → historical patterns before incident
         ├─ HISTORICAL_COMPARISON → (under progress)
         └─ RISK_PREDICTION → (under progress)
    ↓
Response Aggregation
    └─ Returns: {classification, time_resolution, data, metadata}
```

### Core Components

**1. Intent Classification** (`intent_classifier/intent_classifier.py`)
- Sends query to AWS Bedrock Claude Sonnet 4.5
- Extracts primary_intent, secondary_intents, entities (service, time_range)
- Maps intents to data sources using `intent_categories.yaml`
- Applies enrichment rules from `enrichment_rules.yaml`
- Returns classification + timestamp_resolution + data_sources list

**2. Orchestrator** (`orchestrator.py`)
- Main entry point coordinating full pipeline
- Initializes ServiceMatcher for service name resolution
- Collects all intents (primary + secondary + enriched)
- Routes to appropriate adapters based on data_sources
- Passes resolved service_id to adapters
- Aggregates responses into unified JSON structure
- Default app_id: 31854 (hardcoded, can be made configurable)

**3. Service Matcher** (`utils/service_matcher.py`)
- Loads services.yaml (125 services for app 31854)
- Fuzzy matches service names to service IDs using SequenceMatcher
- Supports substring matching with score boosting
- Returns ranked matches with similarity scores
- Used by orchestrator to resolve service names from queries

**4. Service Mapping Generator** (`fetch_services.py`)
- Fetches distinct services from ClickHouse `ai_service_features_hourly` table
- Creates services.yaml with service_id → service_name → service_path mapping
- Extracts clean service paths from full URLs
- Run this script when services change or for initial setup

**5. Context Adapters** (`context_adapter/`)

**Java Stats Adapter** (`java_stats.py`)
- Fetches real-time SLO metrics from Watermelon API
- Keycloak authentication → Bearer token → API call
- **Intent-based routing with 3 specialized functions**:
  - `get_current_health()` - **CURRENT_HEALTH** intent
    - Application-wide health for all services
    - Returns 4 arrays: unhealthy_services_eb, at_risk_services_eb, unhealthy_services_response, at_risk_services_response
  - `get_service_health()` - **SERVICE_HEALTH** intent
    - Health for a specific service (requires service_id)
    - Returns None if service_id not provided
    - Filters data to only include the specified service
  - `get_error_budget_status()` - **ERROR_BUDGET_STATUS** intent
    - Error budget data (EB category only)
    - Works with or without service_id
    - Returns EB health arrays: unhealthy_services_eb, at_risk_services_eb, healthy_services_eb
- All service records include `service_id` (from transactionId)

**Memory Adapter** (`memory_adapter.py`)
- Main orchestrator-facing function: `fetch_patterns_by_intent()`
- Routes intents to specialized pattern query functions
- Resolves service_name → service_id if needed
- Returns aggregated results from all applicable intent queries
- Backward compatible: Falls back to general query if no pattern intents

**Intent-Based Queries** (`intent_based_queries.py`)
- 7 specialized query functions for pattern-specific ClickHouse queries
- Each function targets specific pattern_type in `ai_service_behavior_memory` table
- Dispatcher: `dispatch_intent_query()` routes intent to appropriate function

**6. Time Range Resolution** (`intent_classifier/timestamp.py`, `utils/time_range_resolver.py`)
- Converts natural language time expressions to UTC milliseconds
- **"current" now maps to last 1 hour** (not zero duration)
- Determines index granularity: HOURLY (≤3 days) or DAILY (>3 days)
- Min duration: 5 minutes, Max: 2 years

### Intent-to-Pattern-Type Mapping

| Intent | Pattern Type(s) | Time Filter Logic | Use Case |
|--------|----------------|-------------------|----------|
| **UNDERCURRENTS_TREND** | ≤1h: sudden_spike, sudden_drop<br>>1h: drift_up, drift_down | Strict: detected_at within window | "What changed in last hour?" |
| **CAPACITY_RISK** | volume_driven | Overlap: pattern overlaps query window | "Show volume-driven services in last 30 days" |
| **SEASONALITY_PATTERN** | weekly | Overlap + group by day_of_week | "Do we have issues every Thursday?" |
| **TIME_WINDOW_ANOMALY** | daily | Overlap + group by hour_of_day | "Problems between 4-5 PM daily?" |
| **RECURRING_INCIDENT** | daily, weekly | Historical: patterns BEFORE incident | "Have we seen this before?" |
| **HISTORICAL_COMPARISON** | (under progress) | - | - |
| **RISK_PREDICTION** | (under progress) | - | - |

### Intent Categories (9 Categories)

Defined in `intent_classifier/intent_categories.yaml`:
- **STATE**: Current status (health, alerts, incidents)
- **TREND**: Changes over time (drift, comparison, burn rate)
- **PATTERN**: Recurring behavior (seasonality, anomalies)
- **CAUSE**: Root cause analysis
- **IMPACT**: Blast radius (customer/service impact)
- **ACTION**: Remediation (mitigation, runbook)
- **PREDICT**: Future risk (failure prediction, capacity)
- **OPTIMIZE**: Performance tuning
- **EVIDENCE**: Audit trail (timeline, change history)

Each category contains multiple specific intents (50+ total) with data source mappings.

## Key Files

### Core System
- `orchestrator.py` - Main orchestration with service matching
- `intent_classifier/intent_classifier.py` - LLM intent analysis
- `context_adapter/memory_adapter.py` - ClickHouse adapter with intent routing
- `context_adapter/java_stats.py` - Watermelon API adapter
- `context_adapter/intent_based_queries.py` - 7 pattern-specific query functions
- `utils/service_matcher.py` - Service name → ID fuzzy matching
- `utils/time_range_resolver.py` - Dynamic NLP time parsing

### Configuration
- `intent_classifier/intent_categories.yaml` - Intent→data source mapping (50+ intents)
- `intent_classifier/enrichment_rules.yaml` - Auto-enrichment rules
- `services.yaml` - Service ID mapping (generated by fetch_services.py)
- `.env` - AWS credentials, API credentials

### Utilities
- `fetch_services.py` - Generate services.yaml from ClickHouse
- `example_*.py` - Integration examples

## Data Sources

| Source | Status | Description | Credentials |
|--------|--------|-------------|-------------|
| `java_stats_api` | ✅ Implemented | Real-time SLO metrics, includes service_id | Keycloak in .env |
| `clickhouse` | ✅ Implemented | Pattern queries via intent_based_queries.py | Hardcoded in code |
| `postgres` | ⏳ Planned | SLO definitions, alerts, incidents | Not implemented |
| `opensearch` | ⏳ Planned | Logs, traces | Not implemented |

### ClickHouse Tables Used
- `ai_service_behavior_memory` - Pattern detection (drift, seasonal, volume)
- `ai_service_features_hourly` - Service inventory (for services.yaml generation)

## Critical Design Patterns

### 1. Intent-Based Query Routing
```python
# Orchestrator collects all intents
all_intents = {primary, *secondary, *enriched}

# Memory adapter routes to pattern-specific queries
fetch_patterns_by_intent(
    intents=all_intents,      # Set of intent names
    start_time=...,
    end_time=...,
    service_id=resolved_id    # From ServiceMatcher
)

# Dispatcher calls appropriate functions
if "CAPACITY_RISK" in intents:
    query_capacity_risk(...)  # Queries volume_driven patterns
if "SEASONALITY_PATTERN" in intents:
    query_seasonality_pattern(...)  # Queries weekly patterns
```

### 2. Service Name Resolution
```python
# Orchestrator uses ServiceMatcher
service_name = entities.get('service')  # From intent classifier
matches = service_matcher.find_matches(service_name, threshold=0.3)
service_id = matches[0]['service_id']  # Best match

# Pass to adapters
fetch_patterns_by_intent(..., service_id=service_id)
```

### 3. Time-Based Pattern Selection
```python
# UNDERCURRENTS_TREND logic
duration_hours = (end_time - start_time) / (1000 * 60 * 60)

if duration_hours <= 1:
    # "current" or "last 1 hour" → sudden changes ONLY
    pattern_types = ['sudden_spike', 'sudden_drop']
else:
    # > 1 hour → drift ONLY
    pattern_types = ['drift_up', 'drift_down']
```

### 4. Time Filter Strategies
```python
# UNDERCURRENTS_TREND: Strict boundaries (recent changes)
WHERE detected_at >= start AND detected_at <= end

# SEASONALITY/TIME_WINDOW/CAPACITY: Overlap (long-term patterns)
WHERE first_seen <= end AND last_seen >= start
```

### 5. Java Stats Intent-Based Routing
```python
# Orchestrator routes to specific java_stats functions based on intent
if "SERVICE_HEALTH" in intents:
    # Requires service_id, returns None if not provided
    get_service_health(app_id, start_time, end_time, service_id, index, username, password)

elif "ERROR_BUDGET_STATUS" in intents:
    # EB category only, service_id optional
    get_error_budget_status(app_id, start_time, end_time, index, username, password, service_id)

elif "CURRENT_HEALTH" in intents:
    # Application-wide health for all services
    get_current_health(app_id, start_time, end_time, index, username, password)
```

## Important Notes

### Service Matching
- ServiceMatcher loads services.yaml on orchestrator init
- Fuzzy matching with SequenceMatcher (threshold default: 0.3)
- Substring matches get score boost to 0.7
- Returns ranked matches with service_id, service_path, similarity_score
- Run `fetch_services.py` to regenerate services.yaml when services change

### Intent-Based Queries
- Pattern intents trigger specialized ClickHouse queries
- Each intent maps to specific pattern_type(s)
- Time filters vary: strict for UNDERCURRENTS, overlap for others
- UNDERCURRENTS duration determines pattern type (sudden vs drift)
- Non-pattern intents use general ClickHouse query (backward compatible)

### Time Resolution
- **"current" = last 1 hour** (not zero duration)
- Index: HOURLY (≤3 days), DAILY (>3 days)
- Always milliseconds (not seconds)
- Two implementations exist (timestamp.py and time_range_resolver.py)

### Java Stats API
- **Intent-based routing**: Different functions for different intents
  - **CURRENT_HEALTH**: Returns all services in the application
  - **SERVICE_HEALTH**: Filters to specific service_id (required, returns None if not provided)
  - **ERROR_BUDGET_STATUS**: Returns only EB category data, service_id optional
- Priority order: SERVICE_HEALTH > ERROR_BUDGET_STATUS > CURRENT_HEALTH
- All service records include `service_id` (from transactionId)
- CURRENT_HEALTH returns 4 arrays: unhealthy_eb, at_risk_eb, unhealthy_response, at_risk_response
- ERROR_BUDGET_STATUS returns 3 arrays: unhealthy_services_eb, at_risk_services_eb, healthy_services_eb
- SERVICE_HEALTH returns same structure as CURRENT_HEALTH but filtered for one service
- Each service object has: service_id, service, health, success, latency, volume, risk
- Use service_id to correlate with ClickHouse patterns

### ClickHouse Pattern Types
Current pattern_types in database:
- `daily` (15 records) - TIME_WINDOW_ANOMALY
- `weekly` (58 records) - SEASONALITY_PATTERN
- `volume_driven` (2 records) - CAPACITY_RISK
- `sudden_drop` (1 record) - UNDERCURRENTS_TREND

Not yet in database (queries will return 0):
- `drift_up`, `drift_down`, `sudden_spike`

### Credentials and Security
- AWS credentials in `.env` (required)
- Java Stats credentials in `.env` (optional, defaults provided)
- ClickHouse credentials **hardcoded** in multiple files:
  - `memory_adapter.py`
  - `intent_based_queries.py`
  - `fetch_services.py`
  - URL: `http://ec2-47-129-241-41.ap-southeast-1.compute.amazonaws.com:8123`
  - Auth: `("wm_test", "Watermelon@123")`
- **Never commit credential changes**
- **TODO**: Migrate all hardcoded credentials to .env

### Common Gotchas
- Pattern queries may return 0 records if:
  - Time window too short (use 30 days for volume/seasonal patterns)
  - Pattern type doesn't exist in database yet
  - Service name doesn't match any service_id
- ServiceMatcher requires services.yaml (run fetch_services.py first)
- Intent classifier must run from project root (YAML configs use relative paths)
- "current" queries now work (1 hour window, not zero duration)
- Service_id now available in Java Stats output for correlation
- **Java Stats intent routing**:
  - SERVICE_HEALTH requires service_id - returns None if not provided
  - Intent priority: SERVICE_HEALTH > ERROR_BUDGET_STATUS > CURRENT_HEALTH
  - Only one intent is processed per query (highest priority wins)
  - ERROR_BUDGET_STATUS returns only EB category (not RESPONSE category)

### Scalability Limitations
Current design works for single application, known pattern types. For production scale:
- **Missing**: Cross-application correlation, dependency graphs
- **Missing**: Flexible pattern detection (handles only predefined types)
- **Missing**: Temporal correlation ("what else happened around then?")
- **Missing**: Severity scoring, business impact assessment
- **Missing**: Root cause linking (deploys, config changes)
- **Missing**: Query optimization (batching, caching, indexing)
- **Hard-coded**: Application ID (31854), time thresholds (1 hour)
- **Hard-coded**: Pattern type strings, API endpoints, credentials

### Testing Status
- No formal unit tests
- Each module has standalone test functions (run files directly)
- Integration examples in `example_*.py` files
- Test manually by running components individually

## Environment Variables (.env)

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

## Example Queries

### Java Stats Intent Queries
```
✅ "What's the current health of my application?"
   → CURRENT_HEALTH → get_current_health() → all services, 4 arrays

✅ "Is payment-api healthy?"
   → SERVICE_HEALTH → get_service_health() → specific service_id required

✅ "Show me error budget status"
   → ERROR_BUDGET_STATUS → get_error_budget_status() → EB category only

✅ "Error budget for checkout-service"
   → ERROR_BUDGET_STATUS + service → EB data filtered by service_id
```

### ClickHouse Pattern Queries
```
✅ "What changed in the last hour?"
   → UNDERCURRENTS_TREND → sudden_spike, sudden_drop

✅ "Show volume-driven services in the last 30 days"
   → CAPACITY_RISK → volume_driven patterns → 2 records

✅ "Do we have issues every Thursday?"
   → SEASONALITY_PATTERN → weekly patterns → grouped by day

✅ "Problems between 4-5 PM daily?"
   → TIME_WINDOW_ANOMALY → daily patterns → grouped by hour

✅ "Have we seen this before?"
   → RECURRING_INCIDENT → historical daily/weekly patterns
```

## Future Enhancements
- Add postgres and opensearch adapters
- Complete HISTORICAL_COMPARISON and RISK_PREDICTION queries
- Make app_id configurable (currently hardcoded to 31854)
- Add caching layer for repeated queries
- Implement REST API using FastAPI
- Add retry logic for failed adapter calls
- Move all credentials to .env
- Add proper logging and monitoring
- Implement cross-application correlation
- Add service dependency awareness
- Implement severity scoring and impact assessment
