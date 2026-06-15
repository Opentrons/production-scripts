from datetime import datetime, timedelta
from jose import jwt
from typing import Optional

# 配置项（实际项目应从环境变量读取）
SECRET_KEY = "your-secret-key-here"  # 推荐使用 openssl rand -hex 32 生成
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)