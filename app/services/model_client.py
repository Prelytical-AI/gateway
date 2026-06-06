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

    def test_model_connection(self) -> tuple[bool, str]:
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

    def generate_sql(self, system: str, user: str) -> str:
        content = self.chat(system=system, user=user, temperature=0.1)
        return extract_sql(content)

    def summarize_results(
        self,
        system: str,
        user: str,
    ) -> str:
        return self.chat(system=system, user=user, temperature=0.2)

    def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.1,
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
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                "Cannot connect to Ollama. Ensure Ollama is running on this VM "
                f"at {self.base_url}."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"Model request timed out after {self.timeout} seconds."
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
