# Implementation Plan: AI Detector

## Overview

This implementation plan breaks down the AI Detector feature into discrete, actionable coding tasks. The system detects AI-generated code using an 8-signal ensemble approach with weighted fusion and sigmoid calibration. Tasks are organized by functional area and include unit tests, property-based tests, and integration tests to ensure correctness and reliability.

## Tasks

- [ ] 1. Set up project structure and core interfaces
  - [ ] 1.1 Create test fixtures and synthetic code samples
    - Create test data directory with known AI-generated and human-written code samples
    - Create fixture generators for edge cases (empty code, very short code, syntax errors)
    - _Requirements: 1, 25_

  - [ ] 1.2 Create AIDetectionResult data model
    - Define Result class with ai_probability, confidence, signals, indicators, flagged_lines
    - Add validation to ensure all scores are in [0.0, 1.0]
    - _Requirements: 1, 10, 11, 12_

  - [ ] 1.3 Create signal score data model
    - Define SignalScores class with all 8 signal fields
    - Add validation to ensure weights sum to 1.0
    - _Requirements: 10_

  - [ ]* 1.4 Write property test for data model bounds
    - **Property 1: Score Bounds**
    - **Validates: Requirements 10, 11, 12**

- [ ] 2. Implement signal computation layer
  - [ ] 2.1 Implement Perplexity Signal
    - Implement tokenization function for code
    - Compute unigram and bigram entropy
    - Map raw entropy to [0.0, 1.0] score
    - Handle edge cases (< 10 tokens)
    - _Requirements: 2_

  - [ ]* 2.2 Write property test for Perplexity Signal
    - **Property 2: Perplexity Monotonicity**
    - **Validates: Requirements 2, 29_

  - [ ]* 2.3 Write unit tests for Perplexity Signal
    - Test entropy calculation with known distributions
    - Test edge cases (empty code, single token, very short code)
    - Test calibration (human vs AI code ranges)
    - _Requirements: 2_

  - [ ] 2.4 Implement Burstiness Signal
    - Compute line complexity (indentation + length)
    - Calculate coefficient of variation
    - Map CV to [0.0, 1.0] score
    - Handle edge cases (< 5 lines, zero mean)
    - _Requirements: 3_

  - [ ]* 2.5 Write property test for Burstiness Signal
    - **Property 3: Burstiness Monotonicity**
    - **Validates: Requirements 3, 29_

  - [ ]* 2.6 Write unit tests for Burstiness Signal
    - Test CV calculation with uniform and varied complexity
    - Test edge cases (very short code, uniform indentation)
    - Test calibration (human vs AI code ranges)
    - _Requirements: 3_

  - [ ] 2.7 Implement Stylometry Signal
    - Extract style features using StylometryExtractor
    - Compute descriptive variable ratio, docstring ratio, type-hint ratio
    - Compute single-char variable ratio, exception handling ratio, list comprehension ratio
    - Combine features with specified weights
    - _Requirements: 4_

  - [ ]* 2.8 Write unit tests for Stylometry Signal
    - Test feature extraction with synthetic code samples
    - Test edge cases (no functions, no variables, no docstrings)
    - Test weight combination
    - _Requirements: 4_

  - [ ] 2.9 Implement Pattern Library Signal
    - Define 40+ LLM-specific regex fingerprints (comments, naming, structural)
    - Count total pattern matches in code
    - Normalize by code length (lines)
    - Map density to [0.0, 1.0] score
    - _Requirements: 5_

  - [ ]* 2.10 Write property test for Pattern Library Signal
    - **Property 4: Pattern Density Monotonicity**
    - **Validates: Requirements 5, 29_

  - [ ]* 2.11 Write unit tests for Pattern Library Signal
    - Test regex matching with known patterns
    - Test normalization by code length
    - Test edge cases (empty code, very short code)
    - _Requirements: 5_

  - [ ] 2.12 Implement Structural Entropy Signal
    - Parse Python code into AST
    - Compute node type distribution
    - Calculate normalized entropy
    - Implement fallback for non-Python (indent-level uniformity)
    - _Requirements: 6_

  - [ ]* 2.13 Write unit tests for Structural Entropy Signal
    - Test AST parsing and node type counting
    - Test entropy calculation
    - Test fallback for syntax errors and non-Python code
    - _Requirements: 6_

  - [ ] 2.14 Implement Vocabulary Richness Signal
    - Compute Type-Token Ratio (TTR) in sliding windows
    - Compute hapax legomena ratio
    - Combine TTR and hapax with specified weights
    - Handle edge cases (< 20 tokens)
    - _Requirements: 7_

  - [ ]* 2.15 Write unit tests for Vocabulary Richness Signal
    - Test TTR calculation with sliding windows
    - Test hapax legomena computation
    - Test edge cases (all unique tokens, single token)
    - _Requirements: 7_

  - [ ] 2.16 Implement Whitespace Rhythm Signal
    - Identify runs of consecutive blank lines
    - Compute distribution of run lengths
    - Calculate normalized entropy
    - Handle edge cases (< 3 blank-line runs)
    - _Requirements: 8_

  - [ ]* 2.17 Write unit tests for Whitespace Rhythm Signal
    - Test blank-line run detection
    - Test entropy calculation
    - Test edge cases (no blank lines, uniform spacing)
    - _Requirements: 8_

  - [ ] 2.18 Implement Docstring Density Signal
    - Count function definitions
    - Count docstrings (triple-quoted strings)
    - Compute ratio of docstrings to functions
    - Handle edge cases (no functions, no docstrings)
    - _Requirements: 9_

  - [ ]* 2.19 Write unit tests for Docstring Density Signal
    - Test function and docstring counting
    - Test ratio computation
    - Test edge cases (no functions, all functions documented)
    - _Requirements: 9_

