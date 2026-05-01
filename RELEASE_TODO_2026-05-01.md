# Release Todo 2026-05-01

这份清单用于下次发版前确认哪些修复需要带上。

## 本次建议纳入发版

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
- 内容:
  - `add_nonebot_project()` 只有在安装流程真正走完后才写入项目元数据
  - 失败时不再提前写入 `project.json`

### 3. 添加实例第三步失败时不再白板

- 文件:
  - `frontend/src/components/Modals/AddBot/InstallationItem.vue`
- 内容:
  - 增加失败态错误卡片
  - 展示失败原因
  - 重试时清理上次失败状态

### 4. bcrypt / passlib 兼容修复

- 文件:
  - `pyproject.toml`
  - `poetry.lock`
- 内容:
  - 将 `bcrypt` 固定为 `4.0.1`
  - 避免容器启动时出现 `error reading bcrypt version`

### 5. 包改名后的版本读取修复

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

1. 确认 `pyproject.toml` 版本号与待打 tag 一致
2. 确认 `Dockerfile` 中 `APP_VERSION` 同步更新
3. 确认这次不包含 `htmlrender` 下载源策略调整
4. 构建镜像后优先验证 NAS 容器创建页是否还会自动带出错误挂载
5. 复测“添加实例失败”场景，确认不再留脏记录、不再白板
