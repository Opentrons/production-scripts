from .collections import TestPlanDatabase, ParamsDatabase


class CollectionManager:
    def __init__(self):
        self.test_plan: TestPlanDatabase
        self.params: ParamsDatabase