- [ ] 3. Checkpoint - Ensure all signal tests pass
  - Ensure all signal unit tests pass, ask the user if questions arise.

- [ ] 4. Implement fusion and calibration layer
  - [ ] 4.1 Implement weighted signal fusion
    - Combine all 8 signals using specified weights
    - Verify weights sum to 1.0
    - Return raw fused score [0.0, 1.0]
    - _Requirements: 10_

  - [ ]* 4.2 Write property test for weighted fusion
    - **Property 5: Monotonic Fusion**
    - **Validates: Requirements 10, 29_

  - [ ]* 4.3 Write unit tests for weighted fusion
    - Test weight combination
    - Test edge cases (all zeros, all ones, mixed)
    - _Requirements: 10_

  - [ ] 4.4 Implement sigmoid calibration
    - Apply sigmoid function with k=6.0 to raw score
    - Map to [0.0, 1.0] probability range
    - Round to 3 decimal places
    - _Requirements: 10_

  - [ ]* 4.5 Write property test for sigmoid calibration
    - **Property 6: Probability Bounds**
    - **Validates: Requirements 10, 29_

  - [ ]* 4.6 Write unit tests for sigmoid calibration
    - Test sigmoid output range [0.0, 1.0]
    - Test midpoint at 0.5
    - Test edge cases (0.0, 1.0)
    - _Requirements: 10_

  - [ ] 4.7 Implement confidence scoring
    - Calculate signal agreement (1.0 - 2.0 * std_dev)
    - Calculate boundary distance (abs(ai_prob - 0.5) * 2.0)
    - Combine with weights (50% agreement, 50% boundary, +10% baseline)
    - Round to 3 decimal places
    - _Requirements: 11_

  - [ ]* 4.8 Write property test for confidence scoring
    - **Property 7: Confidence Bounds**
    - **Validates: Requirements 11, 29_

  - [ ]* 4.9 Write unit tests for confidence scoring
    - Test agreement calculation
    - Test boundary distance calculation
    - Test combination formula
    - _Requirements: 11_

  - [ ] 4.10 Implement risk classification
    - Classify as Low (0.0–0.45), Medium (0.45–0.70), or High (0.70–1.0)
    - Assign visual indicators (green, amber, red)
    - _Requirements: 12_

  - [ ]* 4.11 Write unit tests for risk classification
    - Test threshold boundaries (0.45, 0.70)
    - Test visual indicator assignment
    - _Requirements: 12_

