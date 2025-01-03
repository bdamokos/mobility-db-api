from pathlib import Path
from typing import Tuple, Optional
import csv
from logging import getLogger

logger = getLogger(__name__)

def calculate_bounding_box(gtfs_dir: Path) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Calculate the bounding box from stops.txt in a GTFS directory.
    
    Args:
        gtfs_dir: Path to the GTFS directory containing stops.txt
        
    Returns:
        Tuple of (minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude)
        Returns (None, None, None, None) if coordinates cannot be extracted
        
    Note:
        According to GTFS specification, stop_lat and stop_lon are required fields in stops.txt
        However, we handle cases where they might be missing or invalid gracefully.
    """
    stops_file = gtfs_dir / "stops.txt"
    
    if not stops_file.exists():
        logger.warning(f"stops.txt not found in {gtfs_dir}")
        return None, None, None, None
        
    try:
        min_lat = float('inf')
        max_lat = float('-inf')
        min_lon = float('inf')
        max_lon = float('-inf')
        
        coordinates_found = False
        
        with open(stops_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            
            if 'stop_lat' not in reader.fieldnames or 'stop_lon' not in reader.fieldnames:
                logger.warning("stops.txt missing required fields stop_lat and/or stop_lon")
                return None, None, None, None
            
            for row in reader:
                try:
                    # Skip rows with missing values
                    if not row.get('stop_lat') or not row.get('stop_lon'):
                        continue
                        
                    lat = float(row['stop_lat'])
                    lon = float(row['stop_lon'])
                    
                    # Basic coordinate validation
                    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                        logger.warning(f"Invalid coordinates found: lat={lat}, lon={lon}")
                        continue
                    
                    min_lat = min(min_lat, lat)
                    max_lat = max(max_lat, lat)
                    min_lon = min(min_lon, lon)
                    max_lon = max(max_lon, lon)
                    coordinates_found = True
                    
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error processing coordinates in row: {e}")
                    continue
        
        if not coordinates_found:
            logger.warning("No valid coordinates found in stops.txt")
            return None, None, None, None
            
        return min_lat, max_lat, min_lon, max_lon
        
    except Exception as e:
        logger.error(f"Error processing stops.txt: {e}")
        return None, None, None, None 