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
    LAYER_HOTKEY_ACTION_HOLD_TO_HIDE,
    LAYER_HOTKEY_ACTION_HOLD_TO_SHOW,
    LAYER_HOTKEY_ACTION_HOLD_TO_SHOW_PLAY_ONCE,
    BasicLayerSlot,
    BasicLayersState,
    LayerHotkeyBinding,
    apply_layer_hotkey_action,
    apply_hotkey_action_idle_layer_state,
    begin_layer_hotkey_hold,
    end_layer_hotkey_hold,
    is_layer_hotkey_hold_action,
    layer_hotkey_bindings_from_list,
    normalize_layer_hotkey_action,
    consume_layer_gif_playback_visibility_dirty,
    reload_layer_from_asset_material,
    resolve_gif_frame_index,
    layer_has_active_gif_playback,
    set_gif_playback_mode,
)
from layer_hotkey_registry import format_key_spec, hotkey_id_for_binding


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


def test_hold_to_hide_and_release() -> None:
    layer = BasicLayerSlot(slot_id=0, visible=True)
    snapshot = begin_layer_hotkey_hold(layer, LAYER_HOTKEY_ACTION_HOLD_TO_HIDE)
    assert snapshot is not None
    assert snapshot.restore_visible is True
    assert not layer.visible
    end_layer_hotkey_hold(layer, snapshot, action=LAYER_HOTKEY_ACTION_HOLD_TO_HIDE)
    assert layer.visible


def test_hold_to_show_and_release() -> None:
    layer = BasicLayerSlot(slot_id=0, visible=False)
    snapshot = begin_layer_hotkey_hold(layer, LAYER_HOTKEY_ACTION_HOLD_TO_SHOW)
    assert snapshot is not None
    assert snapshot.restore_visible is False
    assert layer.visible
    end_layer_hotkey_hold(layer, snapshot, action=LAYER_HOTKEY_ACTION_HOLD_TO_SHOW)
    assert not layer.visible


def test_hold_to_show_play_once_gif() -> None:
    layer = BasicLayerSlot(slot_id=0, visible=False, asset_path="fx.gif")
    set_gif_playback_mode(layer, GIF_PLAYBACK_LOOP, now=0.0)
    snapshot = begin_layer_hotkey_hold(
        layer, LAYER_HOTKEY_ACTION_HOLD_TO_SHOW_PLAY_ONCE, now=1.0)
    assert snapshot is not None
    assert snapshot.restore_visible is False
    assert snapshot.restore_gif_playback_mode == GIF_PLAYBACK_LOOP
    assert layer.visible
    assert layer.gif_playback_mode == GIF_PLAYBACK_PLAY_ONCE
    assert not layer.gif_hide_when_playback_stops
    durations = [50, 50]
    assert resolve_gif_frame_index(layer, durations, 100, 2, 1.02) == 0
    assert resolve_gif_frame_index(layer, durations, 100, 2, 1.06) == 1
    assert resolve_gif_frame_index(layer, durations, 100, 2, 1.12) == 0
    assert layer.visible
    assert layer.gif_playback_mode == GIF_PLAYBACK_STOPPED
    end_layer_hotkey_hold(
        layer, snapshot, action=LAYER_HOTKEY_ACTION_HOLD_TO_SHOW_PLAY_ONCE)
    assert not layer.visible
    assert layer.gif_playback_mode == GIF_PLAYBACK_STOPPED


def test_hold_to_show_play_once_release_early() -> None:
    layer = BasicLayerSlot(slot_id=0, visible=False, asset_path="fx.gif")
    snapshot = begin_layer_hotkey_hold(
        layer, LAYER_HOTKEY_ACTION_HOLD_TO_SHOW_PLAY_ONCE, now=0.0)
    assert snapshot is not None
    durations = [100, 100]
    assert resolve_gif_frame_index(layer, durations, 200, 2, 0.05) == 0
    end_layer_hotkey_hold(
        layer, snapshot, action=LAYER_HOTKEY_ACTION_HOLD_TO_SHOW_PLAY_ONCE)
    assert not layer.visible
    assert layer.gif_playback_mode == GIF_PLAYBACK_STOPPED


def test_hold_to_show_play_once_requires_gif() -> None:
    layer = BasicLayerSlot(slot_id=0, visible=False, asset_path="still.png")
    assert begin_layer_hotkey_hold(
        layer, LAYER_HOTKEY_ACTION_HOLD_TO_SHOW_PLAY_ONCE) is None


