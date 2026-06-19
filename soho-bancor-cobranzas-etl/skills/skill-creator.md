# Skill: skill-creator

> Load this skill when you need to create a new skill file and register it in the system.

---

## When to Create a New Skill

Create a new skill file when:
- A new recurring pattern is identified that applies to 2+ modules
- A new external integration is added (e.g., new API, new file format)
- A new domain concept needs to be documented for agent reuse (e.g., a new output format from Bancor)
- An existing skill needs to be split because it covers two distinct concerns

Do NOT create a new skill for:
- One-off instructions specific to a single task
- Content that belongs in a module's `AGENTS.md`
- Content that duplicates existing skills

---

## Skill File Structure

Every skill file in `skills/` must follow this exact structure:

```markdown
# Skill: <skill-name>

> One sentence describing when to load this skill.

---

## Section 1 — [Topic]

Content here.

---

## Section 2 — [Topic]

Content here.
```

### Required elements:
- **Title**: `# Skill: <skill-name>` (matches filename without `.md`)
- **Load trigger** (blockquote): When should an agent load this skill?
- **Sections**: At least 2 sections. Use `---` dividers between sections.
- **Code examples**: Use fenced code blocks with language hints (` ```python `)

### Recommended sections (adapt as needed):
- Overview / When to use
- Patterns / Templates / Conventions
- Examples
- Common pitfalls / What NOT to do

---

## Skill File Naming

- Filename: `<skill-name>.md` (lowercase, hyphenated)
- Keep names short (1-3 words): `bug-fix`, `data-model`, `code-conventions`
- The skill name in the title and in the root `AGENTS.md` skills table must match the filename

---

## Registration Steps

After creating the skill file, you MUST update two places:

### 1. Root `AGENTS.md` — Skills Registry table

Add a new row to the `### Available Skills` table:

```markdown
| `<skill-name>` | `skills/<skill-name>.md` | One-sentence purpose |
```

### 2. Module `AGENTS.md` — Required Skills section

If the new skill is relevant to a specific module, add it to that module's "Required Skills" section:

```markdown
## Required Skills

Load these skills before working on this module:

- `<skill-name>` — brief reason
```

---

## Example: Creating a New Skill "email-delivery"

**Scenario**: We need to automate the email sending step for `back-cargaMasiva`. This is a recurring pattern that could apply to other modules.

**Steps**:

1. Create `skills/email-delivery.md`:
```markdown
# Skill: email-delivery

> Load this skill when implementing or modifying email sending functionality.

---

## Configuration

Email is sent via SMTP using Python's `smtplib`. Configuration comes from `.env`:
...
```

2. Register in `AGENTS.md`:
```markdown
| `email-delivery` | `skills/email-delivery.md` | SMTP config, attachment handling, Bancor email rules |
```

3. Add to `back-cargaMasiva/AGENTS.md` Required Skills:
```markdown
- `email-delivery` — for implementing the Wednesday/Friday send automation
```

---

## Keeping Skills Current

- Update a skill when a pattern changes (e.g., new encoding added to the chain)
- Remove a skill if it becomes obsolete — do not keep dead documentation
- Skills should be **prescriptive** (tell agents what to do) not just descriptive
- Keep skills focused: if a skill exceeds ~200 lines, consider splitting it
