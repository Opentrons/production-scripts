from ..driver import MongoDBReader


class TestPlanDatabase(MongoDBReader):
    def __init__(self):
        super().__init__(
            db_name='Params',
            collection_name='Index'
        )
        self.connect()
