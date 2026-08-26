#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TOOLS_DIR="$REPO_ROOT/tools"
DOWNLOAD_DIR="$TOOLS_DIR/.downloads"

JPLAG_URL="https://github.com/jplag/JPlag/releases/download/v4.3.0/jplag-4.3.0-jar-with-dependencies.jar"
PMD_URL="https://github.com/pmd/pmd/releases/download/pmd_releases%2F6.55.0/pmd-bin-6.55.0.zip"
OPENTXL_URL="https://github.com/CordyJ/OpenTxl/releases/download/v11.3.7/opentxl-11.3.7-linux-x64.tar.gz"
NICAD_URL="https://github.com/CordyJ/Open-NiCad/releases/download/v7.0.1/nicad-7.0.1-linux-x86_64.tar.gz"

mkdir -p "$TOOLS_DIR" "$DOWNLOAD_DIR"

info() {
    printf '\n==> %s\n' "$1"
}

ok() {
    printf '    OK: %s\n' "$1"
}

warn() {
    printf '    WARN: %s\n' "$1"
}

fail() {
    printf '    ERROR: %s\n' "$1" >&2
    exit 1
}

need_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        fail "Missing required command: $1"
    fi
}

download() {
    local url="$1"
    local output="$2"

    if [ -s "$output" ]; then
        ok "Using cached $(basename "$output")"
        return
    fi

    if command -v curl >/dev/null 2>&1; then
        curl -fL --retry 3 --retry-delay 2 "$url" -o "$output"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$output" "$url"
    else
        fail "Install curl or wget before running this script."
    fi
}

install_jplag() {
    info "Installing JPlag"
    need_command java

    mkdir -p "$TOOLS_DIR/JPlag"
    if [ -s "$TOOLS_DIR/JPlag/jplag.jar" ]; then
        ok "JPlag already installed at tools/JPlag/jplag.jar"
        return
    fi

    if [ -s "$TOOLS_DIR/external/jplag/jplag.jar" ]; then
        cp "$TOOLS_DIR/external/jplag/jplag.jar" "$TOOLS_DIR/JPlag/jplag.jar"
        ok "Copied existing JPlag jar from tools/external/jplag"
        return
    fi

    download "$JPLAG_URL" "$DOWNLOAD_DIR/jplag.jar"
    cp "$DOWNLOAD_DIR/jplag.jar" "$TOOLS_DIR/JPlag/jplag.jar"
    ok "JPlag installed at tools/JPlag/jplag.jar"
}

install_pmd() {
    info "Installing PMD CPD"
    need_command java
    need_command unzip

    if [ -x "$TOOLS_DIR/pmd/bin/pmd" ]; then
        write_pmd_wrapper
        ok "PMD already installed at tools/pmd/bin/pmd"
        return
    fi

    rm -rf "$TOOLS_DIR/pmd" "$DOWNLOAD_DIR/pmd-bin-6.55.0"
    download "$PMD_URL" "$DOWNLOAD_DIR/pmd-bin-6.55.0.zip"
    unzip -q "$DOWNLOAD_DIR/pmd-bin-6.55.0.zip" -d "$DOWNLOAD_DIR"
    mv "$DOWNLOAD_DIR/pmd-bin-6.55.0" "$TOOLS_DIR/pmd"
    chmod +x "$TOOLS_DIR/pmd/bin/run.sh"
    write_pmd_wrapper
    ok "PMD installed at tools/pmd/bin/pmd"
}

write_pmd_wrapper() {
    cat > "$TOOLS_DIR/pmd/bin/pmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "${1:-}" = "cpd" ]; then
    command_args=("cpd")
    shift
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --no-fail-on-error)
                shift
                ;;
            --no-fail-on-violation)
                command_args+=("--fail-on-violation" "false")
                shift
                ;;
            --language|--minimum-tokens|--format|--encoding|--exclude|--filelist|--file-list|--files|--dir|--uri)
                command_args+=("$1" "$2")
                shift 2
                ;;
            --*)
                command_args+=("$1")
                shift
                ;;
            *)
                command_args+=("--dir" "$1")
                shift
                ;;
        esac
    done
    exec "$DIR/run.sh" "${command_args[@]}"
fi

exec "$DIR/run.sh" "$@"
EOF
    chmod +x "$TOOLS_DIR/pmd/bin/pmd"
}

install_dolos() {
    info "Installing Dolos"
    need_command node
    need_command npm

    mkdir -p "$TOOLS_DIR/dolos-cli"
    if [ -x "$TOOLS_DIR/dolos-cli/node_modules/.bin/dolos" ]; then
        ok "Dolos already installed at tools/dolos-cli/node_modules/.bin/dolos"
        return
    fi

    (
        cd "$TOOLS_DIR/dolos-cli"
        if [ ! -f package.json ]; then
            npm init -y >/dev/null
        fi
        CXXFLAGS="${CXXFLAGS:-} -std=c++20" npm install @dodona/dolos
    )
    ok "Dolos installed at tools/dolos-cli/node_modules/.bin/dolos"
}

