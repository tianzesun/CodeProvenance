# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-05-05

### Added
- Starter code upload feature: Professors can now upload template/starter code files that are automatically excluded from plagiarism detection
- Improved settings page with reorganized tabs and clearer labels (AI Analysis, Scoring & Thresholds, Review Workflow, Evidence Sources, etc.)
- Enhanced sidebar navigation with grouped sections (Academic, Engine & R&D, Management)
- Better UI layout for upload page with starter code section side-by-side with main upload
- Assignment Type selection with button-based interface instead of dropdown
- Backend integration for starter code filtering in similarity analysis

### Changed
- Reorganized settings navigation for better user experience
- Updated test expectations to match current evaluation metrics
- Improved error handling and UI consistency

### Fixed
- Duplicate state declarations in upload page
- Test failures due to updated evaluation logic
- Build issues resolved

### Technical Improvements
- Added starter code removal using MVP pipeline
- Enhanced linting and code quality
- Updated dependencies and security checks