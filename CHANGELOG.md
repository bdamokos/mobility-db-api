# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2025-01-03
### Added
- Bounding box calculation from stops.txt for direct source GTFS files
- Support for bounding box information from CSV catalog and API
- Graceful handling of missing or invalid coordinates in stops.txt
- New `force_bounding_box_calculation` flag to force recalculation of bounding box from stops.txt
- Automatic fallback to stops.txt calculation when bounding box is missing from API/CSV

### Changed
- Enhanced bounding box handling with clear calculation priority
- Improved logging for bounding box calculation sources
- Better error handling for coordinate validation

## [0.5.0b0] - 2025-01-01
### Added
- External GTFS support:
  - New `ExternalGTFSAPI` class for handling GTFS files not in Mobility Database
  - Automatic provider ID generation with `ext-` prefix
  - Agency name extraction from agency.txt
  - Smart file matching based on content hash
  - Support for multiple agencies in a single feed
  - Versioning support with automatic cleanup of old datasets
### Changed
- The saved metadata now contains the geographical bounding boxes of the dataset from Mobility Database. It is not implemented yet for external GTFS feeds and downloads from the CSV catalogue.

## [0.4.2] - 2024-12-30
### Fixed
- Removed redundant metadata saving when using custom download directory
### Added
- IOError handling for downloads and .zip extractions

## [0.4.1] - 2024-12-28
### Added
- New `get_provider_by_id()` method that follows the naming convention of other provider search methods

### Changed
- Enhanced `get_provider_info()` to be the central provider search implementation:
  - Now accepts optional search parameters: `provider_id`, `country_code`, and `name`
  - Returns either a single provider (when searching by ID) or a list of providers (when searching by country or name)
  - Powers all other provider search methods internally for better consistency
  - Improved error handling and CSV fallback behavior

## [0.4.0] - 2024-12-27

### Added
- Enhanced provider information retrieval:
  - New `get_provider_info()` method in both API and CSV modes
  - Combines live provider data with downloaded dataset information
  - Automatic fallback to CSV catalog on API errors
  - Comprehensive metadata about downloaded datasets
- CSV catalog fallback functionality ([#5](https://github.com/bdamokos/mobility-db-api/issues/5)):
  - Automatic fallback to CSV catalog when API key is not available
  - Optional `force_csv_mode` to always use CSV catalog
  - Lazy initialization of CSV catalog to improve performance
  - ID normalization for consistent provider lookup
- Improved error handling:
  - Graceful handling of 413 (Request Entity Too Large) errors
  - Automatic fallback to CSV mode on authentication errors
  - Better token handling with empty headers when no token is available
  - Robust handling of CSV network errors with fallback to cached data
  - Proper handling of empty metadata files during concurrent access

### Changed
- Made CSV catalog initialization lazy to reduce unnecessary directory creation
- Improved token handling to return `None` instead of raising errors
- Enhanced error messages and logging for better debugging
- Improved file locking mechanism:
  - Fixed handling of file modes for concurrent access
  - Added proper file existence checks before opening
  - Enhanced empty file handling during metadata operations

### Developer Changes
- Added comprehensive tests for provider information retrieval
- Added tests for CSV catalog functionality
- Added tests for ID normalization and conversion
- Added tests for lazy initialization behavior
- Added tests for CSV network error scenarios
- Added tests for concurrent file access edge cases
- Updated documentation with CSV fallback examples and API reference

## [0.3.0] - 2024-12-24

### Added
- Comprehensive documentation site at https://bdamokos.github.io/mobility-db-api/
- Thread-safe and process-safe metadata handling:
  - File locking for concurrent metadata access
  - Shared locks for reading (multiple readers allowed)
  - Exclusive locks for writing (one writer at a time)
  - Automatic metadata merging for concurrent writes
- Metadata change detection:
  - Automatic detection of external changes to metadata file
  - `reload_metadata()` method to manually reload metadata
  - `ensure_metadata_current()` method to check and reload if needed
- Improved error handling:
  - Graceful handling of corrupted metadata files
  - Proper cleanup of file locks
  - Informative error logging

### Changed
- Made API instances fully independent:
  - Each instance can have its own data directory
  - Separate logger instances for better debugging
  - Safe concurrent access to shared data directories
- Fixed metadata change detection in multi-process scenarios

### Developer Changes
- Added automated test issue management
- Added comprehensive test suite for concurrent operations
- Improved GitHub Actions security with explicit permissions
- Added documentation testing and validation workflows

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