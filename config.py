import os
from dotenv import load_dotenv
from util.logz import create_logger

load_dotenv() 
logger = create_logger()

PORT=os.getenv("PORT", default=8080)
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
NICKNAME = os.getenv("NICKNAME", default="POPSAUCE-BOT")
CONNECTION = os.getenv("CONNECTION")