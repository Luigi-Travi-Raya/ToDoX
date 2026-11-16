from __future__ import annotations


class AppError(ValueError):
    """Error whose stable code can safely cross the pywebview bridge."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"APP_ERROR:{code}")

