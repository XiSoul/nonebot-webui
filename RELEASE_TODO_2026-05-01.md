# Release Notes Draft 2026-05-01

这份清单用于记录 `0.4.5` 计划带上的修复项。

## 0.4.5 已纳入修复

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

## 本次明确不纳入发版

### htmlrender / Playwright 下载链路

- 文件:
  - `nb_cli_plugin_webui/app/process/service.py`
- 原因:
  - 当前不同平台行为差异大
  - 你已经明确说明这条先不动，后面有时间再单独测试
  - 不建议在这次发版里继续混入 htmlrender 下载策略调整

## 发版前建议确认

1. 确认 `pyproject.toml` 版本号与待打 tag `v0.4.5` 一致
2. 确认 `Dockerfile` 中 `APP_VERSION` 已同步更新到 `0.4.5`
3. 确认这次不包含 `htmlrender` 下载源策略调整
4. 构建镜像后优先验证 NAS 容器创建页是否还会自动带出错误挂载
5. 复测“添加实例失败”场景，确认不再留脏记录
