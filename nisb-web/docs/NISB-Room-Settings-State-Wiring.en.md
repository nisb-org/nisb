# NISB Room Settings State Wiring Guide

## 1. Definition

NISB Room Settings State Wiring is the end-to-end connection required when a new Room setting must be visible in the UI, saved to backend Room state, restored after reload, and optionally consumed by runtime execution.

The full chain is:

UI control
→ frontend form state
→ derived summary
→ save payload builder
→ submit action
→ backend editable-state whitelist
→ backend normalization
→ frontend store normalization
→ reopened settings modal
→ runtime reader

This is not just UI wiring.
It is not just backend runtime wiring.
It is state wiring across frontend, backend persistence, and runtime.

## 2. Reference feature

Reference feature:

Room worker concurrency

Canonical field:

max_worker_concurrency

Compatibility alias:

worker_concurrency

Allowed values:

1, 2, 3, 4

Recommended product policy:

1 = safest low-resource mode
2 = default / recommended RAG-heavy baseline
3 = advanced
4 = experimental

Runtime policy:

- Missing value falls back to default.
- Invalid value falls back to default.
- Value is clamped to 1..4.
- Server cap may further clamp the effective value.
- Final synthesis is not concurrent.
- External Room MCP consumer payload must not expose internal worker scheduling details.

## 3. File map

Backend save-state layer:

mcp-nisb/tools/rooms_shared/room_tools_meta.py

Frontend UI layer:

nisb-web/src/components/Editor/Room/RoomSettingsOrchestrationCard.vue

Frontend derived state layer:

nisb-web/src/composables/editor/room/room_settings_form_derived.js

Frontend payload layer:

nisb-web/src/composables/editor/room/room_settings_form_patch_builder.js

Frontend form layer:

nisb-web/src/composables/editor/room/use_room_settings_form.js

Frontend submit layer:

nisb-web/src/composables/editor/room/use_room_settings_form_submit.js

Frontend i18n layer:

nisb-web/src/locales/en/room.js
nisb-web/src/locales/zh-CN/room.js

Frontend store normalization layer:

nisb-web/src/stores/room/room_normalizers.js

Runtime layer, if applicable:

mcp-nisb/tools/rooms_shared/room_worker_concurrency.py
mcp-nisb/tools/rooms_shared/room_orchestrator_delegate_flow.py

## 4. Layer responsibilities

### UI component

File:

nisb-web/src/components/Editor/Room/RoomSettingsOrchestrationCard.vue

Responsibilities:

- Render the setting.
- Bind directly to the shared form object.
- Use locale keys for all user-visible text.
- Avoid independent local state unless absolutely required.
- Keep the control near related settings.

For worker concurrency, the setting belongs near reply mode / orchestration controls.

### Form composable

File:

nisb-web/src/composables/editor/room/use_room_settings_form.js

Responsibilities:

- Define the default field value.
- Normalize the field on the client.
- Load saved value from room state.
- Support compatibility aliases if needed.
- Export values and handlers used by the settings component.
- Prevent invalid values from remaining in the form.

For worker concurrency:

- Default product value is 2.
- Valid values are 1..4.
- Prefer `max_worker_concurrency`.
- Accept `worker_concurrency` as alias only.

### Derived summary

File:

nisb-web/src/composables/editor/room/room_settings_form_derived.js

Responsibilities:

- Display a compact summary of current settings.
- Use the same normalized value as the form.
- Do not introduce different validation rules.

For worker concurrency:

The summary should include the current concurrency value.

### Patch builder

File:

nisb-web/src/composables/editor/room/room_settings_form_patch_builder.js

Responsibilities:

- Convert the form into the backend state payload.
- Include the new field.
- Normalize before sending.
- Use the canonical backend field name.

For worker concurrency:

The payload must include:

max_worker_concurrency

If omitted here, the UI may work but saving will not.

### Submit composable

File:

nisb-web/src/composables/editor/room/use_room_settings_form_submit.js

Responsibilities:

- Normalize final submit values.
- Pass the normalizer into the patch builder.
- Ensure the save action receives the full state payload.
- Preserve explicit user choices.

For worker concurrency:

Explicit values 1, 2, 3, and 4 must remain unchanged after submit normalization.

### Backend save-state metadata

File:

mcp-nisb/tools/rooms_shared/room_tools_meta.py

Responsibilities:

- Whitelist the new editable state field.
- Normalize the field server-side.
- Clamp or validate values.
- Persist the field in Room state.
- Return the normalized field in save response.

For worker concurrency:

- Add `max_worker_concurrency` to editable state keys.
- Normalize it as integer.
- Clamp to 1..4.
- Default to 2 if missing or invalid.

If the UI briefly shows the chosen value and then resets after the save response, this file is one of the first places to check.

### Frontend store normalizer

File:

nisb-web/src/stores/room/room_normalizers.js

Responsibilities:

- Preserve the backend-returned field.
- Normalize before storing in Pinia.
- Support aliases if needed.
- Ensure reopening the modal can read the saved value.

For worker concurrency:

`normalize_room_state()` must return:

max_worker_concurrency

It should read:

src.max_worker_concurrency ?? src.worker_concurrency