- [ ] 5. Checkpoint - Ensure all fusion tests pass
  - Ensure all fusion and calibration tests pass, ask the user if questions arise.

- [ ] 6. Implement evidence generation layer
  - [ ] 6.1 Implement evidence indicator generation
    - Generate up to 6 human-readable indicators
    - Prioritize by signal strength
    - Include pattern matches, style observations, structural observations
    - Avoid duplicate indicators
    - _Requirements: 13_

  - [ ]* 6.2 Write unit tests for evidence indicators
    - Test indicator generation with various signal combinations
    - Test prioritization by strength
    - Test duplicate avoidance
    - _Requirements: 13_

  - [ ] 6.3 Implement flagged line identification
    - Identify lines containing LLM fingerprints
    - Return up to 30 line numbers (1-indexed)
    - Sort in ascending order
    - Handle multiple patterns per line
    - _Requirements: 14_

  - [ ]* 6.4 Write unit tests for flagged lines
    - Test line identification with known patterns
    - Test sorting and deduplication
    - Test edge cases (no matches, all lines match)
    - _Requirements: 14_

- [ ] 7. Implement core analysis engine
  - [ ] 7.1 Integrate all signals into AIDetectionEngine.analyze()
    - Call all 8 signal computation methods
    - Fuse signals with weighted average
    - Apply sigmoid calibration
    - Compute confidence score
    - Generate indicators and flagged lines
    - Handle edge cases (code too short, syntax errors)
    - _Requirements: 1, 10, 11, 12, 13, 14_

  - [ ]* 7.2 Write property test for analysis idempotence
    - **Property 8: Analysis Idempotence**
    - **Validates: Requirements 30_

  - [ ]* 7.3 Write property test for signal independence
    - **Property 9: Signal Independence**
    - **Validates: Requirements 32_

  - [ ]* 7.4 Write property test for boundary behavior
    - **Property 10: Boundary Behavior**
    - **Validates: Requirements 33_

  - [ ]* 7.5 Write integration tests for core analysis
    - Test end-to-end analysis with various code samples
    - Test edge cases (empty code, very short code, syntax errors)
    - Test all 8 signals are computed
    - _Requirements: 1, 10, 11, 12, 13, 14_

- [ ] 8. Checkpoint - Ensure all analysis tests pass
  - Ensure all analysis and property tests pass, ask the user if questions arise.

- [ ] 9. Implement file upload and validation
  - [ ] 9.1 Implement file type validation
    - Whitelist supported file types (.py, .js, .ts, .java, .cpp, .c, .go, .rb, .php, .cs)
    - Reject unsupported types
    - _Requirements: 15, 23_

  - [ ] 9.2 Implement file size validation
    - Reject individual files > 10 MB
    - Reject ZIP archives > 50 MB
    - _Requirements: 15_

  - [ ] 9.3 Implement file count validation
    - Reject submissions with > 100 files
    - _Requirements: 15_

  - [ ] 9.4 Implement ZIP extraction
    - Extract all files from ZIP archive
    - Validate extracted files
    - Handle nested directories
    - _Requirements: 15_

  - [ ]* 9.5 Write unit tests for file validation
    - Test file type validation
    - Test file size validation
    - Test file count validation
    - Test ZIP extraction
    - _Requirements: 15_

