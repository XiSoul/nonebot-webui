## 脚本说明

请勿在此目录下运行脚本。

请在项目根目录通过：

```
sh ./script/example.sh
```

方式运行。

### WSL 完整回归

如果你需要在 WSL 中执行一轮完整的 WebUI 回归，可以在项目根目录运行：

```
bash ./script/wsl_full_regression.sh
```

该脚本会：

- 使用当前代码重新构建 `xisoul/nonebot-webui:latest`
- 用已知永久 token 重建并拉起 `nonebot-webui`
- 验证未登录拦截、永久 token 登录、JWT 会话时长更新、跨重启 token 持久性

可选环境变量：

- `WEBUI_TEST_TOKEN`
- `WEBUI_TEST_SESSION_HOURS_DEFAULT`
- `WEBUI_TEST_SESSION_HOURS_TEMP`
- `WEBUI_TEST_IMAGE_TAG`
- `WEBUI_TEST_CONTAINER_NAME`
