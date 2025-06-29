from motor.motor_asyncio import AsyncIOMotorClient

# === Configuration ===
MONGO_URI = "mongodb://host.docker.internal:27017"
HARVEST_DB_NAME = "harvest_data"
MODEL_DB_NAME = "floodcast_db"
MODEL_COLLECTION_NAME = "models"

async def get_models_config():
    client = AsyncIOMotorClient(MONGO_URI)
    collection = client[MODEL_DB_NAME][MODEL_COLLECTION_NAME]
    models = []
    async for doc in collection.find({}):
        models.append(doc)
    models_qty = len(models)
    if models_qty == 0:
        print("---- No models found. Exiting...")
        exit(1)
    print(f"++++ Found {models_qty} models")
    return models

async def get_latest_hourly_data(collection_name: str) -> list:
    """
    Connects to MongoDB to fetch the 'hourly' data from the most recent document.
    """
    client = AsyncIOMotorClient(MONGO_URI)
    collection = client[HARVEST_DB_NAME][collection_name]
    
    # Find the most recent document based on the request timestamp
    latest_doc = await collection.find_one(sort=[("dt_request", -1)])
    
    if not latest_doc or "hourly" not in latest_doc:
        raise RuntimeError(f"---- No document with 'hourly' data found in MongoDB for collection {collection_name}.")

    hourly_forecast = latest_doc["hourly"]
    print(f"++++ Successfully fetched {len(hourly_forecast)} hourly records from {collection_name}.")
    return hourly_forecast
