from google.adk.agents import Agent
from google.adk.tools import ToolContext
from google.adk.tools import FunctionTool
from agents.pic_extractor_agent import process_live_receipt

root_agent = Agent(
   # A unique name for the agent.
   name="raseed_live_agent",
   # The Large Language Model (LLM) that agent will use.
   #model="gemini-2.0-flash-exp", # if this model does not work, try below
   model="gemini-2.0-flash-live-001",
   # A short description of the agent's purpose.
   description="Parses receipt and answers user query based on recipt.",
   # Instructions to set the agent's behavior.
   instruction="" \
   """
   You are a very intelligent model, who can parse the recipts
   and answer user query regard the reciept and his previous spending.
   If a receipt is shown, call the receipt detail_extraction_agent once to 
   fetch the details in the receipt. Please acknowledge the user before processing
   the receipt as it is a bit long process.
   """,
   # Add google_search tool to perform grounding with Google search.
   tools=[process_live_receipt],
)