import json

import requests

# Domain = "http://OT2CEP20230630R01-DEBUGGER:31950"
Domain = "http://192.168.6.8:31950"
headers = {
    "Content-Type": "application/json",
    "Opentrons-Version": "3"
}

TimeOut = 120


class HttpClient:
    _Domain = Domain

    @classmethod
    def get(cls, api, params=None):
        """
        get method
        :param api:
        :param params:
        :return:
        """
        _url = f"{cls._Domain}{api}"
        response = requests.get(_url, headers=headers, params=params, timeout=TimeOut)
        code = response.status_code
        text = response.text
        return code, json.loads(text)

    @classmethod
    def post(cls, api, data=None, params=None):
        """
        post method
        :param api:
        :param data:
        :param params:
        :return:
        """
        _url = f"{Domain}{api}"
        if data is not None and params is None:
            data = json.dumps(data)
            response = requests.post(_url, data=data, headers=headers, timeout=TimeOut)
        elif params is not None and data is None:
            _query = []
            for k, v in params.items():
                _query.append(f"?{k}={v}")
            _query = "".join(_query)
            _url = _url + _query
            response = requests.post(_url, headers=headers, timeout=TimeOut)
        elif data is not None and params is not None:
            data = json.dumps(data)
            response = requests.post(_url, params=params, data=data, headers=headers, timeout=TimeOut)
        else:
            response = requests.post(_url, headers=headers, timeout=TimeOut)
        code = response.status_code
        text = response.text
        return code, json.loads(text)

    @classmethod
    def delete(cls, api, data=None):
        """
        post method
        :param api:
        :param data:
        :return:
        """
        _url = f"{Domain}{api}"
        if data is not None:
            data = json.dumps(data)
            response = requests.delete(_url, data=data, headers=headers, timeout=TimeOut)
        else:
            response = requests.delete(_url, headers=headers, timeout=TimeOut)
        code = response.status_code
        text = response.text
        return code, json.loads(text)

    @classmethod
    def patch(cls, api, data):
        """
        post method
        :param api:
        :param data:
        :return:
        """
        _url = f"{Domain}{api}"
        data = json.dumps(data)
        response = requests.patch(_url, data=data, headers=headers, timeout=TimeOut)
        code = response.status_code
        text = response.text
        return code, json.loads(text)

    @classmethod
    def judge_state_code(cls, ret):
        """
        judge response result
        :param ret: (state_code, text)
        :return:
        """
        if ret[0] != 200 and ret[0] != 201:
            raise ValueError(f"state_code = {ret[0]}")

