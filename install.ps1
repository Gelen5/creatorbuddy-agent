$ErrorActionPreference = "Stop"

$SkillName = "creatorbuddy-agent"
$CodexSkills = Join-Path $env:USERPROFILE ".codex\skills"
$Target = Join-Path $CodexSkills $SkillName
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path

New-Item -ItemType Directory -Force -Path $CodexSkills | Out-Null

if (Test-Path $Target) {
  Write-Host "Updating existing CreatorBuddy skill: $Target"
  Remove-Item -Recurse -Force $Target
}

Copy-Item -Recurse -Force $Source $Target
Write-Host "CreatorBuddy skill installed to: $Target"
Write-Host "Restart Codex, then ask: 使用 CreatorBuddy 初始化我的自媒体工作台"
