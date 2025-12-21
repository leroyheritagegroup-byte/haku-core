# Haku Build Session - What We Added

## Changes Made

### 1. **TT-01 Truth Team Validation** ✅
- File: `tt01_validation.py`
- Catches shortcuts, assumptions, contradictions
- Validates responses before returning to user
- Blocks responses that fail validation
- Shows warnings for assumption language

### 2. **MOA (Model-Organism Architecture)** ✅
- File: `moa_routing.py`
- Organ-based routing (Senses/Brain/Conscience/Hands)
- Auto-mode detection (ideating/executing/validating/researching)
- Task classification system
- Privacy tier integration

### 3. **Updated Dependencies** ✅
- Fixed deprecated Gemini API (`google-generativeai` → `google-genai`)
- Updated Anthropic SDK (0.7.7 → 0.39.0)
- Updated OpenAI SDK (1.3.7 → 1.54.0)

### 4. **Enhanced Main Application** ✅
- Integrated TT-01 validation into chat endpoint
- MOA routing replaces simple privacy tier routing
- Auto-mode detection shows user what mode they're in
- Validation warnings appended to responses

## How It Works Now

### User sends message →

1. **Heritage LLM Query**: Search encrypted knowledge base
2. **Privacy Tier Classification**: Determine sensitivity (0-3)
3. **MOA Routing**: 
   - Classify task (observation/strategy/validation/execution/buyer-facing)
   - Detect mode (ideating/executing/validating/researching)
   - Route to correct organ (Senses/Brain/Conscience/Hands)
4. **AI Execution**: Run on selected model
5. **TT-01 Validation** (if required):
   - Check for shortcuts
   - Check for contradictions
   - Check for false certainty
   - Block or warn as needed
6. **Return Response**: With validation feedback if applicable

## Response Format

```json
{
  "response": "AI response text (with validation warnings appended if any)",
  "ai_engine": "claude|gpt|gemini|ollama",
  "privacy_tier": 0-3,
  "task_class": "observation|strategy|validation|execution|buyer_facing",
  "mode": "ideating|executing|validating|researching|general",
  "validation_status": "approved|warnings|blocked",
  "heritage_context_used": true|false
}
```

## Validation Examples

### Approved (High Confidence)
- No shortcuts detected
- Addresses query directly
- No contradictions

### Warnings (Medium Confidence)
```
⚠️ TT-01 detected assumption language:
  • Found assumption language: 'probably'
  • Found assumption language: 'seems like'

📋 Stated Assumptions:
  • assuming the API is configured correctly
```

### Blocked
```
❌ TT-01 BLOCKED: Response failed validation checks.

🚫 TT-01 Issues:
  • Response contains internal contradictions
  • Claims certainty without evidence
```

## Next Steps (Not Built Yet)

1. **HGC-01 6-Level Governance** - Full governance enforcement
2. **RAO Realism Checks** - Validate feasibility/constraints
3. **ETG Earnout Validation** - Buyer-facing claim integrity
4. **CBG Bottleneck Governor** - Constraint-based prioritization
5. **Auto-apply file operations** - Preview → approve → apply workflow
6. **User accounts** - Wife's account with selective access
7. **Prompt caching** - Cost optimization

## Deployment

### Local Testing
```bash
cd /home/claude
pip install -r requirements.txt
python main.py
```

### Railway Deployment
1. Copy files to your GitHub repo
2. Push to main branch
3. Railway auto-deploys
4. Set environment variables in Railway:
   - DATABASE_URL (already set)
   - ANTHROPIC_API_KEY (already set)
   - OPENAI_API_KEY (already set)
   - GOOGLE_API_KEY (already set)
   - ENCRYPTION_PASSWORD (add this)

## Files Changed

- `requirements.txt` - Updated dependencies
- `main.py` - Added TT-01 + MOA integration
- `tt01_validation.py` - NEW: Truth Team validation
- `moa_routing.py` - NEW: Organ routing system

## Files Ready to Deploy

All files in `/home/claude/`:
- main.py
- requirements.txt  
- tt01_validation.py
- moa_routing.py
- index.html
- haku-logo.png
- Procfile
- README.md
