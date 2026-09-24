# Professor's Guide to AI Detector Evidence

## Quick Reference

### What Each Section Tells You

#### 🔢 Code Characteristics
| Metric | AI-Generated | Human-Written |
|--------|-------------|----------------|
| Docstring Ratio | >60% | <30% |
| Type Hints | >30% of lines | <15% of lines |
| Comment Ratio | 20-40% | 5-20% |
| Avg Line Length | 40-60 chars | 30-80 chars (varied) |
| Functions | Many small functions | Fewer, larger functions |

#### 🎯 AI-Specific Patterns
- **Docstring Patterns**: Formal docstrings on every function
- **Comment Patterns**: "Let's", "Here we", "This function"
- **Type Hints**: `Optional[List[str]]`, `Dict[str, int]`
- **Exception Handling**: Explicit `raise ValueError()` patterns
- **Logging**: `logging.info()`, `logging.error()` calls
- **Imports**: Comprehensive standard library imports

#### 📊 Signal Breakdown
Each signal is 0-100%. Higher = more AI-like:
- **Perplexity**: Token predictability (18% weight)
- **Burstiness**: Code uniformity (14% weight)
- **Stylometry**: Style formality (16% weight)
- **Pattern Library**: LLM fingerprints (20% weight) ⭐ Most important
- **Structural Entropy**: AST uniformity (12% weight)
- **Vocabulary Richness**: Token diversity (8% weight)
- **Whitespace Rhythm**: Spacing regularity (6% weight)
- **Docstring Density**: Documentation (6% weight)

### Decision Matrix

| AI Probability | Confidence | Action |
|---|---|---|
| 70%+ | >80% | 🔴 **Investigate** - High confidence AI |
| 70%+ | 50-80% | 🟡 **Review** - Moderate confidence, check evidence |
| 40-70% | Any | 🟡 **Review** - Borderline, examine patterns |
| <40% | Any | 🟢 **Accept** - Low confidence AI detection |

### Red Flags (Strong AI Indicators)

✅ **Multiple signals >70%** (especially Pattern Library)
✅ **Docstring ratio >60%** (AI adds docstrings everywhere)
✅ **Type hints >30% of lines** (AI uses extensive type hints)
✅ **40+ detected patterns** (Concentration of AI fingerprints)
✅ **Formal, generic comments** ("Let's process", "Here we initialize")
✅ **Perfect code structure** (No messy debugging, no trial-and-error)
✅ **Matches student's skill level poorly** (Too advanced for student)

### Green Flags (Likely Human-Written)

✅ **Single signal >70%, others low** (Could be false positive)
✅ **Code follows best practices** (Type hints, docstrings are good practice)
✅ **Messy sections or debugging code** (Trial-and-error visible)
✅ **Inconsistent style** (Mix of commented-out code, refactoring)
✅ **Matches student's prior work** (Similar style, complexity)
✅ **Low confidence score** (<50%)
✅ **Few detected patterns** (<10)

## Investigation Workflow

### Step 1: Initial Assessment (2 minutes)
1. Check AI Probability score
2. Check Confidence level
3. Look at Code Characteristics
4. Count detected patterns

**Decision**: Is this worth investigating further?

### Step 2: Evidence Review (5 minutes)
1. Examine AI-Specific Patterns
   - Are patterns concentrated or spread out?
   - Do they match the code you're seeing?
2. Review Signal Breakdown
   - Which signals are high?
   - Do they agree with each other?
3. Check Annotated Code
   - Look at flagged lines
   - Do they seem AI-generated?

**Decision**: Is the evidence convincing?

### Step 3: Context Check (5 minutes)
1. Compare with student's prior submissions
   - Is this a significant style change?
   - Is complexity level consistent?
2. Check submission metadata
   - When was it submitted?
   - How long did it take to write?
3. Review assignment requirements
   - Does code match requirements?
   - Are there specific patterns required?

**Decision**: Does context support the AI detection?

### Step 4: Student Interview (10 minutes)
If evidence is strong, conduct a brief interview:

