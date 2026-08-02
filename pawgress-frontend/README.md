# Pawgress Frontend — Slice 1

Since this is an existing folder (from Piece 1), just replace it wholesale
with this new zip's contents rather than merging by hand — nothing here
needs `npm install` re-run unless `package.json` changed (it hasn't since
last time).

## Setup (same as before)

1. Backend running locally, reachable at whatever `VITE_API_BASE_URL` in
   your `.env` points to (you already confirmed `127.0.0.1:8000` works —
   keep using that).
2. `npm install` (only if you haven't already / package.json changed)
3. `npm run dev`

## What's new in this piece: the First Capture screen

After logging in, you now land on the actual capture screen instead of the
placeholder — a text box, a Capture button, and the result shown
immediately below it in the same view.

### What to test

1. **A clear multi-item capture.** Try something like:
   `"call the dentist and also pick up groceries and pay the electric bill before friday"`
   You should see three separate task rows appear below the box, each
   showing title / category / priority / estimate (if any). No
   congratulatory message, no exclamation points — just the result.
2. **The box clears itself** after a successful capture, ready for the next
   one — you shouldn't have to manually clear it.
3. **A genuinely non-actionable capture.** Try something like:
   `"today was a pretty good day, nothing special happened"`
   This should show a plain one-line message ("Nothing here needed turning
   into a task.") — **not** an error, not a warning box. This is a
   *successful* outcome per FR-2.2/the golden set's zero-task cases, and it
   should read that way.
4. **A genuine extraction failure**, if you can trigger one (e.g. by
   stopping the AI provider, hitting a rate limit, or temporarily breaking
   `GROQ_API_KEY` to force a `provider_error`): you should see your raw text
   preserved on screen, a plain explanation, and a "Try again" button. Click
   it — it should resubmit the same text as a new capture.
5. **Priority/category/estimate display** — confirm nothing is color-coded
   red/green/etc. Everything should read as plain neutral pill-shaped labels
   regardless of whether priority is Low, Medium, or High.

## What's new in this piece: the flat task list + one-tap correction

Below the capture box, there's now a persistent list of **all** your tasks
(not just the ones from your last capture) — this is `GET /tasks`, fetched
fresh on page load and refreshed automatically right after every capture.

Every field on every row is directly editable, in place:

- **Title** and **Category** — click into the text, edit, then click
  elsewhere (or press Enter) to save. No "Edit" button, no popup.
- **Priority** — a plain dropdown; changing it saves immediately.
- **Estimate (minutes)** — click in, type a number (or clear it entirely
  for "no estimate"), click elsewhere to save.

### What to test

1. **Capture something, then look at the list below it.** The tasks you
   just extracted should appear at the top of the persistent list too (not
   just in the "just captured" panel above) — that's intentional, not a
   duplicate-rendering bug.
2. **Edit a title in place.** Click into any task's title, change it,
   click away. It should just quietly update — no "Saved!" message, no
   confirmation popup, no apologetic copy of any kind. Refresh the page —
   the new title should still be there (confirms it actually persisted, not
   just a visual illusion).
3. **Change a priority via the dropdown.** Should save the instant you pick
   a new value, no extra click needed.
4. **Clear an estimate to blank**, click away — should save as "no
   estimate" (shows as a blank field with a — placeholder, not a 0 or an
   error).
5. **Type garbage into the estimate field** (e.g. letters), click away —
   should just revert to whatever the last valid value was, no error
   message thrown at you.
6. **Reload the whole page.** The task list (and any corrections you made)
   should still be there, fetched fresh from the server — not lost.

### What's new since the last piece: marking a task Done

Each row now has a plain checkbox on the left. Clicking it toggles the task
between Not Started and Done immediately — no confirmation, no "Task
completed!" message, nothing added to the screen beyond the checkbox
itself changing state and the title fading slightly (a quiet
acknowledgment, per UX Philosophy §5.3 — ordinary completions don't get a
celebration).

### What to test

1. **Click a checkbox.** It should check immediately, and the task's title
   should fade to a muted gray — no strikethrough, no color badge, no popup.
2. **Reload the page.** The checked state should still be there (confirms
   it persisted through the real `PATCH` request, not just a visual toggle).
3. **Uncheck it.** Should go back to normal immediately, same lack of
   ceremony either direction.
4. **Confirm no reactive copy anywhere** — no toast, no "nice work," no
   sound. If you saw any of that, something's wrong; the product principle
   here is genuinely "the checkbox is the whole acknowledgment."

This required a small backend patch (`status` added to `TaskUpdateRequest`
in `productivity/schemas.py` + `productivity/routes.py`) — make sure
you've applied that before testing, or the toggle will fail silently
against a backend that doesn't recognize the field.
