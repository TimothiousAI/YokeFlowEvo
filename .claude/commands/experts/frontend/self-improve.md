# Frontend Expert Self-Improvement Triggers

## When to Update Expertise

Update `expertise.yaml` when:

1. **New component pattern discovered**
   - Reusable UI pattern emerges
   - Add to `patterns` with example JSX

2. **shadcn/ui component added**
   - New component from shadcn registry
   - Document usage pattern

3. **Performance optimization found**
   - Discovered better way to structure components
   - Add pattern with before/after

4. **New library integrated**
   - Adding @dnd-kit, charting, etc.
   - Update `stack` section

## Improvement Process

```yaml
# After successful UI implementation:
1. Review component structure decisions
2. Note any reusable patterns
3. Check if Server vs Client choice was optimal
4. Document Tailwind class combinations that work well
5. Update expertise.yaml
```

## Metrics to Track

- **Component reuse**: How often components are shared
- **Bundle impact**: Client component additions
- **Accessibility**: a11y patterns followed

## Skill Generation Threshold

When this expertise reaches:
- confidence >= 0.8
- usage_count >= 10

Generate `.claude/skills/frontend-expert/SKILL.md` with:
- Component templates
- Common Tailwind patterns
- shadcn/ui quick reference
