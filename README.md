# DC-Modpack-Data-Migration

> A Python Tool to help DC players migrating their data from old versions of Modpack

Mainly coded by Gemini 3 Pro & GPT-5.2. 所以屎山代码轻喷（

## 开发环境

项目使用 [uv](https://docs.astral.sh/uv/) 管理 Python、虚拟环境、依赖和锁文件。

首次检出项目后执行：

```powershell
uv sync
```

uv 会按照 `.python-version` 创建项目内的 `.venv`，并根据 `uv.lock` 安装依赖。

### 运行

```powershell
uv run python main.py
```

### 测试

```powershell
uv run pytest
```

### 依赖管理

```powershell
# 运行依赖
uv add <package>

# 开发依赖
uv add --dev <package>

# 构建依赖
uv add --group build <package>

# 删除依赖
uv remove <package>
```

请勿直接使用 `pip install` 修改项目环境。提交依赖变更时，应同时提交
`pyproject.toml` 和 `uv.lock`。

### 打包EXE

```powershell
cmd /c build_exe.bat
```

构建脚本会使用锁文件中的 `build` 依赖组，产物位于 `dist` 目录。
