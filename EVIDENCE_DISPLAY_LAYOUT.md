# AI Detector Evidence Display - Visual Layout

## Results Page Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI DETECTOR REPORT                           │
│  CS 101 · Assignment 3 · 3 files · Highest 72%                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ METRIC CARDS                                                    │
├─────────────────────────────────────────────────────────────────┤
│  Files Analysed: 3  │  Flagged: 1  │  Highest: 72%  │  Avg: 45% │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ RISK DISTRIBUTION                                               │
├─────────────────────────────────────────────────────────────────┤
│ ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│ 🔴 High Risk: 1  │  🟡 Needs Review: 1  │  🟢 Low Risk: 1      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ SIGNAL SUMMARY                                                  │
├─────────────────────────────────────────────────────────────────┤
│ Signal              │ Batch Average │ Peak                      │
│ Perplexity          │ ████░░░░░░ 40% │ 72%                     │
│ Burstiness          │ ██░░░░░░░░ 20% │ 65%                     │
│ Stylometry          │ ███░░░░░░░ 30% │ 68%                     │
│ Pattern Library     │ █████░░░░░ 50% │ 85%                     │
│ Structural Entropy  │ ██░░░░░░░░ 20% │ 55%                     │
│ Vocabulary Richness │ ███░░░░░░░ 30% │ 60%                     │
│ Whitespace Rhythm   │ ██░░░░░░░░ 20% │ 45%                     │
│ Docstring Density   │ ████░░░░░░ 40% │ 75%                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ SUBMISSION EVIDENCE                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 🔴 fibonacci.py                                    [High Risk]  │
│    CS 101 · Python                                             │
│    AI Probability: 72%  │  Confidence: 78%                    │
│                                                                 │
│    Indicators:                                                 │
│    [Pattern Library Match] [High Docstring Ratio] [Type Hints] │
│                                                                 │
│    [▼ Expand for Details]                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Expanded Submission Card

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔴 fibonacci.py                                    [High Risk]  │
│    CS 101 · Python                                             │
│    AI Probability: 72%  │  Confidence: 78%                    │
│                                                                 │
│    Indicators:                                                 │
│    [Pattern Library Match] [High Docstring Ratio] [Type Hints] │
│                                                                 │
│    [▲ Collapse]                                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ CODE CHARACTERISTICS                                            │
│ ┌──────────────┬──────────────┬──────────────┐                │
│ │ Total Lines  │ Functions    │ Type Hints   │                │
│ │     42       │      5       │      8       │                │
│ ├──────────────┼──────────────┼──────────────┤                │
│ │ Docstring    │ Comment      │ Avg Line     │                │
│ │ Ratio: 75%   │ Ratio: 25%   │ Length: 52   │                │
│ └──────────────┴──────────────┴──────────────┘                │
│                                                                 │
│ AI-SPECIFIC PATTERNS DETECTED                                  │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ 📝 Docstring Patterns                              [12 found]││
│ │    Line 5:  """Calculate fibonacci number."""              ││
│ │    Line 12: """Initialize result variable."""              ││
│ │    Line 18: """Return the calculated result."""            ││
│ │    +9 more                                                  ││
│ └─────────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ 💬 Comment Patterns                                [8 found] ││
│ │    Line 3:  # Let's implement the fibonacci function       ││
│ │    Line 7:  # Here we check if n is less than 2           ││
│ │    Line 15: # This function returns the result            ││
│ │    +5 more                                                  ││
│ └─────────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ 🔤 Type Hint Patterns                              [8 found] ││
│ │    Line 1:  from typing import Optional, List             ││
│ │    Line 3:  def fibonacci(n: int) -> int:                 ││
│ │    Line 8:  result: Optional[int] = None                  ││
│ │    +5 more                                                  ││
│ └─────────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ ⚠️  Exception Handling                             [5 found] ││
│ │    Line 6:  raise ValueError("n must be positive")        ││
│ │    Line 14: raise TypeError("n must be an integer")       ││
│ │    +3 more                                                  ││
│ └─────────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ 📋 Logging Statements                              [4 found] ││
│ │    Line 4:  logging.info("Starting fibonacci calculation") ││
│ │    Line 20: logging.debug("Result calculated")            ││
│ │    +2 more                                                  ││
│ └─────────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ 📦 Import Patterns                                 [3 found] ││
│ │    Line 1:  import logging                                 ││
│ │    Line 1:  from typing import Optional, List             ││
│ │    +1 more                                                  ││
│ └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│ SIGNAL BREAKDOWN                                                │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Perplexity (Token Entropy)                                  ││
│ │ ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ││
│ │ 35% - Low entropy suggests AI generation                   ││
│ └─────────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Burstiness (Code Complexity Variation)                      ││
│ │ ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ││
│ │ 30% - Uniform patterns suggest AI generation               ││
│ └─────────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Stylometry (Code Style Profile)                             ││
│ │ ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ││
│ │ 40% - Formal style suggests AI generation                  ││
│ └─────────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Pattern Library (LLM Fingerprints)                          ││
│ │ ██████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ││
│ │ 72% - 40+ patterns from GPT-4, Claude, Copilot            ││
│ └─────────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Structural Entropy (AST Uniformity)                         ││
│ │ ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ││
│ │ 20% - Uniform syntax trees suggest AI generation           ││
│ └─────────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Vocabulary Richness (Token Diversity)                       ││
│ │ ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ││
│ │ 25% - Limited vocabulary suggests AI generation            ││
│ └─────────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Whitespace Rhythm (Blank-Line Spacing)                      ││
│ │ ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ││
│ │ 20% - Regular spacing suggests AI generation               ││
│ └─────────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Docstring Density (Documentation Prevalence)                ││
│ │ ██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ││
│ │ 50% - High density suggests AI generation                  ││
│ └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│ ANNOTATED CODE (First 60 Lines)                                │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Code Preview                                                ││
│ │ Amber lines matched LLM fingerprints                       ││
│ ├─────────────────────────────────────────────────────────────┤│
│ │  1 │ import logging                                         ││
│ │  2 │ from typing import Optional, List                     ││
│ │  3 │                                                        ││
│ │  4 │ def fibonacci(n: int) -> int:                         ││
│ │  5 │     """Calculate fibonacci number."""                 ││ ← Flagged
│ │  6 │     if n < 0:                                         ││
│ │  7 │         raise ValueError("n must be positive")        ││ ← Flagged
│ │  8 │     if n <= 1:                                        ││
│ │  9 │         return n                                      ││
│ │ 10 │     return fibonacci(n-1) + fibonacci(n-2)            ││
│ │ 11 │                                                        ││
│ │ 12 │ if __name__ == "__main__":                            ││
│ │ 13 │     logging.info("Starting fibonacci calculation")    ││ ← Flagged
│ │ 14 │     result = fibonacci(10)                            ││
│ │ 15 │     print(result)                                     ││
│ └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Color Coding System