install_opentxl() {
    info "Installing OpenTxl compatibility path"
    need_command tar

    if [ -x "$TOOLS_DIR/freetxl/current/bin/txl" ]; then
        ok "TXL already available at tools/freetxl/current/bin/txl"
        return
    fi

    local tmp_dir
    tmp_dir="$(mktemp -d)"
    download "$OPENTXL_URL" "$DOWNLOAD_DIR/opentxl-11.3.7-linux-x64.tar.gz"
    tar -xzf "$DOWNLOAD_DIR/opentxl-11.3.7-linux-x64.tar.gz" -C "$tmp_dir"

    local txl_path
    txl_path="$(find "$tmp_dir" -type f -name txl -print -quit)"
    if [ -z "$txl_path" ]; then
        rm -rf "$tmp_dir"
        fail "OpenTxl archive did not contain a txl binary."
    fi

    rm -rf "$TOOLS_DIR/freetxl"
    mkdir -p "$TOOLS_DIR/freetxl/current/bin"
    cp "$txl_path" "$TOOLS_DIR/freetxl/current/bin/txl"
    chmod +x "$TOOLS_DIR/freetxl/current/bin/txl"
    rm -rf "$tmp_dir"
    ok "OpenTxl installed at tools/freetxl/current/bin/txl"
}

install_nicad() {
    info "Installing NiCad"
    need_command tar

    if [ -x "$TOOLS_DIR/NiCad-6.2/nicad6" ]; then
        ok "NiCad compatibility launcher already installed at tools/NiCad-6.2/nicad6"
        return
    fi

    local tmp_dir nicad_bin nicad_root
    tmp_dir="$(mktemp -d)"
    download "$NICAD_URL" "$DOWNLOAD_DIR/nicad-7.0.1-linux-x86_64.tar.gz"
    tar -xzf "$DOWNLOAD_DIR/nicad-7.0.1-linux-x86_64.tar.gz" -C "$tmp_dir"

    nicad_bin="$(find "$tmp_dir" -type f -path '*/bin/nicad' -print -quit)"
    if [ -z "$nicad_bin" ]; then
        rm -rf "$tmp_dir"
        fail "NiCad archive did not contain bin/nicad."
    fi

    nicad_root="$(cd "$(dirname "$nicad_bin")/.." && pwd)"
    rm -rf "$TOOLS_DIR/NiCad-6.2"
    mkdir -p "$TOOLS_DIR/NiCad-6.2"
    cp -a "$nicad_root"/. "$TOOLS_DIR/NiCad-6.2"/
    chmod +x "$TOOLS_DIR/NiCad-6.2/bin/nicad"

    cat > "$TOOLS_DIR/NiCad-6.2/nicad6" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/bin/nicad" "$@"
EOF
    chmod +x "$TOOLS_DIR/NiCad-6.2/nicad6"
    rm -rf "$tmp_dir"
    ok "NiCad installed at tools/NiCad-6.2 with nicad6 compatibility launcher"
}

install_moss() {
    info "Checking MOSS"
    need_command perl

    mkdir -p "$TOOLS_DIR/moss"
    if [ -s "$TOOLS_DIR/moss/moss.pl" ]; then
        chmod +x "$TOOLS_DIR/moss/moss.pl"
        ok "MOSS script found at tools/moss/moss.pl"
    elif [ -n "${MOSS_PL_PATH:-}" ] && [ -s "$MOSS_PL_PATH" ]; then
        cp "$MOSS_PL_PATH" "$TOOLS_DIR/moss/moss.pl"
        chmod +x "$TOOLS_DIR/moss/moss.pl"
        ok "Copied MOSS script from MOSS_PL_PATH"
    elif [ -n "${MOSS_PL_URL:-}" ]; then
        download "$MOSS_PL_URL" "$TOOLS_DIR/moss/moss.pl"
        chmod +x "$TOOLS_DIR/moss/moss.pl"
        ok "Downloaded MOSS script from MOSS_PL_URL"
    else
        warn "MOSS cannot be auto-installed without Stanford's moss.pl."
        warn "Put it at tools/moss/moss.pl or run with MOSS_PL_PATH=/path/to/moss.pl."
    fi

    if [ -z "${MOSS_USER_ID:-}" ]; then
        warn "MOSS_USER_ID is not set in this shell. Add it to src/backend/.env.local before benchmarking MOSS."
    else
        ok "MOSS_USER_ID is set in this shell"
    fi
}

verify() {
    info "Verifying benchmark tool availability"
    if [ -d "$REPO_ROOT/venv" ]; then
        # shellcheck disable=SC1091
        source "$REPO_ROOT/venv/bin/activate"
    fi

    python3 - <<'PY'
from src.backend.api.server import _list_benchmark_tools

wanted = {"integritydesk", "moss", "jplag", "dolos", "nicad", "pmd", "ac"}
for tool in _list_benchmark_tools():
    if tool["id"] in wanted:
        print(f"{tool['id']}: runnable={tool['runnable']} status={tool['status']}")
PY
}

main() {
    echo "=================================================="
    echo " IntegrityDesk Benchmark Tools Installer"
    echo "=================================================="
    echo "Repo root:  $REPO_ROOT"
    echo "Tools dir:  $TOOLS_DIR"

    install_jplag
    install_pmd
    install_dolos
    install_opentxl
    install_nicad
    install_moss
    verify

    echo
    echo "Installation complete."
}

main "$@"
