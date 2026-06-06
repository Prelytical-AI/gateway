from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import requests

from app.core.config import Settings, settings as default_settings

logger = logging.getLogger(__name__)

SQL_FENCE_PATTERN = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


class ModelClient:
    def __init__(self, config: Optional[Settings] = None) -> None:
        self.config = config or default_settings
        self.base_url = self.config.model_base_url.rstrip("/")
        self.timeout = self.config.model_timeout_seconds

    def test_model_connection(self, *, full_chat: bool = False) -> tuple[bool, str]:
        if not full_chat:
            return self.ping()
        try:
            response = self.chat(
                system="You are a helpful assistant.",
                user="Return exactly the word ok.",
                temperature=0.0,
            )
            if "ok" in response.lower():
                return True, "Model connection successful."
            return True, f"Model responded: {response[:80]}"
        except Exception as exc:
            logger.exception("Model connection test failed")
            return False, str(exc)

    def ping(self) -> tuple[bool, str]:
        root = self.base_url.removesuffix("/v1").rstrip("/")
        url = f"{root}/api/tags"
        try:
            response = requests.get(url, timeout=15)
        except requests.exceptions.ConnectionError as exc:
            return False, (
                f"Cannot connect to Ollama at {self.base_url}. "
                "Ensure Ollama is running."
            )
        except requests.exceptions.Timeout:
            return False, "Ollama tags check timed out (15s). Model may still be loading."

        if response.status_code >= 400:
            return False, f"Ollama API error ({response.status_code})"

        try:
            data = response.json()
            names = [m.get("name", "") for m in data.get("models", [])]
        except (ValueError, TypeError):
            return False, "Unexpected response from Ollama /api/tags"

        if not names:
            return False, f"No models pulled on Ollama host. Run: ollama pull {self.config.model_name}"

        configured = self.config.model_name
        if configured in names or any(n.startswith(f"{configured}:") or n == configured for n in names):
            return True, f"Ollama ready ({configured})."
        if any(configured in n for n in names):
            return True, f"Ollama ready (model family: {configured})."

        return False, (
            f"Ollama is up but '{configured}' not found. "
            f"Available: {', '.join(names[:5])}"
        )

    def generate_sql(self, system: str, user: str) -> str:
        content = self.chat(system=system, user=user, temperature=0.1)
        return extract_sql(content)

    def summarize_results(
        self,
        system: str,
        user: str,
    ) -> str:
        return self.chat(system=system, user=user, temperature=0.2)

    def generate_brief(self, system: str, user: str) -> str:
        return self.chat(
            system=system,
            user=user,
            temperature=0.2,
            timeout_seconds=self.config.brief_timeout_seconds,
        )

    def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.1,
        timeout_seconds: Optional[int] = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.model_api_key}",
        }

        try:
            timeout = timeout_seconds if timeout_seconds is not None else self.timeout
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                "Cannot connect to Ollama. Ensure Ollama is running on this VM "
                f"at {self.base_url}."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"Model request timed out after {timeout} seconds."
            ) from exc

        if response.status_code >= 400:
            raise RuntimeError(
                f"Model API error ({response.status_code}): {response.text[:500]}"
            )

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected model response format: {data}") from exc


def extract_sql(content: str) -> str:
    fenced = SQL_FENCE_PATTERN.search(content)
    if fenced:
        return fenced.group(1).strip().rstrip(";")

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    sql_lines: List[str] = []
    for line in lines:
        if line.startswith("--"):
            continue
        sql_lines.append(line)
        if line.endswith(";"):
            break

    if sql_lines:
        return " ".join(sql_lines).rstrip(";").strip()

    return content.strip().rstrip(";")
