"""
Shared logging configuration
"""

import logging
from rich.logging import RichHandler


# 레벨별 색상 매핑
LEVEL_COLORS = {
    "DEBUG": "blue",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold red",
}


class ColoredFormatter(logging.Formatter):
    """Rich 마크업 기반 컬러 포매터"""

    def format(self, record):
        level_color = LEVEL_COLORS.get(record.levelname, "white")
        # 원본 포맷 문자열에 색상 적용
        original_format = self._style._fmt
        self._style._fmt = original_format.replace(
            "%(levelname)s", f"[{level_color}]%(levelname)s[/{level_color}]"
        )
        result = super().format(record)
        self._style._fmt = original_format
        return result


def setup_logger(name):
    """
    RichHandler 기반 로거 생성

    Args:
        name: 로거 이름 (파일명 또는 모듈명)

    Returns:
        configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 기존 핸들러 제거 (중복 방지)
    if logger.hasHandlers():
        logger.handlers.clear()

    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=False,
        show_level=False,
        show_path=False,
    )
    console_handler.setLevel(logging.INFO)

    # 컬러 포매터 적용
    console_formatter = ColoredFormatter(
        f"[[cyan]{name}[/cyan] | %(levelname)s] %(message)s"
    )
    console_handler.setFormatter(console_formatter)

    logger.addHandler(console_handler)

    return logger
