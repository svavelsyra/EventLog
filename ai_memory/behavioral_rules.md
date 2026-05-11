# AI Behavioral Rules - READ FIRST EVERY SESSION

**Purpose**: Core decision-making rules for AI behavior. Read this BEFORE taking any action.

---

## PRIORITIES (When Rules Conflict)

1. **SAFETY** - Read before edit, verify after, use Git carefully when helpful
2. **USER TIME** - Every file changed = user must review = expensive
3. **SMALL PATCHES** - Prefer one coherent decision per change; small-to-medium multi-file edits are acceptable when they apply the same structural fix across direct dependents
4. **DISCUSS FIRST** - User prefers conversation over action

---

## DECISION TREE: When User Speaks

### User asks question (contains "?")
- **ACTION**: ANSWER, don't act
- **NEXT**: DISCUSS alternatives before proposing action
- **REASON**: Question mark = user wants information, not action

### User uses past tense ("I changed X", "I updated Y")
- **ACTION**: This is FYI, NOT a request
- **NEXT**: ASK "Should I sync related files?"
- **NEVER**: Auto-update other files
- **REASON**: User already did the work, they're informing you

### User request is vague/sloppy/unclear
- **ACTION**: STOP - Request clarification
- **NEXT**: If clarification shows large change → Propose incremental approach
- **REASON**: Vague requests often hide large scope

### User uses imperative ("do X", "fix Y", "update Z")
- **ACTION**: OK to act, but CHECK SIZE FIRST
- **SIZE CHECK**:
  - If >3 files affected → STOP, discuss approach
  - If >300 lines changed → STOP, propose smaller steps
  - If unclear scope → STOP, clarify first
  - If all checks pass → Proceed with action

---

## SIZE LIMITS (Hard Stop Points)

**STOP and discuss if ANY of:**
- More than 3 files to modify **and** they require different local decisions
- More than 300 lines of code changes
- Touches more than 2-3 components
- Takes more than 1 focused session (2 hours) of work

**Exception:** A coherent structural propagation may touch more than 3 files when
the same fix is being applied across direct dependents (for example: removing a
symbol export and updating all imports/usages). Treat that as one change theme,
not as forbidden scope creep.

**Core principle**: User prefers 10 small patches over 1 large patch

**Why**: 
- Smaller patches easier to review
- Faster feedback loops
- Less risk per change
- Easier to verify correctness

---

## STORY SPLITTING (Auto-suggest when)

**Triggers for splitting suggestion**:
- More than 4 acceptance criteria
- Expected lines of code > 300
- Touches more than 2 components
- Will take >1 focused session

**Philosophy**: Better to over-split than under-split

**Action**: When you see these triggers, SUGGEST splitting before implementation

---

## COMMUNICATION RULES

### ALWAYS ask first when:
- Syncing multiple files based on inference
- User said "I did X" (past tense)
- Change scope unclear
- Affects >3 files with different local reasoning or different kinds of fixes
- User's request could be interpreted multiple ways

### Act immediately when:
- User uses imperative ("do X")
- Clear bug fix requested
- Single file, small change, clear intent
- Safety issue (file errors, broken code)

---

## SAFETY RULES (NO EXCEPTIONS)

- **Read file before editing** - Never edit blind
- **Validate with get_errors after editing** - Catch problems immediately
- **Git is available** - Git commands may be used when helpful, but still treat validation and careful review as mandatory
- **Think, then act** - Pause and consider before making changes

### Test command approval friction

- Prefer the smallest stable family of approved test commands over many optimized variants.
- Default test command: `python -m pytest`
- Allowed focused command shape: `python -m pytest .\tests\<relative-path-to-single-test-file>.py`
- Do **not** invent extra pytest flags, multi-file command combinations, reordered file lists, node selectors, or `-k` filters unless the user explicitly asks.
- When running tests, reuse the exact approved command shapes and consult `ai_instructions/testing.md` for the detailed policy.

### Approved Git command policy

- Prefer a very small, stable family of read-only Git command shapes to reduce approval churn.
- Default repository-state command: `Set-Location <project-root>; git --no-pager status`
- Default working-tree review command: `Set-Location <project-root>; git --no-pager diff`
- Allowed recent-history command: `Set-Location <project-root>; git --no-pager log --oneline -5`
- Reuse those exact shapes instead of inventing path-limited diffs, per-file Git commands, extra flags, or alternative inspection variants unless the user explicitly asks.
- Treat anything outside that family (`git add`, `git commit`, `git checkout`, `git show`, `git blame`, custom `log` flags, file-specific `diff`, etc.) as ask-first territory unless the user directly requested it.

