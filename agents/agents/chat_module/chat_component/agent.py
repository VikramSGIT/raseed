# Conceptual Code: Hierarchical Research Task
import base64
from google.adk.agents import LlmAgent
from google.adk.tools import agent_tool
from google.adk.planners import BuiltInPlanner
from google.adk.planners import PlanReActPlanner
from google.genai import types
# from chat_component.tools
from chat_component.tools.sql_execution import execute_query_fetch
from google.adk.tools import FunctionTool
execute_query_tool = FunctionTool(func=execute_query_fetch)
from chat_component.tools.google_wallet import create_google_wallet_pass
from chat_component.group_split import group_agent
from google.adk.tools import google_search
import yaml
import os
base_path = os.path.dirname(__file__)
with open(f"{base_path}/prompts.yaml") as f:
    prompts = yaml.safe_load(f)


InformationAgent = LlmAgent(
    name="InformationAgent",
    model="gemini-2.5-flash",
    description="For every information asked, create an sql query and use the execute_query_fetch function to always provide the output.",
    instruction=prompts['prompts']['Text_to_Sql'],
    # planner=BuiltInPlanner(
    #     thinking_config=types.ThinkingConfig(
    #         include_thoughts=True,
    #         thinking_budget=1024,
    #     )
    # ),
    tools=[execute_query_tool]
)

AnalysisAgent = LlmAgent(
    name="AnalysisAgent",
    model="gemini-2.5-flash",
    description="Your Role is to act on analysis of the provided info and act as a financial analyzer and advisor. Do a thorough analysis, ask the Information agent on any required information that is further needed for fulfilling the request",
    instruction=prompts['prompts']['Analysis_prompt'],
    tools=[agent_tool.AgentTool(agent=InformationAgent)]
)

NeedCheckAgent = LlmAgent(
    name="NeedCheckAgent",
    model="gemini-2.0-flash",
    description="Analyzes user purchase frequencies and suggests whether the user likely needs to buy an item again.",
    instruction=prompts['prompts']['Need_Check'],
    tools=[agent_tool.AgentTool(agent=InformationAgent) ]
)

Receipt_Processor = LlmAgent(
    name="Receipt_Processor_Agent",
    model="gemini-2.0-flash",
    description="Analyze the receipt and call the create_google_wallet_pass. Takes image input as well.",
    instruction=prompts['prompts']['Receipt_Processor'],
    tools=[create_google_wallet_pass]
)
Google_Search = LlmAgent(
    name="Google_Search_Agent",
    model="gemini-2.0-flash",
    description="Searches google to retreive any external data",
    instruction="You are an Intelligent Agent with access to google search to find any inoformation required.",
    tools=[google_search]
)

SmartPlannerAgent = LlmAgent(
    name="SmartPlannerAgent",
    model="gemini-2.5-flash",
    description="An intelligent task orchestrator that can handle ANY type of user request by breaking it down into logical steps and coordinating with specialized agents to deliver comprehensive solutions.",
    instruction=prompts['prompts']['Smart_Planner_Agent'],
    tools=[
        agent_tool.AgentTool(agent=InformationAgent),
        agent_tool.AgentTool(agent=AnalysisAgent),
        agent_tool.AgentTool(agent=NeedCheckAgent),
        agent_tool.AgentTool(agent=Receipt_Processor),
        agent_tool.AgentTool(agent=Google_Search)
    ],
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=2048,  # Higher thinking budget for complex planning
        )
    )
)

from google.adk.agents import LlmAgent

Orchestrator = LlmAgent(
    name="OrchestratorAgent",
    model="gemini-2.5-flash",
    description="Goal is to user answer user query on finances. Use AnalysisAgent for any analysis required and use InformationAgent to gather user specific information on his spendings, items purchases, groups he is part of and any financial data. Use current_time to find the current date and time.",
    instruction=prompts['prompts']['Chat_Agent'],
    tools=[agent_tool.AgentTool(agent=AnalysisAgent), 
           agent_tool.AgentTool(agent=InformationAgent),
           agent_tool.AgentTool(agent=NeedCheckAgent),
           agent_tool.AgentTool(agent=Receipt_Processor),
           agent_tool.AgentTool(agent=Google_Search),
           agent_tool.AgentTool(agent=SmartPlannerAgent),
           agent_tool.AgentTool(agent=group_agent)],
    # planner=PlanReActPlanner(),
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=1024,
        )
    )
)

root_agent = Orchestrator


# # root_agent.run_live

# # @title Define Agent Interaction Function
# # @title Setup Session Service and Runner

# # --- Session Management ---
# # Key Concept: SessionService stores conversation history & state.
# # InMemorySessionService is simple, non-persistent storage for this tutorial.
# from google.adk.sessions import InMemorySessionService
# from google.adk.runners import Runner
# session_service = InMemorySessionService()

# # @title 1. Initialize New Session Service and State

# # Import necessary session components
# from google.adk.sessions import InMemorySessionService

# # Create a NEW session service instance for this state demonstration
# session_service_stateful = InMemorySessionService()
# print("✅ New InMemorySessionService created for state demonstration.")

# # Define a NEW session ID for this part of the tutorial
# SESSION_ID_STATEFUL = "session_state_demo_001"
# USER_ID_STATEFUL = "user_state_demo"

# # Define initial state data - user prefers Celsius initially
# initial_state = {
#     "user_id": "ALRT"
# }

# # Create the session, providing the initial state
# session_stateful = session_service_stateful.create_session_sync(
#     app_name="APP_NAME", # Use the consistent app name
#     user_id=USER_ID_STATEFUL,
#     session_id=SESSION_ID_STATEFUL,
#     state=initial_state # <<< Initialize state during creation
# )
# print(f"✅ Session '{SESSION_ID_STATEFUL}' created for user '{USER_ID_STATEFUL}'.")

# # Verify the initial state was set correctly
# retrieved_session =  session_service_stateful.get_session_sync(app_name="APP_NAME",
#                                                          user_id=USER_ID_STATEFUL,
#                                                          session_id = SESSION_ID_STATEFUL)
# print("\n--- Initial Session State ---")
# if retrieved_session:
#     print(retrieved_session.state)
# else:
#     print("Error: Could not retrieve session.")


# from google.genai import types # For creating message Content/Parts

# async def call_agent_async(query: str, runner, user_id, session_id):
#   """Sends a query to the agent and prints the final response."""
#   print(f"\n>>> User Query: {query}")

#   # Prepare the user's message in ADK format
#   content = types.Content(role='user', parts=[types.Part(text=query)])

#   final_response_text = "Agent did not produce a final response." # Default

#   # Key Concept: run_async executes the agent logic and yields Events.
#   # We iterate through events to find the final answer.
#   async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
#       # You can uncomment the line below to see *all* events during execution
#       # print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")

#       # Key Concept: is_final_response() marks the concluding message for the turn.
#       if event.is_final_response():
#           if event.content and event.content.parts:
#              # Assuming text response in the first part
#              final_response_text = event.content.parts[0].text
#           elif event.actions and event.actions.escalate: # Handle potential errors/escalations
#              final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
#           # Add more checks here if needed (e.g., specific error codes)
#           break # Stop processing events once the final response is found

# # #   print(f"<<< Agent Response: {final_response_text}")