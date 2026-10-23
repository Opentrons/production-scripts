from core.google import GoogleDriver
from modules.ecn.repository import MongoEcnRepository
from modules.ecn.service import EcnService
from modules.ecn.monitor import EcnMonitorService


ecn_service = EcnService(MongoEcnRepository(), GoogleDriver())
ecn_monitor_service = EcnMonitorService(ecn_service)
