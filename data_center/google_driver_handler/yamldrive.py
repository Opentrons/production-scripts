import yaml
import os


class yamlfunc():
    def __init__(self) -> None:
        pass

    def readyaml(self,failpath,nama):
        data = ''
        try:
            self.fullpath = os.path.join(failpath,nama)
            # 读取YAML文件
            with open(self.fullpath, "r") as yaml_file:
                data = yaml.load(yaml_file, Loader=yaml.FullLoader)
                print(data)
            return data
        except Exception as errval:
            print("读取yaml出错",data)
            return data

if __name__ == "__main__":
    aa = yamlfunc()
    bb=aa.readyaml("/Users/yew/googledriver/","updata.yaml")
