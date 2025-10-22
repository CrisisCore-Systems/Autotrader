"""Basic test for experiments API endpoints."""

from pathlib import Path


def test_experiments_routes_structure():
    """Test that experiments routes file has correct structure."""
    routes_file = Path("src/api/routes/experiments.py")
    assert routes_file.exists(), "Experiments routes file should exist"
    
    content = routes_file.read_text()
    
    # Check for essential imports
    assert "from fastapi import APIRouter" in content
    assert "from src.utils.experiment_tracker import" in content
    
    # Check for router creation
    assert 'router = APIRouter(prefix="/experiments"' in content
    
    # Check for essential endpoints
    assert '@router.get("/", response_model=' in content or '@router.get("/",' in content
    assert '@router.get("/{config_hash}", response_model=' in content
    assert '@router.get("/{config_hash}/metrics")' in content
    assert '@router.get("/{config_hash}/tree")' in content
    assert '@router.get("/compare/{hash1}/{hash2}", response_model=' in content
    assert '@router.post("/export")' in content
    assert '@router.delete("/{config_hash}")' in content
    
    print("✓ Experiments routes structure is correct")


def test_api_integration():
    """Test that experiments router is integrated into main API."""
    main_file = Path("src/api/main.py")
    assert main_file.exists(), "Main API file should exist"
    
    content = main_file.read_text()
    
    # Check for experiments router import
    assert "from .routes.experiments import router as experiments_router" in content
    
    # Check for router inclusion
    assert "app.include_router(experiments_router" in content
    
    print("✓ Experiments router is integrated into main API")


def test_dashboard_api_integration():
    """Test that experiments router is integrated into dashboard API."""
    dashboard_api_file = Path("src/api/dashboard_api.py")
    assert dashboard_api_file.exists(), "Dashboard API file should exist"
    
    content = dashboard_api_file.read_text()
    
    # Check for experiments router import
    assert "from src.api.routes.experiments import router as experiments_router" in content
    
    # Check for router inclusion
    assert "app.include_router(experiments_router" in content
    
    print("✓ Experiments router is integrated into dashboard API")


def test_frontend_types():
    """Test that frontend types are defined."""
    types_file = Path("dashboard/src/types.ts")
    assert types_file.exists(), "Types file should exist"
    
    content = types_file.read_text()
    
    # Check for experiment types
    assert "ExperimentSummary" in content
    assert "ExperimentConfig" in content
    assert "ExperimentMetrics" in content
    assert "ExperimentDetail" in content
    assert "ExperimentComparison" in content
    
    print("✓ Frontend types are defined")


def test_frontend_api_functions():
    """Test that frontend API functions are defined."""
    api_file = Path("dashboard/src/api.ts")
    assert api_file.exists(), "API file should exist"
    
    content = api_file.read_text()
    
    # Check for experiment API functions
    assert "fetchExperiments" in content
    assert "fetchExperimentDetail" in content
    assert "fetchExperimentMetrics" in content
    assert "fetchExecutionTree" in content
    assert "compareExperiments" in content
    assert "exportExperiment" in content
    assert "deleteExperiment" in content
    
    print("✓ Frontend API functions are defined")


def test_frontend_components():
    """Test that frontend components exist."""
    components = [
        "ExperimentsRegistry.tsx",
        "ExperimentDetail.tsx",
        "ExperimentCompare.tsx",
        "ExperimentsWorkspace.tsx",
    ]
    
    components_dir = Path("dashboard/src/components")
    
    for component in components:
        component_file = components_dir / component
        assert component_file.exists(), f"{component} should exist"
        
        # Check for corresponding CSS file
        css_file = components_dir / component.replace(".tsx", ".css")
        assert css_file.exists(), f"{component.replace('.tsx', '.css')} should exist"
    
    print("✓ All frontend components exist")


def test_data_directories():
    """Test that data directories exist."""
    directories = [
        Path("backtest_results"),
        Path("execution_trees"),
        Path("exports"),
    ]
    
    for directory in directories:
        assert directory.exists(), f"{directory} should exist"
        assert directory.is_dir(), f"{directory} should be a directory"
        
        # Check for .gitkeep
        gitkeep = directory / ".gitkeep"
        assert gitkeep.exists(), f"{directory}/.gitkeep should exist"
    
    print("✓ All data directories exist with .gitkeep files")


def test_gitignore_configuration():
    """Test that .gitignore is properly configured."""
    gitignore_file = Path(".gitignore")
    assert gitignore_file.exists(), ".gitignore should exist"
    
    content = gitignore_file.read_text()
    
    # Check for experiment data patterns
    assert "backtest_results/*.json" in content
    assert "execution_trees/*.json" in content
    assert "exports/*" in content
    assert "!backtest_results/.gitkeep" in content
    assert "!execution_trees/.gitkeep" in content
    assert "!exports/.gitkeep" in content
    
    print("✓ .gitignore is properly configured")


if __name__ == "__main__":
    # Run tests
    test_experiments_routes_structure()
    test_api_integration()
    test_dashboard_api_integration()
    test_frontend_types()
    test_frontend_api_functions()
    test_frontend_components()
    test_data_directories()
    test_gitignore_configuration()
    
    print("\n✅ All tests passed!")
