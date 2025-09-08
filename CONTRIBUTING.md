# Contributing to DLNA Streamer

Thank you for your interest in contributing to DLNA Streamer! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites
- Python 3.8 or higher
- macOS (primary development platform)
- Git

### Development Setup
1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/yourusername/dlna-streamer.git
   cd dlna-streamer
   ```
3. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Code Style

### Python Style Guidelines
- Follow PEP 8 style guidelines
- Use type hints for all function parameters and return values
- Write comprehensive docstrings for all public functions and classes
- Keep functions focused and single-purpose

### Code Formatting
We use Black for code formatting:
```bash
black dlna_streamer/ bin/
```

### Linting
We use flake8 for linting:
```bash
flake8 dlna_streamer/ bin/
```

### Type Checking
We use mypy for type checking:
```bash
mypy dlna_streamer/
```

## Testing

### Running Tests
```bash
pytest
```

### Test Coverage
```bash
pytest --cov=dlna_streamer
```

## Submitting Changes

### Pull Request Process
1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes following the code style guidelines
3. Add tests for new functionality
4. Ensure all tests pass
5. Update documentation as needed
6. Commit your changes with clear, descriptive commit messages
7. Push your branch to your fork
8. Create a pull request on GitHub

### Commit Message Format
Use clear, descriptive commit messages:
```
Add subtitle support for external SRT files

- Implement SRT file detection and parsing
- Add GUI controls for subtitle selection
- Update documentation with subtitle usage examples
```

### Pull Request Guidelines
- Provide a clear description of changes
- Reference any related issues
- Include screenshots for GUI changes
- Ensure CI checks pass

## Areas for Contribution

### High Priority
- **Testing**: Add comprehensive unit and integration tests
- **Error Handling**: Improve error handling and user feedback
- **Documentation**: Enhance API documentation and user guides
- **Performance**: Optimize streaming performance and memory usage

### Medium Priority
- **Platform Support**: Add support for Windows and Linux
- **Additional Formats**: Support more video/audio formats
- **Advanced Features**: Add playlist support, queue management
- **Configuration**: Add configuration file support

### Low Priority
- **UI Improvements**: Enhance GUI design and usability
- **CLI Enhancements**: Add more command-line options
- **Logging**: Implement comprehensive logging system
- **Plugin System**: Design extensible plugin architecture

## Reporting Issues

### Bug Reports
When reporting bugs, please include:
- Operating system and version
- Python version
- Steps to reproduce the issue
- Expected vs actual behavior
- Error messages or logs

### Feature Requests
For feature requests, please include:
- Clear description of the feature
- Use case and motivation
- Proposed implementation approach (if applicable)

## Code of Conduct

### Our Pledge
We are committed to providing a welcoming and inclusive environment for all contributors.

### Expected Behavior
- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards other community members

### Unacceptable Behavior
- Harassment, trolling, or inflammatory comments
- Personal attacks or political discussions
- Public or private harassment
- Publishing private information without permission

## License

By contributing to DLNA Streamer, you agree that your contributions will be licensed under the MIT License.

## Questions?

If you have questions about contributing, please:
- Open an issue on GitHub
- Check existing documentation
- Review closed issues and pull requests for similar questions

Thank you for contributing to DLNA Streamer! 🎉
