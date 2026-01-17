#!/usr/bin/env bash
# ABOUTME: Environment setup script for Illinois Report Card API
# ABOUTME: Installs dependencies, initializes database, and starts the development server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Illinois Report Card API Setup ===${NC}"
echo ""

# Check for Python 3.12+
echo -e "${YELLOW}Checking Python version...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 12 ]); then
        echo -e "${RED}Error: Python 3.12+ required, found $PYTHON_VERSION${NC}"
        exit 1
    fi
    echo -e "${GREEN}Found Python $PYTHON_VERSION${NC}"
else
    echo -e "${RED}Error: Python 3 not found${NC}"
    exit 1
fi

# Check for uv package manager
echo -e "${YELLOW}Checking for uv package manager...${NC}"
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}Installing uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Source the updated PATH
    export PATH="$HOME/.cargo/bin:$PATH"
fi
echo -e "${GREEN}uv is available${NC}"

# Create virtual environment and install dependencies
echo -e "${YELLOW}Setting up virtual environment and installing dependencies...${NC}"
uv venv --python 3.12
uv pip install -e ".[dev]"

echo -e "${GREEN}Dependencies installed${NC}"

# Create data directory if it doesn't exist
echo -e "${YELLOW}Creating data directory...${NC}"
mkdir -p data

# Initialize database if it doesn't exist
echo -e "${YELLOW}Initializing database...${NC}"
if [ ! -f "data/reportcard.db" ]; then
    echo "Database will be created on first run"
else
    echo "Database already exists at data/reportcard.db"
fi

# Set environment variables for development
echo -e "${YELLOW}Setting environment variables...${NC}"
export ENVIRONMENT=development
export DATABASE_URL=sqlite:///./data/reportcard.db

echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "To start the development server:"
echo "  source .venv/bin/activate"
echo "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "Or use Docker:"
echo "  docker-compose up"
echo ""
echo "API will be available at:"
echo "  - API: http://localhost:8000"
echo "  - Swagger UI: http://localhost:8000/docs"
echo "  - OpenAPI JSON: http://localhost:8000/openapi.json"
echo ""
echo "To run tests:"
echo "  source .venv/bin/activate"
echo "  pytest"
echo ""
echo "To run tests with coverage:"
echo "  pytest --cov=app --cov-report=term-missing"
echo ""