**Questions to Ask:**
1. "Walk me through your development process"
2. "Explain this specific function" (point to flagged code)
3. "Why did you use type hints here?"
4. "What does this line do?" (point to complex line)
5. "How would you modify this to handle X?"

**What to Listen For:**
- ✅ Hesitation or confusion = possible AI generation
- ✅ Generic explanations = possible AI generation
- ✅ Can't explain specific choices = possible AI generation
- ✅ Confident, detailed explanations = likely human-written

## Common Scenarios

### Scenario 1: High Score, High Confidence
**Evidence**: 75% AI probability, 85% confidence, 50+ patterns, docstring ratio 70%

**Action**: 🔴 **Investigate**
- Request student explanation
- Conduct code walkthrough
- Compare with prior submissions
- Consider academic integrity violation

### Scenario 2: High Score, Low Confidence
**Evidence**: 75% AI probability, 40% confidence, 15 patterns, docstring ratio 40%

**Action**: 🟡 **Review**
- Check if code matches best practices
- Compare with student's prior work
- Ask student about development process
- Consider giving benefit of doubt

### Scenario 3: Moderate Score, Mixed Signals
**Evidence**: 55% AI probability, 60% confidence, 25 patterns, mixed signal breakdown

**Action**: 🟡 **Review**
- Examine specific patterns
- Check code quality and consistency
- Compare with student's skill level
- Request student explanation if suspicious

### Scenario 4: Low Score, Low Confidence
**Evidence**: 30% AI probability, 45% confidence, 5 patterns, low docstring ratio

**Action**: 🟢 **Accept**
- Likely human-written
- No further investigation needed
- Trust the detector's assessment

## Important Reminders

### ⚠️ This Tool Is Not Perfect
- **False Positives**: Well-written code can look AI-generated
- **False Negatives**: Modified AI code might not be detected
- **Context Matters**: Code from tutorials, with guidance, or using AI as a learning tool

### ✅ Best Practices
1. **Never rely on this tool alone** - Use it as one factor
2. **Always consider context** - Student's skill level, prior work, assignment requirements
3. **Conduct interviews** - Talk to students about suspicious submissions
4. **Document decisions** - Keep records of your investigation
5. **Be fair** - Give students benefit of doubt for borderline cases
6. **Review policy** - Check your institution's AI usage policy

### 📋 Documentation Template
```
Student: [Name]
Assignment: [Assignment Name]
AI Probability: [Score]%
Confidence: [Score]%
Detected Patterns: [Count]

Evidence Summary:
- Code Characteristics: [Observations]
- AI-Specific Patterns: [Key patterns found]
- Signal Analysis: [Which signals are high]
- Code Quality: [Assessment]

Context:
- Prior Work: [Comparison]
- Skill Level: [Assessment]
- Submission Metadata: [Timestamps, etc.]

Investigation:
- Student Interview: [Notes]
- Conclusion: [AI-generated / Likely human / Uncertain]
- Action Taken: [None / Warning / Escalation]
```

## Frequently Asked Questions

**Q: What if the student used AI as a learning tool?**
A: That's legitimate! The tool detects AI patterns, not AI usage. If your policy allows AI-assisted learning, this is not a violation.

**Q: What if the code is from a tutorial?**
A: Tutorial code often has high docstring ratios and type hints. Check if the student modified it or just copied it.

**Q: What if the student has high type hints in all submissions?**
A: That's their coding style. Compare consistency across submissions rather than absolute values.

**Q: Can I use this for plagiarism detection?**
A: No, this detects AI generation, not plagiarism. Use plagiarism detection tools for that.

**Q: What if I disagree with the score?**
A: Trust your judgment! This tool is a starting point, not a final verdict. Your expertise matters.

## Support & Feedback

If you have questions or feedback about the AI Detector:
1. Document the case (student name, assignment, score, your assessment)
2. Note what the tool got right/wrong
3. Share with the development team
4. Help improve the detector's calibration

Your feedback helps make the tool better for everyone!