- [ ] 10. Implement API endpoints
  - [ ] 10.1 Implement POST /api/ai-detect endpoint
    - Accept multipart/form-data with file uploads
    - Accept optional course_name and assignment_name
    - Validate files and metadata
    - Create job and return job_id
    - Process files asynchronously
    - _Requirements: 15, 16, 17, 20_

  - [ ] 10.2 Implement GET /api/jobs/{job_id} endpoint
    - Return job status and results
    - Return per-file results with all signals
    - Return batch summary
    - Handle job not found (404)
    - _Requirements: 20_

  - [ ] 10.3 Implement error handling for API
    - Return 400 for validation errors
    - Return 404 for job not found
    - Return 500 for analysis failures
    - Include error messages and details
    - _Requirements: 22_

  - [ ]* 10.4 Write unit tests for API endpoints
    - Test file upload validation
    - Test job creation and tracking
    - Test result retrieval
    - Test error responses
    - _Requirements: 20, 22_

  - [ ]* 10.5 Write integration tests for API
    - Test end-to-end upload → analysis → results flow
    - Test batch processing with multiple files
    - Test error scenarios and recovery
    - _Requirements: 15, 16, 17, 20, 22_

- [ ] 11. Implement batch processing
  - [ ] 11.1 Implement batch file processing
    - Analyze each file independently
    - Return per-file results
    - Compute batch summary (average probability, file count, risk counts)
    - _Requirements: 17_

  - [ ]* 11.2 Write property test for batch consistency
    - **Property 11: Batch Consistency**
    - **Validates: Requirements 31_

  - [ ]* 11.3 Write property test for summary accuracy
    - **Property 12: Summary Accuracy**
    - **Validates: Requirements 31_

  - [ ]* 11.4 Write integration tests for batch processing
    - Test batch processing with multiple files
    - Test per-file results accuracy
    - Test batch summary computation
    - _Requirements: 17_

- [ ] 12. Implement job history and caching
  - [ ] 12.1 Implement in-memory job cache
    - Store recent jobs in memory
    - Cache up to 100 most recent jobs
    - Evict oldest jobs when cache is full
    - _Requirements: 21_

  - [ ] 12.2 Implement job history retrieval
    - Return up to 6 most recent jobs
    - Include job ID, timestamp, file count, average probability
    - _Requirements: 21_

  - [ ]* 12.3 Write unit tests for job caching
    - Test job storage and retrieval
    - Test cache eviction
    - Test history retrieval
    - _Requirements: 21_

- [ ] 13. Implement results display components
  - [ ] 13.1 Create UploadPage React component
    - Implement drag-and-drop file upload
    - Implement file browser selection
    - Display file list with sizes
    - Accept optional course and assignment names
    - Submit button with loading state
    - Error message display
    - _Requirements: 15, 16, 18_

  - [ ] 13.2 Create ResultsPage React component
    - Display risk banner with color-coded level
    - Display AI probability as percentage
    - Display confidence score
    - Display 8 signal cards with scores and descriptions
    - Display evidence indicators
    - Display annotated code snippets with flagged lines
    - _Requirements: 18_

  - [ ] 13.3 Create JobHistory React component
    - Display up to 6 most recent jobs
    - Show job ID, timestamp, file count, average probability
    - Implement click to view results
    - Implement delete job option
    - _Requirements: 21_

  - [ ]* 13.4 Write component tests for UI
    - Test UploadPage file selection and submission
    - Test ResultsPage display of results
    - Test JobHistory display and navigation
    - _Requirements: 15, 18, 21_

- [ ] 14. Implement report generation
  - [ ] 14.1 Implement PDF export functionality
    - Generate PDF with risk classification and AI probability
    - Include all 8 signal scores with descriptions
    - Include evidence indicators
    - Include annotated code snippets
    - Include methodology explanation
    - Include course and assignment metadata
    - Include generation timestamp
    - _Requirements: 19_

  - [ ] 14.2 Implement HTML report generation
    - Generate HTML with same content as PDF
    - Include styling and formatting
    - _Requirements: 19_

  - [ ]* 14.3 Write unit tests for report generation
    - Test PDF content and formatting
    - Test HTML content and formatting
    - Test accessibility compliance
    - _Requirements: 19, 28_

