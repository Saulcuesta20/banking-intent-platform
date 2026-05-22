import os


def pytest_configure():
    os.environ.setdefault("USE_AI_PROVIDERS", "true")
