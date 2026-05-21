from utils import VILLAGE_CONFIG, village_config

VILLAGE_KEY = "village3"
CONFIG = village_config(VILLAGE_KEY)


def get_config():
    return CONFIG


def load_dashboard_data():
    from app import load_all
    return load_all(VILLAGE_KEY)
