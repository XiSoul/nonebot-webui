<!-- markdownlint-disable MD033 MD041 -->
<p align="center">
  <a href="https://cli.nonebot.dev/"><img src="https://cli.nonebot.dev/logo.png" width="200" height="200" alt="nonebot"></a>
</p>

<div align="center">

# NB CLI Plugin WebUI

_✨ NoneBot2 命令行工具 前端可视化页面（WebUI） 插件 ✨_

</div>

<p align="center">
  <a href="https://raw.githubusercontent.com/nonebot/nb-cli-plugin-webui/master/LICENSE">
    <img src="https://img.shields.io/github/license/nonebot/cli-plugin-webui" alt="license">
  </a>
  <a href="https://pypi.python.org/pypi/nb-cli-plugin-webui">
    <img src="https://img.shields.io/pypi/v/nb-cli-plugin-webui" alt="pypi">
  </a>
  <img src="https://img.shields.io/badge/python-3.8+-blue" alt="python">
  <a href="https://results.pre-commit.ci/latest/github/nonebot/nb-cli-plugin-webui/master">
    <img src="https://results.pre-commit.ci/badge/github/nonebot/cli-plugin-webui/master.svg" alt="pre-commit" />
  </a>
  <br />
  <a href="https://jq.qq.com/?_wv=1027&k=5OFifDh">
    <img src="https://img.shields.io/badge/QQ%E7%BE%A4-1074735930-orange?style=flat-square" alt="QQ Chat Group">
  </a>
  <a href="https://qun.qq.com/qqweb/qunpro/share?_wv=3&_wwv=128&appChannel=share&inviteCode=7b4a3&appChannel=share&businessType=9&from=246610&biz=ka">
    <img src="https://img.shields.io/badge/QQ%E9%A2%91%E9%81%93-NoneBot-5492ff?style=flat-square" alt="QQ Channel">
  </a>
  <a href="https://t.me/botuniverse">
    <img src="https://img.shields.io/badge/telegram-botuniverse-blue?style=flat-square" alt="Telegram Channel">
  </a>
  <a href="https://discord.gg/VKtE6Gdc4h">
    <img src="https://discordapp.com/api/guilds/847819937858584596/widget.png?style=shield" alt="Discord Server">
  </a>
</p>

## 功能

- 可视化的 nb cli 操作
  - 创建新的 NoneBot 实例
  - 添加已有的 NoneBot 实例
  - 拓展（插件、适配器、驱动器）管理（安装、卸载）
- 可同时管理多个 NoneBot 实例
- 为启动的 NoneBot 实例提供状态展示、性能查询
- 可视化的 NoneBot 实例配置

## 功能模块

### 1. 实例管理

- 创建实例、接入已有实例、切换当前实例
- 实例列表集中展示实例名称、运行状态、路径信息
- 添加已有实例时支持相对路径和容器内绝对路径，系统会自动解析为运行时真实路径
- 支持在实例选择页直接切换运行环境：`.env` / `.env.prod`
- 支持实例启停、重启、删除和状态同步

### 2. 配置管理

- 图形化编辑 `pyproject.toml`、`.env`、`.env.prod`
- 配置保存后可按实例运行状态自动触发重启
- 支持运行脚本、环境文件、代理设置等实例级配置
- 支持安全设置、登录凭证修改、端口修改

### 3. 扩展生态

- 拓展商店浏览、安装、卸载插件/驱动/适配器
- 已安装模块管理、版本检查、列表刷新
- 实例运行时支持更顺滑的插件安装与自动重启流程

### 4. 文件管理

- 支持实例目录文件浏览与编辑
- 可根据实例安装方式自动识别容器内目录或映射目录
- 支持常见文件操作与在线修改插件代码

### 5. 备份恢复

- 支持实例目录打包备份
- 支持本地下载、本地上传恢复
- 支持 WebDAV、S3 远端备份与恢复
- 支持手动测试连接、定时备份、备份保留份数
- 支持备份密码、恢复时密码检测、日志备份筛选

### 6. 日志与通知

- 提供 WebUI 日志与实例日志统一查看
- 支持日志等级过滤、日期清理、消息写入日志
- 顶部通知中心统一样式、支持展开详情
- 概览页支持实例消息识别与运行状态展示

### 7. 容器与网络

- 支持 Docker 运行时代理、镜像源、pip 源配置
- 支持代理档案保存、应用、删除与连通性测试
- 支持单输入框统一配置 HTTP/HTTPS/SOCKS 代理
- 适配容器启动场景下的随机 token、端口、自定义启动信息

