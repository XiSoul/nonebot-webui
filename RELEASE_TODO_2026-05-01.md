# Release Notes Draft 2026-05-01

这份清单用于记录 `0.4.6` 计划带上的修复项。

## 0.4.6 已纳入修复

### 1. Docker / NAS 创建容器体验修复

- 文件:
  - `Dockerfile`
  - `README.md`
- 内容:
  - 去掉误导 NAS 面板自动生成挂载项的 `VOLUME /data`
  - 去掉 `VOLUME /opt/nonebot-projects`
  - 补回 `EXPOSE 18080`
  - 文档补充 NAS 自动挂载项说明

### 2. 添加实例失败后不再污染实例列表

- 文件:
  - `nb_cli_plugin_webui/app/project/service.py`
  - `nb_cli_plugin_webui/app/handlers/process/utils.py`
- 内容:
  - `add_nonebot_project()` 与 `create_nonebot_project()` 失败时自动回滚实例记录
  - 异步流程支持失败回调，避免半成品实例残留在 `project.json`

### 3. 实例列表去重与自动扫描污染修复

- 文件:
  - `nb_cli_plugin_webui/app/project/service.py`
- 内容:
  - 目录别名(`/external-projects` / `/opt/nonebot-projects`)不再被当成不同实例
  - 停用实例列表查询时的自动扫描回填，避免测试残留和重复实例反复出现

### 4. 实例操作页与维护终端拆分

- 文件:
  - `frontend/src/views/Operation/OperationIndex.vue`
  - `frontend/src/views/Operation/TerminalItem.vue`
  - `frontend/src/views/Terminal/TerminalIndex.vue`
  - `frontend/src/router/client.ts`
  - `nb_cli_plugin_webui/app/process/router.py`
  - `nb_cli_plugin_webui/app/process/service.py`
- 内容:
  - `/operation` 只展示实例运行日志
  - 新增独立 `/terminal` 菜单用于维护 Shell
  - 运行日志与维护终端日志使用独立 log key 分流

### 5. bcrypt / passlib 兼容修复

- 文件:
  - `pyproject.toml`
  - `poetry.lock`
- 内容:
  - 将 `bcrypt` 固定为 `4.0.1`
  - 避免容器启动时出现 `error reading bcrypt version`

### 6. 包改名后的版本读取修复

- 文件:
  - `nb_cli_plugin_webui/app/application.py`
- 内容:
  - 不再硬编码 `version("nb_cli_plugin_webui")`
  - 改为统一走 `get_version()`
  - 修复改包名后镜像启动 `PackageNotFoundError`

### 7. htmlrender / Playwright 启动前预装与 Linux 依赖补齐

- 文件:
  - `Dockerfile`
  - `README.md`
  - `nb_cli_plugin_webui/app/process/service.py`
- 内容:
  - WebUI 启动实例前会先尝试用项目自己的 Python 环境执行 `python -m playwright install chromium`
  - `nonebot_plugin_htmlrender` 场景下统一补齐 `PLAYWRIGHT_BROWSERS_PATH` 和下载超时等运行时环境
  - Docker 镜像内补齐 Playwright Chromium 常见 Linux 运行库，覆盖 `libicu76`、`libxslt1.1`、`libevent-2.1-7t64`、`libwebpdemux2`、`libwebpmux3`、`libharfbuzz-icu0` 等缺失项
  - 遇到 SOCKS 代理时，日志会明确说明系统库依赖镜像内提供，避免把插件内部 `--with-deps` 失败误判成浏览器未下载

## 本次测试备注

- WSL 侧 Docker `buildx` 插件曾出现段错误，已在本机补装系统包版 `docker-buildx`

## 发版前建议确认

1. 确认 `pyproject.toml` 版本号与待打 tag `v0.4.6` 一致
2. 确认 `Dockerfile` 中 `APP_VERSION` 已同步更新到 `0.4.6`
3. 构建镜像后优先验证 `nonebot_plugin_htmlrender` 项目的 Playwright Chromium 预装与启动
4. 复测 NAS / Docker 场景下的路径映射与默认挂载说明
5. 复测“添加实例失败”场景，确认不再留脏记录
