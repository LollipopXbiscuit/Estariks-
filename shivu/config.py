import os

class Config(object):
    LOGGER = True

    # Get this value from my.telegram.org/apps
    OWNER_ID = os.environ.get("OWNER_ID", "6765826972")
    sudo_users = [uid.strip() for uid in os.environ.get("SUDO_USERS", "6845325416,6765826972").split(",")]
    uploading_users = os.environ.get("UPLOADING_USERS", "").split(",") if os.environ.get("UPLOADING_USERS") else []
    GROUP_ID = int(os.environ.get("GROUP_ID", "-1002133191051"))
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    mongo_url = os.environ.get("MONGODB_URL")
    PHOTO_URL = ["https://i.ibb.co/5gpmxQ5k/jsorg.jpg"]
    SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT", "EstariksSupport")
    UPDATE_CHAT = os.environ.get("UPDATE_CHAT", "EstariksUpdates")
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "EstariksBot")
    CHARA_CHANNEL_ID = os.environ.get("CHARA_CHANNEL_ID", "-1002934487265")
    api_id_str = os.environ.get("TELEGRAM_API_ID", "0")
    api_id = int(api_id_str) if api_id_str and api_id_str.strip() else 0
    api_hash = os.environ.get("TELEGRAM_API_HASH")

    
class Production(Config):
    LOGGER = True


class Development(Config):
    LOGGER = True
