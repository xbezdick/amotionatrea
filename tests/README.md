# Amotion Atrea Integration Tests

This directory contains comprehensive tests for the Amotion Atrea Home Assistant integration.

## Test Structure

- `test_websocket.py` - Tests for websocket connection and message handling
- `test_init.py` - Tests for the main integration module (AmotionAtrea class and coordinator)
- `test_climate.py` - Tests for climate entity functionality
- `test_sensor.py` - Tests for sensor entity functionality  
- `test_config_flow.py` - Tests for configuration flow
- `conftest.py` - Common fixtures and test configuration

## Running Tests

### Prerequisites

Install test dependencies:

```bash
pip install -r tests/requirements_test.txt
```

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test File

```bash
pytest tests/test_websocket.py
pytest tests/test_init.py
pytest tests/test_climate.py
pytest tests/test_sensor.py
pytest tests/test_config_flow.py
```

### Run with Coverage

```bash
pytest tests/ --cov=custom_components/amotionatrea --cov-report=html
```

### Run Specific Test

```bash
pytest tests/test_websocket.py::TestAtreaWebsocket::test_initialization
```

### Run Tests Verbosely

```bash
pytest tests/ -v
```

### Run Tests with Logging

```bash
pytest tests/ -v -s --log-cli-level=DEBUG
```

## Test Coverage

The tests cover:

- **Websocket Module**: Connection handling, message sending/receiving, error handling
- **Integration Module**: AmotionAtrea class initialization, state updates, API calls
- **Climate Module**: Temperature control, HVAC modes, fan modes, device info
- **Sensor Module**: Sensor entity creation, value retrieval, date formatting
- **Config Flow**: User input validation, connection testing, authentication, migration

## Writing New Tests

When adding new tests:

1. Create a test file following the naming convention `test_<module>.py`
2. Use pytest fixtures for common setup
3. Mock external dependencies (websockets, API calls)
4. Test both success and failure scenarios
5. Use async/await for async functions
6. Follow the existing test structure and naming conventions

## Async Tests

All async tests use pytest-asyncio. Tests are marked with `@pytest.mark.asyncio`.

```python
@pytest.mark.asyncio
async def test_async_function():
    # Your async test code
    pass
```

## Mocking

The tests extensively use unittest.mock to isolate the integration from external dependencies:

- Mock Home Assistant instances
- Mock websocket connections
- Mock API responses
- Mock async methods

## CI/CD Integration

Tests can be integrated into CI/CD pipelines using:

```yaml
- name: Run tests
  run: pytest tests/ --cov=custom_components/amotionatrea --cov-report=xml
```
