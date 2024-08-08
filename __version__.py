import os
import subprocess

VERSION = '1.3.0'


def get_version():
    """
    this version
    """
    print(f"__VERSION__ is {VERSION}")
    return VERSION


# 获取当前Python环境下所有的依赖包
def get_dependencies():
    return os.popen('pip freeze').readlines()


# 将依赖包列表写入requirements.txt文件
def write_to_requirements_file(dependencies):
    with open('requirements.txt', 'w') as file:
        file.writelines(dependency for dependency in dependencies)


# 主函数
def explore_requirement():
    dependencies = get_dependencies()
    write_to_requirements_file(dependencies)


def build():
    cmd = f'pyinstaller -F --ico="source/logo.ico"  --name=Productions-{VERSION} production_scripts.py'
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    while True:
        line = process.stdout.readline()
        if not line:
            break  # 如果没有读取到数据，表示子进程已经结束，退出循环
        else:
            print(line, end='')  # 实时打印输出
    process.wait()
    output_path = os.path.join(os.getcwd(), "dist")
    print(f"Complete! target file -> {output_path}")


if __name__ == "__main__":
    build()
