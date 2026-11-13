# 本地真实语音服务

使用 sherpa-onnx，在 CPU 上运行 SenseVoice INT8 识别和 Kokoro v1.1 中文合成。

## 本机路径

| 内容 | 路径 |
|---|---|
| 服务代码 | `D:\挑战杯\silver-travel-avatar\p2-backend\speech` |
| Python虚拟环境 | `D:\挑战杯\p2-speech-local\.venv` |
| 识别和合成模型 | `D:\挑战杯\p2-speech-local\models` |
| 日志、生成的测试音频 | `D:\挑战杯\p2-speech-local` |
| 本地服务 | `http://127.0.0.1:18010` |

模型、环境、日志和录音位于仓库外，不随源码提交。当前环境使用本机已有Python 3.9.25创建独立venv；依赖版本见requirements-lock.txt。迁移服务器时安装匹配平台的依赖和模型，并通过SPEECH_MODEL_DIR指定模型目录。

## 启动和验证

队友首次从仓库启动时，先安装 Python 3.9，并在仓库根目录执行下面的命令。运行目录放在仓库外，已有依赖和模型的同学可以直接启动。

```powershell
$speechData = Join-Path (Split-Path -Parent (Get-Location).Path) 'p2-speech-local'
py -3.9 -m venv (Join-Path $speechData '.venv')
$speechPython = Join-Path $speechData '.venv\Scripts\python.exe'
& $speechPython -m pip install -r .\p2-backend\speech\requirements-lock.txt
& $speechPython -X utf8 .\p2-backend\speech\download-models.py --model-dir (Join-Path $speechData 'models') --workers 4
pwsh -NoProfile -File .\p2-backend\speech\start-local.ps1 -DataRoot $speechData
```

下载完成后，`models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/test_wavs/zh.wav` 就是验收样例。模型下载器同时下载该样例，无需另外获取音频包。

首次部署的模型下载和收尾自检可能在后台进行。先查看状态，不要重复启动同一端口：

```powershell
Get-Content 'D:\挑战杯\p2-speech-local\deployment-status.json'
```

DOWNLOADING表示模型未下载完，STARTING表示正在加载，TESTING表示正在真实推理自检，VERIFIED才表示本次自检通过。FAILED时查看同目录download-final.log、service.err.log、smoke.log。首次部署进程等待下载完成后会自动启动并自检；电脑关机或终止进程会中断此过程。

在仓库根目录执行，终端关闭或按Ctrl+C会停止前台服务：

```powershell
pwsh -File .\p2-backend\speech\start-local.ps1
```

另开终端检查：

```powershell
Invoke-RestMethod http://127.0.0.1:18010/health
& 'D:\挑战杯\p2-speech-local\.venv\Scripts\python.exe' .\p2-backend\speech\smoke.py --data-root 'D:\挑战杯\p2-speech-local'
```

测试会合成真实中文WAV，识别官方中文样例，再识别刚合成的音频，并检查空文本和无效音频被拒绝。生成文件为`D:\挑战杯\p2-speech-local\smoke-generated.wav`。

## 内部HTTP接口

| 请求 | 内容 | 返回 |
|---|---|---|
| GET /health | 无正文 | 两个模型加载成功时200/UP，否则503 |
| POST /transcriptions | multipart字段audio | `{"text":"实际识别文本"}` |
| POST /syntheses | JSON：text和speechRate | audio/wav二进制 |

合成示例：`{"text":"您好，请注意休息。","speechRate":0.9}`。语速范围0.5～1.5，当前使用中文音色sid=3。文本上限2000字符；识别文件上限10MiB，解码后最长60秒。单实例同时执行一个请求，忙时429；不自动保存上传录音，测试脚本会保存生成的音频。

这里只监听本机地址，供P2后端调用，不作为对外公开接口。当前没有给这个独立服务增加平台身份认证，不要直接暴露公网。

## 重新下载模型

```powershell
& 'D:\挑战杯\p2-speech-local\.venv\Scripts\python.exe' .\p2-backend\speech\download-models.py --model-dir 'D:\挑战杯\p2-speech-local\models'
```

从sherpa-onnx维护者的Hugging Face仓库读取固定提交的模型，分段校验长度、完整模型校验LFS SHA256；sources.json记录模型来源与版本。下载脚本会跳过已校验完成的文件，暂存分段支持重用。首次下载需要联网；模型齐全后推理无需云端API Key。

官方说明：

- https://k2-fsa.github.io/sherpa/onnx/sense-voice/pretrained.html
- https://k2-fsa.github.io/sherpa/onnx/tts/all/Chinese-English/kokoro-multi-lang-v1_1.html

## 与P2的关系

语音服务就绪后，另开 PowerShell，从仓库根目录启动 P2。

```powershell
$env:SPEECH_MODE = 'http'
$env:SPEECH_SERVICE_URL = 'http://127.0.0.1:18010'
pwsh -NoProfile -File .\p2-backend\scripts\dev.ps1
```

从模型目录下的 `sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/test_wavs/zh.wav` 取中文样例。通过 P2 的 `POST /api/v3/speech/transcriptions?userId=u100` 上传，multipart 字段为 `audio`，本地老人身份头为 `X-Mock-Actor-Id: u100` 和 `X-Mock-Actor-Role: ELDER`。样例实测识别为「开饭时间早上9点至下午5点。」

P2 合成接口返回签名 WAV 链接。本地用 P2 地址解析相对链接，签名最长 15 分钟，音频保留 24 小时。请求签名链接时无需身份头。使用 `Range: bytes=0-1023` 请求 WAV，本地已验证返回 HTTP 206 和对应的 `Content-Range`。
