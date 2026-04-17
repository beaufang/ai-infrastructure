# cc-sp

Claude Code Provider 快速切换工具。在 Windows Terminal 中临时切换模型供应商，关闭窗口自动恢复。

## 安装

下载 cc-sp.ps1 脚本

### 添加别名（推荐）

在 PowerShell 中运行 `notepad $PROFILE`，添加：

```powershell
function cc-sp { & "你的路径\cc-sp.ps1" @args }
```

重启终端后即可在任意目录使用 `cc-sp`。

## 使用

```powershell
cc-sp              # 交互式菜单
cc-sp minimax      # 快速切换到 MiniMax
cc-sp dashscope    # 快速切换到百炼
cc-sp status       # 查看当前 Provider
cc-sp reset        # 恢复默认
cc-sp add          # 添加自定义 Provider
cc-sp help         # 显示帮助
```

首次运行会自动生成 `providers.json` 配置文件。切换时若未设置 API Key，会提示内联输入并保存。

## 配置

编辑 `providers.json` 管理你的 Provider：

```json
[
  {
    "id": "minimax",
    "name": "MiniMax",
    "baseUrl": "https://api.minimaxi.com/anthropic",
    "model": "MiniMax-M2.7",
    "apiKey": "你的API Key"
  }
]
```

也可以通过 `cc-sp add` 命令交互式添加。
