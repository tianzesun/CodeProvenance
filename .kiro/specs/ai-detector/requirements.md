# AI Detector Requirements Document

## Introduction

The AI Detector is a production-grade system for detecting AI-generated code from large language models (LLMs) such as GPT-4, Claude, and Copilot. Unlike plagiarism checkers, the AI Detector focuses exclusively on identifying code characteristics that indicate LLM generation through an 8-signal ensemble approach. The system provides explainable detection results with annotated code evidence, signal breakdowns, and risk classification to help educators and developers understand why code is flagged as AI-generated.

## Glossary

- **AI_Detector**: The complete system for detecting AI-generated code
- **Signal**: An independent detection metric that measures one aspect of code characteristics (e.g., perplexity, burstiness)
- **Ensemble**: The combination of all eight signals using weighted fusion
- **Submission**: A code file or collection of files uploaded for analysis
- **Risk_Level**: Classification of AI probability as Low (0.0–0.45), Medium (0.45–0.70), or High (0.70–1.0)
- **Confidence**: A measure of agreement among signals and distance from the decision boundary (0.0–1.0)
- **Fingerprint**: A regex pattern that matches LLM-specific code characteristics
- **Perplexity**: Token-level entropy measuring code diversity
- **Burstiness**: Variation in line complexity across code
- **Stylometry**: Analysis of code style including comments, naming, and type hints
- **Pattern_Library**: Collection of 40+ LLM-specific regex fingerprints
- **Structural_Entropy**: AST-level uniformity in code structure
- **Vocabulary_Richness**: Type-Token Ratio (TTR) and hapax legomena ratio
- **Whitespace_Rhythm**: Regularity of blank-line spacing
- **Docstring_Density**: Ratio of docstrings to functions
- **Annotation**: Highlighted code snippets showing evidence of AI generation
- **Report**: Formatted PDF or HTML document containing detection results and methodology

## Requirements

### Requirement 1: AI-Generated Code Detection

**User Story:** As an educator or developer, I want to detect AI-generated code, so that I can identify submissions that may not represent authentic student work.

#### Acceptance Criteria

1. WHEN a code file is submitted, THE AI_Detector SHALL analyze it using all eight signals
2. WHEN analysis completes, THE AI_Detector SHALL return an AI_probability score between 0.0 and 1.0
3. WHEN AI_probability is computed, THE AI_Detector SHALL apply sigmoid calibration to the weighted signal fusion
4. THE AI_Detector SHALL NOT flag code as AI-generated based on plagiarism or code similarity
5. WHEN a submission contains multiple files, THE AI_Detector SHALL analyze each file independently and return per-file results

### Requirement 2: N-Gram Perplexity Signal

**User Story:** As a detection system, I want to measure token-level entropy, so that I can identify code with low diversity (characteristic of LLM output).

#### Acceptance Criteria

1. WHEN code is analyzed, THE Perplexity_Signal SHALL compute unigram entropy from tokenized code
2. WHEN code is analyzed, THE Perplexity_Signal SHALL compute bigram entropy from consecutive token pairs
3. WHEN entropy is computed, THE Perplexity_Signal SHALL combine unigram and bigram entropy (40% unigram, 60% bigram)
4. WHEN combined entropy is computed, THE Perplexity_Signal SHALL map raw entropy to a score between 0.0 and 1.0
5. WHEN code has fewer than 10 tokens, THE Perplexity_Signal SHALL return 0.0

### Requirement 3: Burstiness Signal

**User Story:** As a detection system, I want to measure line complexity variation, so that I can identify code with uniform complexity (characteristic of LLM output).

#### Acceptance Criteria

1. WHEN code is analyzed, THE Burstiness_Signal SHALL compute complexity for each non-empty line
2. WHEN complexity is computed, THE Burstiness_Signal SHALL consider indentation level and line length
3. WHEN complexity is computed, THE Burstiness_Signal SHALL calculate the coefficient of variation across all lines
4. WHEN coefficient of variation is calculated, THE Burstiness_Signal SHALL map it to a score between 0.0 and 1.0
5. WHEN code has fewer than 5 lines, THE Burstiness_Signal SHALL return 0.0

### Requirement 4: Stylometry Signal

**User Story:** As a detection system, I want to analyze code style, so that I can identify LLM-specific stylistic patterns.

#### Acceptance Criteria

