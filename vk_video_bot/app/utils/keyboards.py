from __future__ import annotations

from typing import Iterable


def build_text_button(label: str, payload: dict | None = None) -> dict:
    return {
        "action": {
            "type": "text",
            "label": label,
            "payload": payload or {},
        }
    }


def build_callback_button(label: str, payload: dict) -> dict:
    return {
        "action": {
            "type": "callback",
            "label": label,
            "payload": payload,
        }
    }


def build_keyboard(button_rows: list[list[dict]], inline: bool = False, one_time: bool = False) -> dict:
    return {
        "inline": inline,
        "one_time": one_time,
        "buttons": button_rows,
    }


def build_selection_keyboard(items: Iterable[tuple[int, str]], callback_prefix: str) -> dict:
    rows: list[list[dict]] = []
    row: list[dict] = []
    for idx, (item_id, name) in enumerate(items, start=1):
        button = build_callback_button(
            label=f"Выбрать {name}",
            payload={"data": f"{callback_prefix}:{item_id}"},
        )
        row.append(button)
        if idx % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return build_keyboard(rows, inline=True, one_time=False)

