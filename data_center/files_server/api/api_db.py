from fastapi import Depends, FastAPI, HTTPException, APIRouter
from datetime import datetime
from files_server.api.model import *
from files_server.database.read_data_base import MongoDBReader
import math
from bson.objectid import ObjectId


router = APIRouter()

URI = "mongodb://192.168.6.61:27017/"

def clean_data(data):
    if isinstance(data, dict):
        return {k: clean_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data(item) for item in data]
    elif isinstance(data, float) and math.isnan(data):
        return None  # 将 nan 转为 null
    elif isinstance(data, ObjectId):
        return str(data)  # 转换 ObjectId
    return data

@router.post('/read/document', status_code=200)
async def read_document(request: ReadDocumentRequest):
    """
    connect ot3
    """
    db_name = request.db_name
    document_name = request.document_name
    limit = request.limit
    reader = MongoDBReader(
        uri=URI,
        db_name=db_name,
        collection_name=document_name
    )

    if not reader.connect():
        success = False
        message = "connection error"
        documents = []
    else:
        all_docs = reader.find_all(limit=limit)
        all_docs = clean_data(all_docs)
        print(all_docs)
        documents = []
        for doc in all_docs:
            doc["_id"] = str(doc["_id"])  # 关键转换
            documents.append(doc)
        success = True
        message = "success"
    return {
        "success": success,
        "all_docs": documents,
        "message": message
    }

