1. WHEN code is analyzed, THE Stylometry_Signal SHALL extract style features including comment formality, naming conventions, and type-hint density
2. WHEN style features are extracted, THE Stylometry_Signal SHALL compute a descriptive variable ratio (generic names like "result", "data", "temp")
3. WHEN style features are extracted, THE Stylometry_Signal SHALL compute a docstring ratio relative to code length
4. WHEN style features are extracted, THE Stylometry_Signal SHALL compute a type-hint ratio for function signatures
5. WHEN style features are extracted, THE Stylometry_Signal SHALL compute a single-character variable ratio
6. WHEN style features are extracted, THE Stylometry_Signal SHALL compute an exception-handling ratio
7. WHEN style features are extracted, THE Stylometry_Signal SHALL compute a list-comprehension ratio
8. WHEN all style features are computed, THE Stylometry_Signal SHALL combine them into a single score between 0.0 and 1.0

### Requirement 5: Pattern Library Signal

**User Story:** As a detection system, I want to match LLM-specific code patterns, so that I can identify fingerprints of known LLM generators.

#### Acceptance Criteria

1. WHEN code is analyzed, THE Pattern_Library_Signal SHALL match code against 40+ curated regex fingerprints
2. WHEN fingerprints are matched, THE Pattern_Library_Signal SHALL count total matches across all patterns
3. WHEN matches are counted, THE Pattern_Library_Signal SHALL normalize by code length (lines) to prevent bias toward longer files
4. WHEN normalized, THE Pattern_Library_Signal SHALL map match density to a score between 0.0 and 1.0
5. THE Pattern_Library_Signal SHALL include patterns for LLM-style comments (e.g., "Let's", "Here we", "Step 1:")
6. THE Pattern_Library_Signal SHALL include patterns for generic naming (e.g., "result", "output", "process_")
7. THE Pattern_Library_Signal SHALL include patterns for structural conventions (e.g., "if x is None:", "raise ValueError")

### Requirement 6: Structural Entropy Signal

**User Story:** As a detection system, I want to measure AST uniformity, so that I can identify code with overly regular structure (characteristic of LLM output).

#### Acceptance Criteria

1. WHEN code is Python, THE Structural_Entropy_Signal SHALL parse code into an Abstract Syntax Tree (AST)
2. WHEN AST is parsed, THE Structural_Entropy_Signal SHALL compute the distribution of node types
3. WHEN node distribution is computed, THE Structural_Entropy_Signal SHALL calculate normalized entropy
4. WHEN entropy is calculated, THE Structural_Entropy_Signal SHALL map it to a score between 0.0 and 1.0
5. WHEN code is not Python or parsing fails, THE Structural_Entropy_Signal SHALL fall back to indent-level uniformity analysis
6. WHEN indent-level uniformity is computed, THE Structural_Entropy_Signal SHALL return a score between 0.0 and 1.0

### Requirement 7: Vocabulary Richness Signal

**User Story:** As a detection system, I want to measure vocabulary diversity, so that I can identify code with limited token variety (characteristic of LLM output).

#### Acceptance Criteria

1. WHEN code is analyzed, THE Vocabulary_Richness_Signal SHALL compute Type-Token Ratio (TTR) in sliding windows
2. WHEN TTR is computed, THE Vocabulary_Richness_Signal SHALL use a window size of 50 tokens with 50% overlap
3. WHEN TTR is computed, THE Vocabulary_Richness_Signal SHALL average TTR across all windows
4. WHEN code is analyzed, THE Vocabulary_Richness_Signal SHALL compute hapax legomena ratio (tokens appearing exactly once)
5. WHEN both metrics are computed, THE Vocabulary_Richness_Signal SHALL combine TTR and hapax ratio (60% TTR, 40% hapax)
6. WHEN code has fewer than 20 tokens, THE Vocabulary_Richness_Signal SHALL return 0.0

### Requirement 8: Whitespace Rhythm Signal

**User Story:** As a detection system, I want to measure blank-line spacing regularity, so that I can identify code with overly regular whitespace (characteristic of LLM output).

#### Acceptance Criteria

1. WHEN code is analyzed, THE Whitespace_Rhythm_Signal SHALL identify runs of consecutive blank lines
2. WHEN runs are identified, THE Whitespace_Rhythm_Signal SHALL compute the distribution of run lengths
3. WHEN distribution is computed, THE Whitespace_Rhythm_Signal SHALL calculate normalized entropy
4. WHEN entropy is calculated, THE Whitespace_Rhythm_Signal SHALL map it to a score between 0.0 and 1.0
5. WHEN code has fewer than 3 blank-line runs, THE Whitespace_Rhythm_Signal SHALL return 0.0

