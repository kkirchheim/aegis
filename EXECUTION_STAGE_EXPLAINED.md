# Execution Stage (Stage 2) - High-Level Overview

## What Is The Execution Stage?

The execution stage is the **second of three stages** in the paper reproducibility checker pipeline. Its job is to **automatically run the code from the paper** to see if it produces the same results the authors claimed.

```
[Stage 1: PDF Analysis] → [Stage 2: Code Execution] → [Stage 3: Evaluation]
(extract paper info)      (run the code)              (assess reproducibility)
```

---

## Inputs (What Stage 2 Receives)

### From Stage 1 (PDF Analysis):
1. **Repository URLs** - Links to GitHub repos containing the paper's code
2. **Claimed Results** - What the paper says the code should produce (e.g., "accuracy: 93.33%")
3. **Dependencies** - Software packages the paper lists (e.g., numpy, tensorflow, scikit-learn)
4. **Dataset Description** - Where/how to get the data needed for the code

### Configuration:
- **Container type** - What environment to run in (Python, R, Julia, etc.)
- **CPU/Memory limits** - Resource constraints for the sandbox
- **Timeout** - How long to wait before stopping execution

---

## What It Does

### 1. **Spawn a Sandbox**
   - Creates an isolated Docker container (sandboxed environment)
   - Prevents malicious or badly-written code from damaging the system
   - Each job gets its own isolated container

### 2. **Clone the Repository**
   - Downloads the GitHub code from the URL found in Stage 1
   - Creates a clean working directory inside the container

### 3. **Install Dependencies**
   - Reads the paper's dependency list (requirements.txt, setup.py, etc.)
   - Installs all required software packages
   - Captures what versions are actually installed

### 4. **Run the Code**
   - Executes the main scripts/notebooks from the repository
   - Records everything that happens:
     - **Commands run** - What code was executed
     - **Output/stdout** - What the code printed to console
     - **Errors** - Any warnings or exceptions that occurred
     - **Files discovered** - What data files were created/used

### 5. **Extract Results**
   - Parses the code output to find numerical results
   - Looks for things like: accuracy scores, F1 scores, loss values, etc.
   - Compares them to what the paper claimed

### 6. **Analyze Reproducibility Issues**
   - Did the code run without errors?
   - Were the results the same as claimed?
   - Were there any warnings about random seeds or randomness?
   - Did it use external APIs or online data that might change?

---

## Outputs (What Stage 2 Produces)

### ExecutionDetails Record (stored in database):
```
{
  "commands_run": ["python train.py", "python evaluate.py"],
  "stdout_combined": "Training model...\nEpoch 1/100: loss=0.45\n...",
  "errors_summary": "None",
  "dependencies_used": ["numpy 1.21.0", "scikit-learn 0.24.2"],
  "actual_results": {
    "accuracy": 0.9333,
    "precision": 0.92,
    "recall": 0.95
  },
  "discovered_files": ["data/train.csv", "models/model.pkl"],
  "test_info": "All 10 tests passed",
  "randomness_info": "Using random_state=42 (deterministic)"
}
```

### Key Metrics Captured:
- **stdout_combined** - Full text output from running the code (up to 100k chars)
- **actual_results** - Numerical results the code produced
- **errors_summary** - Any errors or exceptions (or "None" if clean)
- **dependencies_used** - List of packages with version numbers
- **randomness_info** - Whether randomness is controlled (reproducible or not)

---

## Why This Matters

The execution stage is critical because:

1. **Reveals Hidden Issues**
   - Code might run but produce different results than claimed
   - Dependencies might not be available or have version conflicts
   - Data might be missing or inaccessible

2. **Proves Reproducibility**
   - If the code runs successfully AND produces the claimed results → reproducible ✓
   - If it fails or produces different results → not reproducible ✗

3. **Feeds Stage 3**
   - Stage 3 (evaluation) uses these outputs to assess reproducibility aspects:
     - "Can code be executed?" - Did it run without fatal errors?
     - "Are results consistent?" - Do actual_results match claimed_results?
     - "Are dependencies documented?" - Were all packages properly listed?

---

## How Errors Are Handled

If Stage 2 fails:
- Container is forcibly stopped (timeout protection)
- Error message is captured: "ModuleNotFoundError: numpy", etc.
- Job status is marked as "failed"
- Stage 3 still runs, but with empty/error results

If Stage 2 succeeds but code produces errors:
- Errors are logged but considered "partial success"
- Whatever results were produced are still captured
- Stage 3 assesses whether those partial results matter

---

## Data Flow Summary

```
INPUT                              EXECUTION STAGE                    OUTPUT
─────────────────────────────────────────────────────────────────────────────

Repo URL from                          ┌─────────────────┐      
Stage 1                  ────────→     │  Docker         │     ─→  actual_results
                                       │  Container      │     
Paper's claimed          ────────→     │  (sandbox)      │     ─→  stdout_combined
results                                │                 │     
                                       │  Clones repo    │     ─→  errors_summary
Dependency list          ────────→     │  Installs deps  │     
                                       │  Runs code      │     ─→  dependencies_used
Config (RAM, CPU,        ────────→     │  Extracts       │     
timeout)                               │  results        │     ─→  discovered_files
                                       │                 │     
                                       └─────────────────┘     ─→  randomness_info
                                                           │
                                                           ↓
                                                    Stored in database
                                                    (ExecutionDetails table)
                                                           │
                                                           ↓
                                                    Used by Stage 3 for
                                                    reproducibility assessment
```

---

## Key Technical Details

- **Isolation**: Each execution runs in its own Docker container (can't affect other jobs)
- **Timeout**: Default 30 minutes - if code takes longer, container is killed
- **Streaming**: Output is captured in real-time and stored
- **Non-Deterministic**: If code has randomness (no seed set), results may vary
- **No Internet**: Containers are typically isolated from internet (depends on config)

---

## Common Scenarios

### ✓ Success Case
```
User uploads paper → Stage 1 finds GitHub link → Stage 2 runs code
→ Code executes, produces accuracy: 93.33% (matches paper's claim)
→ Success! Can proceed to Stage 3 evaluation
```

### ✗ Dependency Missing
```
User uploads paper → Stage 1 finds code → Stage 2 tries to install deps
→ pip install fails: "Package 'scipy' not found"
→ Captured as error, Stage 2 fails, execution marked as FAILED
```

### ⚠️ Partial Success
```
User uploads paper → Stage 1 finds code → Stage 2 runs it
→ Code runs with warnings (deprecated libraries)
→ Produces results: accuracy: 0.91 (DIFFERENT from paper's 0.93)
→ Captured as "partial success" - Stage 3 will flag this difference
```

---

## Who Runs The Code?

Technically, an **AI agent** (Claude) runs inside the container. The agent:
- Reads the paper's instructions
- Explores the repository structure
- Figures out how to run the code (find train.py, requirements.txt, etc.)
- Executes commands step-by-step
- Reports what happened

This is more robust than just running a hardcoded script, because the agent can adapt to different project structures.
