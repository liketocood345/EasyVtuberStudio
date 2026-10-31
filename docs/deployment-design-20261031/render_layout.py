"""Render resource and installed-layout maps from the current local contract."""
from pathlib import Path
import html,json
from PIL import Image,ImageDraw,ImageFont
D=Path(__file__).resolve().parent
FONT='C:/Windows/Fonts/msyh.ttc'
def render(name,title,cards,size):
    w,h=size;im=Image.new('RGB',size,'#f0f4f9');draw=ImageDraw.Draw(im)
    draw.text((35,22),title,font=ImageFont.truetype(FONT,34),fill='#14233c')
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="100%" height="100%" fill="#f0f4f9"/><g font-family="Microsoft YaHei, sans-serif" fill="#14233c">',f'<text x="35" y="61" font-size="34">{html.escape(title)}</text>']
    for x,y,cw,ch,heading,lines in cards:
        draw.rounded_rectangle((x,y,x+cw,y+ch),radius=15,fill='white',outline='#b8c9df',width=2)
        draw.text((x+22,y+18),heading,font=ImageFont.truetype(FONT,26),fill='#135e99')
        svg.extend([f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="15" fill="white" stroke="#b8c9df"/>',f'<text x="{x+22}" y="{y+49}" font-size="26" fill="#135e99">{html.escape(heading)}</text>'])
        fs=22
        while max(draw.textlength(line,font=ImageFont.truetype(FONT,fs)) for line in lines)>cw-44:fs-=1
        lineh=int(fs*1.65)
        assert 78+len(lines)*lineh<ch,(name,heading)
        for i,line in enumerate(lines):
            yy=y+70+i*lineh
            draw.text((x+22,yy),line,font=ImageFont.truetype(FONT,fs),fill='#263650')
            svg.append(f'<text xml:space="preserve" x="{x+22}" y="{yy+fs}" font-size="{fs}">{html.escape(line)}</text>')
    svg.append('</g></svg>');im.save(D/(name+'.png'));(D/(name+'.svg')).write_text('\n'.join(svg),'utf-8')
top=[
('GitHub CORE：部署前已有',['├─ DEPLOY / 主 EXE / 公共代码 / 脚本','├─ bai 示例角色、beitou.GIF 配件','├─ 已消毒的种子与图层 / 区域晃动设置','├─ 教师源码套件 + 68KB 无运行时薄入口','└─ 不含已安装 addons、Python、torch']),
('共用基座：仅安装目录内',['├─ NuGet Python 3.10.11（固定 SHA256）','├─ PyPI / PyTorch 固定版本 + 文件哈希','├─ runtime/venvs/common：只创建一次','├─ face / output / teacher 按选择追加','└─ torch / Python 不进入 HF']),
('HF 后备方舟：并非整仓镜像',['├─ packages/windows-x64/<module>/<version>/','├─ 每模块一个 ZIP + 固定文件契约','├─ THA3、无运行时教师、OSF、NN、MP','├─ seed/ 与 GitHub 同一份发布种子/示例','└─ 上游下载失败 / 坏哈希后才用；DEPLOY 不取种子'])]
tiers=[
('[1] basic_run：基础运行',['GitHub → bai / 配件 / 种子 / Student 代码','官方源 → base 固定 wheel → 本地 base 模块','落盘 → runtime/python310 + venvs/common','不装 TensorBoard / grpc / quaternion','HF 不需要单独复制 basic_run 包']),
('[2] openseeface：面捕',['本机模块 → GitHub v1.20.5 → HF ZIP 备用','落盘 → addons/openseeface/{Binary,models,Licenses}','Binary 内 Python DLL / 依赖是已验证私有 ABI','完整保留，不强拆为 common Python','不捆绑通用 Python / torch 安装分发']),
('[3] face_puppeteer：MediaPipe',['Google 模型 → 哈希校验 → mediapipe.zip','HF packages/windows-x64/mediapipe/ 备用','落盘 → addons/face_puppeteer/mediapipe/*.task','公共 MP / protobuf → common 的 face overlay','DEPLOY 只补资源，不碰种子']),
('[4] tha3_models：四种变体',['上游固定内容 → tha3_models.zip → HF 备用','separable_half / float + standard_half / float','落盘 → addons/tha3_models/<variant>/*.pt','THA3 代码在 CORE；torch / ORT 复用 common','同一套文件哈希验证两条下载路径']),
('[5] tha4_training：独立教师',['CORE 源码/薄入口 + 上游 5 权重与 pose','规范化 → tha4_training.zip；HF 同内容备用','落盘 → addons/tha4_training/，无 runtime','选择本档才给 common 追加 teacher extras','训练队列/存档 → workspace/tools/tha4_training']),
('[6] output_enhancement：后处理',['上游 NN 数据包 → 单文件 ZIP → HF 备用','RIFE / waifu2x / Real-ESRGAN 固定 ONNX','落盘 → addons/output_enhancement/ezvtb_data','ORT DirectML / PyAnime4K → common overlay','本机已有资源也必须通过完整哈希验证'])]
cards=[(30+i*790,105,760,330,t,lines)for i,(t,lines)in enumerate(top)]
cards += [(30+(i%2)*1185,470+(i//2)*395,1155,365,t,lines)for i,(t,lines)in enumerate(tiers)]
render('01-资源地图','EVS 资源地图｜本机 / 上游优先 → HF 方舟备用｜2026-10-31',cards,(2400,1680))
tree=['<安装根>/','├─ EasyVtuberStudio.exe / DEPLOY.bat / RESET_ADDON.bat','├─ src/ + face-puppeteer-…/ + deps/tha3/        [共用/分叉代码]','├─ data/character_models/…/bai_450k/            [CORE 示例与配件]','├─ packaging/ + deps/pip/                      [版本/哈希/安装配方]','├─ tools/tha4_teacher_portable/                 [教师来源套件，无 runtime]','├─ runtime/                                    [项目内共享]','│  ├─ python310/                               [公共基础解释器]','│  ├─ venvs/common/                            [所有兼容分叉共用]','│  ├─ bindings/components.json                 [解释器绑定]','│  └─ download_venv/                           [按需 HF 下载工具]','├─ addons/                                     [各模块专属内容]','│  ├─ openseeface/{Binary,models,Licenses}/      [私有 Binary ABI]','│  ├─ face_puppeteer/mediapipe/*.task            [MP 模型]','│  ├─ tha3_models/<四变体>/*.pt                  [THA3 权重]','│  ├─ tha4_training/                            [独立教师]','│  │  ├─ THA4Train.exe / app/ / src/tha4/','│  │  └─ data/{tha4/*.pt × 5,pose_dataset.pt}   [无自带 venv]','│  └─ output_enhancement/ezvtb_data/             [NN 模型]','└─ workspace/                                  [根内运行数据]','   ├─ load_preview_ui_state.json / basic_layers/ [发布种子→用户记忆]','   ├─ region_wobble_mask*.png','   ├─ cache/ / logs/ / diagnostics/              [缓存与日志]','   ├─ asset_downloads/ / modules/                [下载与可复用压缩模块]','   ├─ imports/ / module-staging/ / module-backups/','   └─ tools/tha4_training/{queue,jobs,…}          [教师输入/进度/断点]']
base=['runtime/venvs/common/','├─ base：torch / torchvision / wx / NumPy / SciPy','│        contrib OpenCV / Pillow / matplotlib / OmegaConf / einops','├─ face：MediaPipe / protobuf / sounddevice 等','├─ output：ORT DirectML / PyAnime4K 等','└─ teacher：TensorBoard / grpc / quaternion 等（选择 [5] 后）','','分叉只共享公共库；教师仍从自己的组件目录读源码和权重。','未经验证的兼容问题可以绑定根内私有环境。','OSF Binary 是已验证 ABI 例外，不借用 common 的 Python DLL。']
boundary=['本机','├─ 桌面快捷方式 → 安装根内 EXE','└─ 所有受 EVS 控制的文件 → 安装根内','','本图展示正常安装结构，不把实验回滚包当发行内容。','部署不修改系统 Python、全局 PATH 或用户 site-packages。','缓存 / 临时文件 / 导入副本 / 训练产物均使用根内路径。','删除安装根即带走这些项目文件。','','资源地图和结构图均为同一修订的结果；不是改造前后对比。','发布流程：本地验收 → HF / GitHub 回读 → SSH 安装。']
render('02-实装结构图','EVS 完整安装结构｜共享依赖与各分叉私有内容｜2026-10-31',[(30,105,1510,1240,'完整目录树',tree),(1570,105,1060,640,'按需追加到同一 common',base),(1570,780,1060,565,'目录边界与验收状态',boundary)],(2660,1380))
(D/'deployment_target_blueprint.json').write_text(json.dumps({'schema_version':2,'revision':'2026.10.31-r1','status':'verified_layout_release_pipeline','resource_map':{'core':top[0][1],'base':top[1][1],'hf':top[2][1],'tiers':tiers},'installed_tree':tree,'shared':base,'boundary':boundary},ensure_ascii=False,indent=2)+'\n','utf-8')
