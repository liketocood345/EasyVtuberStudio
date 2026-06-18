"""Global layer hotkey registration (Win32 RegisterHotKey via wx)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import wx

from layer_runtime import (
    MAX_LAYER_HOTKEY_BINDINGS,
    BasicLayersState,
    LayerHotkeyBinding,
    layer_registers_own_hotkeys,
    normalize_layer_hotkey_action,
)

HOTKEY_ID_BASE = 0xBE00


@dataclass(frozen=True)
class LayerHotkeyDispatch:
    slot_id: int
    action: str
    modifiers: int = 0
    key_code: int = 0


def format_key_spec(modifiers: int, key_code: int) -> str:
    parts: list[str] = []
    if modifiers & wx.MOD_CONTROL:
        parts.append("Ctrl")
    if modifiers & wx.MOD_ALT:
        parts.append("Alt")
    if modifiers & wx.MOD_SHIFT:
        parts.append("Shift")
    if modifiers & wx.MOD_WIN:
        parts.append("Win")
    try:
        key_name = wx.GetKeyText(int(key_code)).strip()
    except Exception:
        key_name = ""
    if key_name:
        parts.append(key_name)
    return "+".join(parts) if parts else "?"


def capture_hotkey_from_event(event: wx.KeyEvent) -> Optional[LayerHotkeyBinding]:
    key_code = int(event.GetKeyCode())
    if key_code in (wx.WXK_SHIFT, wx.WXK_CONTROL, wx.WXK_ALT, wx.WXK_COMMAND):
        return None
    if key_code in (wx.WXK_ESCAPE, wx.WXK_NONE):
        return None
    modifiers = 0
    if event.ControlDown():
        modifiers |= wx.MOD_CONTROL
    if event.AltDown():
        modifiers |= wx.MOD_ALT
    if event.ShiftDown():
        modifiers |= wx.MOD_SHIFT
    if event.MetaDown():
        modifiers |= wx.MOD_WIN
    return LayerHotkeyBinding(
        action="",
        modifiers=modifiers,
        key_code=key_code,
    )


def hotkey_id_for_binding(slot_id: int, binding_index: int) -> int:
    return HOTKEY_ID_BASE + int(slot_id) * MAX_LAYER_HOTKEY_BINDINGS + int(binding_index)


class LayerHotkeyRegistry:
    def __init__(self, window: wx.Window) -> None:
        self._window = window
        self._dispatch: dict[int, LayerHotkeyDispatch] = {}
        self._failures: list[str] = []

    @property
    def failures(self) -> list[str]:
        return list(self._failures)

    def clear(self) -> None:
        for hotkey_id in list(self._dispatch.keys()):
            try:
                self._window.UnregisterHotKey(hotkey_id)
            except Exception:
                pass
        self._dispatch.clear()
        self._failures.clear()

    def sync_from_state(self, state: BasicLayersState, *, enabled: bool = True) -> None:
        self.clear()
        if not enabled:
            return
        if wx.Platform != "__WXMSW__":
            self._failures.append("Global layer hotkeys require Windows.")
            return
        if not self._window.GetHandle():
            self._failures.append("Layer hotkeys deferred: window handle not ready.")
            return
        seen_keys: dict[tuple[int, int], str] = {}
        for layer in state.layers:
            if not layer_registers_own_hotkeys(layer):
                continue
            for binding_index, binding in enumerate(
                    layer.hotkey_bindings[:MAX_LAYER_HOTKEY_BINDINGS]):
                if binding.key_code <= 0:
                    continue
                action = normalize_layer_hotkey_action(binding.action)
                key = (int(binding.modifiers), int(binding.key_code))
                label = format_key_spec(binding.modifiers, binding.key_code)
                if key in seen_keys:
                    self._failures.append(
                        f"Duplicate hotkey {label}: layer {layer.slot_id + 1} vs {seen_keys[key]}")
                    continue
                hotkey_id = hotkey_id_for_binding(layer.slot_id, binding_index)
                try:
                    registered = self._window.RegisterHotKey(
                        hotkey_id,
                        int(binding.modifiers),
                        int(binding.key_code))
                except Exception as exc:
                    self._failures.append(
                        f"Could not register {label} for layer {layer.slot_id + 1}: {exc}")
                    continue
                if not registered:
                    self._failures.append(
                        f"Could not register {label} for layer {layer.slot_id + 1} "
                        f"(in use or invalid).")
                    continue
                seen_keys[key] = f"layer {layer.slot_id + 1}"
                self._dispatch[hotkey_id] = LayerHotkeyDispatch(
                    slot_id=int(layer.slot_id),
                    action=action,
                    modifiers=int(binding.modifiers),
                    key_code=int(binding.key_code),
                )

    @property
    def registered_count(self) -> int:
        return len(self._dispatch)

    def handle_hotkey(self, hotkey_id: int) -> Optional[LayerHotkeyDispatch]:
        return self._dispatch.get(int(hotkey_id))
