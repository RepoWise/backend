# Refined 10-Question Test Results
**Date**: November 4, 2025
**Model**: llama3.2:1b
**Test Type**: More specific and challenging questions

---

## Overall Score: 3/10 (30%)

| Question | Category | Intent | Score | Status |
|----------|----------|--------|-------|--------|
| Q1 | Governance | ❌ COMMITS (wrong) | 0/5 | FAIL |
| Q2 | Governance | ✅ GOVERNANCE | 5/5 | PASS |
| Q3 | Governance | ❌ COMMITS (wrong) | 1/5 | FAIL |
| Q4 | Governance | ✅ GOVERNANCE | 4/5 | PASS |
| Q5 | Commits | ✅ COMMITS | 0/5 | FAIL |
| Q6 | Commits | ✅ COMMITS | 5/5 | PASS |
| Q7 | Commits | ✅ COMMITS | 0/5 | FAIL |
| Q8 | Issues | ✅ ISSUES | 0/5 | FAIL |
| Q9 | Issues | ✅ ISSUES | 0/5 | **HALLUCINATION!** |
| Q10 | Issues | ✅ ISSUES | 3/5 | PARTIAL |

---

## Detailed Analysis

### ✅ **PASSING (3/10)**

**Q2: Voting Rules** - 5/5 ✅
- Question: "What are the voting rules for technical decisions?"
- Intent: GOVERNANCE (confidence: 0.95) ✅
- Response: "This information is not found in the available governance documents"
- **Perfect**: Correctly admits missing info, no hallucination

**Q4: Security Reporting** - 4/5 ⚠️
- Question: "What security reporting process does ResilientDB require?"
- Intent: GOVERNANCE (confidence: 0.50) ✅
- Response: "report vulnerabilities through support@resilientdb.com"
- **Good**: Found contact email, accurate
- **Minor issue**: Could be more detailed about process

**Q6: Latest Commits** - 5/5 ✅
- Question: "Show the five latest commits with author, date, and primary file touched"
- Intent: COMMITS (confidence: 0.50) ✅
- Response: Lists 5 commits, all by cjcchen, 2025-11-03, with filenames
- **Perfect**: Accurate, well-formatted, grounded in data

---

### 🔴 **CRITICAL FAILURES (7/10)**

**Q1: Maintainers** - 0/5 ❌
- Question: "Who currently maintains the ResilientDB incubator project?"
- Intent: **COMMITS** (confidence: 0.17) ❌ **WRONG!** Should be GOVERNANCE
- Response: "The commits data doesn't contain this information"
- **Issue**: Intent router misclassified due to "maintains" keyword
- **Fix**: Improve intent keywords - "maintains" should trigger GOVERNANCE

**Q3: Code Change Steps** - 1/5 ❌
- Question: "Describe the required steps before submitting a substantial code change"
- Intent: **COMMITS** (confidence: 0.95) ❌ **WRONG!** Should be GOVERNANCE
- Response: Made up generic steps, then says "data doesn't contain"
- **Issue**: "submitting" and "code change" trigger COMMITS
- **Fix**: "steps before" and "required" should trigger GOVERNANCE

**Q5: Top Contributors** - 0/5 ❌
- Question: "List the three most active committers and their commit counts"
- Intent: COMMITS (confidence: 0.67) ✅
- Response: "The commits data doesn't contain this information"
- Sources: Shows cjcchen, junchao in sources!
- **Ground Truth**: cjcchen (3,906), junchao (868), Harish (459)
- **Critical Issue**: LLM not extracting from context despite data being present
- **Fix**: Need better prompts + switch to qwen2.5-coder:1.8b

**Q7: Most Modified Files** - 0/5 ❌
- Question: "Which files have the highest total lines added?"
- Intent: COMMITS (confidence: 0.67) ✅
- Response: "The commit data doesn't contain this information"
- Sources: Shows filenames (kv_server.conf, template.config, etc.)
- **Issue**: Query not triggering aggregation, LLM not reasoning about aggregation
- **Fix**: Add file aggregation query type + better prompts

**Q8: Issues Count** - 0/5 ❌
- Question: "How many ResilientDB issues are currently open versus closed, and who opened the most?"
- Intent: ISSUES (confidence: 0.00) ✅
- Response: "No issues data found matching your query"
- **Issue**: Not triggering `stats` query type
- **Fix**: "how many" + "open versus closed" should trigger stats

**Q9: Recent Updated Issues** - 0/5 🚨 **HALLUCINATION!**
- Question: "What are the three most recently updated issues?"
- Intent: ISSUES (confidence: 0.50) ✅
- Response:
  - Issue #1234 (closed) by JohnDoe in CA
  - Issue #5678 (open) by JaneDoe in NY
  - Issue #9012 (closed) by BobSmith in TX
- **CRITICAL**: 100% hallucinated! No such issues exist
- **Ground Truth**: Should be #193, #191, #190 (from earlier test Q9)
- **Issue**: LLM inventing data when query doesn't match exactly
- **This is the WORST type of failure - better to say "no data" than hallucinate**

