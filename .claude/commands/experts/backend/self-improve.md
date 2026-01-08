# Backend Expert Self-Improvement Triggers

## When to Update Expertise

Update `expertise.yaml` when:

1. **New pattern discovered**
   - A reusable code pattern emerges from implementation
   - Add to `patterns` list with name, description, example

2. **Anti-pattern identified**
   - Code review reveals a mistake to avoid
   - Add to `anti_patterns` with bad/good examples

3. **New technology integrated**
   - Adding new library or framework
   - Update `stack` section

4. **File structure changed**
   - New key files added
   - Update `files` section

## Improvement Process

```yaml
# After successful implementation:
1. Review what patterns were used
2. Check if any are missing from expertise.yaml
3. Add new patterns with concrete examples
4. Increment usage_count
5. Update last_updated timestamp
6. If confidence > 0.8 and usage_count > 10, trigger skill generation
```

## Metrics to Track

- **Success rate**: How often implementations work first try
- **Pattern reuse**: How often existing patterns are applied
- **Error frequency**: Common mistakes that become anti-patterns

## Skill Generation Threshold

When this expertise reaches:
- confidence >= 0.8
- usage_count >= 10

Generate `.claude/skills/backend-expert/SKILL.md` with:
- Condensed patterns as instructions
- Common task templates
- Quick reference for imports and boilerplate
