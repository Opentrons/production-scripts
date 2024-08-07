import hashlib


# md5_object = hashlib.md5()  # 创建MD5对象
# pwd = "0192023a7bbd73250516f069df18b500"  # admin123
# user_pwd = input("password:").strip().encode('utf-8')
# md5_object.update(user_pwd)
# user_pwd = md5_object.hexdigest()
#
# if user_pwd == pwd:
#     print("验证通过")
# else:
#     print("密码错误")


def get_hash(code: int):
    md5_object = hashlib.md5()
    user_pwd = str(code).strip().encode('utf-8')
    md5_object.update(user_pwd)
    res = md5_object.hexdigest()
    print(res)


if __name__ == '__main__':
    get_hash(342566)
