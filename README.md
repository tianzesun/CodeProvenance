# CodeProvenance

A System for Detecting Software Similarity

## Overview

CodeProvenance is a backend service designed to detect software similarity between code submissions, similar to MIT's MOSS (Measure of Software Similarity) system. This service operates as a background processing component that can be integrated into grading platforms to help educators identify potential code plagiarism or similarity across student submissions.

## Key Features

- **Submission Comparison**: Analyzes and compares code submissions within a class to detect similarities
- **Background Service**: Runs as a non-GUI backend service, designed to be consumed by external grading platforms
- **RESTful API**: Provides programmatic interface for integration with other systems
- **Scalable Architecture**: Can handle multiple comparison requests concurrently

## Usage

The service accepts a folder containing all student submissions and returns similarity analysis results. It is designed to be called by other platforms rather than used directly by end users.

### Typical Workflow

1. Upload a folder containing all submissions to compare
2. The service processes and analyzes the code files
3. Receive similarity reports or scores for each submission pair

## Integration

CodeProvenance is not a standalone application with a GUI or web interface. It is intended to be integrated as a backend service component within larger grading or learning management systems.

## API

The service provides endpoints for:
- Submitting code folders for comparison
- Retrieving similarity analysis results
- Managing service configuration

## License

[License information]
