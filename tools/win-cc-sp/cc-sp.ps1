# cc-sp.ps1 — Claude Code Provider Switcher
# 在当前终端会话中临时切换模型供应商，关闭窗口自动恢复
# 用法: cc-sp [provider-id|command]

param([Parameter(Position = 0)][string]$Command)

$ErrorActionPreference = "Stop"
$ConfigFile = Join-Path $PSScriptRoot "providers.json"

# ── Config ────────────────────────────────────────────────────────

function Load-Providers {
    if (!(Test-Path $ConfigFile)) { return $null }
    $raw = [System.IO.File]::ReadAllText($ConfigFile, [System.Text.Encoding]::UTF8)
    $data = $raw | ConvertFrom-Json
    if ($data -isnot [array]) { $data = @($data) }
    return $data
}

function Save-Providers($providers) {
    $json = $providers | ConvertTo-Json -Depth 3
    [System.IO.File]::WriteAllText($ConfigFile, $json, [System.Text.Encoding]::UTF8)
}

function Init-Config {
    $defaults = @(
        [PSCustomObject]@{ id = "minimax";   name = "MiniMax";       baseUrl = "https://api.minimaxi.com/anthropic";             model = "MiniMax-M2.7"; apiKey = "" },
        [PSCustomObject]@{ id = "dashscope";  name = "百炼（阿里云）"; baseUrl = "https://dashscope.aliyuncs.com/compatible-mode/v1"; model = "qwen3.6-plus"; apiKey = "" },
        [PSCustomObject]@{ id = "zhipu";      name = "智谱";          baseUrl = "https://open.bigmodel.cn/api/anthropic";         model = "glm-4.7";      apiKey = "" }
    )
    Save-Providers $defaults
    Write-Host "`n  已创建配置文件: $ConfigFile" -ForegroundColor Green
    return $defaults
}

# ── Helpers ───────────────────────────────────────────────────────

function Find-Provider($providers, [string]$id) {
    foreach ($p in $providers) { if ($p.id -eq $id) { return $p } }
    return $null
}

function Get-Active($providers) {
    $base = $env:ANTHROPIC_BASE_URL
    if (!$base) { return $null }
    foreach ($p in $providers) { if ($p.baseUrl -eq $base) { return $p } }
    return $null
}

function Enter-ApiKey($provider) {
    Write-Host "`n  未设置 $($provider.name) 的 API Key" -ForegroundColor Yellow
    Write-Host "  请输入: " -NoNewline -ForegroundColor Yellow
    $key = Read-Host
    if ([string]::IsNullOrWhiteSpace($key)) { return $false }
    $all = Load-Providers
    foreach ($p in $all) { if ($p.id -eq $provider.id) { $p.apiKey = $key; break } }
    Save-Providers $all
    $provider.apiKey = $key
    Write-Host "  已保存。`n" -ForegroundColor Green
    return $true
}

# ── Actions ───────────────────────────────────────────────────────

function Show-Help($providers) {
    Write-Host ""
    Write-Host "  cc-sp — Claude Code Provider Switcher" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  用法: cc-sp [provider-id|command]" -ForegroundColor White
    Write-Host ""
    Write-Host "  命令:" -ForegroundColor White
    Write-Host "    (无参数)    交互式菜单"
    Write-Host "    status      显示当前 Provider"
    Write-Host "    reset       恢复默认配置"
    Write-Host "    add         添加自定义 Provider"
    Write-Host "    help        显示帮助"
    Write-Host ""
    Write-Host "  快速切换:" -ForegroundColor White
    foreach ($p in $providers) { Write-Host ("    cc-sp {0,-12} {1}" -f $p.id, $p.name) }
    Write-Host ""
}

function Show-Status($providers) {
    $active = Get-Active $providers
    Write-Host ""
    if ($active) {
        Write-Host "  当前: $($active.name)" -ForegroundColor Green
        Write-Host "  Base URL: $($active.baseUrl)" -ForegroundColor Gray
        Write-Host "  Model: $($active.model)" -ForegroundColor Gray
    } elseif ($env:ANTHROPIC_BASE_URL) {
        Write-Host "  当前: 自定义 [$env:ANTHROPIC_BASE_URL]" -ForegroundColor Yellow
    } else {
        Write-Host "  当前: 默认（全局 settings.json）" -ForegroundColor DarkGray
    }
    Write-Host ""
}

function Switch-To($provider) {
    if ([string]::IsNullOrWhiteSpace($provider.apiKey)) {
        if (!(Enter-ApiKey $provider)) {
            Write-Host "  已取消。`n" -ForegroundColor DarkGray
            exit 1
        }
    }
    $env:ANTHROPIC_BASE_URL  = $provider.baseUrl
    $env:ANTHROPIC_AUTH_TOKEN = $provider.apiKey
    $env:ANTHROPIC_MODEL      = $provider.model

    Write-Host ""
    Write-Host "  已切换: $($provider.name)" -ForegroundColor Green
    Write-Host "  Base URL: $($provider.baseUrl)" -ForegroundColor Gray
    Write-Host "  Model: $($provider.model)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  仅当前会话有效，关闭窗口自动恢复。" -ForegroundColor DarkGray
}

