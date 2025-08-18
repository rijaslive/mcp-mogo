import json
from typing import Any, Optional, Dict
from datetime import datetime
import logging

from mcp.server.fastmcp import FastMCP
import motor.motor_asyncio

logging.basicConfig(level=logging.DEBUG)

mcp = FastMCP("mongo-tools")
MONGO_URI = "" # Update if using cloud Mongo
DB_NAME = "discovery_dev"

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]


# Custom JSON serializer for non-serializable types like datetime
def json_default(obj: Any):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

@mcp.tool()
async def find_documents(collection: str, filter_json: str, projection_json: Optional[str] = None, limit: int = 10) -> str:
    """Find documents in a collection.uv run server.py
    Args:
        collection: Name of the collection.
        filter_json: JSON string for the filter (e.g., '{"age": {"$gt": 30}}').
        projection_json: Optional JSON string for fields to return (e.g., '{"name": 1}').
        limit: Max documents to return (default 10).
    """
    try:
        filter_dict = json.loads(filter_json)
        proj_dict = json.loads(projection_json) if projection_json else None
        coll = db[collection]
        cursor = coll.find(filter_dict, proj_dict).limit(limit)
        docs = await cursor.to_list(limit)
        return json.dumps(docs, default=json_default)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def aggregate_documents(collection: str, pipeline_json: str) -> str:
    """Run an aggregation pipeline on a collection.
    Args:
        collection: Name of the collection.
        pipeline_json: JSON string for the pipeline (e.g., '[{"$match": {"age": {"$gt": 30}}}]').
    """
    try:
        pipeline = json.loads(pipeline_json)
        coll = db[collection]
        cursor = coll.aggregate(pipeline)
        results = await cursor.to_list(None)
        return json.dumps(results, default=json_default)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def count_documents(collection: str, filter_json: str) -> str:
    """Count documents matching a filter.
    Args:
        collection: Name of the collection.
        filter_json: JSON string for the filter (e.g., '{"age": {"$gt": 30}}').
    """
    try:
        filter_dict = json.loads(filter_json)
        coll = db[collection]
        count = await coll.count_documents(filter_dict)
        return str(count)
    except Exception as e:
        return f"Error: {str(e)}"
    
@mcp.tool()
async def list_collections(db_name: str) -> Dict[str, Any]:
    """
    List all collections in a MongoDB database.

    Args:
        db_name (str): The database name.

    Returns:
        dict: A dictionary with the list of collection names.
    """
    try:
        collections = await db.list_collection_names()
        return {"collections": collections}
    except Exception as e:
        return {"error": str(e)}

# Add more tools as needed, e.g., insert, update, delete.

if __name__ == "__main__":
    logging.debug("Server started...")
    mcp.run(transport='stdio')
    # To run the server, use the command: uvicorn server:app --reload
    # or run server.py directly if using FastMCP with stdio transport.
    for tool in mcp.list_tools():
        logging.debug(f"- {tool.name}: {tool.description}")
    try:
        mcp.run(transport='stdio')
    except Exception as e:
         logging.debug(f"Server error: {str(e)}")