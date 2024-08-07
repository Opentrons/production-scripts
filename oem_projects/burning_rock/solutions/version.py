from http_client import HttpClient


def get_version(Domain):
    HttpClient._Domain = Domain
    res = HttpClient.get('/version')
    if res[0] == 200:
        return res[1]["version"]
    else:
        return ""


if __name__ == '__main__':
    res = get_version("http://OT2RS20240523003:31950")
    print(res)