### Risk Levels
- 🔴 **High Risk** (70%+): Red border, red background
- 🟡 **Medium Risk** (40-70%): Orange border, orange background
- 🟢 **Low Risk** (<40%): Green border, green background

### Signal Strength
- 🔴 **Strong** (70%+): Red progress bar
- 🟡 **Moderate** (50-70%): Orange progress bar
- 🟢 **Weak** (30-50%): Yellow progress bar
- ⚪ **Minimal** (<30%): Gray progress bar

### Pattern Sections
- 🟨 **Amber background**: Evidence patterns (AI indicators)
- ⚪ **Gray background**: Code metrics (neutral information)
- 🔵 **Blue background**: Signal breakdown (analysis)

## Responsive Design

### Desktop (1200px+)
- 2-column grid for code characteristics
- Full-width pattern sections
- Side-by-side signal breakdown

### Tablet (768px-1199px)
- 2-column grid for code characteristics
- Full-width pattern sections
- Stacked signal breakdown

### Mobile (< 768px)
- 1-column grid for code characteristics
- Full-width pattern sections
- Stacked signal breakdown
- Collapsible sections for space

## Accessibility Features

- ✅ Color-coded information has text labels
- ✅ Semantic HTML structure
- ✅ ARIA labels for interactive elements
- ✅ Keyboard navigation support
- ✅ High contrast text
- ✅ Readable font sizes

## Interactive Elements

### Expandable Sections
- Click to expand/collapse
- Smooth animations
- Keyboard accessible (Enter/Space)
- Visual indicators (▼/▲)

### Hover Effects
- Subtle background color change
- Cursor changes to pointer
- Tooltip on hover (optional)

### Copy to Clipboard
- Click line number to copy
- Keyboard shortcut (Ctrl+C)
- Visual feedback

## Print Layout

- Optimized for PDF export
- Removes interactive elements
- Maintains color coding
- Includes all evidence
- Page breaks for readability

## Mobile Considerations

- Touch-friendly buttons (44px minimum)
- Readable text (16px minimum)
- Adequate spacing between elements
- Collapsible sections to save space
- Horizontal scroll for code snippets

## Performance Optimizations

- Lazy-load code snippets
- Virtualize long pattern lists
- Debounce expand/collapse
- Cache computed metrics
- Minimize re-renders

## Accessibility Compliance

- WCAG 2.1 Level AA
- Color contrast ratios >4.5:1
- Keyboard navigation
- Screen reader support
- Focus indicators
