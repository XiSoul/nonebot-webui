# 部署文档

这份文档聚焦 `nonebot-webui` 的 Docker / NAS / WSL 部署方式，适合作为正式部署参考。

## 推荐镜像

推荐直接使用 Docker Hub 镜像：

- `docker.io/xisoul/nonebot-webui:latest`
- `docker.io/xisoul/nonebot-webui:master`
- `docker.io/xisoul/nonebot-webui:${version}`

更推荐使用显式版本号，例如 `0.4.8`，便于后续升级、回滚和版本排查。

## 最小可用 `docker run`

```bash
docker run -d \
  --name nonebot-webui \
  --restart=always \
  --network host \
  -e HOST=0.0.0.0 \
  -e PORT=18080 \
  -e WEBUI_DATA_DIR=/data \
  -e WEBUI_CONFIG_DIR=/data \
  -e WEBUI_CACHE_DIR=/data \
  -v /home/xisoul/nonebot-webui-data/projects:/projects \
  -v /home/xisoul/nonebot-webui-data/external-projects:/external-projects \
  -v /path/to/your/nonebot/projects:/opt/nonebot-projects \
  -v /home/xisoul/nonebot-webui-data:/data \
  xisoul/nonebot-webui:latest
```

## 关键挂载说明

部署时至少要理解下面这几项：

- `/projects`
  用于 WebUI 自己创建的新实例
- `/external-projects`
  用于挂载宿主机上已经存在的 NoneBot 项目
- `/opt/nonebot-projects`
  可选挂载，用于自动扫描并接入宿主机目录下的多个现有项目
- `/data`
  WebUI 的运行期状态目录，包括 `config.json`、`project.json`、缓存和日志等可变数据，生产部署建议统一挂载宿主机数据目录到这里

## 自定义项目挂载

如果你已经有一批宿主机上的 NoneBot 项目，可以把它们统一挂载到容器的 `/opt/nonebot-projects`：

- 容器启动后会扫描这个目录下的子目录
- 可以识别标准 NoneBot 项目
- 接入后可直接在 WebUI 中完成启停、依赖安装、日志查看等操作

## `docker-compose.yml`

如果你更习惯 compose，也可以直接使用仓库里的 [docker-compose.yml](../docker-compose.yml)。

部署时请记住这条原则：

- WebUI 创建的新实例走 `/projects`
- 宿主机已有实例走 `/external-projects`

当前 compose 示例还额外带了一套 `watchtower` 自动更新容器：

- 会定时检查 `nonebot-webui:latest` 是否有新的远端 digest
- 发现更新后自动拉取新镜像
- 自动重建 `nonebot-webui` 容器

如果你不想自动更新，可以直接删掉 `watchtower` 服务和 `labels` 中的：

- `com.centurylinklabs.watchtower.enable=true`

如果你想保留自动更新，但把检查周期调长，可以修改：

- `--interval 300`

这个值单位是秒，`300` 表示每 5 分钟检查一次。

## NAS / Docker Desktop 注意事项

较新的镜像已经不再声明误导性的默认 `VOLUME`，就是为了避免 NAS 面板自动生成一堆看起来“必须挂载”、但实际容易误导的目录。

如果你的 NAS 面板仍然自动带出旧默认卷，建议只保留这些明确需要持久化或接入项目的挂载：

- `/data`
- `/projects`
- `/external-projects`
- `/opt/nonebot-projects`（可选，批量接入已有项目时使用）

## 路径映射规则

Docker / NAS 部署最容易错的地方，就是把宿主机路径和容器内路径混用了。

例如：

- 宿主机路径：`/vol1/1000/nonebot`
- 容器内路径：`/external-projects`

推荐映射方式：

- WebUI 自建实例：`宿主机目录 -> /projects`
- 已有机器人项目：`宿主机目录 -> /external-projects`

错误示例：

- `/vol1/1000/nonebot -> /vol1/1000/nonebot`

这会让你在页面里误以为应该填写宿主机路径，后续接入实例时很容易报错。

## WSL 场景

如果你在 Windows + WSL 下部署，建议：

- Docker 运行在 WSL 侧
- 数据目录明确放到你长期保留的位置
- 升级前备份 `config.json` 和 `project.json`

如果后续需要做磁盘清理或 `ext4.vhdx` 压缩，请先执行：

```powershell
wsl --shutdown
```

这样可以避免在 WSL 仍在运行时处理宿主机侧虚拟磁盘文件。

## 登录与认证

首次启动后，请到容器日志查看 token：

```bash
docker logs nonebot-webui
```

说明：

- 永久 token 会写入 `/data/config.json`
- 浏览器实际访问接口使用的是登录后换取的 JWT
- 修改“安全设置”中的会话时长，只会影响 JWT 生命周期，不等于永久 token 被替换

## 代理与镜像源

如果你的环境需要代理或镜像源，可以在 WebUI 内配置，也可以在部署阶段传入环境变量：

- `WEBUI_HTTP_PROXY`
- `WEBUI_HTTPS_PROXY`
- `WEBUI_ALL_PROXY`
- `WEBUI_NO_PROXY`
- `WEBUI_DEBIAN_MIRROR`
- `WEBUI_PIP_INDEX_URL`
- `WEBUI_PIP_EXTRA_INDEX_URL`
- `WEBUI_PIP_TRUSTED_HOST`

## 升级建议

升级时建议遵循下面的顺序：

1. 备份 `config.json` 和 `project.json`
2. 拉取新的镜像版本
3. 重建容器
4. 登录后检查实例列表、日志、终端和安全设置
5. 如涉及版本更新，再核对仓库中的更新文档

如果你已经启用了 `watchtower` 自动更新，则通常不需要手工 `docker pull` 和重建容器；只需要确保你使用的是：

- `xisoul/nonebot-webui:latest`

并且 `watchtower` 容器本身在正常运行。

## Docker Hub 页面说明

Docker Hub 仓库页里的 `Overview` 是仓库介绍区，不是镜像更新推送配置。

需要注意：

- 这个页面不会因为 GitHub Actions 推镜像就自动填充
- 如果你想让它显示项目介绍，需要在 Docker Hub 仓库页手动填写
- Docker Desktop 里“有新版本”的提示是本地客户端自己检查远端 tag / digest 后显示的，不是 Docker Hub 主动推送通知
