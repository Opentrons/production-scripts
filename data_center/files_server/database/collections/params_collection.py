from ..driver import MongoDBReader


class ParamsDatabase(MongoDBReader):
    def __init__(self):
        super().__init__(
            db_name='test_db',
            collection_name='test_collection'
        )
        self.__auto_upload: bool
        self.connect()

    @property
    def auto_upload(self):
        result = self.find_all()[0]
        current_status = result["auto_upload_data"]
        if current_status == "true":
            self.__auto_upload = True
        else:
            self.__auto_upload = False
        return self.__auto_upload

    @auto_upload.setter
    def auto_upload(self, value: bool):
        """
        storing as a switch for turn off the upload-data
        """
        if isinstance(value, bool):
            self.__auto_upload = value
            auto_upload = "true" if self.__auto_upload else "false"
            self.set_database_filed({"index": 1}, {"auto_upload_data": auto_upload})
        else:
            raise TypeError("value should be a bool value")
