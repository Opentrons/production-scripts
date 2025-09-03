from fastapi import Depends, FastAPI, HTTPException, APIRouter
from datetime import datetime
from files_server.api.model import *
from files_server.database.read_data_base import MongoDBReader
import math
from bson.objectid import ObjectId


router = APIRouter()

URI = "mongodb://192.168.6.21:27017/"

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


@router.post('/insert/document', status_code=201)
async def insert_document(request: InsertDocumentRequest):
    """
    Insert a document into the specified collection after checking if Link field already exists

    Args:
        request: InsertDocumentRequest containing:
            - db_name: Name of the database
            - document_name: Name of the collection
            - collections: The document data to insert (dict or list of dicts)

    Returns:
        The ID of the inserted document or error if Link exists
    """
    db_name = request.db_name
    document_name = request.document_name
    document_data = request.collections
    reader = MongoDBReader(
        uri=URI,
        db_name=db_name,
        collection_name=document_name
    )

    if not reader.connect():
        raise HTTPException(status_code=404, detail="Failed to connect to MongoDB")

    try:
        # Check if Link field exists in the collection
        if isinstance(document_data, dict):
            if 'Link' in document_data:
                existing = reader.collection.find_one({"Link": document_data['Link']})
                if existing:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Document with Link '{document_data['Link']}' already exists"
                    )
            print("inserting document: ", document_data)
            # Insert single document
            reader.collection.insert_one(document_data)


        elif isinstance(document_data, list):
            # Check each document in the list for duplicate Links
            links = [doc['Link'] for doc in document_data if 'Link' in doc]
            if links:
                existing_links = reader.collection.find(
                    {"Link": {"$in": links}},
                    {"Link": 1}
                ).distinct("Link")

                if existing_links:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Documents with these Links already exist: {', '.join(existing_links)}"
                    )

            # Insert multiple documents
            result = reader.collection.insert_many(document_data)
            inserted_id = result.inserted_ids
        else:
            raise HTTPException(status_code=400, detail="Invalid document format")

        return {"status_code": 200}

    except HTTPException:
        raise  # Re-raise the HTTPException we created
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to insert document: {str(e)}")



@router.post('/read/document', status_code=200)
async def read_document(request: ReadDocumentRequest):
    """
    read document
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

















