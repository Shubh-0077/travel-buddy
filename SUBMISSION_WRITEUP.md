# TravelBuddy — Submission Write-Up

## Problem Statement

Millions of travelers face decision fatigue when planning a trip: too many flight options, hotel comparisons across a dozen sites, and itineraries that don't match their personal interests. A traveler typically spends hours researching, cross-referencing, and manually building a plan — only to second-guess their choices.

TravelBuddy solves this by acting as an intelligent travel concierge. It takes a simple natural-language request, securely processes it, retrieves relevant flight and hotel options via MCP tools, seeks human approval before committing, and then generates a personalized day-by-day itinerary. The result: a complete, personalized travel plan in minutes, not hours.

---

## Solution Architecture

```
START → Security Checkpoint → Orchestrator → Approval Check (HITL) → Itinerary Agent
                ↓ (SECURITY_EVENT)
         Security Error Node
```

- **Security Checkpoint**: First node; scrubs PII, detects prompt injection, validates destinations, logs every decision.
- **Orchestrator**: Delegates to the Flight & Hotel Agent via `AgentTool`. Uses MCP tools to search real options.
- **Approval Check Node**: Pauses the workflow (`RequestInput`) for the human to approve or reject flight/hotel options.
- **Itinerary Agent**: Generates a day-by-day plan using `get_itinerary_ideas` from the MCP Server.
- **Security Error Node**: Terminal node for blocked inputs.

---

## Concepts Used

| Concept | File | Description |
|---|---|---|
| **ADK Workflow** | `app/agent.py` | `Workflow(name=..., edges=[...])` graph with function nodes + LlmAgent nodes |
| **LlmAgent** | `app/agent.py` | `flight_hotel_agent`, `itinerary_agent`, `orchestrator` |
| **AgentTool** | `app/agent.py` | Orchestrator delegates to sub-agents via `AgentTool(flight_hotel_agent)` |
| **ctx.state** | `app/agent.py` | Saves `scrubbed_input` and `flight_hotel_recommendations` across nodes |
| **MCP Server** | `app/mcp_server.py` | `FastMCP` server exposing `search_flights`, `search_hotels`, `get_itinerary_ideas` |
| **MCPToolset** | `app/agent.py` | Wired into `flight_hotel_agent` and `itinerary_agent` via `StdioConnectionParams` |
| **Security Checkpoint** | `app/agent.py` | `security_checkpoint()` function node with PII scrubbing + injection detection |
| **RequestInput (HITL)** | `app/agent.py` | `approval_check_node` yields `RequestInput` to pause for user approval |
| **ResumabilityConfig** | `app/agent.py` | `App(resumability_config=ResumabilityConfig(is_resumable=True))` |
| **Agents CLI** | `Makefile`, `agents-cli-manifest.yaml` | Scaffold, playground, install targets |

---

## Security Design

| Control | Implementation | Why It Matters |
|---|---|---|
| **PII Scrubbing** | Regex strips emails, phone numbers, passport numbers from user input | Prevents sensitive traveler data from being sent raw to the LLM |
| **Prompt Injection Detection** | Keyword scan for "ignore previous instructions", "system prompt", etc. | Prevents adversarial inputs from hijacking agent behavior |
| **Unsafe Destination Filter** | Checks for sanctioned/conflict zones (North Korea, Syria, Somalia) | Prevents liability and ensures responsible use |
| **Structured Audit Log** | JSON log on every request with severity (INFO/WARNING/CRITICAL) | Full traceability for compliance and debugging |
| **SECURITY_EVENT routing** | Critical inputs route to `security_error_node` and terminate gracefully | Fail-safe behavior without crashing the agent |

---

## MCP Server Design

**File**: `app/mcp_server.py`  
**Server name**: `travel-buddy-mcp`  
**Transport**: stdio (FastMCP)

| Tool | Used By | Purpose |
|---|---|---|
| `search_flights(destination, date)` | `flight_hotel_agent` | Returns simulated flight options with prices, times, duration |
| `search_hotels(destination, checkin, checkout)` | `flight_hotel_agent` | Returns simulated hotel options with ratings and amenities |
| `get_itinerary_ideas(destination, interests)` | `itinerary_agent` | Returns day-part activity suggestions tailored to traveler interests |

---

## Human-in-the-Loop (HITL) Flow

The `approval_check_node` implements HITL using `RequestInput`:

1. After the orchestrator returns flight/hotel recommendations, the node yields a `RequestInput` with `interrupt_id="user_approval"`.
2. The workflow pauses. The ADK web playground displays the question to the user.
3. The user types `yes` or `no` (or feedback).
4. On resume, `ctx.resume_inputs["user_approval"]` contains the response.
5. If `yes` → routes to `itinerary_agent`. If `no` → routes back to `orchestrator` with feedback.

**Why it matters for travel**: Flight and hotel choices involve real money. A human must confirm before the agent proceeds to building a full itinerary — preventing wasted planning effort if the options don't suit the traveler.

---

## Demo Walkthrough

Refer to the 3 sample test cases in `README.md`:

1. **Case 1**: Send a natural language travel request → see flight/hotel options surface from MCP tools.
2. **Case 2**: Approve → see a personalized 7-day day-by-day itinerary generated by the itinerary agent.
3. **Case 3**: Send an injection prompt → see the security checkpoint block it immediately.

---

## Impact / Value Statement

**Who benefits**: Everyday travelers who want a personalized, AI-assisted trip plan without spending hours on research.

**How it helps**:
- Reduces planning time from hours to minutes
- Keeps sensitive traveler data private (PII scrubbing)
- Ensures human oversight on key decisions (HITL approval)
- Demonstrates how multi-agent orchestration, MCP tool integration, and security best practices combine in a real-world concierge use case

TravelBuddy is a showcase of how ADK's Workflow graph, MCP tooling, and human-in-the-loop design can power genuinely useful, safe, and production-ready AI agents.
