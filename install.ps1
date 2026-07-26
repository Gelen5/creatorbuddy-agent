$ErrorActionPreference = "Stop"

$SkillName = "creatorbuddy-agent"
$CodexSkills = Join-Path $env:USERPROFILE ".codex\skills"
$Target = Join-Path $CodexSkills $SkillName
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path

New-Item -ItemType Directory -Force -Path $CodexSkills | Out-Null

if (Test-Path $Target) {
  $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $Backup = "$Target.backup-$Stamp"
  Write-Host "Backing up existing CreatorBuddy skill to: $Backup"
  Move-Item -LiteralPath $Target -Destination $Backup
}

New-Item -ItemType Directory -Force -Path $Target | Out-Null
Get-ChildItem -LiteralPath $Source -Force | Where-Object { $_.Name -ne ".git" } | Copy-Item -Destination $Target -Recurse -Force
Write-Host "CreatorBuddy skill installed to: $Target"
Write-Host "Restart Codex, then ask: 使用 CreatorBuddy 初始化我的自媒体工作台"
