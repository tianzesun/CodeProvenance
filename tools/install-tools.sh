#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=================================================="
echo " IntegrityDesk Benchmark Tools Installer"
echo "=================================================="
echo

mkdir -p tools
cd tools

echo "✅ Installing JPlag..."
if [ ! -f JPlag/jplag.jar ]; then
    mkdir -p JPlag
    cd JPlag
    wget -q https://github.com/jplag/JPlag/releases/download/v4.3.0/jplag-4.3.0-jar-with-dependencies.jar -O jplag.jar
    cd ..
    echo "   JPlag installed successfully"
else
    echo "   JPlag already installed"
fi

echo
echo "✅ Installing PMD CPD..."
if [ ! -f pmd/bin/pmd ]; then
    wget -q https://github.com/pmd/pmd/releases/download/pmd_releases%2F6.55.0/pmd-bin-6.55.0.zip
    unzip -q pmd-bin-6.55.0.zip
    rm pmd-bin-6.55.0.zip
    mv pmd-bin-6.55.0 pmd
    echo "   PMD CPD installed successfully"
else
    echo "   PMD CPD already installed"
fi

echo
echo "✅ Installing SIM..."
if [ ! -f sim/sim ]; then
    mkdir -p sim
    cd sim
    wget -q https://www.dickgrune.com/Programs/similarity_tester/src/sim-3.0.2.tar.gz
    tar xzf sim-3.0.2.tar.gz --strip-components=1
    rm sim-3.0.2.tar.gz
    make > /dev/null 2>&1
    cd ..
    echo "   SIM installed successfully"
else
    echo "   SIM already installed"
fi

echo
echo "✅ Installing Dolos..."
if [ ! -d dolos-cli/node_modules ]; then
    mkdir -p dolos-cli
    cd dolos-cli
    npm init -y > /dev/null
    npm install @dodona/dolos > /dev/null 2>&1
    cd ..
    echo "   Dolos installed successfully"
else
    echo "   Dolos already installed"
fi

echo
echo "✅ Installing NiCad 6.2..."
if [ ! -f NiCad-6.2/nicad6 ]; then
    wget -q https://www.txl.ca/nicaddownload/NiCad-6.2.tar.gz
    tar xzf NiCad-6.2.tar.gz
    rm NiCad-6.2.tar.gz
    cd NiCad-6.2
    make > /dev/null 2>&1
    cd ..
    echo "   NiCad installed successfully"
else
    echo "   NiCad already installed"
fi

echo
echo "✅ Installing Sherlock..."
if [ ! -f sherlock/sherlock ]; then
    mkdir -p sherlock
    cd sherlock
    wget -q https://www.cs.auckland.ac.nz/~mcw/Research/Resources/sherlock/sherlock-2.1.tar.gz
    tar xzf sherlock-2.1.tar.gz --strip-components=1
    rm sherlock-2.1.tar.gz
    make > /dev/null 2>&1
    cd ..
    echo "   Sherlock installed successfully"
else
    echo "   Sherlock already installed"
fi

echo
echo "=================================================="
echo " Installation complete!"
echo "=================================================="
echo
echo "The following tools are now installed:"
echo "  ✅ JPlag 4.3.0"
echo "  ✅ PMD CPD 6.55.0"
echo "  ✅ SIM 3.0.2"
echo "  ✅ Dolos (latest)"
echo "  ✅ NiCad 6.2"
echo "  ✅ Sherlock 2.1"
echo
echo "Run the following command to verify:"
echo "  source venv/bin/activate && python3 -c \"from src.backend.api.server import _list_benchmark_tools; print([t['id'] for t in _list_benchmark_tools() if t['runnable']])\""
echo