def test_reload_layer_from_asset_material_for_hotkey_action() -> None:
    layer = BasicLayerSlot(slot_id=0, visible=True, asset_path="fx.gif")
    set_gif_playback_mode(layer, GIF_PLAYBACK_PLAY_ONCE, now=1.0)
    layer.gif_hide_when_playback_stops = True
    assert reload_layer_from_asset_material(
        layer, idle_for_hotkey_action="hold_to_show_play_once", now=2.0)
    assert not layer.visible
    assert layer.gif_playback_mode == GIF_PLAYBACK_STOPPED
    assert not layer.gif_hide_when_playback_stops

    layer.visible = True
    set_gif_playback_mode(layer, GIF_PLAYBACK_STOPPED, now=3.0)
    apply_hotkey_action_idle_layer_state(layer, "gif_play", now=4.0)
    assert layer.visible
    assert layer.gif_playback_mode == GIF_PLAYBACK_LOOP


def test_gif_play_once_motion_only_when_visible() -> None:
    layer = BasicLayerSlot(slot_id=0, visible=False, asset_path="fx.gif")
    set_gif_playback_mode(layer, GIF_PLAYBACK_PLAY_ONCE, now=0.0)
    assert not layer_has_active_gif_playback(layer)
    layer.visible = True
    assert layer_has_active_gif_playback(layer)


def test_reload_layer_from_asset_material_requires_path() -> None:
    layer = BasicLayerSlot(slot_id=0, asset_path=None)
    assert not reload_layer_from_asset_material(layer)


def test_hold_action_normalization() -> None:
    assert is_layer_hotkey_hold_action(LAYER_HOTKEY_ACTION_HOLD_TO_HIDE)
    assert is_layer_hotkey_hold_action(LAYER_HOTKEY_ACTION_HOLD_TO_SHOW)
    assert is_layer_hotkey_hold_action(LAYER_HOTKEY_ACTION_HOLD_TO_SHOW_PLAY_ONCE)
    assert not is_layer_hotkey_hold_action("toggle_visible")
    assert normalize_layer_hotkey_action("hold_to_hide") == LAYER_HOTKEY_ACTION_HOLD_TO_HIDE


def test_apply_layer_hotkey_gif_requires_gif_asset() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "test.png"
    assert not apply_layer_hotkey_action(state, layer.slot_id, "gif_play")


def test_hotkey_binding_round_trip() -> None:
    binding = LayerHotkeyBinding(action="toggle_visible", modifiers=2, key_code=70)
    restored = LayerHotkeyBinding.from_dict(binding.to_dict())
    assert restored is not None
    assert restored.action == "toggle_visible"
    assert restored.modifiers == 2
    assert restored.key_code == 70


def test_draft_hotkey_binding_without_key() -> None:
    draft = LayerHotkeyBinding(action="hold_to_show", modifiers=0, key_code=0)
    restored = LayerHotkeyBinding.from_dict(draft.to_dict())
    assert restored is not None
    assert restored.key_code == 0
    assert restored.action == "hold_to_show"
    bindings = layer_hotkey_bindings_from_list([draft.to_dict()])
    assert len(bindings) == 1
    assert bindings[0].key_code == 0


def test_hotkey_id_encoding() -> None:
    assert hotkey_id_for_binding(3, 1) != hotkey_id_for_binding(3, 0)
    assert hotkey_id_for_binding(3, 1) != hotkey_id_for_binding(4, 1)


def test_format_key_spec() -> None:
    try:
        import wx
    except ImportError:
        return
    app = wx.App(False)
    try:
        label = format_key_spec(0, ord("F"))
        assert "F" in label
    finally:
        app.Destroy()


def main() -> None:
    test_gif_playback_stopped_returns_first_frame()
    test_gif_playback_loop_wraps()
    test_gif_playback_once_returns_to_stopped()
    test_gif_show_play_once_hide()
    test_apply_layer_hotkey_toggle_visible()
    test_hold_to_hide_and_release()
    test_hold_to_show_and_release()
    test_hold_to_show_play_once_gif()
    test_hold_to_show_play_once_release_early()
    test_hold_to_show_play_once_requires_gif()
    test_reload_layer_from_asset_material_for_hotkey_action()
    test_gif_play_once_motion_only_when_visible()
    test_reload_layer_from_asset_material_requires_path()
    test_hold_action_normalization()
    test_apply_layer_hotkey_gif_requires_gif_asset()
    test_hotkey_binding_round_trip()
    test_draft_hotkey_binding_without_key()
    test_hotkey_id_encoding()
    test_format_key_spec()
    print("smoke_layer_hotkeys_ok")


if __name__ == "__main__":
    main()
