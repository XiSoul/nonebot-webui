<!-- markdownlint-disable MD033 MD041 -->
<p align="center">
  <a href="https://cli.nonebot.dev/"><img src="https://cli.nonebot.dev/logo.png" width="200" height="200" alt="nonebot"></a>
</p>

<div align="center">

# NB CLI Plugin WebUI

_✨ 面向 NoneBot 多实例运维的 WebUI ✨_

</div>

<p align="center">
  <a href="https://github.com/XiSoul/nonebot-webui">
    <img src="https://img.shields.io/badge/GitHub-XiSoul%2Fnonebot--webui-181717?style=flat-square&logo=github" alt="GitHub">
  </a>
  <a href="https://raw.githubusercontent.com/XiSoul/nonebot-webui/master/LICENSE">
    <img src="https://img.shields.io/github/license/XiSoul/nonebot-webui?style=flat-square" alt="license">
  </a>
  <img src="https://img.shields.io/badge/python-3.8+-blue" alt="python">
  <br />
  <a href="https://jq.qq.com/?_wv=1027&k=5OFifDh">
    <img src="https://img.shields.io/badge/QQ%E7%BE%A4-1074735930-orange?style=flat-square" alt="QQ Chat Group">
  </a>
  <a href="https://github.com/XiSoul/nonebot-webui/releases">
    <img src="https://img.shields.io/badge/Releases-Update%20Notes-2ea44f?style=flat-square" alt="Releases">
  </a>
</p>

## 项目简介

这是一个基于 NoneBot WebUI 深度二改的项目，重点面向 NAS、Docker、WSL 和长期运行场景。

它更偏向“机器人实例运维面板”，而不只是原版 `nb-cli` 的简单图形封装，核心目标是：

- 同时管理多个 NoneBot 实例
- 直接接入 NAS / 宿主机上已经存在的机器人项目
- 尽量减少手动进容器、手动改配置、手动查日志的频率
- 让常用的运行、安装依赖、插件管理、文件修改、日志排查都能在 WebUI 里完成

## 主要功能

- 多实例管理：创建实例、接入已有实例、切换实例、启停与状态同步
- 配置与文件：在线编辑 `pyproject.toml`、`.env`、`.env.prod` 以及实例目录文件
- 扩展管理：安装、卸载、更新插件 / 驱动 / 适配器，并处理依赖安装流程
- 日志与通知：统一查看 WebUI 与实例日志，通知中心常驻留痕
- 备份恢复：支持本地备份、上传恢复，以及 WebDAV / S3 远端备份
- 容器场景支持：代理、镜像源、路径映射、随机 token、外部实例接入

## 这次二改的重点

- 重点适配 NAS / Docker / WSL 的长期运行场景
- 优化已有实例导入，支持相对路径和容器内绝对路径识别
- 修复坏虚拟环境导致的依赖安装失败，自动备份并重建 `.venv`
- 补齐导入实例后的驱动 / 依赖初始化流程，减少第三步报错
- 调整概览、通知、日志、终端交互，让运维动作更集中
- 新增关于页，文档入口和项目信息集中展示

## 适合谁用

- NAS 上已经有一批 NoneBot 项目，想统一接进一个面板管理的人
- 用 Docker 跑 WebUI，希望新建实例和外部已有实例分开挂载的人
- 需要经常安装依赖、排查插件问题、看日志、改配置的人
- 不想每次都手动进容器敲命令的人

## 使用

### Docker 安装

如果你主要是部署到 NAS、Docker 或 WSL，直接使用 Docker Hub 镜像就行：

- `docker.io/xisoul/nonebot-webui:latest`
- `docker.io/xisoul/nonebot-webui:master`
- `docker.io/xisoul/nonebot-webui:${version}`

推荐优先使用显式版本号，例如 `0.4.2`、`0.4`，后面做升级、回滚、版本检测会更方便。

### 非 Docker 安装

如果你明确是本机直接运行 `nb-cli`，也可以走插件安装方式：

```shell
nb self install nb-cli-plugin-webui-xisoul
```

### 生产部署

推荐最少保留这几项挂载：

```shell
docker run -d \
  --name nonebot-webui \
  --restart=always \
  --network host \
  -e HOST=0.0.0.0 \
  -e PORT=18080 \
  -v /home/xisoul/nonebot-webui-data/projects:/projects \
  -v /home/xisoul/nonebot-webui-external-projects:/external-projects \
  # 挂载你本地的NoneBot项目目录到容器内，容器会自动扫描并添加所有项目
  -v /path/to/your/nonebot/projects:/opt/nonebot-projects \
  -v /home/xisoul/nonebot-webui-data/config.json:/app/config.json \
  -v /home/xisoul/nonebot-webui-data/project.json:/app/project.json \
  xisoul/nonebot-webui:latest
```

#### 自定义项目挂载说明：
你可以把宿主机上任意目录下的所有NoneBot项目，通过挂载到容器的`/opt/nonebot-projects`目录来实现自动接入：
- 容器启动后会自动扫描该目录下的所有子目录
- 自动识别原版NoneBot项目（不需要做任何适配修改）
- 自动添加到WebUI的实例列表，支持启停、依赖管理、日志查看等全功能操作

也可以直接使用仓库里的 `docker-compose.yml`。

只需要记住：

- `/projects` 给 WebUI 新建实例使用
- `/external-projects` 给宿主机 / NAS 里已经存在的实例使用
- `/app/config.json` 与 `/app/project.json` 会被程序写回，不能只读挂载
- 如果 NAS 面板自动带出 `/data` 等默认卷，建议手动删掉，再按上面这些路径重新配置