### Requirement 9: Docstring Density Signal

**User Story:** As a detection system, I want to measure docstring prevalence, so that I can identify over-documentation (characteristic of LLM output).

#### Acceptance Criteria

1. WHEN code is analyzed, THE Docstring_Density_Signal SHALL count function/method definitions
2. WHEN code is analyzed, THE Docstring_Density_Signal SHALL count docstrings (triple-quoted strings)
3. WHEN counts are computed, THE Docstring_Density_Signal SHALL compute the ratio of docstrings to functions
4. WHEN ratio is computed, THE Docstring_Density_Signal SHALL map it to a score between 0.0 and 1.0
5. WHEN code has no functions, THE Docstring_Density_Signal SHALL compute docstring density relative to code length

### Requirement 10: Signal Fusion and Calibration

**User Story:** As a detection system, I want to combine signals into a final score, so that I can provide a calibrated AI probability.

#### Acceptance Criteria

1. WHEN all signals are computed, THE AI_Detector SHALL apply weighted fusion with the following weights:
   - Perplexity: 0.18
   - Burstiness: 0.14
   - Stylometry: 0.16
   - Pattern_Library: 0.20
   - Structural_Entropy: 0.12
   - Vocabulary_Richness: 0.08
   - Whitespace_Rhythm: 0.06
   - Docstring_Density: 0.06
2. WHEN weighted fusion is computed, THE AI_Detector SHALL apply sigmoid calibration with k=6.0
3. WHEN sigmoid is applied, THE AI_Detector SHALL return a final AI_probability between 0.0 and 1.0
4. WHEN AI_probability is computed, THE AI_Detector SHALL round to 3 decimal places

### Requirement 11: Confidence Scoring

**User Story:** As a detection system, I want to provide confidence in results, so that users understand signal agreement and decision certainty.

#### Acceptance Criteria

1. WHEN all signals are computed, THE AI_Detector SHALL calculate signal agreement as 1.0 minus (2.0 × standard deviation)
2. WHEN AI_probability is computed, THE AI_Detector SHALL calculate boundary distance as absolute distance from 0.5 × 2.0
3. WHEN both metrics are computed, THE AI_Detector SHALL combine them (50% agreement, 50% boundary distance, +10% baseline)
4. WHEN confidence is computed, THE AI_Detector SHALL return a score between 0.0 and 1.0
5. WHEN confidence is computed, THE AI_Detector SHALL round to 3 decimal places

### Requirement 12: Risk Classification

**User Story:** As a user, I want to understand detection results at a glance, so that I can quickly assess the likelihood of AI generation.

#### Acceptance Criteria

1. WHEN AI_probability is between 0.0 and 0.45, THE AI_Detector SHALL classify risk as Low
2. WHEN AI_probability is between 0.45 and 0.70, THE AI_Detector SHALL classify risk as Medium
3. WHEN AI_probability is between 0.70 and 1.0, THE AI_Detector SHALL classify risk as High
4. WHEN risk is classified, THE AI_Detector SHALL assign a visual indicator (green for Low, amber for Medium, red for High)

### Requirement 13: Evidence Indicators

**User Story:** As a user, I want to understand why code is flagged, so that I can review the evidence for AI generation.

#### Acceptance Criteria

1. WHEN code is analyzed, THE AI_Detector SHALL generate up to 6 human-readable evidence indicators
2. WHEN indicators are generated, THE AI_Detector SHALL prioritize by signal strength
3. WHEN indicators are generated, THE AI_Detector SHALL include specific pattern matches (e.g., "LLM-style comment pattern detected (3×)")
4. WHEN indicators are generated, THE AI_Detector SHALL include style observations (e.g., "High docstring density — every function documented")
5. WHEN indicators are generated, THE AI_Detector SHALL include structural observations (e.g., "Unusually uniform line complexity")
6. WHEN indicators are generated, THE AI_Detector SHALL avoid duplicate indicators

### Requirement 14: Flagged Lines

**User Story:** As a user, I want to see which lines contain AI fingerprints, so that I can review specific evidence.

#### Acceptance Criteria

1. WHEN code is analyzed, THE AI_Detector SHALL identify lines containing LLM fingerprints
2. WHEN lines are identified, THE AI_Detector SHALL return up to 30 line numbers (1-indexed)
3. WHEN lines are returned, THE AI_Detector SHALL sort them in ascending order
4. WHEN a line matches multiple patterns, THE AI_Detector SHALL return the line number once

