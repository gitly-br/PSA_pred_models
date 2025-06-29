import asyncio
import pandas as pd
import gdown
import joblib
import os
from motor.motor_asyncio import AsyncIOMotorClient

# Import custom transformers
from .custom_transformers import WindowAgg, DropColumnsTransformer

# === Configuration ===
MONGO_URI = "mongodb://host.docker.internal:27017"
DB_NAME = "harvest_data"
COLLECTION_NAME = "openweather_santo_andre_all"
PIPELINE_ID = "1X7mD9f0sH4UG7fI9R3pR6w6jOjq2J4UP"
PIPELINE_FILE = "pipeline.joblib"


async def get_latest_hourly_data() -> pd.DataFrame:
    """
    Connects to MongoDB to fetch the 'hourly' data from the most recent document.
    """
    print("Connecting to MongoDB to get the latest hourly forecast...")
    client = AsyncIOMotorClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION_NAME]
    
    # Find the most recent document based on the request timestamp
    latest_doc = await collection.find_one(sort=[("dt_request", -1)])
    
    if not latest_doc or "hourly" not in latest_doc:
        raise RuntimeError("No document with 'hourly' data found in MongoDB.")

    # Convert the list of hourly forecasts into a DataFrame
    df = pd.DataFrame(latest_doc["hourly"])
    print(f"Successfully fetched {len(df)} hourly records.")
    return df


async def grab_from_gdrive(file_id, filename):

  url = f"https://drive.google.com/uc?id={file_id}"
  output = os.path.join('.', filename)
  if not(os.path.isfile(output)):
    gdown.download(url, output=output, quiet=True)


async def main():
    """
    Main function to run the flood prediction.
    """
    # Step 1: Fetch the latest raw hourly data from MongoDB
    hourly_df = await get_latest_hourly_data()

    # Step 2: Download and load the feature engineering pipeline
    await grab_from_gdrive(PIPELINE_ID, PIPELINE_FILE)
    pipeline = joblib.load(PIPELINE_FILE)

    # Step 3: Run the pipeline
    print("Running pipeline...")
    prediction = pipeline.predict(hourly_df)[0]
    print(f"\nPrediction: {prediction}")


if __name__ == "__main__":
    asyncio.run(main())
