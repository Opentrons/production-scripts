from __future__ import annotations

from bson import ObjectId

import settings as setting
from database.mongodb import mongodb

from api.services.data import serialize_mongo_doc
from api.services.logging import logger


def get_messages() -> dict:
    try:
        collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.DATA_UPLOAD_STATUS_COLLECTION]
        cursor = collection.find().sort("created_at", -1).limit(50)
        messages = [serialize_mongo_doc(doc) for doc in cursor]
        return {
            "messages": messages,
            "total": collection.count_documents({}),
            "unread_count": collection.count_documents({"new": True}),
        }
    except Exception as exc:
        logger.error(f"Error fetching messages: {str(exc)}")
        return {
            "messages": [],
            "total": 0,
            "unread_count": 0,
            "error": str(exc),
        }


def mark_message_read(message_id: str) -> dict:
    try:
        collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.DATA_UPLOAD_STATUS_COLLECTION]
        result = collection.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": {"new": False}},
        )
        if result.modified_count > 0:
            return {"success": True, "message": "Message marked as read"}
        return {"success": False, "message": "Message not found or already read"}
    except Exception as exc:
        logger.error(f"Error marking message as read: {str(exc)}")
        return {"success": False, "error": str(exc)}


def mark_all_messages_read() -> dict:
    try:
        collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.DATA_UPLOAD_STATUS_COLLECTION]
        result = collection.update_many(
            {"new": True},
            {"$set": {"new": False}},
        )
        return {
            "success": True,
            "message": f"{result.modified_count} messages marked as read",
        }
    except Exception as exc:
        logger.error(f"Error marking all messages as read: {str(exc)}")
        return {"success": False, "error": str(exc)}