## 二改特性

当前仓库在原版基础上做了面向实际部署场景的增强，重点包括：

- 登录安全增强：永久 token / 随机 token 双模式、随机 token 输出到 Docker 日志、旧凭证校验、新凭证二次确认、可见性切换、长度校验
- 服务端口可配：默认 `18080`，支持在安全设置中修改，并加入 Docker 端口映射提示
- 概览页重构：登录后主视图直接进入概览，欢迎区、实例信息、实例消息、运行状态展示更符合运维场景
- 实例环境切换前移：在实例选择页直接切换 `.env` / `.env.prod`，减少跨页面操作
- 拓展安装流程优化：安装成功后按实例状态自动重启，配置保存后自动重启机器人
- 全局代理重构：统一输入框支持 HTTP / HTTPS / SOCKS，支持保存代理档案和连通性测试
- 文件管理增强：支持实例目录/映射目录识别、目录浏览、在线编辑、布局优化
- 备份恢复增强：支持 WebDAV / S3、手动测试、定时备份、备份密码、日志备份筛选、远端拉取恢复
- 全局日志中心：支持 WebUI 与实例日志统一查看、日志等级筛选、操作入日志、通知详情展开
- Docker 场景增强：支持容器运行时代理和镜像源配置，适配更稳定的测试/生产部署流程

## 项目特色

- 面向多实例运维，而不只是单实例可视化
- 面向 Docker 场景做了较多适配，适合直接部署到测试机或生产机
- 将“安全、代理、备份、日志、文件管理”整合到统一 WebUI 中，减少人工进容器操作
- 更偏向实际运营和维护机器人，而不是只做基础的 `nb-cli` 图形封装
- 保留原有 NoneBot 生态兼容性的同时，补齐了长期运行和远程管理需要的能力

## 使用

### 安装