### Requirement 15: File Upload and Submission

**User Story:** As a user, I want to upload code files for analysis, so that I can detect AI-generated code.

#### Acceptance Criteria

1. WHEN a user accesses the upload page, THE AI_Detector SHALL display a file upload interface
2. WHEN a user selects files, THE AI_Detector SHALL accept individual code files or ZIP archives
3. WHEN files are selected, THE AI_Detector SHALL display file names and sizes
4. WHEN a ZIP archive is uploaded, THE AI_Detector SHALL extract and analyze all code files within it
5. WHEN files are uploaded, THE AI_Detector SHALL support the following file types: .py, .js, .ts, .java, .cpp, .c, .go, .rb, .php, .cs
6. WHEN files are uploaded, THE AI_Detector SHALL reject files larger than 10 MB individually
7. WHEN files are uploaded, THE AI_Detector SHALL reject ZIP archives larger than 50 MB
8. WHEN files are uploaded, THE AI_Detector SHALL reject submissions with more than 100 files

### Requirement 16: Metadata Collection

**User Story:** As an educator, I want to associate submissions with courses and assignments, so that I can organize detection results.

#### Acceptance Criteria

1. WHEN a user uploads files, THE AI_Detector SHALL accept optional course name
2. WHEN a user uploads files, THE AI_Detector SHALL accept optional assignment name
3. WHEN metadata is provided, THE AI_Detector SHALL store it with the submission
4. WHEN metadata is not provided, THE AI_Detector SHALL use default values ("AI Detector" for course, "AI Generated Code Review" for assignment)

### Requirement 17: Batch Processing

**User Story:** As a user, I want to analyze multiple files at once, so that I can efficiently review submissions.

#### Acceptance Criteria

1. WHEN multiple files are uploaded, THE AI_Detector SHALL process them in a single batch
2. WHEN files are processed, THE AI_Detector SHALL analyze each file independently
3. WHEN analysis completes, THE AI_Detector SHALL return per-file results with individual scores
4. WHEN results are returned, THE AI_Detector SHALL compute a batch summary with average AI probability and file count

### Requirement 18: Results Display

**User Story:** As a user, I want to view detection results, so that I can understand the analysis.

#### Acceptance Criteria

1. WHEN analysis completes, THE AI_Detector SHALL display a results page
2. WHEN results are displayed, THE AI_Detector SHALL show a risk banner with color-coded risk level
3. WHEN results are displayed, THE AI_Detector SHALL show the AI probability as a percentage
4. WHEN results are displayed, THE AI_Detector SHALL show the confidence score
5. WHEN results are displayed, THE AI_Detector SHALL show metric cards for each of the eight signals
6. WHEN results are displayed, THE AI_Detector SHALL show a signal summary with human-readable descriptions
7. WHEN results are displayed, THE AI_Detector SHALL show annotated code snippets highlighting flagged lines
8. WHEN results are displayed, THE AI_Detector SHALL show evidence indicators in priority order

### Requirement 19: Report Generation

**User Story:** As a user, I want to export detection results, so that I can share findings with others.

#### Acceptance Criteria

1. WHEN results are available, THE AI_Detector SHALL provide a PDF export option
2. WHEN PDF is generated, THE AI_Detector SHALL include the risk classification and AI probability
3. WHEN PDF is generated, THE AI_Detector SHALL include all eight signal scores with descriptions
4. WHEN PDF is generated, THE AI_Detector SHALL include evidence indicators
5. WHEN PDF is generated, THE AI_Detector SHALL include annotated code snippets
6. WHEN PDF is generated, THE AI_Detector SHALL include methodology explanation
7. WHEN PDF is generated, THE AI_Detector SHALL include course and assignment metadata
8. WHEN PDF is generated, THE AI_Detector SHALL include generation timestamp

### Requirement 20: API Contract

**User Story:** As a developer, I want to integrate AI detection into my application, so that I can programmatically analyze code.

#### Acceptance Criteria

1. WHEN a POST request is sent to /api/ai-detect, THE API SHALL accept multipart/form-data with file uploads
2. WHEN a request is received, THE API SHALL accept optional course_name and assignment_name form fields
3. WHEN a request is received, THE API SHALL validate file types and sizes
4. WHEN validation passes, THE API SHALL process files asynchronously and return a job_id
5. WHEN a GET request is sent to /api/jobs/{job_id}, THE API SHALL return job status and results
6. WHEN results are available, THE API SHALL return a JSON response with ai_probability, confidence, signals, indicators, and flagged_lines
7. WHEN an error occurs, THE API SHALL return a 400 or 500 status code with an error message