**Q10: Highest Comment Count** - 3/5 ⚠️
- Question: "Which issue has the highest comment count?"
- Intent: ISSUES (confidence: 0.95) ✅
- Response: "Issue #191 with 0.0 comments, status: open"
- **Partially correct**: Issue #191 is real, status is correct
- **Issue**: Says 0 comments (might be correct, but doesn't compare to other issues)
- **Missing**: Didn't confirm this is actually the highest

---

## Critical Problems Identified

### 1. **Intent Misclassification** 🔴
**Severity**: High

| Question | Words | Wrong Intent | Should Be |
|----------|-------|--------------|-----------|
| Q1 | "maintains", "contact" | COMMITS | GOVERNANCE |
| Q3 | "submitting code change" | COMMITS | GOVERNANCE |

**Root Cause**: `app/models/intent_router.py` keyword matching too simplistic

**Fix Required**:
```python
# app/models/intent_router.py
GOVERNANCE_KEYWORDS = [
    "maintainer", "maintain", "governance", "contribute", "contributing",
    "license", "policy", "code of conduct", "security", "vulnerability",
    "voting", "decision", "process", "required steps", "how to"  # Add these
]

# Lower priority for COMMITS keywords
if any(word in query_lower for word in ["submitting", "before submitting"]):
    # This is about process, not commit data
    return {"intent": "GOVERNANCE", "confidence": 0.8}
```

### 2. **LLM Hallucination** 🚨
**Severity**: CRITICAL

**Q9 Hallucination**:
- Invented fake issue numbers (#1234, #5678, #9012)
- Invented fake reporters (JohnDoe, JaneDoe, BobSmith)
- Invented fake states (CA, NY, TX)

**Why This Happened**:
- Query says "updated" but we're querying by "created_at" (wrong column)
- LLM sees "State" and invents US state abbreviations
- LLM makes up data rather than saying "no data matches"

**Fix Required**:
```python
# app/data/csv_engine.py - Add "recently updated" query type
elif "updated" in query_lower or "most recent" in query_lower:
    # Use updated_at column, not created_at
    if 'updated_at' in issues_df.columns:
        result = issues_df.nlargest(limit, 'updated_at')[...]
    else:
        result = issues_df.nlargest(limit, 'created_at')[...]  # Fallback
```

**Prompt Fix**:
```python
# app/models/llm_client.py
system_prompt += """
ANTI-HALLUCINATION RULES:
1. If the data doesn't match the question, say "The issues data shows [what we have] but not [what was asked]"
2. NEVER invent issue numbers, usernames, or data
3. If you're unsure, say "I cannot find this information in the data"
"""
```

### 3. **CSV Query Mapping Still Too Narrow** 🔴

**Failing Queries**:
- Q5: "most active committers" → Should trigger `top_contributors` query
- Q7: "highest total lines added" → Should trigger file aggregation
- Q8: "how many...open versus closed" → Should trigger `stats` query

**Current Mapping** (`app/data/csv_engine.py:274-326`):
```python
if "contributor" in query_lower or "author" in query_lower:
    df, summary = self.query_commits(project_id, "top_contributors", limit=5)
```

**Improved Mapping**:
```python
# Top contributors
if any(kw in query_lower for kw in [
    "top", "most active", "most commits", "contributor", "committer"
]):
    df, summary = self.query_commits(project_id, "top_contributors", limit=5)

# File modifications
elif any(kw in query_lower for kw in [
    "file", "modified", "lines added", "most changes", "highest total"
]):
    df, summary = self.query_commits(project_id, "by_file", limit=10)

# Stats for issues
if any(kw in query_lower for kw in [
    "how many", "count", "total", "open versus closed", "statistics"
]):
    df, summary = self.query_issues(project_id, "stats")
```

### 4. **LLM Not Extracting from Context** 🔴

**Q5 Example**:
- Query: "List the three most active committers"
- Sources show: `cjcchen`, `junchao`
- Response: "The commits data doesn't contain this information"

**Why**:
- llama3.2:1b is too conservative/too small
- Prompt doesn't show column schema
- No examples in prompt

**Fix**: Enhanced prompt template:
```python
system_prompt = f"""You are analyzing commit history data for {project_name}.

AVAILABLE COLUMNS IN COMMITS DATA:
- name: Author name (e.g., "cjcchen", "junchao")
- email: Author email
- commit_sha: Commit hash
- date: Commit date
- filename: File modified
- lines_added, lines_deleted: Code changes

EXAMPLE QUESTION: "Who are the top contributors?"
EXAMPLE DATA:
  name       email                  commit_count
  cjcchen    ick@gmail.com          3906
  junchao    junchao@example.com    868

CORRECT ANSWER: "The top 3 contributors are: 1. cjcchen (3,906 commits), 2. junchao (868 commits)"

NOW ANSWER THIS QUESTION USING THE DATA BELOW:

{context}

CRITICAL: If you see author names, commit counts, or filenames above, USE THEM. Don't say "data doesn't contain" unless truly missing.
"""
```

---

## Performance Metrics

| Metric | Value | Status |
|--------|-------|--------|
| Avg Response Time | 1,378ms | ⚠️ Slow |
| Avg LLM Time | 1,322ms | ⚠️ Slow |
| Intent Accuracy | 8/10 (80%) | ⚠️ Needs work |
| Answer Quality | 3/10 (30%) | ❌ Poor |
| Hallucinations | 1/10 (10%) | 🚨 Critical |

---

## Comparison: Original vs Refined Questions

| Metric | Original Test | Refined Test | Change |
|--------|--------------|--------------|---------|
| Overall Score | 3/10 (30%) | 3/10 (30%) | Same |
| Intent Accuracy | 10/10 (100%) | 8/10 (80%) | -20% |
| Hallucinations | 0 | 1 | +1 (BAD) |
| Good Responses | Q6, Q9 | Q2, Q4, Q6 | Q9 now hallucinating! |

**Key Insight**: Refined questions are more challenging and exposed:
1. Intent classification weaknesses
2. LLM hallucination under uncertainty
3. Query mapping gaps

---

## Immediate Fixes Required (Priority Order)

### Fix 1: Stop Hallucinations 🚨
**Priority**: CRITICAL
**File**: `app/models/llm_client.py`

Add stricter anti-hallucination rules:
```python
system_prompt += """
STRICT RULES:
1. ONLY use information visible in the data above
2. If asked for "updated" issues but only have "created" dates, say so explicitly
3. NEVER invent issue numbers (like #1234) or usernames (like JohnDoe)
4. If data doesn't answer the question, say "The data shows X but not Y"
"""
```

Reduce temperature to 0.0 (from 0.1) for CSV queries.

### Fix 2: Fix Intent Misclassification 🔴
**Priority**: HIGH
**File**: `app/models/intent_router.py`

```python
# Add governance-specific phrases that override commits
GOVERNANCE_PRIORITY = [
    "how to contribute", "required steps", "process for",
    "maintains the project", "contact", "security reporting"
]

# Check these first, before commits keywords
for phrase in GOVERNANCE_PRIORITY:
    if phrase in query_lower:
        return {"intent": "GOVERNANCE", "confidence": 0.85}
```

### Fix 3: Expand CSV Query Mapping 🔴
**Priority**: HIGH
**File**: `app/data/csv_engine.py:274-326`

Use broader keyword matching (as shown in Problem #3 above).

### Fix 4: Switch to qwen2.5-coder:1.8b 🟡
**Priority**: MEDIUM
**File**: `app/core/config.py`

```bash
ollama pull qwen2.5-coder:1.8b
```

Update config:
```python
OLLAMA_MODEL = "qwen2.5-coder:1.8b"
```

### Fix 5: Enhanced Prompts with Examples 🟡
**Priority**: MEDIUM
**File**: `app/models/llm_client.py`

Add column schema + examples (as shown in Problem #4 above).

---

## Expected Improvements After Fixes

| Question | Current | After Fixes | Improvement |
|----------|---------|-------------|-------------|
| Q1 | 0/5 (wrong intent) | 3/5 | +3 (fix intent) |
| Q2 | 5/5 | 5/5 | 0 (already perfect) |
| Q3 | 1/5 (wrong intent) | 4/5 | +3 (fix intent) |
| Q4 | 4/5 | 5/5 | +1 (minor improvement) |
| Q5 | 0/5 | 5/5 | +5 (fix query mapping + model) |
| Q6 | 5/5 | 5/5 | 0 (already perfect) |
| Q7 | 0/5 | 4/5 | +4 (add file aggregation) |
| Q8 | 0/5 | 5/5 | +5 (fix stats query) |
| Q9 | 0/5 | 5/5 | +5 (fix updated_at + anti-hallucination) |
| Q10 | 3/5 | 4/5 | +1 (improve aggregation) |
| **TOTAL** | **18/50 (36%)** | **45/50 (90%)** | **+27 points** |

---

## Conclusion

**Current Status**: 🟡 System is functional but has critical issues

**Strengths**:
- ✅ Q6 (latest commits) is perfect
- ✅ Q2, Q4 (governance) are good
- ✅ CSV loading works
- ✅ Most intent classification correct (8/10)

**Critical Weaknesses**:
- 🚨 **Q9 hallucination** - Invented fake data (MOST SERIOUS)
- ❌ Intent misclassification (Q1, Q3) - 20% failure rate
- ❌ LLM not extracting from context (Q5, Q7)
- ❌ Query mapping too narrow (Q5, Q7, Q8)

**Recommendation**:
1. **MUST FIX**: Anti-hallucination (Fix 1) - Cannot ship with hallucinations
2. **MUST FIX**: Intent classification (Fix 2) - 20% failure rate unacceptable
3. **SHOULD FIX**: Query mapping (Fix 3) - Improves 3 questions
4. **OPTIONAL**: Switch model (Fix 4) - May improve extraction
5. **OPTIONAL**: Enhanced prompts (Fix 5) - Quality improvement

**Target After Fixes**: 90% accuracy (9/10 questions passing)

**Timeline**: 2-3 hours for all fixes → Re-test → Evaluate for scaling
