"""3DFrame configuration.

TODO: This is incomplete (and unused). In future, all configuration
values will be loaded and sourced from here.

"""

from pydantic import BaseSettings


class Config(BaseSettings):
    SEGMENTS: int = 48
