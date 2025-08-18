from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from client import MCPClient
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mcp_client = MCPClient()

class QueryRequest(BaseModel):
    query: str

@app.on_event("startup")
async def startup():
    await mcp_client.connect_to_server("../mcp-server/server.py")

@app.on_event("shutdown")
async def shutdown():
    await mcp_client.close()

@app.post("/query")
async def handle_query(request: QueryRequest):
    response = await mcp_client.process_query(request.query)
    return {"response": response}