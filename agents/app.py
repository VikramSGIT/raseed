import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
import json
import base64
import asyncio
import uvicorn

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions import DatabaseSessionService
from google.genai.types import (
    Part,
    Content,
    Blob,
    AudioTranscriptionConfig
)

from agents.live_chat_agent import root_agent
from services.sessions import init_session
from urllib.parse import parse_qs

from agents.pic_extractor_agent import images

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = get_fast_api_app(
    agents_dir=f".", 
    session_service_uri=f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}",
    web=False,
    port=8083,
    lifespan=lifespan)

app.middleware("http")(init_session)

async def start_agent_session(user_id: str):
    """Starts an agent session"""
    
    runner = Runner(
        app_name='raseed',
        agent=root_agent,
        session_service=DatabaseSessionService(f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
    )

    session = await runner.session_service.create_session(
        app_name='raseed',
        user_id=user_id
    )
    session.state['user_id'] = user_id

    # Set response modality
    run_config = RunConfig(
        response_modalities=["AUDIO"],
        streaming_mode=StreamingMode.BIDI,
        output_audio_transcription=AudioTranscriptionConfig()
    )

    # Create a LiveRequestQueue for this session
    live_request_queue = LiveRequestQueue()

    # Start agent session
    live_events = runner.run_live(
        session_id=session.id,
        user_id=user_id,
        live_request_queue=live_request_queue,
        run_config=run_config,
    )
    return live_events, live_request_queue



async def agent_to_client_messaging(websocket, live_events):
    """Agent to client communication"""
    print("[AGENT TO CLIENT]: Starting task.")
    try:
        async for event in live_events:

            # If the turn complete or interrupted, send it
            if event.turn_complete or event.interrupted:
                message = {
                    "turn_complete": event.turn_complete,
                    "interrupted": event.interrupted,
                }
                await websocket.send_text(json.dumps(message))
                print(f"[AGENT TO CLIENT]: {message}")
                continue
            

            # Read the Content and its first Part
            part: Part = (
                event.content and event.content.parts and event.content.parts[0]
            )
            if not part:
                continue

            # If it's audio, send Base64 encoded audio data
            is_audio = part.inline_data and part.inline_data.mime_type.startswith("audio/pcm")
            if is_audio:
                audio_data = part.inline_data and part.inline_data.data
                if audio_data:
                    message = {
                        "mime_type": "audio/pcm",
                        "data": base64.b64encode(audio_data).decode("ascii")
                    }
                    await websocket.send_text(json.dumps(message))
                    print(f"[AGENT TO CLIENT]: audio/pcm: {len(audio_data)} bytes.")
                    continue

            # If it's text and a parial text, send it
            if part.text and event.partial:
                message = {
                    "mime_type": "text/plain",
                    "data": part.text
                }
                await websocket.send_text(json.dumps(message))
                print(f"[AGENT TO CLIENT]: text/plain: {message}")
        print("[AGENT TO CLIENT]: live_events stream finished.")
    except Exception as e:
        print(f"[AGENT TO CLIENT]: An error occurred: {e}")
    finally:
        print("[AGENT TO CLIENT]: Task finished.")


async def client_to_agent_messaging(websocket, live_request_queue: LiveRequestQueue):
    """Client to agent communication"""
    print("[CLIENT TO AGENT]: Starting task.")
    try:
        while True:
            # Decode JSON message
            message_json = await websocket.receive_text()
            message = json.loads(message_json)
            mime_type = message["mime_type"]
            data = message["data"]

            # Send the message to the agent
            if mime_type == "text/plain":
                # Send a text message
                content = Content(role="user", parts=[Part.from_text(text=data)])
                live_request_queue.send_content(content=content)
                print(f"[CLIENT TO AGENT]: {data}")
            elif mime_type == "audio/pcm" or mime_type == "image/jpeg":
                decoded_data = base64.b64decode(data)
                if mime_type == "image/jpeg":
                    images.append(decoded_data)
                # Send an audio data
                live_request_queue.send_realtime(Blob(data=decoded_data, mime_type=mime_type))
            else:
                raise ValueError(f"Mime type not supported: {mime_type}")
    except WebSocketDisconnect:
        print("[CLIENT TO AGENT]: WebSocket disconnected.")
    except Exception as e:
        print(f"[CLIENT TO AGENT]: An error occurred: {e}")
    finally:
        print("[CLIENT TO AGENT]: Task finished.")

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, is_audio: str):
    """Client websocket endpoint"""
    # Wait for client connection
    await websocket.accept()
    print(f"Client #test_session connected, audio mode: {is_audio}")

    # Start agent session
    live_events, live_request_queue = await start_agent_session("123")

    # Start tasks
    agent_to_client_task = asyncio.create_task(
        agent_to_client_messaging(websocket, live_events)
    )
    client_to_agent_task = asyncio.create_task(
        client_to_agent_messaging(websocket, live_request_queue)
    )

    # Wait until the websocket is disconnected or an error occurs
    done, pending = await asyncio.wait(
        [agent_to_client_task, client_to_agent_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    for task in done:
        if task.exception():
            print(f"Task finished with exception: {task.exception()}")
        else:
            print("Task finished without exception.")

    for task in pending:
        task.cancel()

    # Close LiveRequestQueue
    live_request_queue.close()

    # Disconnected
    print(f"Client #test_session disconnected")

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8001)