#!/bin/bash
#
# STL Processing Pipeline Runner
# Usage: ./run.sh [command]
#
# Commands:
#   analyze   - Only analyze STL files (default)
#   fix       - Analyze and fix thickness issues
#   verify    - Verify assembly fit
#   render    - Generate render comparisons
#   simulate  - Generate assembly simulations
#   hardware  - Verify hardware alignment (screws, PCB)
#   pipeline  - Run complete pipeline
#   all       - Run everything including renders and simulation
#   clean     - Remove all output files
#   shell     - Open shell in container
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Build the Docker image
build() {
    print_header "Building Docker Image"
    docker-compose build stl-analyzer
    print_success "Docker image built successfully"
}

# Run analysis only
analyze() {
    print_header "Analyzing STL Files"
    docker-compose run --rm stl-analyzer
    print_success "Analysis complete. Check output/analysis_report.json"
}

# Run fix
fix() {
    print_header "Fixing Wall Thickness"
    docker-compose run --rm --profile fix stl-fix
    print_success "Fix complete. Check output/fixed/"
}

# Run verification
verify() {
    print_header "Verifying Assembly Fit"
    docker-compose run --rm --profile verify stl-verify
    print_success "Verification complete. Check output/verification_report.json"
}

# Run render
render() {
    print_header "Generating Renders"
    docker-compose run --rm --profile render stl-render
    print_success "Renders complete. Check output/renders/"
}

# Run simulation
simulate() {
    print_header "Generating Assembly Simulation"
    docker-compose run --rm --profile simulate stl-simulate
    print_success "Simulation complete. Check output/simulation/"
}

# Run hardware verification
hardware() {
    print_header "Verifying Hardware Fit"
    docker-compose run --rm --profile hardware stl-hardware-verify
    print_success "Hardware verification complete. Check output/hardware_verification_report.json"
}

# Run complete pipeline
pipeline() {
    print_header "Running Complete Pipeline"
    docker-compose run --rm --profile pipeline stl-pipeline
    print_success "Pipeline complete. Check output/pipeline_report.html"
}

# Run everything
all() {
    build
    pipeline
    render
    simulate
    hardware
    print_header "All Steps Complete"
    echo -e "\nOutput files:"
    echo "  - Analysis:    output/analysis_report.json"
    echo "  - Fixed STLs:  output/fixed/"
    echo "  - Pipeline:    output/pipeline_report.html"
    echo "  - Renders:     output/renders/"
    echo "  - Simulation:  output/simulation/"
    echo "  - Hardware:    output/hardware_verification_report.json"
}

# Clean output
clean() {
    print_header "Cleaning Output"
    rm -rf output/*
    print_success "Output directory cleaned"
}

# Open shell
shell() {
    print_header "Opening Shell in Container"
    docker-compose run --rm stl-analyzer /bin/bash
}

# Show help
help() {
    echo "STL Processing Pipeline"
    echo ""
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  analyze   - Only analyze STL files (default)"
    echo "  fix       - Analyze and fix thickness issues"
    echo "  verify    - Verify assembly fit"
    echo "  render    - Generate render comparisons"
    echo "  simulate  - Generate assembly simulations"
    echo "  hardware  - Verify hardware alignment (screws, PCB)"
    echo "  pipeline  - Run complete pipeline (analyze + fix + verify)"
    echo "  all       - Run everything including renders and simulation"
    echo "  clean     - Remove all output files"
    echo "  shell     - Open shell in container"
    echo "  help      - Show this help"
    echo ""
    echo "Examples:"
    echo "  ./run.sh                  # Run analysis only"
    echo "  ./run.sh pipeline         # Run full pipeline"
    echo "  ./run.sh all              # Run everything"
}

# Main
case "${1:-analyze}" in
    build)
        build
        ;;
    analyze)
        build
        analyze
        ;;
    fix)
        build
        fix
        ;;
    verify)
        build
        verify
        ;;
    render)
        build
        render
        ;;
    simulate)
        build
        simulate
        ;;
    hardware)
        build
        hardware
        ;;
    pipeline)
        build
        pipeline
        ;;
    all)
        all
        ;;
    clean)
        clean
        ;;
    shell)
        build
        shell
        ;;
    help|--help|-h)
        help
        ;;
    *)
        print_error "Unknown command: $1"
        help
        exit 1
        ;;
esac
