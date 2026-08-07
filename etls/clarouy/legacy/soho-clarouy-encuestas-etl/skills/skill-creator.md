# Skill: skill-creator

> Load this skill before creating a new skill file.

---

## When to Create a New Skill

### DO create a skill when:
- A recurring pattern needs documentation
- A specific domain has unique conventions
- A testing approach differs from the general testing skill
- A new module has specific implementation rules

### DON'T create a skill for:
- One-off patterns (use inline comments)
- Module-specific config (put in the module's `AGENTS.md`)
- Single-use utilities (document in code)

---

## Skill File Structure

Every skill file must contain:

1. **Title**: `# Skill: <name>`
2. **Load trigger**: `> Load this skill when <condition>`
3. **Sections** with `---` dividers
4. **Code examples** where applicable
5. **Tables** for quick reference

---

## Naming Convention

- Lowercase
- Hyphenated
- 1-3 words
- Example: `bug-fix`, `code-conventions`, `data-model`

---

## Registration Steps

After creating a new skill:

1. **Update root `AGENTS.md`**: Add to the "AI Skills Registry" table
2. **Update relevant module `AGENTS.md`**: Add to "Required Skills" section

---

## Example: Creating "email-delivery" skill

```markdown
# Skill: email-delivery

> Load this skill when implementing email notification features.

---

## Email Pattern

Use this pattern for sending emails:
...
```

Then register in `AGENTS.md`:

| Skill name | File | Purpose |
|------------|------|---------|
| `email-delivery` | `skills/email-delivery.md` | Email sending patterns |

---

## Keeping Skills Current

- Review skills when module conventions change
- Update examples to match current code
- Remove deprecated patterns
