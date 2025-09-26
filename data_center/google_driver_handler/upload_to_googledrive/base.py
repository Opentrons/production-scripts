from google_driver_handler.googledrive import googledrive
import re
from pandas import DataFrame
from fastapi import HTTPException
from google_driver_handler.sheetdrive import sheetdrive
import pandas as pd


Productions = {
    "Robot": {"parent_id": "1e1NCGcll_g2Nk4NWvXYj1-fvLogZyLDO",
              "data_template": "1T-zUNRmvHqHNrfAxqsjr3ABSqtwooUUrmyCiOGLl-HI",
              "unit_tracker": ""}
}


def get_df_from_csv(csv_path):
    df = pd.read_csv(csv_path)
    return df


def clean_dataframe(df):
    """
    清理DataFrame数据，处理NaN值、无限值等
    """
    df_clean = df.copy()

    # 处理NaN值
    df_clean = df_clean.fillna('')

    # 处理无限值
    df_clean = df_clean.replace([float('inf'), float('-inf')], '')

    # 转换numpy类型到Python原生类型
    for col in df_clean.columns:
        if pd.api.types.is_integer_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].astype('Int64')  # 支持NaN的整数类型
        elif pd.api.types.is_float_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].astype(float)

    return df_clean


class UploadToGoogleDrive:
    def __init__(self, product):
        self.product_id = Productions[product]["parent_id"]
        self.data_template = Productions[product]["data_template"]
        self.unit_tracker = Productions[product]["unit_tracker"]
        self.error = None
        try:
            self.gdrive = googledrive()
            self.sheet_drive = sheetdrive()
        except Exception as e:
            self.error = e
            raise e

    def create_new_quarter(self, quarter):
        """
        quarter, 2025-Q1, 2025-Q2, 2025-Q3, 2025-Q
        """
        pattern = r'^\d{4}-Q[1-4]$'
        ret = re.match(pattern, quarter)
        if not ret:
            return None, "wrong quarter"
        else:
            _files = self.list_files_in_production()
            for item in _files:
                if quarter in item['name']:
                    return item['id'], "already exist"
            else:
                _id = self.gdrive.create_folders(quarter, self.product_id)
                return _id, "created"

    def list_files_in_production(self):
        try:
            _files = self.gdrive.show_shared_files(self.product_id)
            return _files
        except Exception as e:
            raise e

    def copy_template(self, new_quarter_id, new_name):
        """
        复制文件夹内的文件
        """
        # 复制模板
        name, _id = self.gdrive.get_coppy_file(self.data_template, 'template')
        self.rename_file_name_by_sn(_id, new_name)
        # 移动模板到目标目录
        self.gdrive.move_files(_id, new_quarter_id)
        return _id

    def copy_data_to_template(self, df: DataFrame, template_id, sheet_title: str) -> bool:
        """
        复制数据到模板里面
        """
        # 准备数据
        df = clean_dataframe(df)
        sheet_info = self.sheet_drive.get_sheet_info(template_id)
        for _sheet in sheet_info:
            name = _sheet['title']
            if sheet_title in name:
                print(_sheet)
                sheet_id = _sheet['sheet_id']
                ret = self.sheet_drive.copy_df_to_sheet(df, template_id, sheet_title)
                return ret
        return False

    def rename_file_name_by_sn(self, new_file_id, sn):
        self.gdrive.rename(new_file_id, sn)

    def upload_production_data(self, quarter_name, sn, this_file_name: str, sheet_title: str):
        """
        上传数据到对应的季度
            Parameters:
                quarter_name: 季度文件夹名
                sn: 产品序列号
                this_file_name: 数据
                sheet_title: 产品的测试名
        """
        # 提取序列号
        pattern2 = r'_CSVReport-([^-.]+)\.csv$'
        match2 = re.search(pattern2, this_file_name)
        if match2:
            serial_number = match2.group(1)
        else:
            raise HTTPException(status_code=404, detail="cannot find serial number")
        if sn != '':
            if serial_number != sn:
                return
        df = get_df_from_csv(this_file_name)
        file_id = None
        folder_id, create_new_folder_message = self.create_new_quarter(quarter_name)
        if not folder_id:
            raise HTTPException(status_code=404, detail=create_new_folder_message)
        # is file exist ?
        if create_new_folder_message == "already exist":
            _files = self.gdrive.show_shared_files(folder_id)
            for item in _files:
                if serial_number in item['name']:
                    file_id = item['id']
                    break
        try:
            if file_id is None:
                file_id = self.copy_template(folder_id, serial_number)
            self.copy_data_to_template(df, file_id, sheet_title)
        except HTTPException as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)


if __name__ == '__main__':
    ...
