"""Smoke tests for layer hotkeys and GIF playback modes."""
import sys
import time
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from layer_runtime import (
    GIF_PLAYBACK_LOOP,
    GIF_PLAYBACK_PLAY_ONCE,
    GIF_PLAYBACK_STOPPED,
    LAYER_HOTKEY_ACTION_GIF_PLAY,
    LAYER_HOTKEY_ACTION_GIF_PLAY_ONCE,
    LAYER_HOTKEY_ACTION_GIF_SHOW_PLAY_ONCE_HIDE,
    LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE,
    BasicLayerSlot,
    BasicLayersState,
    LayerHotkeyBinding,
    apply_layer_hotkey_action,
    apply_hotkey_action_idle_layer_state,
    layer_hotkey_action_needs_asset_cache_reset,
    layer_hotkey_bindings_from_list,
    migrate_layer_hotkey_bindings,
    normalize_layer_hotkey_action,
    consume_layer_gif_playback_visibility_dirty,
    reload_layer_from_asset_material,
    resolve_gif_frame_index,
    layer_has_active_gif_playback,
    set_gif_playback_mode,
)
from layer_hotkey_registry import hotkey_id_for_binding


def test_gif_playback_stopped_returns_first_frame() -> None:
    layer = BasicLayerSlot(slot_id=0)
    set_gif_playback_mode(layer, GIF_PLAYBACK_STOPPED, now=100.0)
    durations = [100, 100]
    idx = resolve_gif_frame_index(layer, durations, 200, 2, 150.0)
    assert idx == 0


def test_gif_playback_loop_wraps() -> None:
    layer = BasicLayerSlot(slot_id=0)
    set_gif_playback_mode(layer, GIF_PLAYBACK_LOOP, now=1.0)
    durations = [100, 100]
    idx_early = resolve_gif_frame_index(layer, durations, 200, 2, 1.05)
    idx_late = resolve_gif_frame_index(layer, durations, 200, 2, 1.15)
    assert idx_early == 0
    assert idx_late == 1


def test_gif_playback_once_returns_to_stopped() -> None:
    layer = BasicLayerSlot(slot_id=0)
    set_gif_playback_mode(layer, GIF_PLAYBACK_PLAY_ONCE, now=0.0)
    durations = [50, 50]
    assert resolve_gif_frame_index(layer, durations, 100, 2, 0.02) == 0
    assert resolve_gif_frame_index(layer, durations, 100, 2, 0.08) == 1
    assert resolve_gif_frame_index(layer, durations, 100, 2, 0.2) == 0
    assert layer.gif_playback_mode == GIF_PLAYBACK_STOPPED


def test_gif_show_play_once_hide() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "test.gif"
    layer.visible = False
    assert apply_layer_hotkey_action(
        state, layer.slot_id, "gif_show_play_once_hide", now=0.0)
    assert layer.visible
    assert layer.gif_hide_when_playback_stops
    durations = [40, 40]
    assert resolve_gif_frame_index(layer, durations, 80, 2, 0.05) == 0
    assert resolve_gif_frame_index(layer, durations, 80, 2, 0.15) == 0
    assert not layer.visible
    assert not layer.gif_hide_when_playback_stops
    assert layer._gif_playback_visibility_dirty
    assert consume_layer_gif_playback_visibility_dirty(state)
    assert not layer._gif_playback_visibility_dirty


def test_apply_layer_hotkey_toggle_visible() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.visible = True
    assert apply_layer_hotkey_action(state, layer.slot_id, "toggle_visible")
    assert not layer.visible


def test_deprecated_hold_actions_migrate_on_load() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.hotkey_bindings = [
        LayerHotkeyBinding(action="hold_to_hide", modifiers=0, key_code=65),
        LayerHotkeyBinding(action="hold_to_show_play_once", modifiers=0, key_code=66),
    ]
    migrate_layer_hotkey_bindings(state)
    assert layer.hotkey_bindings[0].action == LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE
    assert (
        layer.hotkey_bindings[1].action
        == LAYER_HOTKEY_ACTION_GIF_SHOW_PLAY_ONCE_HIDE)


def test_normalize_layer_hotkey_action_defaults_unknown() -> None:
    assert normalize_layer_hotkey_action("hold_to_hide") == LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE
    assert normalize_layer_hotkey_action("bogus") == LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE
    assert normalize_layer_hotkey_action("gif_play_once") == LAYER_HOTKEY_ACTION_GIF_PLAY_ONCE


def test_hotkey_binding_round_trip() -> None:
    draft = LayerHotkeyBinding(action="gif_play_once", modifiers=0, key_code=0)
    restored = LayerHotkeyBinding.from_dict(draft.to_dict())
    assert restored is not None
    assert restored.action == "gif_play_once"


def test_hotkey_action_needs_asset_cache_reset() -> None:
    layer = BasicLayerSlot(slot_id=0, asset_path="x.gif")
    assert layer_hotkey_action_needs_asset_cache_reset(
        layer, LAYER_HOTKEY_ACTION_GIF_PLAY_ONCE)
    assert not layer_hotkey_action_needs_asset_cache_reset(
        layer, LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE)


def test_reload_layer_idle_for_gif_show_play_once_hide() -> None:
    layer = BasicLayerSlot(slot_id=0, asset_path="a.gif", visible=True)
    assert reload_layer_from_asset_material(
        layer, idle_for_hotkey_action="gif_show_play_once_hide", now=2.0)
    assert not layer.visible
    assert layer.gif_playback_mode == GIF_PLAYBACK_STOPPED


def test_layer_hotkey_bindings_from_list() -> None:
    bindings = layer_hotkey_bindings_from_list([
        {"action": "hold_to_show", "modifiers": 2, "key_code": 70},
    ])
    assert len(bindings) == 1
    assert bindings[0].action == LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE


def test_hotkey_id_for_binding() -> None:
    assert hotkey_id_for_binding(2, 1) > hotkey_id_for_binding(2, 0)


def test_apply_hotkey_action_idle_layer_state_gif_play() -> None:
    layer = BasicLayerSlot(slot_id=0, asset_path="loop.gif")
    apply_hotkey_action_idle_layer_state(layer, LAYER_HOTKEY_ACTION_GIF_PLAY, now=0.0)
    assert layer.gif_playback_mode == GIF_PLAYBACK_LOOP


def test_layer_has_active_gif_playback() -> None:
    layer = BasicLayerSlot(slot_id=0, asset_path="a.gif", visible=True)
    set_gif_playback_mode(layer, GIF_PLAYBACK_LOOP, now=0.0)
    assert layer_has_active_gif_playback(layer)


def main() -> None:
    test_gif_playback_stopped_returns_first_frame()
    test_gif_playback_loop_wraps()
    test_gif_playback_once_returns_to_stopped()
    test_gif_show_play_once_hide()
    test_apply_layer_hotkey_toggle_visible()
    test_deprecated_hold_actions_migrate_on_load()
    test_normalize_layer_hotkey_action_defaults_unknown()
    test_hotkey_binding_round_trip()
    test_hotkey_action_needs_asset_cache_reset()
    test_reload_layer_idle_for_gif_show_play_once_hide()
    test_layer_hotkey_bindings_from_list()
    test_hotkey_id_for_binding()
    test_apply_hotkey_action_idle_layer_state_gif_play()
    test_layer_has_active_gif_playback()
    print("smoke_layer_hotkeys_ok")


if __name__ == "__main__":
    main()
