# /review - Risk-Tiered Code Review

Perform code review with risk-based issue classification.

## Usage

```
/review              # Review uncommitted changes
/review --staged     # Review staged changes only
```

## Risk Tiers

### BLOCKER (Must fix)
- Security vulnerabilities
- Data loss potential
- Application crashes

### HIGH RISK (Should fix)
- Performance issues
- Incomplete implementations
- Missing error handling

### MEDIUM RISK (Consider fixing)
- Missing tests
- Code duplication
- Technical debt

### LOW RISK (Nice to have)
- Style inconsistencies
- Naming improvements

## Output Format

```markdown
## Code Review Report

**Verdict**: PASS / FAIL

### Summary
| Risk Level | Count |
|------------|-------|
| BLOCKER | 0 |
| HIGH | X |
| MEDIUM | Y |
| LOW | Z |

### Issues
[Listed by risk tier with file:line and fix suggestions]

### Recommendations
[Priority actions]
```

Output saved to `reviews/<timestamp>.md`
