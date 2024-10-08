from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
import utility.handler_db as handler_db
from utility.logger_local import get_logger
from utility.parse_file import parse_file
import utility.queries_db as queries_db
from pathlib import Path
import os

from utility.types import ActivityRequest


app = FastAPI()

GLOBAL_LOGGER = None
GLOBAL_TABLE_ACTIVITIES = "activities"
GLOBAL_TABLE_WAYPOINTS = "waypoints"
GLOBAL_DB_NAME = "prava.db"

PATH_DATA = "data/"


@app.on_event("startup")
async def startup_event():
    global GLOBAL_LOGGER
    GLOBAL_LOGGER = get_logger()
    if not os.path.isdir(PATH_DATA):
        os.makedirs(PATH_DATA)
    handler_db.checkConnection(GLOBAL_DB_NAME, GLOBAL_LOGGER)
    if not handler_db.get_table_names(GLOBAL_LOGGER):
        try:
            handler_db.createTable(
                GLOBAL_TABLE_ACTIVITIES, queries_db.TABLE_ACITVITIES, GLOBAL_LOGGER
            )
            handler_db.createTable(
                GLOBAL_TABLE_WAYPOINTS, queries_db.TABLE_WAYPOINTS, GLOBAL_LOGGER
            )
            res = handler_db.get_table_names(GLOBAL_LOGGER)
            return {"message": f"Successfully created table: {res[0]}"}
        except Exception as e:
            return {"message": f"Error creating the DB: {e}"}

    GLOBAL_LOGGER.info("API is starting up")


@app.post("/ping")
async def ping():
    return {"message": "Up and running"}


@app.post("/get_activity")
async def create_table(request: ActivityRequest):
    if (
        handler_db.getRow(
            tableName=GLOBAL_TABLE_ACTIVITIES, column="fileName", condition=request.file
        )
        is not None
    ):
        try:
            activities = handler_db.getActivity(
                tableName=GLOBAL_TABLE_ACTIVITIES,
                column="fileName",
                condition=request.file,
                logger=GLOBAL_LOGGER,
            )
            waypoints = handler_db.getWaypoints(
                tableName=GLOBAL_TABLE_WAYPOINTS,
                column="waypointFile",
                condition=activities["fileId"],
                logger=GLOBAL_LOGGER,
            )
            activities["waypoints"] = waypoints
            GLOBAL_LOGGER.info(f"Successfully fetched data for {request.file}")
            return activities
        except Exception as e:
            return {"message": f"Error fetching {request.file}: {e}"}


@app.post("/process")
async def process():
    await parse_files()
    result = analyze_activities()
    return result


@app.post("/upload_files")
async def upload_files(files: list[UploadFile]):
    # TODO
    # Check if the file is a .tcx file
    uploaded_files = []
    try:
        # Upload files
        for file in files:
            if ".tcx" in file.filename:
                with open(PATH_DATA + file.filename, "wb") as f:
                    while contents := file.file.read(1024 * 1024):
                        f.write(contents)
                uploaded_files.append(file.filename)
                file.file.close()
            else:
                continue
        # Parse Files
        await parse_files()
    except Exception as e:
        return {f'message": "There was an error uploading the file: {repr(e)}'}

    return {"message": f"Successfully uploaded {len(uploaded_files)} files."}


@app.post("/parse_files")
async def parse_files():
    files_parsed = []
    for file in os.listdir(PATH_DATA):
        if not handler_db.getRow(
            tableName=GLOBAL_TABLE_ACTIVITIES, column="fileName", condition=file
        ):
            data = await parse_file(
                filename=file, file=PATH_DATA + file, logger=GLOBAL_LOGGER
            )
            files_parsed.append(data["fileName"])
            only_waypoints = data["waypoints"]
            data.pop("waypoints", None)
            handler_db.addRow(GLOBAL_TABLE_ACTIVITIES, data, GLOBAL_LOGGER)
            row = handler_db.getRow(
                tableName=GLOBAL_TABLE_ACTIVITIES,
                column="fileName",
                condition=data["fileName"],
            )
            if row is not None:
                for entry in only_waypoints:
                    data = {
                        "sequence": entry["sequence"],
                        "longitude": entry["longitude"],
                        "latitude": entry["latitude"],
                        "waypointFile": row[0],
                    }
                    handler_db.addRow(GLOBAL_TABLE_WAYPOINTS, data, GLOBAL_LOGGER)

    return {
        "message": f"Successfully parsed {len(files_parsed)} files: {files_parsed}",
        "data": len(files_parsed),
    }


@app.post("/analyze_activities")
def analyze_activities():
    try:
        handler_db.checkConnection(GLOBAL_DB_NAME, GLOBAL_LOGGER)
        distance = round(
            handler_db.getSum(GLOBAL_TABLE_ACTIVITIES, "distance", GLOBAL_LOGGER)
        )
        average_distance = round(
            handler_db.getAvg(GLOBAL_TABLE_ACTIVITIES, "distance", GLOBAL_LOGGER)
        )
        avg_heart_rate = round(
            handler_db.getAvg(GLOBAL_TABLE_ACTIVITIES, "avgHeartRate", GLOBAL_LOGGER)
        )
        total_ascent = round(
            handler_db.getSum(GLOBAL_TABLE_ACTIVITIES, "ascent", GLOBAL_LOGGER)
        )
        total_time = handler_db.getTotalTime(GLOBAL_TABLE_ACTIVITIES, GLOBAL_LOGGER)

        data = {
            "total_distance": distance,
            "average_distance": average_distance,
            "avg_heart_rate": avg_heart_rate,
            "total_ascent": total_ascent,
            "total_time": total_time,
        }
        return data
    except Exception as e:
        return {f"Error: {e}"}


@app.post("/create_table")
async def create_table():
    try:
        handler_db.checkConnection(GLOBAL_DB_NAME, GLOBAL_LOGGER)
        handler_db.createTable(
            GLOBAL_TABLE_ACTIVITIES, queries_db.TABLE_ACITVITIES, GLOBAL_LOGGER
        )
        handler_db.createTable(
            GLOBAL_TABLE_WAYPOINTS, queries_db.TABLE_WAYPOINTS, GLOBAL_LOGGER
        )
        res = handler_db.get_table_names(GLOBAL_LOGGER)
        return {"message": f"Successfully created table: {res}"}
    except Exception as e:
        return {"message": f"Error creating the DB: {e}"}


@app.post("/drop_table")
async def drop_table():
    try:
        handler_db.checkConnection(GLOBAL_DB_NAME, GLOBAL_LOGGER)
        res1 = handler_db.dropTable(GLOBAL_TABLE_ACTIVITIES, GLOBAL_LOGGER)
        res2 = handler_db.dropTable(GLOBAL_TABLE_WAYPOINTS, GLOBAL_LOGGER)
        return {"message": f"Deleted table {res1, res2}"}
    except Exception as e:
        return {"message": f"{e}"}
