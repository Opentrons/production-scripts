from fastapi import Depends, FastAPI, HTTPException, APIRouter
from datetime import datetime
from files_server.api.model import *
from files_server.database.read_data_base import MongoDBReader


router = APIRouter()



@router.post('/read/document', status_code=200)
async def read_document(request: ReadDocumentRequest):
    """
    connect ot3
    """
    db_name = request.db_name
    document_name = request.document_name
    limit = request.limit
    reader = MongoDBReader(
        uri="mongodb://localhost:27017/",
        db_name=db_name,
        collection_name=document_name
    )

    if not reader.connect():
        success = False
        message = "connection error"
        all_docs = []
    else:
        all_docs = reader.find_all(limit=limit)
        success = True
        message = "success"
    return {
        "success": success,
        "all_docs": all_docs,
        "message": message
    }

















