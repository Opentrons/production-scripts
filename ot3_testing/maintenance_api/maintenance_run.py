from ot3_testing.http_client import HttpClient


class MaintenanceApi(HttpClient):
    def __init__(self, domain):
        super().__init__(domain)
        pass

    def create_run(self):
        self.post('/maintenance_runs')