- [ ] 15. Implement language support
  - [ ] 15.1 Implement language detection
    - Detect language from file extension
    - Support Python, JavaScript, TypeScript, Java, C++, C, Go, Ruby, PHP, C#
    - _Requirements: 23_

  - [ ] 15.2 Implement language-specific analysis
    - Apply AST parsing for Python
    - Apply language-agnostic signals for other languages
    - _Requirements: 23_

  - [ ]* 15.3 Write unit tests for language support
    - Test language detection
    - Test language-specific analysis
    - Test fallback for unsupported languages
    - _Requirements: 23_

- [ ] 16. Implement data privacy and security
  - [ ] 16.1 Implement secure file storage
    - Store uploaded files in isolated directory
    - Use job ID for isolation
    - _Requirements: 27_

  - [ ] 16.2 Implement file deletion after analysis
    - Delete uploaded files after analysis completes
    - Implement configurable retention policy
    - _Requirements: 27_

  - [ ] 16.3 Implement data retention policy
    - Configure retention days (default: 7)
    - Configure cache size (default: 100)
    - Implement job deletion endpoint
    - _Requirements: 27_

  - [ ] 16.4 Implement input validation
    - Validate file types and sizes
    - Validate metadata (course name, assignment name)
    - Reject suspicious file names
    - _Requirements: 22, 27_

  - [ ]* 16.5 Write unit tests for security
    - Test file storage isolation
    - Test file deletion
    - Test input validation
    - _Requirements: 27_

- [ ] 17. Implement accessibility features
  - [ ] 17.1 Implement keyboard navigation
    - Make all UI elements keyboard accessible
    - Implement tab order
    - _Requirements: 28_

  - [ ] 17.2 Implement ARIA labels
    - Add ARIA labels to all interactive elements
    - Add ARIA descriptions for complex components
    - _Requirements: 28_

  - [ ] 17.3 Implement color-blind friendly colors
    - Use color-blind friendly color scheme
    - Don't rely on red/green alone
    - _Requirements: 28_

  - [ ]* 17.4 Write accessibility tests
    - Test keyboard navigation
    - Test ARIA labels
    - Test color contrast
    - _Requirements: 28_

- [ ] 18. Implement performance optimization
  - [ ] 18.1 Implement regex pattern caching
    - Cache compiled regex patterns at startup
    - Reuse patterns across analyses
    - _Requirements: 24_

  - [ ] 18.2 Implement tokenization caching
    - Cache tokenization results per file
    - Avoid recomputation
    - _Requirements: 24_

  - [ ] 18.3 Implement performance monitoring
    - Add timing instrumentation to signal computation
    - Log performance metrics
    - _Requirements: 24_

  - [ ]* 18.4 Write performance tests
    - Benchmark single file analysis (target: <2s for ≤100 KB)
    - Benchmark batch processing (target: <5s for 10 files)
    - Benchmark large file analysis (target: <10s for 100 KB–10 MB)
    - _Requirements: 24_

- [ ] 19. Implement explainability features
  - [ ] 19.1 Implement signal descriptions
    - Add plain-language descriptions for each signal
    - Explain what each signal measures
    - _Requirements: 26_

  - [ ] 19.2 Implement methodology documentation
    - Document detection approach
    - Document signal weights and calibration
    - _Requirements: 26_

  - [ ] 19.3 Implement system limitations documentation
    - Document limitations of detection system
    - Document false positive/negative rates
    - _Requirements: 26_

  - [ ]* 19.4 Write documentation tests
    - Verify all signals have descriptions
    - Verify methodology is documented
    - Verify limitations are documented
    - _Requirements: 26_

