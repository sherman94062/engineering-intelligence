"""Shared helpers for talking to the DevLake REST API.

DevLake exposes a JSON REST API on :8080. The admin user / password configured
in env gates write actions via Basic Auth. Endpoints used here follow the
`plugins/github/connections`, `blueprints`, and `pipelines` shapes documented
at https://devlake.apache.org/docs/DeveloperManuals/RestApi .
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / "devlake-config" / "env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


@dataclass
class DevLakeClient:
    base_url: str
    user: str
    password: str
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "DevLakeClient":
        return cls(
            base_url=os.getenv("DEVLAKE_URL", "http://localhost:8080").rstrip("/"),
            user=os.getenv("DEVLAKE_ADMIN_USER", "admin"),
            password=os.getenv("DEVLAKE_ADMIN_PASS", "admin"),
        )

    @property
    def auth(self) -> tuple[str, str]:
        return (self.user, self.password)

    def request(self, method: str, path: str, **kw: Any) -> Any:
        url = f"{self.base_url}{path}"
        kw.setdefault("timeout", self.timeout)
        kw.setdefault("auth", self.auth)
        resp = requests.request(method, url, **kw)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"DevLake {method} {path} failed ({resp.status_code}): {resp.text}"
            )
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text

    def get(self, path: str, **kw: Any) -> Any:
        return self.request("GET", path, **kw)

    def post(self, path: str, json: Any = None, **kw: Any) -> Any:
        return self.request("POST", path, json=json, **kw)

    def patch(self, path: str, json: Any = None, **kw: Any) -> Any:
        return self.request("PATCH", path, json=json, **kw)

    def put(self, path: str, json: Any = None, **kw: Any) -> Any:
        return self.request("PUT", path, json=json, **kw)

    def delete(self, path: str, **kw: Any) -> Any:
        return self.request("DELETE", path, **kw)

    def wait_ready(self, attempts: int = 60, delay: float = 2.0) -> None:
        for _ in range(attempts):
            try:
                self.get("/ping")
                return
            except Exception:
                time.sleep(delay)
        raise RuntimeError(f"DevLake at {self.base_url} did not become ready")


def env_or_die(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"error: {name} is not set (check devlake-config/env)", file=sys.stderr)
        sys.exit(1)
    return value
