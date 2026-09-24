# 安装 TCCLI

**首选：装进 Artemis 自带的 Python 虚拟环境（venv）**——与 Artemis 运行环境一致、版本可控、不污染系统 Python、无需 sudo。Artemis 专家的 Agent 命令执行时继承该环境。

**定位 Artemis venv**（通过 artemis 主进程的工作目录）：

```sh
ARTEMIS_PID=$(pgrep -f '\.venv/bin/artemis run' | head -1)
ARTEMIS_ROOT=$([ -n "$ARTEMIS_PID" ] && readlink -f /proc/$ARTEMIS_PID/cwd || echo /workspace/artemis)
```

**安装方式（按优先级）**：

```sh
# 方式一（推荐）：uv 装进 Artemis venv
uv pip install --python "$ARTEMIS_ROOT/.venv/bin/python3" tccli

# 方式二：无 uv 时，用 venv 自带 pip（需先 ensurepip）
"$ARTEMIS_ROOT/.venv/bin/python3" -m ensurepip --upgrade
"$ARTEMIS_ROOT/.venv/bin/python3" -m pip install tccli

# 方式三：系统 pip（桌面/CLI 独立使用 tccli 时）
pip install tccli

# 若从 3.0.252.3 以下版本升级，需先卸载再装：
# pip uninstall tccli jmespath && pip install tccli
```

升级同理，加 `-U`：`uv pip install --python "$ARTEMIS_ROOT/.venv/bin/python3" -U tccli`

其他系统安装方式：

```sh
# macOS Homebrew
brew tap tencentcloud/tccli
brew install tccli
# 更新：brew upgrade tccli

# 源码安装
# git clone https://github.com/TencentCloud/tencentcloud-cli.git && cd tencentcloud-cli && python setup.py install
```

验证安装：

```sh
"$ARTEMIS_ROOT/.venv/bin/tccli" --version   # venv 内验证
tccli --version                            # 系统安装验证
```