### Requirement 21: Job History

**User Story:** As a user, I want to view past detection results, so that I can track submissions over time.

#### Acceptance Criteria

1. WHEN a user views the upload page, THE AI_Detector SHALL display recent job history
2. WHEN history is displayed, THE AI_Detector SHALL show up to 6 most recent jobs
3. WHEN history is displayed, THE AI_Detector SHALL show job ID, timestamp, file count, and average AI probability
4. WHEN a user clicks a history entry, THE AI_Detector SHALL navigate to the results page for that job

### Requirement 22: Error Handling

**User Story:** As a user, I want clear error messages, so that I can understand what went wrong.

#### Acceptance Criteria

1. IF no files are uploaded, THEN THE AI_Detector SHALL return an error message "Upload at least one valid code file or ZIP archive"
2. IF a file is too large, THEN THE AI_Detector SHALL return an error message with the file size limit
3. IF a ZIP archive is too large, THEN THE AI_Detector SHALL return an error message with the archive size limit
4. IF too many files are submitted, THEN THE AI_Detector SHALL return an error message with the file count limit
5. IF an unsupported file type is uploaded, THEN THE AI_Detector SHALL skip the file and continue processing others
6. IF analysis fails, THEN THE AI_Detector SHALL return an error message with details
7. WHEN an error occurs, THE AI_Detector SHALL log the error with full context for debugging

### Requirement 23: Language Support

**User Story:** As a user, I want to analyze code in multiple languages, so that I can detect AI generation across different projects.

#### Acceptance Criteria

1. WHEN code is analyzed, THE AI_Detector SHALL support Python (.py) files
2. WHEN code is analyzed, THE AI_Detector SHALL support JavaScript (.js) and TypeScript (.ts) files
3. WHEN code is analyzed, THE AI_Detector SHALL support Java (.java) files
4. WHEN code is analyzed, THE AI_Detector SHALL support C++ (.cpp) and C (.c) files
5. WHEN code is analyzed, THE AI_Detector SHALL support Go (.go) files
6. WHEN code is analyzed, THE AI_Detector SHALL support Ruby (.rb) files
7. WHEN code is analyzed, THE AI_Detector SHALL support PHP (.php) files
8. WHEN code is analyzed, THE AI_Detector SHALL support C# (.cs) files
9. WHEN code is analyzed, THE AI_Detector SHALL apply language-specific analysis where available (e.g., AST parsing for Python)
10. WHEN code is analyzed, THE AI_Detector SHALL fall back to language-agnostic signals for unsupported languages

### Requirement 24: Performance Requirements

**User Story:** As a user, I want fast analysis results, so that I can quickly review submissions.

#### Acceptance Criteria

1. WHEN a single file (≤100 KB) is analyzed, THE AI_Detector SHALL complete analysis within 2 seconds
2. WHEN multiple files are analyzed, THE AI_Detector SHALL complete analysis within 5 seconds for up to 10 files
3. WHEN a large file (100 KB–10 MB) is analyzed, THE AI_Detector SHALL complete analysis within 10 seconds
4. WHEN analysis is in progress, THE API SHALL return a job_id immediately for asynchronous processing

### Requirement 25: Accuracy and Calibration

**User Story:** As a system, I want to provide reliable detection, so that users can trust the results.

#### Acceptance Criteria

1. WHEN the AI_Detector analyzes known AI-generated code, THE false_negative_rate SHALL be less than 15%
2. WHEN the AI_Detector analyzes known human-written code, THE false_positive_rate SHALL be less than 10%
3. WHEN the AI_Detector analyzes code, THE AI_probability scores SHALL be calibrated such that 70% of submissions with score ≥0.70 are actually AI-generated
4. WHEN the AI_Detector analyzes code, THE AI_probability scores SHALL be calibrated such that 50% of submissions with score ≥0.50 are actually AI-generated
5. WHEN the AI_Detector analyzes code, THE confidence scores SHALL correlate with actual accuracy (higher confidence = higher accuracy)

### Requirement 26: Explainability

**User Story:** As a user, I want to understand how detection works, so that I can trust the system.

#### Acceptance Criteria

