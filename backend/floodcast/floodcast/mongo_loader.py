from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import pytz

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
    Connects to MongoDB to fetch the 'hourly' data from the most recent document
    where dt_request is at 00:00 (midnight) in America/Sao_Paulo timezone.
    """
    client = AsyncIOMotorClient(MONGO_URI)
    collection = client[HARVEST_DB_NAME][collection_name]

    sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
    now_sao_paulo = datetime.now(sao_paulo_tz)

    # Calculate midnight (00:00) for today in Sao Paulo time
    midnight_sao_paulo = now_sao_paulo.replace(hour=0, minute=0, second=0, microsecond=0)
    midnight_utc = midnight_sao_paulo.astimezone(pytz.utc)

    # Calculate 23:00 (11 PM) for the previous day in Sao Paulo time
    previous_day_23h_sao_paulo = (now_sao_paulo - timedelta(days=1)).replace(hour=23, minute=0, second=0, microsecond=0)
    previous_day_23h_utc = previous_day_23h_sao_paulo.astimezone(pytz.utc)

    # Calculate 01:00 (1 AM) for today in Sao Paulo time
    current_day_01h_sao_paulo = now_sao_paulo.replace(hour=1, minute=0, second=0, microsecond=0)
    current_day_01h_utc = current_day_01h_sao_paulo.astimezone(pytz.utc)

    # Try to find the document for midnight first
    latest_doc = await collection.find_one({"dt_request": midnight_utc})

    # Fallback to 23:00 of the previous day if midnight not found
    if not latest_doc:
        print(f"---- No forecast found for {midnight_sao_paulo.strftime('%Y-%m-%d %H:%M')} SP. Trying {previous_day_23h_sao_paulo.strftime('%Y-%m-%d %H:%M')} SP...")
        latest_doc = await collection.find_one({"dt_request": previous_day_23h_utc})

    # Fallback to 01:00 of the current day if 23:00 not found
    if not latest_doc:
        print(f"---- No forecast found for {previous_day_23h_sao_paulo.strftime('%Y-%m-%d %H:%M')} SP. Trying {current_day_01h_sao_paulo.strftime('%Y-%m-%d %H:%M')} SP...")
        latest_doc = await collection.find_one({"dt_request": current_day_01h_utc})
    
    if not latest_doc:
        raise RuntimeError(f"---- No forecast found for {collection_name} for the current day (midnight, 23h, or 01h).")

    if "hourly" not in latest_doc:
        raise RuntimeError(f"---- Document found for {collection_name} but no 'hourly' data.")

    hourly_forecast = latest_doc["hourly"]
    print(f"++++ Successfully fetched {len(hourly_forecast)} hourly records from {collection_name}.")
    return hourly_forecast