- [ ] 20. Implement accuracy validation
  - [ ] 20.1 Collect test dataset
    - Gather known AI-generated code samples (GPT-4, Claude, Copilot)
    - Gather known human-written code samples
    - Create edge case samples
    - _Requirements: 25_

  - [ ] 20.2 Measure false negative rate
    - Analyze known AI-generated code
    - Calculate false negative rate (target: <15%)
    - _Requirements: 25_

  - [ ] 20.3 Measure false positive rate
    - Analyze known human-written code
    - Calculate false positive rate (target: <10%)
    - _Requirements: 25_

  - [ ] 20.4 Verify calibration at thresholds
    - Verify 70% of scores ≥0.70 are actually AI-generated
    - Verify 50% of scores ≥0.50 are actually AI-generated
    - _Requirements: 25_

  - [ ] 20.5 Measure confidence correlation
    - Verify confidence scores correlate with actual accuracy
    - Higher confidence = higher accuracy
    - _Requirements: 25_

- [ ] 21. Final integration and testing
  - [ ] 21.1 Write end-to-end integration tests
    - Test complete upload → analysis → results → export flow
    - Test batch processing with multiple files
    - Test PDF export and download
    - Test job history retrieval
    - Test error scenarios and recovery
    - _Requirements: 15, 16, 17, 18, 19, 20, 21, 22_

  - [ ] 21.2 Run full test suite
    - Run all unit tests
    - Run all property-based tests
    - Run all integration tests
    - Verify code coverage >80%
    - _Requirements: 1–28_

  - [ ] 21.3 Verify all requirements are met
    - Check each requirement is covered by at least one test
    - Verify all acceptance criteria are satisfied
    - _Requirements: 1–28_

- [ ] 22. Final checkpoint - Ensure all tests pass
  - Ensure all unit, property-based, and integration tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property-based tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- All code must follow project style guide (black, ruff, PEP 8)
- All functions must have docstrings
- Use type hints for all new code
- Run tests before finalizing each task

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["1.4", "2.1", "2.4", "2.7", "2.9", "2.12", "2.14", "2.16", "2.18"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.5", "2.6", "2.8", "2.10", "2.11", "2.13", "2.15", "2.17", "2.19"] },
    { "id": 3, "tasks": ["4.1", "4.4", "4.7", "4.10"] },
    { "id": 4, "tasks": ["4.2", "4.3", "4.5", "4.6", "4.8", "4.9", "4.11"] },
    { "id": 5, "tasks": ["6.1", "6.3"] },
    { "id": 6, "tasks": ["6.2", "6.4"] },
    { "id": 7, "tasks": ["7.1"] },
    { "id": 8, "tasks": ["7.2", "7.3", "7.4", "7.5"] },
    { "id": 9, "tasks": ["9.1", "9.2", "9.3", "9.4"] },
    { "id": 10, "tasks": ["9.5"] },
    { "id": 11, "tasks": ["10.1", "10.2", "10.3"] },
    { "id": 12, "tasks": ["10.4", "10.5"] },
    { "id": 13, "tasks": ["11.1"] },
    { "id": 14, "tasks": ["11.2", "11.3", "11.4"] },
    { "id": 15, "tasks": ["12.1", "12.2"] },
    { "id": 16, "tasks": ["12.3"] },
    { "id": 17, "tasks": ["13.1", "13.2", "13.3"] },
    { "id": 18, "tasks": ["13.4"] },
    { "id": 19, "tasks": ["14.1", "14.2"] },
    { "id": 20, "tasks": ["14.3"] },
    { "id": 21, "tasks": ["15.1", "15.2"] },
    { "id": 22, "tasks": ["15.3"] },
    { "id": 23, "tasks": ["16.1", "16.2", "16.3", "16.4"] },
    { "id": 24, "tasks": ["16.5"] },
    { "id": 25, "tasks": ["17.1", "17.2", "17.3"] },
    { "id": 26, "tasks": ["17.4"] },
    { "id": 27, "tasks": ["18.1", "18.2", "18.3"] },
    { "id": 28, "tasks": ["18.4"] },
    { "id": 29, "tasks": ["19.1", "19.2", "19.3"] },
    { "id": 30, "tasks": ["19.4"] },
    { "id": 31, "tasks": ["20.1", "20.2", "20.3", "20.4", "20.5"] },
    { "id": 32, "tasks": ["21.1", "21.2", "21.3"] }
  ]
}
```