1. WHEN results are displayed, THE AI_Detector SHALL explain each of the eight signals in plain language
2. WHEN results are displayed, THE AI_Detector SHALL show signal descriptions (e.g., "Token Entropy measures code diversity")
3. WHEN results are displayed, THE AI_Detector SHALL show why each signal contributed to the final score
4. WHEN a report is generated, THE AI_Detector SHALL include a methodology section explaining the detection approach
5. WHEN a report is generated, THE AI_Detector SHALL include limitations of the detection system

### Requirement 27: Data Privacy

**User Story:** As a user, I want my code to be handled securely, so that I can trust the system with sensitive submissions.

#### Acceptance Criteria

1. WHEN code is uploaded, THE AI_Detector SHALL store it in a secure, isolated directory
2. WHEN code is analyzed, THE AI_Detector SHALL NOT transmit code to external services
3. WHEN code is analyzed, THE AI_Detector SHALL NOT use code for training or model improvement
4. WHEN results are stored, THE AI_Detector SHALL NOT retain code after analysis completes (unless explicitly configured)
5. WHEN a user requests deletion, THE AI_Detector SHALL remove all associated files and results

### Requirement 28: Accessibility

**User Story:** As a user with accessibility needs, I want to use the AI Detector, so that I can analyze code regardless of my abilities.

#### Acceptance Criteria

1. WHEN the upload page is displayed, THE UI SHALL be keyboard navigable
2. WHEN the results page is displayed, THE UI SHALL include ARIA labels for all interactive elements
3. WHEN results are displayed, THE UI SHALL use color-blind friendly color schemes (not red/green alone)
4. WHEN code snippets are displayed, THE UI SHALL include text alternatives for visual indicators
5. WHEN a report is generated, THE PDF SHALL be accessible to screen readers

### Requirement 29: Correctness Property: Signal Calibration

**User Story:** As a system, I want to ensure signals are properly calibrated, so that the final score is reliable.

#### Acceptance Criteria

1. FOR ALL code samples, THE sum of all signal weights SHALL equal 1.0
2. FOR ALL code samples, EACH signal score SHALL be between 0.0 and 1.0
3. FOR ALL code samples, THE final AI_probability after sigmoid calibration SHALL be between 0.0 and 1.0
4. FOR ALL code samples, THE confidence score SHALL be between 0.0 and 1.0
5. FOR ALL code samples, THE AI_probability SHALL be monotonically increasing with respect to signal scores (higher signals = higher probability)

### Requirement 30: Correctness Property: Idempotence

**User Story:** As a system, I want to ensure consistent results, so that analyzing the same code twice produces the same output.

#### Acceptance Criteria

1. FOR ALL code samples, ANALYZING the same code twice SHALL produce identical AI_probability scores
2. FOR ALL code samples, ANALYZING the same code twice SHALL produce identical signal scores
3. FOR ALL code samples, ANALYZING the same code twice SHALL produce identical confidence scores
4. FOR ALL code samples, ANALYZING the same code twice SHALL produce identical risk classifications

### Requirement 31: Correctness Property: Batch Consistency

**User Story:** As a system, I want to ensure batch processing is consistent, so that analyzing files individually or in a batch produces equivalent results.

#### Acceptance Criteria

1. FOR ALL file collections, ANALYZING files individually SHALL produce the same per-file scores as analyzing them in a batch
2. FOR ALL file collections, THE batch summary average SHALL equal the arithmetic mean of per-file AI_probabilities
3. FOR ALL file collections, THE batch file count SHALL equal the number of analyzed files

### Requirement 32: Correctness Property: Signal Independence

**User Story:** As a system, I want to ensure signals are independent, so that the ensemble is robust.

#### Acceptance Criteria

1. FOR ALL code samples, EACH signal SHALL be computed independently without reference to other signals
2. FOR ALL code samples, MODIFYING one signal SHALL NOT affect the computation of other signals
3. FOR ALL code samples, THE final score SHALL depend only on the weighted combination of signals, not on signal order

### Requirement 33: Correctness Property: Boundary Behavior

**User Story:** As a system, I want to handle edge cases correctly, so that the detector is robust.

#### Acceptance Criteria

1. WHEN code is empty or very short (<20 characters), THE AI_Detector SHALL return AI_probability of 0.0
2. WHEN code has no functions, THE Docstring_Density_Signal SHALL compute density relative to code length
3. WHEN code has no blank lines, THE Whitespace_Rhythm_Signal SHALL return 0.0
4. WHEN code has only one unique token, THE Perplexity_Signal SHALL return 0.0
5. WHEN code cannot be parsed (syntax error), THE Structural_Entropy_Signal SHALL fall back to indent-level analysis