### General terminal approval friction

- Prefer a very small, stable family of terminal command shapes, not only for pytest.
- Do **not** introduce extra terminal commands unless they are necessary to complete or verify the task.
- For Git, stick to the approved Git command policy above instead of improvising new variants.
- Reason: approval friction comes from command-shape variation itself, not only from pytest flags.

---

## FILE MODIFICATION PROTOCOL

1. **Before editing ANY file**:
   - Read the file first (unless already in context)
   - Understand current state
   - Plan the change

2. **While editing**:
   - Use minimal, focused changes
   - Keep changes logically grouped
   - Preserve existing structure/style
   - Prefer the simplest sane ownership shape for small state: do not create a dedicated file/class plus getter/setter methods for each single scalar value when a plain attribute on an existing or broader state object is enough
   - Prefer updating existing rows/entries/lines in place when that preserves the contract; add new rows/lines only when the change truly introduces new information or a new required branch
   - If multiple project documents repeatedly state a layer boundary or ownership rule, do NOT bypass it with a tactical fix even if the bug is real; move the fix to the owning layer or rethink the patch before proceeding

3. **After editing**:
   - Run get_errors on modified files
   - Fix any errors immediately
   - Report what was changed and why

---

## DOCUMENTATION ABSTRACTION RULES

### Architecture and design docs are NOT implementation files

- Architecture docs should define ownership, boundaries, responsibilities, and cross-component flow.
- Design docs should define contracts, invariants, validation rules, data shapes, and required sequences.
- Do **NOT** place copy-paste-ready implementation code in architecture/design docs unless the exact implementation shape is itself a required contract.
- Prefer bullets, decision tables, sequence descriptions, or clearly labeled pseudocode over real Python implementations.
- If a code-like example is truly needed, keep it short, explicitly label it as illustrative/current-example/pseudocode, and avoid presenting it as the only acceptable implementation path.
- Exact schemas, config formats, SQL DDL, or protocol/order requirements may still be documented concretely when precision is the point.
- Reason: concrete implementation code in design docs locks implementers in too early, encourages copy-paste without thinking, and makes docs stale when code evolves.

### AI memory files are durable guidance, not session history

- `ai_memory/*.md` should store reusable rules, stable patterns, boundary decisions, and durable user preferences.
- Do **not** fill AI memory files with chronological "I changed X in Session Y" narration when the real value is only historical context.
- Put task chronology, temporary migration notes, and step-by-step "what happened" detail in `session_logs/` instead.
- When updating an AI memory file, prefer extracting the durable lesson from a change rather than copying the change history itself.
- Reason: more context is not automatically better; the goal is the right context with low noise.

---

## SESSION PROTOCOL

### Session Definition

- A "session" means one continuous AI instance lifespan
- A session starts when the current AI instance is started
- A session ends only when the user starts a new AI instance
- Side tracks and topic changes within the same instance are still part of the same session

**At start of every session**:
1. Read `ai_memory/behavioral_rules.md` (this file)
2. Check latest session log in `session_logs/`
3. Create new session log: `session_logs/session_XXX.md` (increment number)

**During session**:
- Follow decision tree above
- When in doubt, ASK
- Log significant decisions in session log
- Update the session log continuously during the session when meaningful progress happens, not only at the end
- Treat the session log as the source of truth for what has been done in the current session; update it immediately after each meaningful completed step or new user-confirmed knowledge, not later as a cleanup task
- Session-log maintenance is continuous background work and is NOT part of the normal queued file-step logic; do it automatically as progress happens
- Reason: crashes can happen, so progress should be recorded as it happens

**At end of session**:
- Update session log with summary
- Update behavioral rules if new patterns learned
- Note any unfinished work

---

## ⚠️ CRITICAL: NEVER USE CHECKLISTS IN SESSION LOGS

**DANGER:** Checklist format (`- [ ]`) triggers batch-completion behavior.

**❌ NEVER write in session logs:**
```markdown
## Next Steps
- [ ] File 1
- [ ] File 2  
- [ ] File 3
```

**Why this is dangerous:** The checkbox format is cognitively associated with TODO lists and batch completion, which overrides the stop-and-ask-between-each protocol.

**✅ ALWAYS write in session logs:**
```markdown
## WORK QUEUE - ONE FILE AT A TIME (Stop and Ask Between Each)

**CURRENT STATUS:**
- ✅ File1 - COMPLETED - User confirmed
- ⏸️ NEXT: File2 - AWAITING USER PERMISSION

**REMAINING FILES** (for reference - NOT a batch, each requires separate permission):
- File3
- File4
- File5
```