If backend response is correct but the modal still reopens with the default, this file is one of the first places to check.

### Locale files

Files:

nisb-web/src/locales/en/room.js
nisb-web/src/locales/zh-CN/room.js

Responsibilities:

- Provide all user-facing labels.
- Provide hints and option labels.
- Keep UI bilingual.
- Keep non-locale source files free from hardcoded Chinese.

For worker concurrency, include:

- Title
- Hint
- Option 1 label
- Option 2 label
- Option 3 label
- Option 4 label

## 5. Implementation checklist

Use this checklist for any future Room setting:

- Choose one canonical field name.
- Add the field to the frontend default form.
- Add client normalization.
- Add modal open/load logic.
- Add UI control.
- Add derived summary if useful.
- Add locale keys.
- Add field to patch builder.
- Add submit normalization.
- Add backend editable-state whitelist.
- Add backend normalization.
- Add frontend store normalization.
- Verify save response contains the field.
- Verify modal reopen shows the saved value.
- Verify browser refresh keeps the saved value.
- If runtime uses it, verify runtime request/state can read it.

## 6. Debug checklist

### UI missing

Check:

- RoomSettingsOrchestrationCard.vue
- locale keys
- composable return values

### UI changes but save payload is missing the field

Check:

- room_settings_form_patch_builder.js
- use_room_settings_form_submit.js

### Save payload includes the field but response does not

Check:

- room_tools_meta.py

### Response includes field but store does not

Check:

- room_normalizers.js

### Store includes field but modal reopens with default

Check:

- use_room_settings_form.js
- room opening / fill form logic

### Modal saves and reopens correctly but runtime ignores it

Check:

- runtime reader
- runtime request args
- runtime state snapshot
- backend execution path

## 7. Reference grep commands

Frontend full-chain grep:

```bash
grep -RIn "max_worker_concurrency\\|worker_concurrency" \
  /opt/mcp-gateway/nisb-web/src/components/Editor/Room \
  /opt/mcp-gateway/nisb-web/src/composables/editor/room \
  /opt/mcp-gateway/nisb-web/src/stores/room \
  /opt/mcp-gateway/nisb-web/src/locales
```

Backend save-state grep:

```bash
grep -RIn "max_worker_concurrency\\|worker_concurrency" \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared/room_tools_meta.py
```

Backend runtime grep:

```bash
grep -RIn "max_worker_concurrency\\|worker_concurrency" \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared \
  --exclude-dir=__pycache__
```

## 8. Validation commands

Frontend build:

```bash
cd /opt/mcp-gateway/nisb-web
npm run build
```

Backend compile:

```bash
cd /opt/mcp-gateway/mcp-nisb
python3 -m py_compile tools/rooms_shared/room_tools_meta.py
```

If runtime files were changed:

```bash
python3 -m py_compile tools/rooms_shared/room_worker_concurrency.py
python3 -m py_compile tools/rooms_shared/room_orchestrator_delegate_flow.py
```

Find service name:

```bash
systemctl list-units --type=service | grep -Ei 'nisb|mcp|gateway'
```

Restart the actual backend/frontend service used by deployment.

## 9. Acceptance test

For worker concurrency:

- Open a Room settings modal.
- Confirm default value is 2.
- Change to 1 and save.
- Reopen modal and confirm it stays 1.
- Change to 2 and save.
- Reopen modal and confirm it stays 2.
- Change to 3 and save.
- Reopen modal and confirm it stays 3.
- Change to 4 and save.
- Reopen modal and confirm it stays 4.
- Refresh the browser.
- Reopen modal and confirm the last saved value still remains.

Runtime test:

- Save 1 and verify serial/single-worker behavior.
- Save 2 and verify bounded concurrency behavior.
- Save 3 or 4 only for advanced testing.
- Confirm final synthesis remains serial.
- Confirm result ordering remains stable.
- Confirm LibreChat Room MCP still receives the final answer.
- Confirm external consumer payload does not expose internal worker scheduling details.

## 10. Failure signatures

### Briefly shows selected value, then resets

Meaning:

Backend or frontend store reload overwrote optimistic form state.

Check in order:

1. Backend save response contains the field.
2. room_tools_meta.py whitelists the field.
3. room_normalizers.js preserves the field.

### Always shows default

Meaning:

Saved field is missing from room state or form open logic cannot read it.

Check:

1. Backend response.
2. Store state.
3. `pick_*_from_state` function in form composable.

### Runtime ignores saved setting

Meaning:

Settings state wiring works, but execution path does not read the field.

Check:

1. Runtime request args.
2. Runtime control snapshot.
3. Runtime helper that normalizes the field.

## 11. Rules for future Room settings

- Use one canonical field name.
- Keep aliases read-only unless migration is needed.
- Normalize on both frontend and backend.
- Clamp on backend even if frontend already clamps.
- Do not expose internal runtime settings to external Room MCP consumers unless explicitly designed.
- Do not change Room MCP payload shape for UI-only settings.
- Keep source comments and logic in English.
- Put all user-visible text in locale files.
- Preserve old rooms with missing fields.
- Keep runtime protocol changes separate from settings-state wiring.
