# Xiaohongshu Playbook Integration

CreatorBuddy includes a sanitized Xiaohongshu operating playbook for internal-test users.

The playbook adapts reusable workflow patterns from a MIT-licensed public Xiaohongshu workbench. It does not vendor that project as a runtime dependency, does not call it at runtime, and does not expose the original project's brand, author, manual, or skill names in user-facing CreatorBuddy output.

## Integrated Capabilities

- Profile gate: check whether a new visitor can understand the account in 3 seconds.
- Topic planner: classify each note as attract, resonate, trust, educate, convert, or interact.
- Title design: choose between cover short line, comment style, insight judgment, and search conversion.
- Title safety: block empty platform cliches and invented proof.
- Comment plan: prepare a value-adding pinned comment and objection reply rules.
- Conversion path: connect content to low-pressure next actions.
- Measurement: require content_id, publish time, 24h/48h/7d metrics, and conversion signal.

## Runtime Contract

The default playbook lives in:

```text
templates/agent_config.json
```

After `init`, each user's editable copy lives in:

```text
%USERPROFILE%\CreatorBuddy\config\agent_config.json
```

`draft --platform xiaohongshu` adds:

```json
{
  "xiaohongshu_brief": {
    "profile_gate": {},
    "topic_planner": {},
    "title_design": {},
    "comment_plan": {},
    "conversion_path": {},
    "measurement": {}
  }
}
```

`precheck --platform xiaohongshu` uses `xiaohongshu_playbook.title_banned_terms` to flag weak or overused title wording.

## Evidence Boundary

The playbook improves packaging and operating discipline. It does not prove platform heat, traffic, saves, followers, leads, sales, or revenue.

Those facts must come from the user's own workspace records or explicitly labeled public samples.