### 路径映射说明

Docker / NAS 场景下请区分“宿主机路径”和“容器内路径”：

- 宿主机路径：例如群晖 NAS 上的 `/vol1/1000/nonebot`
- 容器内路径：例如 `/projects`、`/external-projects`

不要把容器内路径也写成宿主机路径，例如：

- 错误：`/vol1/1000/nonebot -> /vol1/1000/nonebot`

推荐映射方式：

- WebUI 自己新建的实例：`宿主机目录 -> /projects`
- 已有机器人项目：`宿主机目录 -> /external-projects`

群晖 / NAS 常见示例：

- 宿主机已有目录：`/vol1/1000/nonebot`
- 容器挂载方式：`/vol1/1000/nonebot -> /external-projects`

如果你还需要让 WebUI 自己创建新实例，再单独准备一块目录映射到 `/projects` 即可。

### 添加已有实例时怎么填路径

添加已有实例时，实例路径支持以下几种写法：

- `3998382152`
- `external-projects/3998382152`
- `/external-projects/3998382152`

WebUI 会自动把它解析并保存为容器内的真实绝对路径。

如果当前是 Docker / NAS 部署，不要填写宿主机自己的物理路径，例如：

- `/vol1/...`
- `/volume1/...`
- `/home/...`

这些路径对容器里的 WebUI 来说是不可见的，必须填写容器内路径。

另外，添加的目录本身需要是一个 NoneBot 项目根目录，至少应当能看到 `pyproject.toml`。如果 `pyproject.toml` 在子目录里，就填写那个子目录，不要填到父目录。

本镜像当前不内置 Playwright Linux 系统依赖；若你管理的外部项目自身依赖 Playwright，请在对应项目运行环境中单独安装。

### 登录说明

首次启动容器后，请先去查看容器日志里的登录凭证（token），再用它登录 WebUI。

例如：

```shell
docker logs nonebot-webui
```

如果你在群晖 Docker 管理界面中部署，也同样需要到“容器日志”里查看首次生成的 token。

登录流程是：

1. 用日志里的登录凭证登录
2. WebUI 会换取当前浏览器会话用的 JWT
3. 后续页面请求和 WebSocket 连接都会使用 JWT

因此，登录凭证本身不是直接拿来当 `Authorization: Bearer ...` 用的。

如果后面你在“安全设置”里改成随机 token 模式，新 token 也会继续写到容器日志里。

### 常用环境变量

- HOST: 指定监听地址，默认为 `0.0.0.0`
- PORT: 指定监听端口，默认为 `18080`

### 代理与镜像源

容器运行时代理、Debian 镜像源、pip 源都可以在 WebUI 里直接配置，不需要部署阶段先写一大堆复杂参数。

如果你的环境确实需要，也支持通过环境变量传入：

- `WEBUI_HTTP_PROXY`
- `WEBUI_HTTPS_PROXY`
- `WEBUI_ALL_PROXY`
- `WEBUI_NO_PROXY`
- `WEBUI_DEBIAN_MIRROR`
- `WEBUI_PIP_INDEX_URL`
- `WEBUI_PIP_EXTRA_INDEX_URL`
- `WEBUI_PIP_TRUSTED_HOST`

## 常见提醒

- WebUI 新建实例默认放在 `/projects`
- 外部已有实例建议统一挂到 `/external-projects`
- 添加已有实例时，路径必须填写容器内路径，不要填写 NAS 宿主机路径
- 如果实例根目录里没有 `pyproject.toml`，说明你填错目录层级了
- 首次登录凭证请去容器日志里看
- 想回头找 token，直接看容器日志，不是在页面里反查
- 如果某些插件依赖 Playwright 或系统库，请在对应机器人项目自己的运行环境里安装，不是装在 WebUI 容器里

## 发布流程

这个仓库当前的 Docker 镜像发布依赖 GitHub Actions 自动完成。

需要注意：

- 只在本地 `docker build` 不会自动更新 Docker Hub
- 自动推送镜像依赖 GitHub 上的提交和 tag
- 版本号必须和 tag 对应，否则 release workflow 会失败

### 自动发布触发规则

- 推送到 `master` 会触发 Docker 构建流程
- 推送 `v*` 格式的 tag 也会触发 Docker 构建流程

当前 Docker workflow 会自动生成这些常用标签：

- `latest`
- `master`
- `${major}.${minor}`
- `${version}`

例如版本 `0.4.4` 会自动生成：

- `xisoul/nonebot-webui:latest`
- `xisoul/nonebot-webui:master`
- `xisoul/nonebot-webui:0.4`
- `xisoul/nonebot-webui:0.4.4`

### 推荐发版步骤

1. 修改代码并在本地测试通过
2. 更新 `pyproject.toml` 中的版本号
3. 同步更新 `Dockerfile` 中的 `APP_VERSION`
4. 提交代码
5. 打版本 tag，例如 `v0.4.4`
6. 推送 `master` 和对应 tag

示例：

```bash
git add .
git commit -m "feat: your change"
git push origin master

git tag v0.4.4
git push origin v0.4.4
```

### 重要说明

- tag 必须和 `pyproject.toml` 中的版本一致
- 如果 tag 已经打错位置，需要先修正 tag 指向再重新 push
- 当前 release workflow 已移除 PyPI 发布，只保留 GitHub Release 产物上传，避免因为 PyPI Trusted Publisher 配置导致整条流程报红
- 如果 Docker Hub 没更新，优先去 GitHub Actions 看 `docker.yml` 是否成功
