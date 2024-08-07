from http_client import HttpClient


def get_door_status():
    """
    get door status
    :return:
    """
    ret = HttpClient.get("/robot/door/status")
    HttpClient.judge_state_code(ret)
    data = ret[1]
    if data["door_status"] is False:
        return "Opened"
    else:
        return "Closed"


if __name__ == '__main__':
    ret = get_door_status()
    print(ret)
