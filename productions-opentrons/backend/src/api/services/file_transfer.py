from __future__ import annotations

import os
import subprocess
import time
import zipfile
from datetime import datetime

import aiofiles
import paramiko
from fastapi import HTTPException, UploadFile

import settings as setting

from api.services.logging import logger


TIME_OUT = 60
key_file = setting.ROBOT_KEY_PATH


def zip_folder(folder_path: str, output_path: str | None = None) -> str | None:
    logger.info(f"Zipping folder: {folder_path}")
    if not os.path.exists(folder_path):
        logger.error(f"Folder to zip does not exist: {folder_path}")
        return None

    output_path = output_path or folder_path + ".zip"
    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(folder_path):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    arcname = os.path.relpath(file_path, os.path.dirname(folder_path))
                    zipf.write(file_path, arcname)
        logger.info(f"Folder zipped successfully: {output_path}")
        return output_path
    except Exception as exc:
        logger.error(f"Failed to zip folder: {str(exc)}")
        return None


def sftp_pull_folder(robot_ip: str, folder_name: str, target_dir: str, username: str = "root", password: str = ""):
    try:
        logger.info(f"Starting SFTP pull from {robot_ip}:{folder_name} to {target_dir}")
        start_time = time.time()
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(robot_ip, username=username, key_filename=key_file, timeout=TIME_OUT)
            logger.info("Connected to remote server using SSH key authentication")
        except Exception as exc:
            logger.warning(f"SSH key authentication failed: {str(exc)}. Trying password authentication.")
            client.connect(robot_ip, username=username, password=password, timeout=TIME_OUT)
            logger.info("Connected to remote server using password authentication")

        sftp = client.open_sftp()
        remote_folder = f"/{folder_name}" if not folder_name.startswith("/") else folder_name
        os.makedirs(target_dir, exist_ok=True)

        def download_recursive(remote_path: str, local_base_path: str) -> None:
            try:
                for file_attr in sftp.listdir_attr(remote_path):
                    remote_file_path = os.path.join(remote_path, file_attr.filename)
                    local_file_path = os.path.join(local_base_path, file_attr.filename)
                    if file_attr.st_mode & 0o040000:
                        os.makedirs(local_file_path, exist_ok=True)
                        download_recursive(remote_file_path, local_file_path)
                    else:
                        sftp.get(remote_file_path, local_file_path)
            except Exception as exc:
                logger.error(f"Error in download_recursive: {str(exc)}", exc_info=True)
                raise

        download_recursive(remote_folder, target_dir)
        sftp.close()
        client.close()
        elapsed_time = time.time() - start_time
        logger.info(f"SFTP pull completed in {elapsed_time:.2f} seconds")
        return True, "Folder pulled successfully via SFTP"
    except paramiko.ssh_exception.SSHException as exc:
        logger.error(f"SFTP connection error: {str(exc)}", exc_info=True)
        return False, f"SFTP connection error: {str(exc)}"
    except TimeoutError:
        logger.error("SFTP connection timeout after 30 seconds", exc_info=True)
        return False, "SFTP connection timeout after 30 seconds"
    except Exception as exc:
        logger.error(f"SFTP error: {str(exc)}", exc_info=True)
        return False, f"SFTP error: {str(exc)}"


def scp_pull_folder(robot_ip: str, folder_name: str, target_dir: str, username: str = "root"):
    try:
        logger.info(f"Starting SCP pull from {robot_ip}:{folder_name} to {target_dir}")
        start_time = time.time()
        remote_path = f"{username}@{robot_ip}:{folder_name}"
        os.makedirs(target_dir, exist_ok=True)
        scp_command = [
            "scp",
            "-r",
            "-o",
            "ConnectTimeout=30",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            key_file,
            remote_path,
            target_dir,
        ]
        logger.info(" ".join(scp_command))
        result = subprocess.run(scp_command, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            elapsed_time = time.time() - start_time
            logger.info(f"SCP pull completed in {elapsed_time:.2f} seconds")
            return True, "Folder pulled successfully via SCP"
        logger.error(f"SCP error: {result.stderr}")
        return False, f"SCP error: {result.stderr}"
    except subprocess.TimeoutExpired:
        logger.error("SCP command timeout after 30 seconds", exc_info=True)
        return False, "SCP command timeout after 30 seconds"
    except Exception as exc:
        logger.error(f"SCP error: {str(exc)}", exc_info=True)
        return False, f"SCP error: {str(exc)}"


async def pull_folder(
    *,
    robot_ip: str,
    csv_file: UploadFile,
    folder_name: str,
    pull_method: str,
) -> dict:
    zip_path = None
    date_string = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = setting.DOWNLOAD_DIR
    folder_basename = os.path.basename(folder_name)
    final_folder_path = os.path.join(target_dir, f"{folder_basename}-{date_string}")
    os.makedirs(target_dir, exist_ok=True)

    csv_path = os.path.join(target_dir, csv_file.filename)
    logger.info(f"Saving CSV file to: {csv_path}")
    async with aiofiles.open(csv_path, "wb") as out_file:
        content = await csv_file.read()
        await out_file.write(content)

    if pull_method.lower() == "scp":
        success, message = scp_pull_folder(robot_ip, folder_name, final_folder_path)
    else:
        success, message = sftp_pull_folder(robot_ip, folder_name, final_folder_path)

    if not success:
        logger.error(f"Failed to pull folder: {message}")
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Failed to pull folder",
                "error": message,
                "robot_ip": robot_ip,
                "folder_name": final_folder_path,
                "zip_path": zip_path,
                "file_name": csv_path,
                "pull_method": pull_method,
            },
        )

    logger.info(f"Folder pulled successfully: {message}")
    zip_path = zip_folder(final_folder_path)
    return {
        "success": success,
        "message": message,
        "robot_ip": robot_ip,
        "folder_name": final_folder_path,
        "zip_path": zip_path,
        "pull_method": pull_method,
        "target_dir": target_dir,
        "file_name": csv_path,
    }
