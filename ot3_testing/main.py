#!/usr/bin/env python3
import paramiko

key = paramiko.RSAKey.from_private_key_file("../shared_data/robot_key")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("connecting")
ssh.connect(hostname="192.168.6.8", username="root",
            pkey=key, allow_agent=False, look_for_keys=False)
print("connected")
commands = "df"
stdin, stdout, stderr = ssh.exec_command(commands)
stdin.close()
res, err = stdout.read(), stderr.read()
result = res if res else err
print(result)
ssh.close()