**Key points:**
- Use status symbols: ✅ (done), ⏸️ (waiting), ❌ (not started)
- Explicitly state "AWAITING USER PERMISSION"
- Explicitly state "NOT a batch"
- Never use `- [ ]` checkbox format in multi-file work

**Exception:** If writing a work plan or architecture document (NOT a session log), checklists may be used BUT must have explicit warning directly above:

```markdown
⚠️ **THESE ARE SEPARATE TASKS - Complete ONE, STOP, ASK, WAIT for permission before next**

- [ ] Task 1 (requires separate user permission)
- [ ] Task 2 (requires separate user permission)
- [ ] Task 3 (requires separate user permission)
```

---

## MULTI-FILE WORK PROTOCOL

When user requests work on multiple files (e.g., "fix all user stories"):

**MANDATORY WORKFLOW:**
1. Complete ONE file
2. STOP immediately after completion
3. Report what was done
4. ASK: "Ready for the next story! Should I continue with [SPECIFIC_FILENAME]?"
5. WAIT for explicit user confirmation
6. ONLY after user says "yes" → Start THAT ONE file
7. Repeat from step 1

**CRITICAL RULE:** Each user "yes" = permission for EXACTLY ONE file. Permission expires when that file is done.

**Structural propagation exception:** If the requested change is one coherent
structural fix that must be applied across direct dependents in the same way,
the change may span multiple files under a single approval. Examples: removing
an accidental export and updating its imports/tests; renaming one API and
updating direct usages. Stop and split the work again as soon as different
files require different design decisions.

**Exception:** Updating the current session log as background maintenance does **not** consume or require separate per-file permission. It should happen automatically while doing the approved work.

**DO NOT:**
- Assume permission carries over to multiple files
- Continue to next file without explicit confirmation
- Interpret "yes" as blanket permission for remaining files
- Use checklist format in session logs (triggers batch behavior)
- Add temporary compatibility shims purely to satisfy an artificial one-file boundary when the cleaner structural fix is to update direct dependents in the same change
- Mark a user story as `Done`, move a story between `user_stories/ToDo/` and `user_stories/Done/`, or check off parent-epic story boxes unless the user explicitly asks for that story-state change

**Example CORRECT behavior:**
```
AI: "✅ Fixed file1.md. Ready for the next story! Should I continue with file2.md?"
User: "yes"
AI: [Fixes file2.md]
AI: "✅ Fixed file2.md. Ready for the next story! Should I continue with file3.md?"
User: "yes"
AI: [Fixes file3.md]
```

**Example WRONG behavior:**
```
AI: "✅ Fixed file1.md. Continuing with file2.md..." ← WRONG! No permission asked
AI: [Starts file2.md without waiting] ← WRONG! Violated protocol
```

---

## SPECIALIZED CONTEXT FILES (Read When Needed)

- **`project_facts.md`** - Read when needing technical context (Python version, stack, constraints)
- **`domain_knowledge.md`** - Read when working on features (military terms, operational context)
- **`story_writing_rules.md`** - Read when creating/editing user stories
- **`gui_learnings.md`** - Read when working on GUI layer
- **`core_learnings.md`** - Read when working on business logic layer
- **`db_learnings.md`** - Read when working on database layer

**Token efficiency**: Only read what you need for current task

---

## EXAMPLE: How This Would Have Prevented the 2600-Line Disaster

**What happened**: AI tried to clean 11 story files at once (2600 lines changed)

**Where behavioral rules would have stopped it**:
1. **Size limit exceeded**: >3 files (violated "STOP at >3 files")
2. **Size limit exceeded**: >300 lines (violated "STOP at >300 lines")
3. **Decision tree missed**: "Continue with file 4/14" in session log = unclear request
4. **Should have asked**: "I see 11 files need cleaning. Should I do them all, or one at a time?"

**Correct behavior**:
- Read decision tree
- See vague continuation context
- ASK: "Would you like me to clean file 4/14 now, or should we discuss how many to do?"
- If user says "do them all" → STOP: "That's 11 files, ~1500 lines. Should we do 2-3 at a time instead?"

---

## REMEMBER

- **User wants discussion, not magic** - Slow down, talk it through
- **Questions deserve answers, not actions** - "?" means respond, not fix
- **Small is better** - Always err on side of smaller changes
- **When uncertain, ask** - User prefers questions to wrong assumptions
- **Past tense = FYI** - "I changed" ≠ "Change this"

---

**Last Updated**: 2026-05-07 (Session 102 - Added explicit approved Git command family and AI-memory scope rule)

