# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2024-12-23

### Added
- New bulk deletion methods:
  - `delete_provider_datasets()`: Delete all datasets for a specific provider
  - `delete_all_datasets()`: Delete all downloaded datasets across all providers
- Smart directory cleanup:
  - Automatic removal of empty provider directories
  - Preservation of custom files and directories
  - Safe cleanup that only removes dataset-related content

### Changed
- Enhanced `delete_dataset()` method to handle provider directory cleanup
- Improved logging for deletion operations

### Developer Changes
- Added comprehensive tests for directory cleanup behavior
- Added tests for bulk deletion operations
- Updated documentation with new deletion methods and examples

## [0.1.1] - Initial Release - 2024-12-22

### Added
- Basic GTFS Schedule dataset management functionality
- Provider search by country and name
- Dataset download and extraction
- Metadata tracking
- Environment variable support
- Progress tracking for downloads
- Feed validity period detection 