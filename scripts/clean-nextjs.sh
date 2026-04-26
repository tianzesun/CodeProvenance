#!/usr/bin/env bash

# =============================================================================
# Next.js Deep Clean Script
# =============================================================================
# A robust, cross-platform shell script to clean Next.js development environment
# Compatible with Bash and Zsh
#
# Features:
#   - Removes .next, node_modules, lock files, and various caches
#   - Dry-run mode to preview deletions
#   - Error handling for locked files/directories
#   - Automatic package manager detection (npm, yarn, pnpm)
#   - Option to reinstall dependencies and run clean build
#
# Usage:
#   ./clean-nextjs.sh [--dry-run] [--no-install] [--help]
#
#   --dry-run   : Show what would be deleted without actually deleting
#   --no-install: Skip the reinstall and build prompt after cleanup
#   --help      : Show this help message
# =============================================================================

set -euo pipefail

# Script metadata
SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# Text formatting (works in both Bash and Zsh)
BOLD=$(tput bold 2>/dev/null || echo '')
RESET=$(tput sgr0 2>/dev/null || echo '')
RED=$(tput setaf 1 2>/dev/null || echo '')
GREEN=$(tput setaf 2 2>/dev/null || echo '')
YELLOW=$(tput setaf 3 2>/dev/null || echo '')
BLUE=$(tput setaf 4 2>/dev/null || echo '')

# Logging functions
log_info() {
    echo "${BLUE}[INFO]${RESET} $*"
}

log_success() {
    echo "${GREEN}[SUCCESS]${RESET} $*"
}

log_warning() {
    echo "${YELLOW}[WARNING]${RESET} $*"
}

log_error() {
    echo "${RED}[ERROR]${RESET} $*" >&2
}

# Default values
DRY_RUN=false
SKIP_INSTALL=false

# Files and directories to clean
CLEAN_ITEMS=(
    ".next"
    "node_modules"
    "package-lock.json"
    "yarn.lock"
    "pnpm-lock.yaml"
    ".eslintcache"
    ".stylelintcache"
    ".turbo"
)

# Package manager detection
DETECTED_PM=""

# =============================================================================
# Helper Functions
# =============================================================================

print_help() {
    # Extract help from script comments
    awk '/^#+=*$/{in_help=1; next} in_help && /^#[[:space:]]*[^#]/ {gsub(/^#[[:space:]]*/, ""); print} in_help && /^#[[:space:]]*$/ {print ""} in_help && /^#[^[:space:]]/ {exit}' "$0" | sed '1,2d;$d'
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Detect package manager based on lock files and available commands
detect_package_manager() {
    # Check for lock files first (most reliable)
    if [[ -f "pnpm-lock.yaml" ]]; then
        DETECTED_PM="pnpm"
    elif [[ -f "yarn.lock" ]]; then
        DETECTED_PM="yarn"
    elif [[ -f "package-lock.json" ]]; then
        DETECTED_PM="npm"
    else
        # Fallback to checking available commands
        if command_exists pnpm; then
            DETECTED_PM="pnpm"
        elif command_exists yarn; then
            DETECTED_PM="yarn"
        elif command_exists npm; then
            DETECTED_PM="npm"
        else
            log_warning "No package manager detected. Please install npm, yarn, or pnpm."
            DETECTED_PM="none"
        fi
    fi
    log_info "Detected package manager: ${DETECTED_PM}"
}

# Perform cleanup (dry-run or actual)
perform_cleanup() {
    local item
    local deleted_count=0
    local error_count=0

    log_info "Starting cleanup process..."

    for item in "${CLEAN_ITEMS[@]}"; do
        if [[ -e "$item" ]]; then
            if [[ "$DRY_RUN" = true ]]; then
                log_info "[DRY-RUN] Would remove: $item"
            else
                if rm -rf "$item" 2>/dev/null; then
                    log_success "Removed: $item"
                    ((deleted_count++))
                else
                    log_error "Failed to remove: $item (might be locked or permission denied)"
                    ((error_count++))
                fi
            fi
        fi
    done

    # Summary
    if [[ "$DRY_RUN" = true ]]; then
        log_info "Dry-run complete. $deleted_count items would be removed."
    else
        log_info "Cleanup complete. $deleted_count items removed, $error_count errors."
        if [[ $error_count -gt 0 ]]; then
            log_warning "Some items could not be removed. You may need to check permissions or close conflicting applications."
        fi
    fi
}

# Reinstall dependencies and run build
reinstall_and_build() {
    log_info "Reinstalling dependencies with $DETECTED_PM..."

    case "$DETECTED_PM" in
        npm)
            if ! npm install; then
                log_error "npm install failed"
                return 1
            fi
            ;;
        yarn)
            if ! yarn install; then
                log_error "yarn install failed"
                return 1
            fi
            ;;
        pnpm)
            if ! pnpm install; then
                log_error "pnpm install failed"
                return 1
            fi
            ;;
        *)
            log_error "Cannot reinstall: no valid package manager detected"
            return 1
            ;;
    esac

    log_info "Running Next.js clean build..."

    case "$DETECTED_PM" in
        npm)
            if ! npm run build; then
                log_error "npm run build failed"
                return 1
            fi
            ;;
        yarn)
            if ! yarn build; then
                log_error "yarn build failed"
                return 1
            fi
            ;;
        pnpm)
            if ! pnpm run build; then
                log_error "pnpm run build failed"
                return 1
            fi
            ;;
        *)
            log_error "Cannot build: no valid package manager detected"
            return 1
            ;;
    esac
}

# =============================================================================
# Main Script
# =============================================================================

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-install)
            SKIP_INSTALL=true
            shift
            ;;
        --help)
            print_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            print_help
            exit 1
            ;;
    esac
done

# Change to project root (where script is located)
cd "$PROJECT_ROOT" || {
    log_error "Cannot change to project root: $PROJECT_ROOT"
    exit 1
}

log_info "Starting Next.js deep clean script"
log_info "Project root: $PROJECT_ROOT"

# Detect package manager before any potential deletion of lock files
detect_package_manager

# Perform cleanup
perform_cleanup

# Offer to reinstall and build
if [[ "$SKIP_INSTALL" = false ]]; then
    if [[ "$DRY_RUN" = true ]]; then
        log_info "[DRY-RUN] Skipping reinstall and build (use without --dry-run to enable)"
    else
        if [[ $DRY_RUN = false ]]; then
            read -rp "Do you want to reinstall dependencies and run a clean build? (y/N): " choice
            case "$choice" in
                [Yy]* )
                    if reinstall_and_build; then
                        log_success "Reinstall and build completed successfully"
                    else
                        log_error "Reinstall and build failed"
                        exit 1
                    fi
                    ;;
                * )
                    log_info "Skipping reinstall and build"
                    ;;
            esac
        fi
    fi
else
    log_info "Skipping reinstall and build as requested (--no-install)"
fi

log_info "Script completed successfully"
exit 0