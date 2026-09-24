# Artemis — 飞牛 FnOS 安装包

本目录包含将 Artemis 打包为飞牛 fnOS `.fpk` 安装包所需的全部文件。

## 首次使用（初始账号）

安装向导中设置管理员账号与密码，两种方式任选：

1. **自己输入密码** —— 至少 8 位，且必须同时包含字母和数字（与应用侧密码策略一致；过于常见的密码如 `Artemis123` 会被拒绝，无效输入会在安装时直接提示，不会装完才失败）。
2. **自动生成随机密码（推荐）** —— 安装时自动生成 16 位强密码。

生成的 / 设置的密码通过以下两种方式**双保险**送达用户：

- **应用「设置」窗口**：飞牛应用中心 → Artemis → 设置，窗口顶部直接显示当前管理员账号与密码，也可在此随时改密（保持不变 / 随机生成 / 自己设置）；
- **回落备份文件**：数据共享目录下的 `artemis-login.txt`（本地版在 data-share 共享目录，Docker 版在 `/var/apps/artemis/share/artemis/data/`），永久保留并随改密同步更新。

> 若你在 Web 控制台「头像菜单 → 修改密码」中改过密码，则以 Web 密码为准（`artemis-login.txt` 与「设置」窗口显示的是安装/配置阶段写入的凭据）。

### 官方命令行管理

本地版安装后自动注册 Artemis CLI 到 PATH（`/usr/local/bin/artemis`），SSH 进飞牛即可使用全部管理命令（以 root 或 artemis-native 身份执行最顺）：

```bash
artemis --help            # 官方 CLI 全部子命令
artemis version
artemis provider list     # 模型 provider
artemis agent list        # 专家/Agent
artemis user list         # 用户管理
artemis user passwd <用户名> --password <新密码>   # 离线改密（应用「设置」窗口改密也走这一命令）
artemis skills --help     # 技能管理
artemis backup --help     # 备份/恢复
```

> 注意：不要手动执行 `artemis run`（会与飞牛应用中心托管的服务实例抢 8089 端口）；Web 服务一律由应用中心启停。

## 两种安装包

仓库同时产出 **两款** `.fpk`，用于满足不同部署偏好：

| 版本 | 包名 | 体积 | 运行方式 | 依赖 |
|------|------|------|----------|------|
| **Docker 版** | `Artemis-fnos-docker-<ver>.fpk` | ~8 KB | 飞牛自动从配置的镜像仓库拉取镜像运行 | 宿主需有 Docker 运行时 |
| **本地版（非 Docker）** | `Artemis-fnos-native-<ver>.fpk` | ~560 MB | 自带 Python 3.12 运行时 + 前端 + 核心依赖，原生运行在飞牛主机 | 无需 Docker |

- **Docker 版**实现为 FnOS `docker-project`：包体只含 `docker-compose.yaml` 与向导配置，运行时由飞牛从配置的镜像仓库拉取镜像。镜像已内置 `desktop` 桌面控制与前端；Playwright Chromium 不预装，可在控制台按需安装。
- **本地版**实现为 FnOS 原生 `app`：包内自带独立 Python 3.12 运行时、Artemis 核心依赖、前端构建产物，以及 `data-share` 共享数据目录，直接以进程方式运行，不依赖 Docker。

## 目录结构

```
fnos/
├── README.md
├── docker/                 # Docker 版（docker-project）
│   ├── manifest            # 应用元信息（platform=all / 名称/版本/桌面入口等）
│   ├── ICON.PNG / ICON_256.PNG
│   ├── LICENSE             # 复用仓库根 LICENSE（MIT）
│   ├── cmd/                # 生命周期脚本（main / install_callback / config_callback 等）
│   ├── config/
│   │   ├── privilege       # 权限声明（docker-artemis 用户）
│   │   └── resource        # 资源声明（docker-project + 数据共享目录）
│   ├── wizard/
│   │   ├── install       # 安装向导（管理员账号/密码：自输或随机生成、日志级别、LLM 密钥）
│   │   ├── config        # 应用「设置」窗口（当前密码显示 + 改密 + 日志级别 + LLM 密钥）
│   │   └── uninstall     # 卸载向导（数据清理方式）
│   ├── app/
│   │   ├── docker/
│   │   │   └── docker-compose.yaml   # 引用配置的镜像仓库
│   │   └── ui/
│   │       ├── config                # 桌面图标入口
│   │       └── images/icon-{64,256}.png
│   └── Dockerfile          # 从仓库源码构建镜像，安装 desktop extra（不预装 Chromium）
└── native/                 # 本地版（非 Docker 的 FnOS 原生 app）
    ├── manifest            # platform=all + 原生 app 元信息
    ├── cmd/                # 生命周期脚本（main / install_callback / config_callback）
    ├── config/
    │   ├── privilege       # 权限声明（root，用于 sudo / 远程桌面等）
    │   └── resource        # data-share + usr-local-linker
    ├── app/
    │   ├── bin/artemis       # 内部启动器（用自带 Python 运行时启动 Artemis，init 带弱密码自动重试兜底）
    │   ├── wizard/config.template   # 「设置」窗口表单模板（渲染当前密码后落到已安装包 wizard/config）
    │   └── ui/             # 桌面图标入口
    └── wizard/             # 安装/配置/卸载/升级向导
```

## 本地构建 .fpk（无需 Docker）

```bash
bash scripts/build-fpk.sh            # 仅 Docker 版  → dist/Artemis-fnos-docker-<version>.fpk
bash scripts/build-fpk.sh docker     # 仅 Docker 版
bash scripts/build-fpk.sh native     # 仅本地版      → dist/Artemis-fnos-native-<version>.fpk
```

`.fpk` 为「双层 gzip tar」：外层含 `app.tgz / cmd / config / wizard / ICON.PNG / ICON_256.PNG / LICENSE / manifest`，内层 `app.tgz` 含 `app/` 内容。

## 在飞牛上安装

1. 飞牛「应用中心 → 设置 → 手动安装应用」选择对应 `.fpk`：
   - 想用 Docker 跑、主机已装 Docker → 选 `Artemis-fnos-docker-<version>.fpk`
   - 不想依赖 Docker、希望自带运行时原生运行 → 选 `Artemis-fnos-native-<version>.fpk`
2. 安装向导中设置管理员账号/密码、日志级别、LLM 密钥（可选）。
3. 安装完成后桌面出现「Artemis AI 助手」图标，浏览器打开 `http://<设备IP>:8088`。
4. Docker 版镜像首次会从配置的镜像仓库拉取；请确保镜像可访问。本地版无需联网拉镜像。Playwright Chromium 不预装，需要远程浏览器时在控制台按需安装。

> 服务端口固定为 `8088`（飞牛端口映射与桌面图标均据此）。`desktop` 桌面控制已在镜像中默认安装。
