from .collections import TestPlanDatabase, ParamsDatabase
from typing import Optional


class CollectionManager:
    def __init__(self):
        self.test_plan: Optional[TestPlanDatabase] = None
        self.params: Optional[ParamsDatabase] = None

    async def init_collection(self):
        self.test_plan = TestPlanDatabase()
        self.params = ParamsDatabase()


if __name__ == '__main__':
    from datetime import datetime
    import asyncio


    async def test_find():
        cm = CollectionManager()
        await cm.init_collection()

        this_date = datetime.now().strftime("%Y-%m-%d")
        print(f"查询日期: '{this_date}'")

        collections = cm.test_plan.find_all(
            filter_query={'date': this_date},
            limit=100
        )
        print(collections)
    asyncio.run(test_find())