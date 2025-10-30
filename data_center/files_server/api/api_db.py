from fastapi import Depends, FastAPI, HTTPException, APIRouter
from datetime import datetime
from files_server.api.model import *
from files_server.database.read_data_base import MongoDBReader
import math
from bson.objectid import ObjectId
from files_server.utils.utils import require_config
from fastapi.responses import JSONResponse

router = APIRouter()
URI = require_config()["db_url"]


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

@router.get("/require/upload_switch")
async def require_upload_switch():
    try:
        reader = MongoDBReader(
            uri=URI
        )
        result = reader.auto_upload
        return JSONResponse(
            status_code=200,
            content={
                "status": result
            }
        )
    except Exception as e:
        return HTTPException(status_code=400, detail=e)

@router.get("/require/upload_switch/{value}")
async def require_upload_switch(value: bool):
    try:
        reader = MongoDBReader(
            uri=URI
        )
        reader.auto_upload = value
        return JSONResponse(
            status_code=200,
            content={
                "status": reader.auto_upload
            }
        )
    except Exception as e:
        return HTTPException(status_code=400, detail=e)


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
            validation = ['Link', 'barcode']
            for _v in validation:
                if _v in document_data:
                    _check_document = {_v: document_data[_v]}
                    existing = reader.collection.find_one(_check_document)
                    print(_check_document)
                    print(existing)
                    print(type(_check_document))
                    if existing is not None:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Document with {_v} '{document_data[_v]}' already exists"
                        )
            # Insert single document
            reader.collection.insert_one(document_data)
        # 插入多条数据
        elif isinstance(document_data, list):
            # Check each document in the list for duplicate Links
            validation = ['Link', 'barcode']
            for _val in validation:
                val = [doc[_val] for doc in document_data if _val in doc]
                if val:
                    existing = reader.collection.find(
                        {"Val": {"$in": val}},
                        {"Val": 1}
                    ).distinct("Val")

                    if existing:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Documents with these {val} already exist"
                        )

            # Insert multiple documents
            result = reader.collection.insert_many(document_data)
            inserted_id = result.inserted_ids
        else:
            raise HTTPException(status_code=400, detail="Invalid document format")

        return JSONResponse(status_code=200, content={"detail": "success"})

    except HTTPException:
        raise  # Re-raise the HTTPException we created
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to insert document: {str(e)}")
    finally:
        reader.close()


@router.post('/delete/document', status_code=200)
async def delete_document(request: DeleteDocumentRequest):
    db_name = request.db_name
    document_name = request.document_name
    require_key = request.require_key
    reader = MongoDBReader(
        uri=URI,
        db_name=db_name,
        collection_name=document_name
    )
    if not reader.connect():
        raise HTTPException(
            status_code=500,
            detail="Connection error"
        )
    else:
        try:
            require = require_key["require_key"]
            reader.delete_document(require)
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Delete success",
                    "db_name": db_name,
                    "document_name": document_name
                }
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Delete failed: {str(e)}"
            )


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
    try:
        if not reader.connect():
            success = False
            message = "connection error"
            documents = []
        else:
            all_docs = reader.find_all(limit=limit)
            all_docs = clean_data(all_docs)
            documents = []
            for doc in all_docs:
                doc["_id"] = str(doc["_id"])  # 关键转换
                documents.append(doc)
            success = True
            message = "success"
        reader.close()
        return {
            "success": success,
            "all_docs": documents,
            "message": message
        }
    except Exception as e:
        message = "读取出现错误" + str(e)
        raise HTTPException(status_code=500, detail=message)
    finally:
        reader.close()
