# 第三方声明

本工作台新编写的代码使用 MIT。未复制第三方完整后台或界面，也未声称为闲鱼官方软件。

真实连接依赖：

- 项目：E-R-Butch/goofish-cli-redux
- 来源：https://github.com/E-R-Butch/goofish-cli-redux
- 固定提交：c2d5a02ad83b18863514389cedf7afbd993b683d
- 包名及版本：goofish-cli 0.3.0
- 上游许可：Apache-2.0；安装包自身保留其 LICENSE / NOTICE。
- 本项目仅通过独立子进程中的白名单函数使用该依赖，不把它的 unrestricted MCP 直接交给 Agent。

该依赖还引用其他项目，使用时须保留相应许可和声明。升级需要重新运行契约测试、检查接口语义及真实账号只读验收，不能只按同名 PyPI 包覆盖。

基础组件包括 FastAPI、Starlette、Pydantic、Uvicorn、cryptography、httpx、Pillow、filelock、MCP Python SDK 等，各组件保留自己的许可证。依赖锁文件记录本次解析的确切版本。
