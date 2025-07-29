import argparse
import asyncio
import os
from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure


def expand_hourly(list_data):
    hourly = []
    for entry in list_data:
        base_dt = entry["dt"]
        # Extract fields with defaults and mappings
        temp = entry["main"]["temp"]
        feels_like = entry["main"]["feels_like"]
        pressure = entry["main"]["pressure"]
        humidity = entry["main"]["humidity"]
        dew_point = 15
        uvi = None
        clouds = entry["clouds"]["all"]
        visibility = entry.get("visibility", None)
        wind_speed = entry["wind"]["speed"]
        wind_deg = entry["wind"]["deg"]
        wind_gust = entry["wind"].get("gust", None)
        weather = entry["weather"]
        pop = entry.get("pop", 0)
        rain = 0
        if "rain" in entry and "3h" in entry["rain"]:
            rain = entry["rain"]["3h"]

        # Repeat 3 times, incrementing dt by 1 hour each time
        for i in range(3):
            hourly.append(
                {
                    "dt": base_dt + i * 3600,
                    "temp": temp,
                    "feels_like": feels_like,
                    "pressure": pressure,
                    "humidity": humidity,
                    "dew_point": dew_point,
                    "uvi": uvi,
                    "clouds": clouds,
                    "visibility": visibility,
                    "wind_speed": wind_speed,
                    "wind_deg": wind_deg,
                    "wind_gust": wind_gust,
                    "weather": weather,
                    "pop": pop,
                    "rain": rain,
                }
            )
    return hourly


def get_dt_request(list_data):
    # Use the date of the first dt in the list, set to 3 AM UTC
    first_dt = list_data[0]["dt"]
    dt_obj = datetime.utcfromtimestamp(first_dt)
    dt_3am = dt_obj.replace(hour=3, minute=0, second=0, microsecond=0)
    # If the hour is after 3, keep the same day; if before, go to previous day
    if dt_obj.hour < 3:
        dt_3am -= timedelta(days=1)
    return dt_3am


def convert_object(obj):
    list_data = obj["list"]
    converted = {
        "hourly": expand_hourly(list_data),
        "current": None,
        "minutely": None,
        "daily": None,
        "alerts": None,
        "dt_request": get_dt_request(list_data),
    }
    return converted


async def main():
    parser = argparse.ArgumentParser(
        description="Convert weather JSON format from MongoDB."
    )
    parser.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    args = parser.parse_args()

    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        print("Error: MONGO_URI environment variable not set.")
        return

    try:
        client = AsyncIOMotorClient(mongo_uri)
        await client.admin.command("ismaster")
    except ConnectionFailure as e:
        print(f"Error: Could not connect to MongoDB: {e}")
        return

    source_db = client.api_data
    source_collection = source_db.openweather_col
    dest_db = client.harvest_data
    dest_collection = dest_db.openweather_santoandre_all

    try:
        target_date = datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print("Error: Invalid date format. Please use YYYY-MM-DD.")
        return

    target_dt = target_date.replace(hour=3, minute=0, second=0, microsecond=0)
    start_window = target_dt - timedelta(hours=2)
    end_window = target_dt + timedelta(hours=2)

    pipeline = [
        {"$match": {"dt_request": {"$gte": start_window, "$lte": end_window}}},
        {
            "$addFields": {
                "time_diff": {"$abs": {"$subtract": ["$dt_request", target_dt]}}
            }
        },
        {"$sort": {"time_diff": 1}},
        {"$limit": 1},
    ]

    cursor = source_collection.aggregate(pipeline)
    source_obj_list = await cursor.to_list(length=1)

    if not source_obj_list:
        print(
            f"Error: No document found for date {args.date} within a 2-hour window of 3:00 AM UTC."
        )
        return

    source_obj = source_obj_list[0]
    converted_obj = convert_object(source_obj)

    existing_doc = await dest_collection.find_one(
        {"dt_request": converted_obj["dt_request"]}
    )

    if existing_doc:
        print(
            f"Skipping: A document with dt_request {converted_obj['dt_request'].strftime('%Y-%m-%dT%H:%M:%S.000Z')} already exists in the destination collection."
        )
        return

    await dest_collection.insert_one(converted_obj)
    print(f"Successfully converted and inserted document for date {args.date}.")


if __name__ == "__main__":
    asyncio.run(main())
