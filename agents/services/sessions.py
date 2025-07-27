import os
from uuid import uuid4
import redis
from inspect import isawaitable
from fastapi import Request, Response
from dotenv import load_dotenv
load_dotenv()

class SessionData:
    def __init__(self, session_id: str, redis_client: redis.Redis, ttl: int):
        self._session_id = session_id
        self._redis = redis_client
        self._ttl = ttl

        result = dict()
        if redis_client.exists(session_id):
            result = redis_client.hgetall(session_id)
        else:
            redis_client.hset(session_id, 'session_id', session_id)
            result['session_id'] = session_id
        
        if not isawaitable(result):
            self._data: dict[str, str] = result

    def _refresh_ttl(self):
        self._redis.expire(self._session_id, self._ttl)

    def __setitem__(self, key: str, value: str):
        str_value = str(value)
        self._data[key] = str_value
        self._redis.hset(self._session_id, key, str_value)
        self._refresh_ttl()

    def __getitem__(self, key: str) -> str:
        if key in self._data.keys():
            return self._data[key]
        else: return ''

    def __delitem__(self, key: str) -> None:
        if key in self._data.keys():
            del self._data[key]
            self._redis.hdel(self._session_id, key)
            self._refresh_ttl()

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return str(self._data)

    def get(self, key: str, default=''):
        if key in self._data.keys():
            return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

async def init_session(request: Request, call_next) -> Response:
    redis_client = redis.Redis(host=os.getenv('REDIS_HOST', 'localhost'), port=int(os.getenv('REDIS_PORT', 6379)), db=0, decode_responses=True)
    cookies = request.cookies
    session = None
    agent_session= None
    new_session = True
    if 'session_id' in cookies:
        session =SessionData(session_id=cookies['session_id'], redis_client=redis_client, ttl=int(os.getenv('REDIS_SESSION_TTL', 3600)))
        new_session = False
    else:
        session = SessionData(session_id=str(uuid4()), redis_client=redis_client, ttl=int(os.getenv('REDIS_SESSION_TTL', 3600)))
        #TODO: update this id when google oauth is setup.
        session['user_id'] = '123'

    print("session accessed")

    request.state.session = session
    request.state.agent_session = agent_session
    response = await call_next(request)
    
    if new_session:
        response.set_cookie(
            key='session_id',
            value=session['session_id'],
            max_age=int(os.getenv('REDIS_SESSION_TTL', 3600)), # Use TTL from manager
            samesite="lax",
        )

    return response