**需要 [nb-cli](https://github.com/nonebot/nb-cli/)**

使用 nb-cli 安装

```shell
nb self install nb-cli-plugin-webui
```

使用 Docker 运行

```shell
docker pull docker.io/xisoul/nonebot-webui:latest
```

当前默认推荐直接使用 Docker Hub 镜像，下载链路相对更稳定：

- `docker.io/xisoul/nonebot-webui`

Docker 镜像可以选择以下版本:

- `latest`: 默认分支最新可用镜像
- `master`: 默认分支镜像，适合持续跟进测试
- `${version}` / `${major}.${minor}`: 当推送 `v*` tag 时自动生成的正式版本镜像，例如 `0.4.2`、`0.4`

当前不再推荐使用 GitHub commit 短 SHA 作为公开版本标签。镜像版本统一以显式版本号为主，便于后续做镜像更新检测、版本对比和回滚。

例如:

```shell
docker pull docker.io/xisoul/nonebot-webui:latest
docker pull docker.io/xisoul/nonebot-webui:master
docker pull docker.io/xisoul/nonebot-webui:0.4.2
docker pull docker.io/xisoul/nonebot-webui:0.4
```

### 生产部署

生产部署文档和默认示例统一使用 Docker Hub 镜像：

- `docker.io/xisoul/nonebot-webui`

测试服部署默认使用以下运行参数：

```shell
docker run -d \
  --name nonebot-webui \
  --restart=always \
  --network host \
  -e HOST=0.0.0.0 \
  -e PORT=18080 \
  -v /home/xisoul/nonebot-webui-data/projects:/projects \
  -v /home/xisoul/nonebot-webui-external-projects:/external-projects \
  -v /home/xisoul/nonebot-webui-data/config.json:/app/config.json \
  -v /home/xisoul/nonebot-webui-data/project.json:/app/project.json \
  docker.io/xisoul/nonebot-webui:latest
```

部署前请确保以下路径存在且可写：

- `/home/xisoul/nonebot-webui-data/projects`
- `/home/xisoul/nonebot-webui-external-projects`
- `/home/xisoul/nonebot-webui-data/config.json`
- `/home/xisoul/nonebot-webui-data/project.json`

注意：`/app/config.json` 与 `/app/project.json` 会在运行时被程序写回，不能只读挂载。
Docker 运行模式下项目默认根目录为 `/projects`。

添加已有实例时，实例路径支持以下几种写法：

- `3998382152`
- `external-projects/3998382152`
- `/external-projects/3998382152`

WebUI 会自动把它解析并保存为容器内的真实绝对路径。
如果当前是 Docker 部署，不要填写 NAS 或宿主机自己的物理路径，例如 `/vol1/...`、`/volume1/...`、`/home/...` 这类容器外路径。

如需本地打包后手工部署，可使用：

```shell
./build-and-export.sh
./deploy.sh
```

默认情况下，这两个脚本都会自动读取 `pyproject.toml` 中的版本号作为 Docker tag。
如果你想手动指定镜像版本，也可以直接传参：

```shell
./build-and-export.sh 0.4.2
./deploy.sh 0.4.2
```

容器内显示的 WebUI 版本也会优先使用这个显式版本号，而不是 GitHub 随机 commit 字符串。

本镜像当前不内置 Playwright Linux 系统依赖；若你管理的外部项目自身依赖 Playwright，请在对应项目运行环境中单独安装。

### 登录说明

WebUI 登录使用“登录凭证”换取 JWT 会话：

1. 在登录页输入当前登录凭证
2. 前端调用 `/v1/auth/login`
3. 后端校验凭证后返回 JWT
4. 前端将 JWT 保存到当前浏览器会话并用于后续 API / WebSocket 调用

因此，登录凭证本身不能直接作为 `Authorization: Bearer <token>` 使用。


可用下面这组命令快速验证镜像是否能正常启动：

```shell
docker run -d --rm \
  --name nonebot-webui-test \
  -p 18080:18080 \
  docker.io/xisoul/nonebot-webui:latest

docker logs nonebot-webui-test
docker rm -f nonebot-webui-test
```

可选附加 env 参数:

- HOST: 指定监听地址，默认为 `0.0.0.0`
- PORT: 指定监听端口，默认为 `18080`

## 开发

待补充......

## 补充

nb-cli WebUI 目前正处于快速迭代中，欢迎各位提交在使用过程中发现的 BUG 和建议。

### Docker advanced runtime settings

The container supports runtime proxy and mirror settings via environment variables:

- `WEBUI_HTTP_PROXY`, `WEBUI_HTTPS_PROXY`, `WEBUI_ALL_PROXY`, `WEBUI_NO_PROXY`
- `WEBUI_SOURCE_PRESET` (`official` / `tuna` / `ustc` / `aliyun` / `huawei`)
- `WEBUI_AUTO_BEST_PRESET=1` (startup benchmark and apply best preset automatically)
- `WEBUI_AUTO_BEST_PRESET_FORCE=1` (force benchmark even if saved source values already exist)
- `WEBUI_DEBIAN_MIRROR` / `WEBUI_APT_MIRROR` (or `DEBIAN_MIRROR`, `APT_MIRROR`, `LINUX_MIRROR`)
- `WEBUI_PIP_INDEX_URL`, `WEBUI_PIP_EXTRA_INDEX_URL`, `WEBUI_PIP_TRUSTED_HOST`

You can also edit these values in WebUI `Settings -> 容器代理与镜像源`.
Priority: explicit environment variables passed to `docker run` > `WEBUI_SOURCE_PRESET` > values saved in WebUI.
Auto-best preset is disabled by default.
When enabled, container startup may take longer because mirror connectivity benchmark is executed first.

WebUI also provides:
- one-click source presets (Official / TUNA / USTC / Aliyun / Huawei)
- runtime profile templates (save/apply/delete for scenarios like home/company)
- preset benchmark (auto speed ranking)
- apply best preset directly from benchmark result
- connectivity test for Debian mirror and pip index (quick/deep)
- auto quick pre-check before saving (can force save on failure)
- one-click rollback to official source

For Linux hosts, if your proxy runs on host machine, add:

```shell
--add-host host.docker.internal:host-gateway
```

Example:

```shell
docker run -it --rm \
  -p 18080:18080 \
  -v ./:/app \
  -e WEBUI_HTTP_PROXY=http://host.docker.internal:7890 \
  -e WEBUI_HTTPS_PROXY=http://host.docker.internal:7890 \
  -e WEBUI_SOURCE_PRESET=tuna \
  docker.io/xisoul/nonebot-webui:latest
```

镜像默认使用 Docker Hub:

```shell
docker.io/xisoul/nonebot-webui:latest
```

Auto-select best preset on startup:

```shell
docker run -it --rm \
  -p 18080:18080 \
  -v ./:/app \
  -e WEBUI_AUTO_BEST_PRESET=1 \
  docker.io/xisoul/nonebot-webui:latest
```
