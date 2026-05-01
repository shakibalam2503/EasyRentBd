import mysql.connector
import os
import logging
from typing import Dict, List, Optional, Any
import json
from mysql.connector import Error
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database manager for property management system with Rasa integration"""
    
    def __init__(self):
        # Load environment variables with fallback defaults
        self.host = os.getenv('DB_HOST', 'localhost')
        self.user = os.getenv('DB_USER', 'root')
        self.password = os.getenv('DB_PASSWORD', '')
        self.database = os.getenv('DB_NAME', 'propertymanagement')
        self.connection = None
        
        # Debug: Log database configuration
        logger.info(f"Database config - Host: {self.host}, User: {self.user}, Database: {self.database}")
        
        # Ensure we have proper defaults if env vars are None
        if self.host is None:
            self.host = 'localhost'
        if self.user is None:
            self.user = 'root'
        if self.password is None:
            self.password = ''
        if self.database is None:
            self.database = 'propertymanagement'
        
    def connect(self):
        """Establish database connection"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                autocommit=True
            )
            logger.info("Database connection established successfully")
            return True
        except Error as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("Database connection closed")
    
    def test_connection(self) -> Dict[str, Any]:
        """Test database connection and return status with sample data"""
        try:
            if not self.connect():
                return {
                    "success": False,
                    "error": "Failed to connect to database"
                }
            
            cursor = self.connection.cursor(dictionary=True)
            
            # Test basic connectivity
            cursor.execute("SELECT 1 as test")
            cursor.fetchone()
            
            # Get sample statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_properties,
                    COUNT(CASE WHEN status = 'vacant' THEN 1 END) as vacant_properties,
                    AVG(monthly_rent) as avg_rent
                FROM properties
            """)
            stats = cursor.fetchone()
            
            # Get sample properties - show all properties regardless of status for testing
            cursor.execute("""
                SELECT id, title, thana, city, monthly_rent, bedrooms, status
                FROM properties 
                LIMIT 3
            """)
            sample_properties = cursor.fetchall()
            
            cursor.close()
            self.disconnect()
            
            return {
                "success": True,
                "message": "Database connection successful",
                "statistics": {
                    "total_properties": stats['total_properties'],
                    "vacant_properties": stats['vacant_properties'], 
                    "avg_rent": round(stats['avg_rent'] or 0, 2)
                },
                "sample_properties": sample_properties
            }
            
        except Error as e:
            logger.error(f"Database test failed: {e}")
            return {
                "success": False,
                "error": f"Database test failed: {str(e)}"
            }
    
    def search_properties(self, criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Search properties based on given criteria"""
        try:
            if not self.connect():
                return {"success": False, "error": "Database connection failed"}
            
            cursor = self.connection.cursor(dictionary=True)
            
            # Build dynamic query - more flexible status matching
            where_conditions = ["(status = 'vacant' OR status = 'draft' OR status IS NULL OR status = 'available' OR status = 'active')"]
            params = []
            
            # Location/Thana filter
            if criteria.get('location'):
                location = criteria['location']
                where_conditions.append(
                    "(thana LIKE %s OR neighborhood LIKE %s OR full_address LIKE %s)"
                )
                location_param = f"%{location}%"
                params.extend([location_param, location_param, location_param])
            
            # Budget filter
            if criteria.get('budget'):
                try:
                    budget = float(criteria['budget'])
                    where_conditions.append("monthly_rent <= %s")
                    params.append(budget)
                except ValueError:
                    pass  # Skip invalid budget
            
            # Property type filter
            if criteria.get('property_type'):
                where_conditions.append("property_type LIKE %s")
                params.append(f"%{criteria['property_type']}%")
            
            # Bedrooms filter
            if criteria.get('bedrooms'):
                try:
                    bedrooms = int(criteria['bedrooms'])
                    where_conditions.append("bedrooms >= %s")
                    params.append(bedrooms)
                except ValueError:
                    pass
            
            query = f"""
                SELECT 
                    id, title, description, property_type, bedrooms, bathrooms,
                    monthly_rent, security_deposit, full_address, thana,
                    neighborhood, latitude, longitude, furnished, pets_allowed,
                    owner_id
                FROM properties 
                WHERE {' AND '.join(where_conditions)}
                ORDER BY monthly_rent ASC
                LIMIT 20
            """
            
            cursor.execute(query, params)
            properties = cursor.fetchall()
            
            # Get owner information for each property
            for prop in properties:
                cursor.execute("""
                    SELECT name, phone, email 
                    FROM users 
                    WHERE id = %s AND role = 'owner'
                """, (prop['owner_id'],))
                owner = cursor.fetchone()
                prop['owner'] = owner
            
            cursor.close()
            self.disconnect()
            
            return {
                "success": True,
                "properties": properties,
                "count": len(properties),
                "criteria": criteria
            }
            
        except Error as e:
            logger.error(f"Property search failed: {e}")
            return {
                "success": False,
                "error": f"Property search failed: {str(e)}"
            }
    
    def get_property_details(self, property_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific property"""
        try:
            if not self.connect():
                return {"success": False, "error": "Database connection failed"}
            
            cursor = self.connection.cursor(dictionary=True)
            
            # Get property details
            cursor.execute("""
                SELECT 
                    p.*, u.name as owner_name, u.phone as owner_phone, 
                    u.email as owner_email
                FROM properties p
                JOIN users u ON p.owner_id = u.id
                WHERE p.id = %s
            """, (property_id,))
            
            property_data = cursor.fetchone()
            
            if not property_data:
                return {"success": False, "error": "Property not found"}
            
            # Get property amenities
            cursor.execute("""
                SELECT a.name 
                FROM amenities a
                JOIN property_amenities pa ON a.id = pa.amenity_id
                WHERE pa.property_id = %s
            """, (property_id,))
            
            amenities = [row['name'] for row in cursor.fetchall()]
            property_data['amenities'] = amenities
            
            # Get property images
            cursor.execute("""
                SELECT image_url, is_cover
                FROM property_images
                WHERE property_id = %s
                ORDER BY is_cover DESC
            """, (property_id,))
            
            images = cursor.fetchall()
            property_data['images'] = images
            
            cursor.close()
            self.disconnect()
            
            return {
                "success": True,
                "property": property_data
            }
            
        except Error as e:
            logger.error(f"Get property details failed: {e}")
            return {
                "success": False,
                "error": f"Failed to get property details: {str(e)}"
            }
    
    def get_location_data(self, location: str) -> Dict[str, Any]:
        """Get cached location data from database"""
        try:
            if not self.connect():
                return {"success": False, "error": "Database connection failed"}
            
            cursor = self.connection.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT * FROM location_data 
                WHERE address LIKE %s
                LIMIT 1
            """, (f"%{location}%",))
            
            location_data = cursor.fetchone()
            
            cursor.close()
            self.disconnect()
            
            if location_data:
                return {
                    "success": True,
                    "location_data": location_data
                }
            else:
                return {
                    "success": False,
                    "error": "Location not found in cache"
                }
                
        except Error as e:
            logger.error(f"Get location data failed: {e}")
            return {
                "success": False,
                "error": f"Failed to get location data: {str(e)}"
            }
    
    def save_location_data(self, location_data: Dict[str, Any]) -> bool:
        """Save geocoded location data to cache"""
        try:
            if not self.connect():
                return False
            
            cursor = self.connection.cursor()
            
            cursor.execute("""
                INSERT INTO location_data 
                (address, formatted_address, latitude, longitude, thana, district, 
                 division, postal_code, place_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                formatted_address = VALUES(formatted_address),
                latitude = VALUES(latitude),
                longitude = VALUES(longitude),
                thana = VALUES(thana),
                district = VALUES(district),
                division = VALUES(division),
                postal_code = VALUES(postal_code),
                place_id = VALUES(place_id)
            """, (
                location_data.get('address'),
                location_data.get('formatted_address'),
                location_data.get('latitude'),
                location_data.get('longitude'), 
                location_data.get('thana'),
                location_data.get('district'),
                location_data.get('division'),
                location_data.get('postal_code'),
                location_data.get('place_id')
            ))
            
            cursor.close()
            self.disconnect()
            return True
            
        except Error as e:
            logger.error(f"Save location data failed: {e}")
            return False
    
    def search_properties_near_landmark(self, coordinates: Dict[str, float], radius_km: float = 5) -> Dict[str, Any]:
        """Search properties near a landmark using coordinates and radius"""
        try:
            if not self.connect():
                return {"success": False, "error": "Database connection failed"}
            
            cursor = self.connection.cursor(dictionary=True)
            
            lat = coordinates['lat']
            lng = coordinates['lng']
            
            # Use Haversine formula to calculate distance
            query = f"""
                SELECT 
                    id, title, description, property_type, bedrooms, bathrooms,
                    monthly_rent, security_deposit, full_address, thana,
                    neighborhood, latitude, longitude, furnished, pets_allowed,
                    owner_id,
                    (
                        6371 * acos(
                            cos(radians(%s)) * cos(radians(latitude)) * 
                            cos(radians(longitude) - radians(%s)) + 
                            sin(radians(%s)) * sin(radians(latitude))
                        )
                    ) AS distance_km
                FROM properties 
                WHERE (status = 'vacant' OR status = 'draft' OR status IS NULL OR status = 'available' OR status = 'active')
                    AND latitude IS NOT NULL 
                    AND longitude IS NOT NULL
                HAVING distance_km <= %s
                ORDER BY distance_km ASC
                LIMIT 20
            """
            
            cursor.execute(query, (lat, lng, lat, radius_km))
            properties = cursor.fetchall()
            
            # Get owner information for each property
            for prop in properties:
                cursor.execute("""
                    SELECT name, phone, email 
                    FROM users 
                    WHERE id = %s AND role = 'owner'
                """, (prop['owner_id'],))
                owner = cursor.fetchone()
                prop['owner'] = owner
                prop['distance_km'] = round(prop['distance_km'], 2)
            
            cursor.close()
            self.disconnect()
            
            return {
                "success": True,
                "properties": properties,
                "count": len(properties),
                "search_center": coordinates,
                "radius_km": radius_km
            }
            
        except Error as e:
            logger.error(f"Landmark search failed: {e}")
            return {
                "success": False,
                "error": f"Landmark search failed: {str(e)}"
            }
    
    def save_search_history(self, user_id: Optional[int], session_id: int, 
                           search_query: str, search_criteria: Dict[str, Any], 
                           results_count: int) -> bool:
        """Save search history for analytics"""
        try:
            if not self.connect():
                return False
            
            cursor = self.connection.cursor()
            
            cursor.execute("""
                INSERT INTO search_history 
                (user_id, session_id, search_query, search_location, 
                 search_criteria, results_count)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                session_id,
                search_query,
                search_criteria.get('location', ''),
                json.dumps(search_criteria),
                results_count
            ))
            
            cursor.close()
            self.disconnect()
            return True
            
        except Error as e:
            logger.error(f"Save search history failed: {e}")
            return False
            
    def find_nearest_budget_properties(self, criteria: Dict[str, Any], range_percent: int = 25) -> Dict[str, Any]:
        """Find properties with the nearest budget to the specified criteria
        
        When no properties match an exact budget, this function finds alternatives by:
        1. Looking for properties at price points both above and below the requested budget
        2. Expanding the search range by a percentage (default 25%)
        3. Finding the closest matches to the requested budget
        
        Args:
            criteria: Search criteria including budget and other filters
            range_percent: How much to expand the search range (as percentage)
            
        Returns:
            Dictionary with search results and metadata about budget adjustments
        """
        try:
            if not self.connect():
                return {"success": False, "error": "Database connection failed"}
            
            cursor = self.connection.cursor(dictionary=True)
            
            # Extract the budget from criteria
            if not criteria.get('budget'):
                return {"success": False, "error": "Budget must be specified for nearest budget search"}
                
            target_budget = float(criteria['budget'])
            
            # Calculate range for searching (e.g., ±25% of target budget)
            min_budget = target_budget * (1 - range_percent/100)
            max_budget = target_budget * (1 + range_percent/100)
            
            # Build query with all criteria except budget - flexible status
            where_conditions = ["(status = 'vacant' OR status = 'draft' OR status IS NULL OR status = 'available' OR status = 'active')"]
            params = []
            
            # Location/Thana filter
            if criteria.get('location'):
                location = criteria['location']
                where_conditions.append(
                    "(thana LIKE %s OR neighborhood LIKE %s OR full_address LIKE %s)"
                )
                location_param = f"%{location}%"
                params.extend([location_param, location_param, location_param])
            
            # Property type filter
            if criteria.get('property_type'):
                where_conditions.append("property_type LIKE %s")
                params.append(f"%{criteria['property_type']}%")
            
            # Bedrooms filter
            if criteria.get('bedrooms'):
                try:
                    bedrooms = int(criteria['bedrooms'])
                    where_conditions.append("bedrooms >= %s")
                    params.append(bedrooms)
                except ValueError:
                    pass
            
            # First, try to get properties below target budget
            lower_query = f"""
                SELECT 
                    id, title, description, property_type, bedrooms, bathrooms,
                    monthly_rent, security_deposit, full_address, thana,
                    neighborhood, latitude, longitude, furnished, pets_allowed,
                    owner_id, ABS(monthly_rent - %s) as price_diff
                FROM properties 
                WHERE {' AND '.join(where_conditions)} AND monthly_rent <= %s
                ORDER BY monthly_rent DESC
                LIMIT 10
            """
            
            # Then, try to get properties above target budget
            higher_query = f"""
                SELECT 
                    id, title, description, property_type, bedrooms, bathrooms,
                    monthly_rent, security_deposit, full_address, thana,
                    neighborhood, latitude, longitude, furnished, pets_allowed,
                    owner_id, ABS(monthly_rent - %s) as price_diff
                FROM properties 
                WHERE {' AND '.join(where_conditions)} AND monthly_rent > %s AND monthly_rent <= %s
                ORDER BY monthly_rent ASC
                LIMIT 10
            """
            
            # Execute queries to find properties below and above target budget
            cursor.execute(lower_query, [target_budget] + params + [target_budget])
            lower_properties = cursor.fetchall()
            
            cursor.execute(higher_query, [target_budget] + params + [target_budget, max_budget])
            higher_properties = cursor.fetchall()
            
            # Combine and sort by closest to target budget
            all_properties = lower_properties + higher_properties
            all_properties.sort(key=lambda x: x['price_diff'])
            
            # Get owner information for each property
            for prop in all_properties:
                cursor.execute("""
                    SELECT name, phone, email 
                    FROM users 
                    WHERE id = %s AND role = 'owner'
                """, (prop['owner_id'],))
                owner = cursor.fetchone()
                prop['owner'] = owner
            
            cursor.close()
            self.disconnect()
            
            # Prepare result categories
            lower_budget_options = [p for p in all_properties if p['monthly_rent'] < target_budget]
            higher_budget_options = [p for p in all_properties if p['monthly_rent'] > target_budget]
            
            # Find the closest matches if we have enough properties
            closest_matches = all_properties[:10] if all_properties else []
            
            return {
                "success": True,
                "properties": closest_matches,
                "count": len(closest_matches),
                "criteria": criteria,
                "target_budget": target_budget,
                "lower_options": len(lower_budget_options),
                "higher_options": len(higher_budget_options),
                "min_price": min([p['monthly_rent'] for p in all_properties]) if all_properties else 0,
                "max_price": max([p['monthly_rent'] for p in all_properties]) if all_properties else 0,
                "adjusted": True
            }
            
        except Error as e:
            logger.error(f"Nearest budget search failed: {e}")
            return {
                "success": False,
                "error": f"Nearest budget search failed: {str(e)}"
            }

# Global database manager instance
db_manager = DatabaseManager()