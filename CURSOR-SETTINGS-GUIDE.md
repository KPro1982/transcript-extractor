# Cursor AI Settings Configuration Guide

## Optimal Settings Created

I've created `.cursor/settings.json` with cost-optimized settings. However, Cursor also uses VS Code-compatible settings. Since `.vscode/settings.json` is blocked by `.cursorignore`, you'll need to configure these manually in Cursor's global settings.

## Manual Configuration Steps

### 1. Open Cursor Settings
- Press `Ctrl+,` (Windows) or `Cmd+,` (Mac)
- Or go to: File → Preferences → Settings

### 2. Configure AI Model Defaults

**Search for "cursor.ai" or "cursor model"** and set:

```
Cursor → Features → Model
- Default Model: claude-haiku-3 (or gpt-4o-mini)
- Composer Model: claude-sonnet-4 (for complex multi-file edits)
- Chat Model: claude-haiku-3 (for simple questions)
```

### 3. Optimize Autocomplete

**Search for "cursor autocomplete"**:

```
Cursor → Features → Autocomplete
- Enabled: ✓ (checked)
- Delay: 300ms (reduces unnecessary calls)
- Max Results: 3
- Skip Simple Completions: ✓ (checked)
```

### 4. Context Window Settings

**Search for "cursor context"**:

```
Cursor → Features → Context
- Max Context Length: 200000 tokens
- Include Workspace Files: ✓
- Exclude Patterns: 
  - **/node_modules/**
  - **/__pycache__/**
  - **/dist/**
  - **/.git/**
```

### 5. Code Actions

**Search for "cursor code actions"**:

```
Cursor → Features → Code Actions
- Enabled: ✓
- Require Confirmation: ✓ (review before applying)
- Batch Related Edits: ✓
```

### 6. Enable "Use Faster Model" Prompt

**Search for "cursor faster model"**:

```
Cursor → Features → Model Selection
- Use Faster Model When Available: ✓
- Auto Switch to Faster Model: ✓
```

## Model Selection Strategy

### Use Haiku/GPT-4o-mini for:
- ✅ Simple code edits
- ✅ Formatting/linting fixes
- ✅ Reading files
- ✅ Basic questions
- ✅ Single-file refactoring

### Use Sonnet/GPT-4 for:
- ✅ Complex architecture decisions
- ✅ Multi-file refactoring
- ✅ Debugging tricky issues
- ✅ Design planning
- ✅ Composer sessions

## Quick Settings Summary

**Most Cost-Effective Setup:**
1. Default: `claude-haiku-3`
2. Composer: `claude-sonnet-4` (only when needed)
3. Autocomplete delay: 300ms
4. Require confirmation for code actions
5. Auto-switch to faster model enabled

**Expected Cost Reduction:** 70-90% for routine tasks

## Verify Settings

After configuring, test with a simple prompt:
- Should use Haiku/mini by default
- Complex multi-file edits should prompt for Sonnet/GPT-4
- Autocomplete should wait 300ms before suggesting

## Files Created

- ✅ `.cursor/settings.json` - Cursor-specific AI settings
- ✅ `.vscode/extensions.json` - Recommended extensions

## Additional Tips

1. **Use Tab sparingly** - Each Tab completion uses tokens
2. **Batch requests** - Group related edits in one Composer session
3. **Be specific** - Clear prompts reduce back-and-forth
4. **Review before accepting** - Avoid accepting and reverting
5. **Use local tools** - Terminal/git commands don't use AI tokens

## Monitoring Usage

Check Cursor's usage dashboard (if available in your plan) to track:
- Token usage per model
- Cost per session
- Most expensive operations

Adjust settings based on actual usage patterns.












