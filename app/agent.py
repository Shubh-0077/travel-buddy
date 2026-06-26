# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import logging
import os
import re
import sys
from zoneinfo import ZoneInfo

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App, ResumabilityConfig
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.models import Gemini
from google.adk.tools import AgentTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.workflow import Workflow, START
from google.genai import types
from mcp import StdioServerParameters

from app.config import config

# Logger
logger = logging.getLogger("travel_buddy")

# Absolute path to mcp_server.py
current_dir = os.path.dirname(os.path.abspath(__file__))
mcp_server_path = os.path.join(current_dir, "mcp_server.py")

# Specialized Agents
flight_hotel_agent = LlmAgent(
    name="flight_hotel_agent",
    model=Gemini(
        model=config.model,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are a specialized Flight & Hotel Planner.
Your job is to recommend flight options and hotel options based on destination, dates, budget, and travel preferences.
Use the search_flights and search_hotels tools to retrieve real options.
Provide 2-3 specific options for flights and hotels, including estimated pricing and details.
Explain your recommendations clearly.
""",
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[mcp_server_path],
                )
            ),
            tool_filter=["search_flights", "search_hotels"]
        )
    ]
)

itinerary_agent = LlmAgent(
    name="itinerary_agent",
    model=Gemini(
        model=config.model,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are a specialized Itinerary Planner.
Based on the approved flight and hotel recommendations, generate a detailed day-by-day sightseeing and activity itinerary.
Use the get_itinerary_ideas tool to find fun things to do in the destination based on user interests.
Include morning, afternoon, and evening suggestions. Keep it highly engaging, practical, and tailored to the destination.
""",
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[mcp_server_path],
                )
            ),
            tool_filter=["get_itinerary_ideas"]
        )
    ]
)

# Orchestrator Agent
orchestrator = LlmAgent(
    name="orchestrator",
    model=Gemini(
        model=config.model,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the TravelBuddy Orchestrator.
Your goal is to coordinate a traveler's planning.
Use the flight_hotel_agent tool first to recommend flights and hotels for their destination and preferences.
Once you receive the flight/hotel recommendations from the tool, present them to the user and ask: 'Do you approve these flight and hotel options? Please reply with YES or NO.'
Do not generate the detailed daily itinerary yourself. Only use the tools to retrieve information.
""",
    tools=[AgentTool(flight_hotel_agent), AgentTool(itinerary_agent)]
)

# Security Checkpoint
def security_checkpoint(ctx: Context, node_input: types.Content):
    # Extract user text input
    text = ""
    if isinstance(node_input, types.Content):
        for part in node_input.parts:
            if part.text:
                text += part.text
    elif isinstance(node_input, str):
        text = node_input
    else:
        text = str(node_input)
        
    # 1. PII Scrubbing
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    scrubbed_text = re.sub(email_pattern, "[EMAIL_REDACTED]", text)
    
    passport_pattern = r'\b[A-Z0-9]{6,9}\b'
    scrubbed_text = re.sub(passport_pattern, "[PASSPORT_REDACTED]", scrubbed_text)
    
    phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
    scrubbed_text = re.sub(phone_pattern, "[PHONE_REDACTED]", scrubbed_text)
    
    # 2. Prompt Injection Detection
    injection_keywords = ["ignore previous instructions", "system prompt", "override rules", "bypass security"]
    is_injection = any(kw in text.lower() for kw in injection_keywords)
    
    # 3. Domain Specific Check: Destination validation
    unsafe_destinations = ["north korea", "syria", "somalia"]
    contains_unsafe_destination = any(dest in text.lower() for dest in unsafe_destinations)
    
    # 4. Structured JSON Audit Log
    audit_log = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "session_id": ctx.session.id if ctx.session else "none",
        "input_length": len(text),
        "pii_detected": scrubbed_text != text,
        "injection_detected": is_injection,
        "unsafe_destination_detected": contains_unsafe_destination,
        "severity": "INFO"
    }
    
    if is_injection or contains_unsafe_destination:
        audit_log["severity"] = "CRITICAL"
        print(json.dumps(audit_log))
        reason = "Prompt injection attempt detected." if is_injection else "Unsafe destination requested."
        return Event(output=reason, route="SECURITY_EVENT")
    
    if scrubbed_text != text:
        audit_log["severity"] = "WARNING"
    
    print(json.dumps(audit_log))
    
    # Save scrubbed input to state and pass downstream
    ctx.state["scrubbed_input"] = scrubbed_text
    return Event(output=scrubbed_text, route="__DEFAULT__")

# Security Error Node
def security_error_node(node_input: str):
    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=f"❌ Security Block: {node_input}")]
        )
    )
    yield Event(output=f"Security Block: {node_input}")

# Approval Check Node
async def approval_check_node(ctx: Context, node_input: types.Content):
    # Extract text from orchestrator's output
    orchestrator_text = ""
    if isinstance(node_input, types.Content):
        for part in node_input.parts:
            if part.text:
                orchestrator_text += part.text
    else:
        orchestrator_text = str(node_input)
        
    # If we haven't asked for approval yet:
    if not ctx.resume_inputs or "user_approval" not in ctx.resume_inputs:
        # Save recommendations to state
        ctx.state["flight_hotel_recommendations"] = orchestrator_text
        yield RequestInput(
            interrupt_id="user_approval",
            message="Do you approve these flight and hotel options? Please reply with 'yes' or 'no'."
        )
        return
    
    # Read approval response
    user_response = ctx.resume_inputs["user_approval"].strip().lower()
    if "yes" in user_response:
        yield Event(
            output=f"The traveler approved the flights and hotels. Recommendations: {ctx.state['flight_hotel_recommendations']}",
            route="approved"
        )
    else:
        yield Event(
            output=f"The traveler rejected or provided feedback: '{user_response}'. Please regenerate flight and hotel recommendations considering this feedback.",
            route="rejected"
        )

# Workflow Definition
root_agent = Workflow(
    name="travel_buddy_workflow",
    edges=[
        (START, security_checkpoint),
        (security_checkpoint, {
            "SECURITY_EVENT": security_error_node,
            "__DEFAULT__": orchestrator
        }),
        (orchestrator, approval_check_node),
        (approval_check_node, {
            "approved": itinerary_agent,
            "rejected": orchestrator
        }),
    ]
)

# App configuration with Resumability enabled
app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True)
)
