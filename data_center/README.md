# Data Center Service

- Description:
  
  It's a service for downloading test_data from flex and upload the data to google drive, the service support api for that, and call the aip automaticly by user

---

## Overview

- server name
  
  data-center.service  (/opt/data-center-files)

## Structure

- ./download_report_handler

- ./files_server

- ./google_driver_handler

- README.md

- upload_to_server.py
  
  (Run this script for upload the scripts to server and restart the server)

## API Method

- /api/download/testing_data 
  
  POST: download files from Flex to server

- /api/flex/discover
  
  GET:

- /api/flex/update/date
  
  POST:

- /api/flex/run/script
  
  POST:

- /version
  
  GET:
  
  ---
  
  

- /api/google/drive/create/folder
  
  POST:

- /api/google/drive/copy/file
  
  POST:

- /api/google/drive/delete/file
  
  DELETE:

- /api/google/drive/fill/cell
  
  POST:
  
  
  
  




