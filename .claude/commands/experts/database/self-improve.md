# Database Expert Self-Improvement Triggers

## When to Update Expertise

Update `expertise.yaml` when:

1. **New query pattern discovered**
   - Efficient way to query data
   - Add to `patterns` with SQL example

2. **Schema evolution**
   - New tables or columns added
   - Update `files` section

3. **Performance insight gained**
   - Index usage, query optimization
   - Document in patterns

4. **JSONB pattern emerged**
   - New way to use JSONB fields
   - Add example

## Improvement Process

```yaml
# After database changes:
1. Review query performance
2. Check if new patterns emerged
3. Validate indexes are used
4. Document any schema changes
5. Update expertise.yaml
```

## Skill Generation Threshold

When this expertise reaches:
- confidence >= 0.8
- usage_count >= 10

Generate `.claude/skills/database-expert/SKILL.md`
