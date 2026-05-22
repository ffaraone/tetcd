"""Dynaconf-backed settings loader for tetcd.

Settings are layered (highest priority first): environment variables prefixed
with ``TETCD_``, ``settings.toml``, ``.secrets.toml`` (gitignored).
"""

from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="TETCD",
    settings_files=["settings.toml", ".secrets.toml"],
    environments=True,
    load_dotenv=True,
)
