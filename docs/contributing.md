# Contributing

## Development Setup

```bash
# Clone repository
git clone https://github.com/bdamokos/mobility-db-api.git
cd mobility-db-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mobility_db_api
```

## Documentation

```bash
# Install documentation dependencies
pip install -e ".[docs]"

# Start documentation server
mkdocs serve
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and update documentation
5. Submit pull request

### Commit Messages

Follow the conventional commits specification:

```
type(scope): description

[optional body]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding/updating tests
- `refactor`: Code refactoring

Example:
```
feat(client): add support for direct downloads

- Add direct_download parameter
- Update documentation
- Add tests
```

## Release Process

1. Update version in `pyproject.toml`
2. Update the [changelog](changelog.md)
3. Create release commit
4. Create GitHub release
5. GitHub Actions will publish to PyPI 