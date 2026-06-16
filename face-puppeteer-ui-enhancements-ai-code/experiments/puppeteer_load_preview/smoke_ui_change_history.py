"""Smoke test for UserChangeHistory (no wx required)."""
from ui_change_history import UserChangeHistory, EMPTY_LINE


def main() -> None:
    h = UserChangeHistory(3)
    assert h.lines(3) == [EMPTY_LINE, EMPTY_LINE, EMPTY_LINE]

    h.add("调整 平滑 → 0.50")
    assert h.lines(3)[0] == "调整 平滑 → 0.50"

    h.add("切换 面捕输入 → 摄像头")
    h.add("开启 显示网格")
    assert h.lines(3) == [
        "开启 显示网格",
        "切换 面捕输入 → 摄像头",
        "调整 平滑 → 0.50",
    ]

    h.add("开启 显示网格")
    assert h.lines(3)[0] == "开启 显示网格"
    assert h.lines(3)[1] == "切换 面捕输入 → 摄像头"

    h.add("切换 推理后端 → TensorRT")
    assert len([x for x in h.lines(3) if x != EMPTY_LINE]) == 3
    assert h.lines(3)[0] == "切换 推理后端 → TensorRT"

    print("smoke_ui_change_history: OK")


if __name__ == "__main__":
    main()
