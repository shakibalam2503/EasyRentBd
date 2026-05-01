import requests
import os
import logging
from typing import Dict, List, Optional, Any, Tuple
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleMapsService:
    """Google Maps API integration for geocoding, reverse geocoding, and places search"""
    
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_MAPS_API_KEY', 'AIzaSyD2eRjLYkpWYq_MPYMSlJRgu1W9Gv_ZqI8')
        self.geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
        self.places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        self.places_details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        
        if not self.api_key:
            logger.warning("Google Maps API key not found in environment variables")
    
    def geocode_location(self, location: str, country: str = "Bangladesh") -> Dict[str, Any]:
        """Convert address/location to coordinates using Google Geocoding API"""
        try:
            params = {
                'address': f"{location}, {country}",
                'key': self.api_key
            }
            
            response = requests.get(self.geocoding_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                result = data['results'][0]
                
                location_info = {
                    'success': True,
                    'formatted_address': result['formatted_address'],
                    'coordinates': {
                        'lat': result['geometry']['location']['lat'],
                        'lng': result['geometry']['location']['lng']
                    },
                    'place_id': result['place_id'],
                    'address_components': self._parse_address_components(result.get('address_components', []))
                }
                
                return location_info
            else:
                return {
                    'success': False,
                    'error': f"Geocoding failed: {data.get('status', 'Unknown error')}"
                }
                
        except requests.RequestException as e:
            logger.error(f"Geocoding request failed: {e}")
            return {
                'success': False,
                'error': f"Geocoding request failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Geocoding failed: {e}")
            return {
                'success': False,
                'error': f"Geocoding failed: {str(e)}"
            }
    
    def reverse_geocode(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Convert coordinates to address using reverse geocoding"""
        try:
            params = {
                'latlng': f"{latitude},{longitude}",
                'key': self.api_key
            }
            
            response = requests.get(self.geocoding_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                result = data['results'][0]
                
                return {
                    'success': True,
                    'formatted_address': result['formatted_address'],
                    'place_id': result['place_id'],
                    'address_components': self._parse_address_components(result.get('address_components', []))
                }
            else:
                return {
                    'success': False,
                    'error': f"Reverse geocoding failed: {data.get('status', 'Unknown error')}"
                }
                
        except requests.RequestException as e:
            logger.error(f"Reverse geocoding request failed: {e}")
            return {
                'success': False,
                'error': f"Reverse geocoding request failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Reverse geocoding failed: {e}")
            return {
                'success': False,
                'error': f"Reverse geocoding failed: {str(e)}"
            }
    
    def find_nearby_places(self, coordinates: Dict[str, float], place_type: str = 'point_of_interest', 
                          radius: int = 5000) -> Dict[str, Any]:
        """Find nearby places using Google Places API"""
        try:
            params = {
                'location': f"{coordinates['lat']},{coordinates['lng']}",
                'radius': radius,
                'type': place_type,
                'key': self.api_key
            }
            
            response = requests.get(self.places_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data['status'] == 'OK':
                places = []
                for place in data.get('results', []):
                    place_info = {
                        'name': place.get('name'),
                        'place_id': place.get('place_id'),
                        'coordinates': {
                            'lat': place['geometry']['location']['lat'],
                            'lng': place['geometry']['location']['lng']
                        },
                        'types': place.get('types', []),
                        'rating': place.get('rating'),
                        'price_level': place.get('price_level'),
                        'vicinity': place.get('vicinity')
                    }
                    places.append(place_info)
                
                return {
                    'success': True,
                    'places': places,
                    'count': len(places)
                }
            else:
                return {
                    'success': False,
                    'error': f"Places search failed: {data.get('status', 'Unknown error')}"
                }
                
        except requests.RequestException as e:
            logger.error(f"Places search request failed: {e}")
            return {
                'success': False,
                'error': f"Places search request failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Places search failed: {e}")
            return {
                'success': False,
                'error': f"Places search failed: {str(e)}"
            }
    
    def find_landmark(self, landmark_name: str, location_bias: Optional[str] = "Bangladesh") -> Dict[str, Any]:
        """Find a specific landmark and return its coordinates"""
        try:
            # Use text search to find the landmark
            search_query = f"{landmark_name} {location_bias}" if location_bias else landmark_name
            
            geocode_result = self.geocode_location(search_query)
            
            if geocode_result['success']:
                return {
                    'success': True,
                    'landmark_name': landmark_name,
                    'coordinates': geocode_result['coordinates'],
                    'formatted_address': geocode_result['formatted_address'],
                    'place_id': geocode_result['place_id']
                }
            else:
                return geocode_result
                
        except Exception as e:
            logger.error(f"Landmark search failed: {e}")
            return {
                'success': False,
                'error': f"Landmark search failed: {str(e)}"
            }
    
    def search_amenities_near_property(self, coordinates: Dict[str, float], 
                                     amenity_type: str, radius: int = 2000) -> Dict[str, Any]:
        """Search for specific amenities near a property"""
        
        # Map amenity types to Google Places types
        amenity_mapping = {
            'hospital': 'hospital',
            'hospitals': 'hospital',
            'school': 'school',
            'schools': 'school',
            'university': 'university',
            'universities': 'university',
            'bank': 'bank',
            'banks': 'bank',
            'restaurant': 'restaurant',
            'restaurants': 'restaurant',
            'shopping': 'shopping_mall',
            'mall': 'shopping_mall',
            'pharmacy': 'pharmacy',
            'mosque': 'mosque',
            'transport': 'transit_station',
            'bus_station': 'bus_station',
            'gas_station': 'gas_station',
            'atm': 'atm',
            'grocery': 'grocery_or_supermarket',
            'market': 'grocery_or_supermarket'
        }
        
        google_type = amenity_mapping.get(amenity_type.lower(), 'point_of_interest')
        
        try:
            result = self.find_nearby_places(coordinates, google_type, radius)
            
            if result['success']:
                return {
                    'success': True,
                    'amenity_type': amenity_type,
                    'places': result['places'],
                    'count': result['count'],
                    'search_radius': radius
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Amenity search failed: {e}")
            return {
                'success': False,
                'error': f"Amenity search failed: {str(e)}"
            }
    
    def calculate_distance(self, coord1: Dict[str, float], coord2: Dict[str, float]) -> float:
        """Calculate distance between two coordinates using Haversine formula"""
        import math
        
        lat1, lng1 = coord1['lat'], coord1['lng']
        lat2, lng2 = coord2['lat'], coord2['lng']
        
        # Convert to radians
        lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth radius in km
        r = 6371
        
        return round(r * c, 2)
    
    def get_nearby_thanas(self, coordinates: Dict[str, float], radius_km: int = 10) -> List[str]:
        """Get nearby thana/upazila names for fallback search"""
        try:
            # This would ideally use a Bangladesh-specific dataset
            # For now, we'll use reverse geocoding to get area information
            reverse_result = self.reverse_geocode(coordinates['lat'], coordinates['lng'])
            
            if reverse_result['success']:
                components = reverse_result['address_components']
                nearby_areas = []
                
                # Extract different administrative levels
                for component_type in ['sublocality_level_1', 'sublocality_level_2', 
                                     'locality', 'administrative_area_level_3']:
                    if component_type in components:
                        nearby_areas.append(components[component_type])
                
                return nearby_areas
            
            return []
            
        except Exception as e:
            logger.error(f"Get nearby thanas failed: {e}")
            return []
    
    def _parse_address_components(self, components: List[Dict[str, Any]]) -> Dict[str, str]:
        """Parse Google's address components into a structured format"""
        parsed = {}
        
        for component in components:
            types = component.get('types', [])
            long_name = component.get('long_name', '')
            short_name = component.get('short_name', '')
            
            # Map Google's address component types to our format
            if 'sublocality_level_1' in types:
                parsed['thana'] = long_name
            elif 'locality' in types:
                parsed['city'] = long_name
            elif 'administrative_area_level_1' in types:
                parsed['division'] = long_name
            elif 'administrative_area_level_2' in types:
                parsed['district'] = long_name
            elif 'postal_code' in types:
                parsed['postal_code'] = long_name
            elif 'country' in types:
                parsed['country'] = long_name
        
        return parsed
    
    def batch_geocode_landmarks(self, landmarks: List[str]) -> Dict[str, Dict[str, Any]]:
        """Geocode multiple landmarks with rate limiting"""
        results = {}
        
        for landmark in landmarks:
            try:
                result = self.find_landmark(landmark)
                results[landmark] = result
                
                # Add small delay to respect API rate limits
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Failed to geocode landmark {landmark}: {e}")
                results[landmark] = {
                    'success': False,
                    'error': f"Failed to geocode: {str(e)}"
                }
        
        return results

# Global maps service instance
maps_service = GoogleMapsService()
