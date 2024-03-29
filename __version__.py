import os

VERSION = '1.0.0'


def get_version():
    """
    this version
    """
    return VERSION


# 获取当前Python环境下所有的依赖包
def get_dependencies():
    return os.popen('pip freeze').readlines()


# 将依赖包列表写入requirements.txt文件
def write_to_requirements_file(dependencies):
    with open('requirements.txt', 'w') as file:
        file.writelines(dependency for dependency in dependencies)


# 主函数
def main():
    dependencies = get_dependencies()
    write_to_requirements_file(dependencies)


if __name__ == "__main__":
    main()
