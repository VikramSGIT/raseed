from google.adk import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import (
    Part,
    Content
)
from pydantic import BaseModel
from enum import Enum
import json
from google.adk.tools import ToolContext

import os

images = list[bytes]()

class Rating(BaseModel):
    rating: int

pic_selector = Agent(
    name="pic_extractor",
    description="Search through the images and rates which image ",
    instruction=
    """
    You task is to look at a pic and rate it from a scale of 1 to 100 in
    how much of the content of the receipt recipt is visible. Make sure every
    text of the image is legible and whole reciept is visible, then rate it accordingly.
    """,
    output_schema=Rating,
    tools=[],
    model="gemini-2.5-flash-lite"
)

class ItemType(Enum):
    groceries = "groceries"
    laundries = "laundries"
    electronics = "electronics"
    software_service = "software_service"
    clothing_and_apparel = "clothing_and_apparel"
    gas_and_fuel = "gas_and_fuel"
    entertainment = "entertainment"
    travel = "travel"
    health_care = "health_care"
    personal_care = "personal_care"
    repairs = "repairs"
    utilities = "utilities"

class ItemList(BaseModel):
    name: str
    quantity: float
    unit_price: float
    total_price: float
    item_type: ItemType

class Bill(BaseModel):
    Amount: float
    expense_date: str
    location: str
    item_list: list[ItemList]

data_extracted = Agent(
    name="extract_bill",
    description="Go through the picture(s) and extract bill",
    instruction=
    """
    You are the worlds best parser, you will be provided with 
    picture(s), go through the receipt throughly and parse each
    and every part of receipt. Produce you output based on the 
    output format provided to you.
    """,
    model="gemini-2.5-flash-lite",
    output_schema=Bill
)

buffer = list[bytes]()

async def _run_pic_selection(data):
    rating = ''
    runner = Runner(app_name='raseed', agent=pic_selector, session_service=InMemorySessionService())
    session = await runner.session_service.create_session(user_id="123", app_name="raseed")
    async for event in runner.run_async(
    new_message=Content(role="user", parts=[
        Part.from_bytes(data=data, mime_type="image/jpeg"), 
        Part.from_text(text=
            """
            Can you understand all the parts of recipt? Please rate it from a scale of 1 to 100
            on how much of the data within the receipt is legible.
            """)
    ]),
    user_id="123",
    session_id=session.id
    ):
        part: Part | None | list[Part]= (
            event.content and event.content.parts and event.content.parts[0]
        )
        if not part: continue

        if not isinstance(part, list) and part.text:
            rating = part.text
    print(f"Scoring agent result: {rating}")
    return rating

async def _run_bill_extraction(images):
    bill_json = ''
    runner = Runner(app_name='raseed', agent=data_extracted, session_service=InMemorySessionService())
    session = await runner.session_service.create_session(user_id="123", app_name="raseed")
    parts = [Part.from_bytes(data=pic, mime_type="image/jpeg") for pic in images]
    parts.append(Part.from_text(text=f"Go through the recipt{"s" if len(parts) > 1 else ''} throughly and extract the bill details."))
    async for event in runner.run_async(
        new_message=Content(role="user", parts=parts),
        user_id="123",
        session_id=session.id
    ):
        part: Part | None | list[Part]= (
            event.content and event.content.parts and event.content.parts[0]
        )
        if not part: continue

        if not isinstance(part, list) and part.text:
            bill_json = part.text
    print(f"Bill agent result: {bill_json}")
    return bill_json
    
async def process_live_receipt() -> dict[str, str]:
    # folder_path = "/home/dedshot/adk-docs/examples/python/snippets/streaming/adk-streaming-ws/app/static/output_video"
    # if not os.path.isdir(folder_path):
    #     print(f"Error: The folder was not found at '{folder_path}'")

    # image_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])

    # if not image_files:
    #     print(f"No image files found in '{folder_path}'")

    # for filename in image_files:
    #     try:
    #         with open(os.path.join(folder_path, filename), "rb") as image_file:
    #             buffer.append(image_file.read())
    #     except IOError as e:
    #         print(f"Error reading file {filename}: {e}")
    
    # collected_image_indices = []
    # scores = []
    # for img in buffer:
    #     scores.append(int(json.loads(await _run_pic_selection(img))['rating']))

    # max_score = max(scores)
    # error_bound = max_score - 20
    # for i, score in enumerate(scores):
    #     if score >= error_bound:
    #         collected_image_indices.append(i)

    # collected_images = []
    # for i in collected_image_indices:
    #     collected_images.append(buffer[i])

    print("Called live process agent.")

    return json.loads(await _run_bill_extraction(images))