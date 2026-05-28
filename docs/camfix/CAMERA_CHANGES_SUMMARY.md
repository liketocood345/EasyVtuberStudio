## Camfix 说明

本目录用于**隔离测试摄像头问题**：在 THA4 原版界面上，只改摄像头区域，不包含实验版里的其它 UI/功能升级。

### 文件

| 文件 | 说明 |
|------|------|
| `character_model_mediapipe_puppeteer.original.py` | 未改动的原版 |
| `character_model_mediapipe_puppeteer.camfix.py` | 原版 + **仅摄像头区**升级 |
| `run_camfix_puppeteer.bat` | 双击运行 camfix |

### 相对原版，camfix **只**增加了

1. **摄像头来源列**（预览右侧）：下拉选择、刷新按钮、状态文字  
2. **设备枚举**：DirectShow 名称列表（`pygrabber`），DroidCam 优先用 MSMF  
3. **后台打开摄像头**：切换来源时在子线程打开，避免 UI 卡死/闪退  
4. **多后端重试**：MSMF / DSHOW（DroidCam 项跳过 DSHOW 回退）、MJPG/YUY2、640×480  
5. **预览缓冲**：`wx.Image.SetData`、保留上一帧、摄像头区专用错误提示  
6. **启动**：不再写死 `VideoCapture(0)`，启动后自动扫描并优先连接名称含 DroidCam 的设备  

### 刻意 **未** 包含（避免干扰判断）

- 紧凑/完整双窗口、独立输出窗、自动平移缩放、曲线 UI、持久化等实验版功能  
- 未加载模型时锁定/解锁其它面板（原版行为保留）  
- 视频文件/图片文件输入（仅摄像头，便于对比）

### 对比方法

1. 运行 `run_camfix_puppeteer.bat`  
2. 不加载模型，只测摄像头预览与 head 数值是否变化  
3. 若 camfix 正常而实验版异常 → 问题多半在**非摄像头**改动  
4. 若 camfix 仍异常 → 优先查 DroidCam 驱动/格式与 OpenCV 后端
