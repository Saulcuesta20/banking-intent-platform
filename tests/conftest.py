import os


def pytest_configure():
    os.environ["USE_AI_PROVIDERS"] = "false"
