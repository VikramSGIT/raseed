import os
from google.adk.cli.fast_api import get_fast_api_app
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = get_fast_api_app(
    agents_dir=f".", 
    session_service_uri=f"postgresql://{os.getenv('DB_USER_AGENT_SESSION')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}",
    web=False,
    port=8083,
    lifespan=lifespan)