# Post-Audit Execution Skill

## Purpose

This skill defines how agents operate **after an audit is completed**.

Input:

* `audit.json`
* `audit.md` (optional)
* `implementation_plan.json` (optional)

Goal:
Convert audit findings into **validated code changes through controlled agent execution**.

---

# SYSTEM OVERVIEW

```id="flow1"
Audit Log → Issue Normalization → Prioritization → Fix Units → Execution → Validation → Iteration → Completion
```

---

# AGENT ROLES (POST-AUDIT)

The system uses specialized roles within execution:

1. Issue Processor
2. Planner
3. Fix Executor
4. Validator
5. Loop Controller

All roles operate on shared state.

---

# GLOBAL STATE

```json id="state1"
{
  "audit_issues": [],
  "normalized_issues": [],
  "execution_queue": [],
  "fix_units": [],
  "fix_results": [],
  "validation_results": [],
  "completed": [],
  "failed": [],
  "unknowns": []
}
```

---

# STEP 1: ISSUE PROCESSING

## Role: Issue Processor

## Input:

* audit.json

## Task:

Convert raw audit issues into normalized structure.

## Output:

```json id="norm1"
{
  "id": "",
  "title": "",
  "severity": "low|medium|high|critical",
  "component": "",
  "fix_complexity": "low|medium|high",
  "dependencies": []
}
```

## Rules:

* Assign unique IDs
* Do not lose information
* If unclear → add to unknowns

---

# STEP 2: PRIORITIZATION

## Role: Planner

## Task:

Create execution queue.

## Logic:

```id="prio1"
Priority Score = severity × impact × fix_complexity
```

## Execution Order:

1. critical + low complexity
2. critical + medium complexity
3. high severity
4. medium
5. low

## Output:

```json id="queue1"
execution_queue = []
```

---

# STEP 3: FIX UNIT CREATION

## Role: Planner

## Task:

Convert issues into actionable fix units.

## Output:

```json id="fixunit1"
{
  "issue_id": "",
  "goal": "",
  "files_to_modify": [],
  "change_type": "logic_fix|refactor|config",
  "risk_level": "low|medium|high",
  "test_required": true,
  "rollback_possible": true
}
```

## Rules:

* One issue → one fix unit
* Keep scope minimal
* Explicitly define target files

---

# STEP 4: FIX EXECUTION

## Role: Fix Executor

## Task:

Apply code changes.

## Prompt Template:

```id="exec1"
You are a senior engineer applying a fix.

Input:
- issue details
- fix unit

Rules:
- make minimal changes
- do not refactor unrelated code
- preserve behavior
- add inline comments for changes

Output:
{
  "issue_id": "",
  "changes": "",
  "explanation": "",
  "risk": ""
}
```

## Constraints:

* No large rewrites
* No architectural changes unless specified

---

# STEP 5: VALIDATION

## Role: Validator

## Task:

Verify fix correctness.

## Process:

1. Generate tests if missing
2. Execute or simulate
3. Check:

   * issue resolved
   * no regression

## Output:

```json id="val1"
{
  "issue_id": "",
  "status": "fixed|failed|partial",
  "evidence": ""
}
```

---

# STEP 6: EXECUTION LOOP (CORE)

## Role: Loop Controller

This loop drives the entire system using the audit log.

```id="loop1"
while execution_queue not empty:

    issue = pop_next(execution_queue)

    unit = get_fix_unit(issue)

    fix_result = execute_fix(unit)

    validation = validate_fix(unit)

    if validation.status == "fixed":
        move issue → completed

    elif validation.status == "partial":
        refine fix_unit
        requeue issue

    else:
        move issue → failed
        log root cause

    if new issues detected:
        add to normalized_issues
        recompute execution_queue
```

---

# STEP 7: FAILURE HANDLING

## Rules:

* Do not retry blindly
* Update fix strategy before retry
* Track root cause for failure

## Failure Output:

```json id="fail1"
{
  "issue_id": "",
  "reason": "",
  "next_action": ""
}
```

---

# STEP 8: UNKNOWN HANDLING

If any step encounters uncertainty:

```id="unk1"
- log in unknowns
- pause execution for that issue
- continue with next issue
```

---

# STEP 9: COMPLETION CRITERIA

Execution completes when:

```id="done1"
- execution_queue is empty
- all critical issues are resolved
- no unresolved high severity issues remain
```

---

# STEP 10: FINAL OUTPUT

```json id="final1"
{
  "completed_issues": [],
  "failed_issues": [],
  "validation_results": [],
  "remaining_risks": [],
  "next_steps": []
}
```

---

# CRITICAL RULES

* Always operate from audit log
* Never skip validation
* Never batch unrelated fixes
* Maintain traceability per issue
* Recompute queue after every iteration

---

# EXECUTION PRINCIPLE

```id="principle1"
Audit drives execution.
Execution produces validation.
Validation updates audit state.
Repeat until stable.
```

---



---
