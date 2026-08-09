# WeChat Publisher Adapter

CreatorBuddy treats `wechat-publisher` as a publishing adapter, not as a second content-growth engine.

## Boundary

CreatorBuddy owns:

- topic and strategy selection;
- account fit and product fit;
- draft generation;
- publish precheck;
- post-publish review and self-growth.

`wechat-publisher` owns:

- WeChat-compatible HTML execution;
- copy-preview delivery;
- optional authenticated `draft/add` publishing.

## Default Flow

```powershell
python scripts\creatorbuddy.py wechat-publish --title "公众号标题" --content "公众号正文"
```

Default output:

- `reports/*-wechat-mp-precheck.json`
- `publish/wechat-mp/*.html`

The HTML preview includes `ARTICLE HTML START/END` markers and a copy button. It does not require WeChat credentials.

## Optional Draft Box Publishing

Only use this when the user has a certified WeChat Official Account and has configured publisher credentials:

```powershell
python scripts\creatorbuddy.py wechat-publish --title "公众号标题" --file article.md --send-draft --cover cover.jpg
```

Requirements:

- installed `wechat-publisher` skill;
- Node.js and `npx`;
- `WECHAT_APP_ID`;
- `WECHAT_APP_SECRET`;
- WeChat IP whitelist;
- cover image, or `--gen-cover` with image generation credentials.

CreatorBuddy must never print the AppSecret.
