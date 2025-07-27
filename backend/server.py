import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.exceptions import HTTPException
from services.sessions import init_session
from services.oauth import get_credentials, get_login_redirect_url
from repository.database import get_user_by_email, create_user, init_db, shutdown_db
from contextlib import asynccontextmanager
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
load_dotenv()

CLIENT_BASE_URL: str = os.getenv("CLIENT_BASE_URL", '')

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(app)
    yield
    await shutdown_db(app)

app = FastAPI(lifespan=lifespan)

app.middleware("http")(init_session)

@app.get("/home")
async def home_page():
    file_path = './testUI.html'
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return HTMLResponse(content=file.read())
    except FileNotFoundError:
        print(f"Error: The file at '{file_path}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

class RequestData(BaseModel):
    prompt: str

# @app.post("/generate")
# async def generate(request: Request, data: RequestData):
#     return {'response': await run(app=app, prompt=data.prompt, session=request.state.session)}

@app.get("/auth/google/login")
async def login_with_google():
    return RedirectResponse(get_login_redirect_url())

@app.get("/auth/google/callback")
async def auth_callback(request: Request, code: str = '', error: str = ''):
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    creds = get_credentials(code=code)
    user_id = get_user_by_email(db_pool=app.state.db_pool, user_email=creds['email'])
    if user_id == None:
        user_id = create_user(db_pool=app.state.db_pool, user_name=creds['name'], user_email=creds['email'], access_token=creds['access_token'])
    
    request.state.session['user_id'] = user_id

    return RedirectResponse(CLIENT_BASE_URL + os.getenv('DASHBOARD_ENDPOINT', '/'))

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)