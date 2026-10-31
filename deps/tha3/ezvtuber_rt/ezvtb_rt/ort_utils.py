import json
import os
import time
from datetime import datetime
import onnxruntime as ort


def _ts():
    return datetime.now().strftime('[%m/%d/%Y-%H:%M:%S]')


def _select_ort_providers(device_id: int = 0):
    available = list(ort.get_available_providers())
    if 'DmlExecutionProvider' in available:
        return (
            ['DmlExecutionProvider', 'CPUExecutionProvider'],
            [
                {
                    'device_id': device_id,
                },
                {},
            ],
            'dml',
        )
    if 'CUDAExecutionProvider' in available:
        return (
            ['CUDAExecutionProvider', 'CPUExecutionProvider'],
            [{'device_id': device_id}, {}],
            'cuda',
        )
    return (['CPUExecutionProvider'], [{}], 'cpu')


def createORTSession(model_path: str, device_id: int = 0):
    """创建 ONNX Runtime 推理会话。会输出加载流程和当前使用的模型文件名（与 TRT 加载时的输出风格对应）。"""
    filename = os.path.basename(model_path)
    print(f'{_ts()} [ORT] Loading ONNX model from path {model_path}...')
    available = list(ort.get_available_providers())
    # （补上 DirectML 推理后端）26.10.29 22:15 s
    providers, provider_options, kind = _select_ort_providers(device_id)
    # #region agent log
    try:
        with open(r'e:\debug-86a17c.log', 'a', encoding='utf-8') as _df:
            _df.write(json.dumps({
                'sessionId': '86a17c',
                'runId': 'post-fix-dml',
                'hypothesisId': 'T',
                'location': 'ort_utils.py:createORTSession',
                'message': 'ORT session providers',
                'data': {
                    'file': filename,
                    'available': available,
                    'chosen': providers,
                    'kind': kind,
                    'has_dml': 'DmlExecutionProvider' in available,
                },
                'timestamp': int(time.time() * 1000),
            }) + '\n')
    except Exception:
        pass
    # #endregion
    options = ort.SessionOptions()
    options.enable_mem_pattern = kind != "dml"
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.enable_cpu_mem_arena = True
    session = ort.InferenceSession(
        model_path,
        sess_options=options,
        providers=providers,
        provider_options=provider_options)
    # （补上 DirectML 推理后端）26.10.29 22:15 e
    print(f'{_ts()} [ORT] Completed loading session: {filename}')
    return session