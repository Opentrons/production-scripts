from fastapi import Request


async def get_instance(request: Request):
    return request.app.state.instance