function Reset-Session {
    $removed = @()
    foreach ($v in @("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL")) {
        if (Test-Path "Env:$v") { Remove-Item "Env:$v"; $removed += $v }
    }
    Write-Host ""
    if (!$removed) {
        Write-Host "  当前已是默认配置。`n" -ForegroundColor DarkGray
    } else {
        Write-Host "  已清除: $($removed -join ', ')" -ForegroundColor Green
        Write-Host "  已恢复为全局 settings.json 配置。`n" -ForegroundColor Green
    }
}

function Add-CustomProvider {
    Write-Host ""
    Write-Host "  添加自定义 Provider" -ForegroundColor Cyan
    Write-Host "  ────────────────────" -ForegroundColor Cyan
    $id      = (Read-Host "  ID (如 openrouter)").Trim()
    $name    = (Read-Host "  显示名称").Trim()
    $baseUrl = (Read-Host "  Base URL").Trim()
    $model   = (Read-Host "  模型名称").Trim()
    $apiKey  = (Read-Host "  API Key").Trim()

    if (!$id -or !$baseUrl) {
        Write-Host "`n  ID 和 Base URL 不能为空。`n" -ForegroundColor Red; exit 1
    }
    $providers = Load-Providers
    if (Find-Provider $providers $id) {
        Write-Host "`n  Provider '$id' 已存在。`n" -ForegroundColor Red; exit 1
    }

    $providers += [PSCustomObject]@{ id = $id; name = $name; baseUrl = $baseUrl; model = $model; apiKey = $apiKey }
    Save-Providers $providers
    Write-Host "`n  已添加: $name`n" -ForegroundColor Green
}

function Show-Menu($providers) {
    $active = Get-Active $providers

    Clear-Host
    Write-Host ""
    Write-Host "  Claude Code Provider Switcher" -ForegroundColor Cyan
    Write-Host "  ──────────────────────────────" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "  当前: " -NoNewline -ForegroundColor Gray
    if ($active) {
        Write-Host $active.name -ForegroundColor Green
    } elseif ($env:ANTHROPIC_BASE_URL) {
        Write-Host "自定义" -ForegroundColor Yellow
    } else {
        Write-Host "默认" -ForegroundColor DarkGray
    }
    Write-Host ""

    for ($i = 0; $i -lt $providers.Count; $i++) {
        $p   = $providers[$i]
        $cur = ($active -and $active.id -eq $p.id)
        $c   = if ($cur) { "Green" } else { "White" }
        Write-Host "  [$($i + 1)] " -NoNewline -ForegroundColor $c
        Write-Host "$($p.name)" -NoNewline -ForegroundColor $c
        if ($cur) { Write-Host " *" -ForegroundColor Green } else { Write-Host "" }
    }

    Write-Host ""
    Write-Host "  [0] 恢复默认" -ForegroundColor DarkGray
    Write-Host "  [Q] 退出" -ForegroundColor DarkGray
    Write-Host ""

    $choice = (Read-Host "  选择").Trim()
    if ($choice -in @("Q", "q")) { exit 0 }
    if ($choice -eq "0") { Reset-Session; exit 0 }

    $target = Find-Provider $providers $choice
    if (!$target -and $choice -match '^\d+$') {
        $idx = [int]$choice - 1
        if ($idx -ge 0 -and $idx -lt $providers.Count) { $target = $providers[$idx] }
    }
    if (!$target) { Write-Host "`n  无效选项。`n" -ForegroundColor Red; exit 1 }

    Switch-To $target
}

# ── Main ──────────────────────────────────────────────────────────

$providers = Load-Providers
if (!$providers) { $providers = Init-Config }

$c = $Command.ToLower()

switch -Regex ($c) {
    '^(status|-s|--status)$' { Show-Status $providers; exit 0 }
    '^(reset|-r|--reset)$'   { Reset-Session; exit 0 }
    '^(add|-a|--add)$'       { Add-CustomProvider; exit 0 }
    '^(help|-h|--help|\?)$'  { Show-Help $providers; exit 0 }
    '^$'                     { Show-Menu $providers; exit 0 }
    default {
        $target = Find-Provider $providers $c
        if (!$target) {
            Write-Host "`n  未知 Provider: $Command" -ForegroundColor Red
            Write-Host "  运行 cc-sp 查看可用选项。`n" -ForegroundColor Yellow
            exit 1
        }
        Switch-To $target
    }
}
