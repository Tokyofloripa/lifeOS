---
globs: ["**/*"]
---
# CI Environment Rules

If the environment variable CI is set (indicating a headless/automated environment):
- Skip interactive confirmations — auto-approve or auto-deny based on security level
- Do not attempt git commits or pushes (the CI workflow handles this)
- Do not display status banners or progress notifications
- Security hooks remain active — block dangerous commands regardless of environment
- The SessionStart and Stop hooks exit early when CI is detected (see settings.json)
