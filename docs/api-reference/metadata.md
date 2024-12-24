# API Reference: Metadata

## Metadata Structure

The metadata is stored in JSON format with the following structure:

```json
{
    "dataset_id": {
        "provider_id": "string",
        "provider_name": "string",
        "dataset_id": "string",
        "download_date": "string (ISO format)",
        "source_url": "string",
        "is_direct_source": "boolean",
        "api_provided_hash": "string (optional)",
        "file_hash": "string (SHA-256)",
        "download_path": "string (relative path)",
        "feed_start_date": "string (optional)",
        "feed_end_date": "string (optional)"
    }
}
```

## DatasetMetadata Class

```python
@dataclass
class DatasetMetadata:
    """Metadata for a downloaded GTFS dataset"""
    provider_id: str
    provider_name: str
    dataset_id: str
    download_date: datetime
    source_url: str
    is_direct_source: bool
    api_provided_hash: Optional[str]
    file_hash: str
    download_path: Path
    feed_start_date: Optional[str] = None
    feed_end_date: Optional[str] = None
```

## MetadataLock Class

```python
class MetadataLock:
    """Context manager for safely reading/writing metadata file"""
    def __init__(self, metadata_file: Path, mode: str):
        self.file = open(metadata_file, mode)
        self.mode = mode
    
    def __enter__(self):
        # Use exclusive lock for writing, shared lock for reading
        fcntl.flock(self.file.fileno(), 
                   fcntl.LOCK_EX if 'w' in self.mode else fcntl.LOCK_SH)
        return self.file
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()
```

## Usage Examples

### Reading Metadata

```python
from mobility_db_api import MobilityAPI

api = MobilityAPI()

# List all downloaded datasets
datasets = api.list_downloaded_datasets()
for dataset in datasets:
    print(f"\nDataset: {dataset.dataset_id}")
    print(f"Provider: {dataset.provider_name}")
    print(f"Downloaded: {dataset.download_date}")
    print(f"Path: {dataset.download_path}")
```

### Metadata Management

```python
from mobility_db_api import MobilityAPI

api = MobilityAPI()

# Force metadata reload
api.reload_metadata(force=True)

# Check if metadata needs reload
if api.ensure_metadata_current():
    print("Metadata was reloaded")
else:
    print("Metadata is current")
```

## Implementation Details

### File Structure

- Default metadata file: `data/datasets_metadata.json`
- Each download directory can have its own metadata file
- Lock files use `.lock` extension

### Thread Safety

The metadata handler ensures thread safety through:

1. File locking during read/write operations:
   - Shared locks for reading (multiple readers allowed)
   - Exclusive locks for writing (one writer at a time)
2. Atomic write operations
3. Lock file cleanup on process exit

### Process Safety

Cross-process safety is achieved by:

1. Using file system locks (fcntl)
2. Handling stale locks
3. Implementing lock timeouts

### Error Handling

```python
from mobility_db_api import MobilityAPI
import json

api = MobilityAPI()

try:
    # Force metadata reload
    api.reload_metadata(force=True)
except json.JSONDecodeError as e:
    print(f"Corrupted metadata file: {e}")
except OSError as e:
    print(f"File system error: {e}")
``` 