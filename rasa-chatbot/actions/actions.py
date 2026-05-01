import os
import sys
import logging
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction
from .database import db_manager
from .maps_service import maps_service
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ActionSimpleSearch(Action):
    """Simple search to test database connectivity and show all properties"""
    
    def name(self) -> Text:
        return "action_simple_search"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            # Search for any properties without strict filters
            if not db_manager.connect():
                dispatcher.utter_message(text="❌ Database connection failed")
                return []
            
            cursor = db_manager.connection.cursor(dictionary=True)
            
            # Get all properties regardless of status
            cursor.execute("""
                SELECT 
                    id, title, description, property_type, bedrooms, bathrooms,
                    monthly_rent, full_address, thana, city,
                    neighborhood, latitude, longitude, furnished, status
                FROM properties 
                LIMIT 10
            """)
            
            properties = cursor.fetchall()
            cursor.close()
            db_manager.disconnect()
            
            if properties:
                message = f"🔍 Found {len(properties)} properties in database:\n\n"
                
                for i, prop in enumerate(properties[:5], 1):
                    title = prop.get('title', 'Untitled Property')
                    location = prop.get('thana', prop.get('city', 'Unknown Location'))
                    rent = prop.get('monthly_rent', 0)
                    status = prop.get('status', 'No Status')
                    
                    message += f"**{i}. {title}**\n"
                    message += f"📍 {location}\n"
                    message += f"💰 ৳{rent:,}/month\n"
                    message += f"📊 Status: {status}\n\n"
                
                message += "These are the actual properties in your database!"
                
                # Send structured data to frontend
                dispatcher.utter_message(
                    text=message,
                    custom={
                        "properties": properties,
                        "count": len(properties),
                        "search_type": "simple_test"
                    }
                )
                
                return [SlotSet("search_results", properties)]
            else:
                dispatcher.utter_message(text="No properties found in the database.")
                return []
                
        except Exception as e:
            logger.error(f"Simple search failed: {e}")
            dispatcher.utter_message(text="❌ Database search failed due to system error.")
            return []


class ActionTestDatabase(Action):
    """Test database connection and show sample data"""
    
    def name(self) -> Text:
        return "action_test_database"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            # Test database connection
            result = db_manager.test_connection()
            
            if result['success']:
                # Format success message
                stats = result['statistics']
                sample_props = result['sample_properties']
                
                message = f"✅ Database connection successful!\n\n"
                message += f"📊 **Statistics:**\n"
                message += f"• Total Properties: {stats['total_properties']}\n"
                message += f"• Vacant Properties: {stats['vacant_properties']}\n"
                message += f"• Average Rent: ৳{stats['avg_rent']}\n\n"
                
                if sample_props:
                    message += f"🏠 **Sample Properties:**\n"
                    for i, prop in enumerate(sample_props[:3], 1):
                        title = prop.get('title', 'Property')
                        location = prop.get('thana', prop.get('city', 'Location'))
                        rent = prop.get('monthly_rent', 0)
                        message += f"{i}. {title} - {location} - ৳{rent:,}/month\n"
                
                dispatcher.utter_message(text=message)
                
                return []
                
            else:
                error_msg = f"❌ Database connection failed: {result['error']}"
                dispatcher.utter_message(text=error_msg)
                return []
                
        except Exception as e:
            logger.error(f"Database test action failed: {e}")
            dispatcher.utter_message(text="❌ Database test failed due to system error.")
            return []


class ActionSearchProperties(Action):
    """Search for properties based on criteria"""
    
    def name(self) -> Text:
        return "action_search_properties"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            # Extract search criteria from slots and entities - SMART EXTRACTION
            location = tracker.get_slot("location")
            budget = tracker.get_slot("budget")
            property_type = tracker.get_slot("property_type")
            bedrooms = tracker.get_slot("bedrooms")
            
            # If no location in slot, try to extract from latest message
            if not location:
                latest_message = tracker.latest_message.get('text', '').lower()
                # Extract location from any text - smart parsing
                import re
                
                # Common patterns for location extraction
                location_patterns = [
                    r'in\s+([a-zA-Z\s]+?)(?:\s|$|,|\.)',
                    r'at\s+([a-zA-Z\s]+?)(?:\s|$|,|\.)',
                    r'near\s+([a-zA-Z\s]+?)(?:\s|$|,|\.)',
                    r'around\s+([a-zA-Z\s]+?)(?:\s|$|,|\.)'
                ]
                
                for pattern in location_patterns:
                    match = re.search(pattern, latest_message)
                    if match:
                        potential_location = match.group(1).strip().title()
                        logger.info(f"Extracted location from text: {potential_location}")
                        location = potential_location
                        break
            
            # Build search criteria
            search_criteria = {}
            if location:
                search_criteria['location'] = location
            if budget:
                search_criteria['budget'] = budget
            if property_type:
                search_criteria['property_type'] = property_type
            if bedrooms:
                search_criteria['bedrooms'] = bedrooms
            
            logger.info(f"Searching properties with criteria: {search_criteria}")
            
            # Search properties in database
            result = db_manager.search_properties(search_criteria)
            
            if result['success']:
                properties = result['properties']
                count = result['count']
                
                # Check if there's a budget but no results - try nearest budget alternatives
                if count == 0 and budget:
                    logger.info(f"No exact budget matches, trying alternatives for budget: {budget}")
                    return [FollowupAction("action_budget_alternatives")]
                
                # If no results found and we have a location, try a broader search
                if count == 0 and location:
                    logger.info(f"No properties found for {location}, trying broader search")
                    # Try searching without exact location match
                    broader_criteria = search_criteria.copy()
                    broader_criteria.pop('location', None)  # Remove location for broader search
                    broader_result = db_manager.search_properties(broader_criteria)
                    
                    if broader_result['success'] and broader_result['count'] > 0:
                        message = f"No properties found in {location}, but I found {broader_result['count']} properties in nearby areas:\n\n"
                        properties = broader_result['properties'][:3]
                        count = len(properties)
                        
                        for i, prop in enumerate(properties, 1):
                            rent = f"৳{prop['monthly_rent']:,}/month" if prop['monthly_rent'] else "Price on request"
                            location_text = prop.get('thana', prop.get('neighborhood', 'Location TBD'))
                            
                            message += f"**{i}. {prop['title']}**\n"
                            message += f"📍 {location_text}\n"
                            message += f"💰 {rent}\n\n"
                        
                        message += "Would you like to see more details about these properties?"
                        
                        dispatcher.utter_message(
                            text=message,
                            custom={
                                "properties": properties,
                                "count": count,
                                "search_type": "broader_search"
                            }
                        )
                        return [SlotSet("search_results", properties)]
                
                if count > 0:
                    # Format response with property list
                    message = f"🏠 Found **{count} properties** matching your criteria:\n\n"
                    
                    for i, prop in enumerate(properties[:5], 1):  # Show first 5
                        rent = f"৳{prop['monthly_rent']:,}/month" if prop['monthly_rent'] else "Price on request"
                        bedrooms_text = f"{int(prop['bedrooms'])} bed" if prop['bedrooms'] else "N/A"
                        location_text = prop.get('thana', prop.get('neighborhood', 'Location TBD'))
                        
                        message += f"**{i}. {prop['title']}**\n"
                        message += f"📍 {location_text}\n"
                        message += f"💰 {rent} | 🛏️ {bedrooms_text}\n"
                        if prop.get('furnished'):
                            message += "✨ Furnished\n"
                        if prop.get('pets_allowed'):
                            message += "🐾 Pet-friendly\n"
                        message += f"_{prop.get('description', '')[:100]}..._\n\n"
                    
                    if count > 5:
                        message += f"...and {count - 5} more properties.\n\n"
                    
                    message += "Would you like to see these properties on a map or get details about a specific property?"
                    
                    # Send structured data to frontend
                    dispatcher.utter_message(
                        text=message,
                        custom={
                            "properties": properties,
                            "count": count,
                            "search_type": "standard"
                        }
                    )
                    
                    # Store search results in slot for later use and return immediately
                    return [SlotSet("search_results", properties)]
                    
                else:
                    # No results found - provide helpful suggestions without triggering fallback
                    no_results_message = "I couldn't find any properties matching your exact criteria. Here are some suggestions:\n\n"
                    no_results_message += "• Try searching in nearby areas\n"
                    no_results_message += "• Consider adjusting your budget range\n"
                    no_results_message += "• Broaden your location search\n"
                    no_results_message += "• Remove some specific requirements\n\n"
                    no_results_message += "Would you like me to show you all available properties instead?"
                    
                    dispatcher.utter_message(text=no_results_message)
                    return []
                    
            else:
                error_msg = f"❌ Property search failed: {result['error']}"
                dispatcher.utter_message(text=error_msg)
                return []
                
        except Exception as e:
            logger.error(f"Property search action failed: {e}")
            dispatcher.utter_message(text="Sorry, I encountered an error while searching for properties. Please try again.")
            return []


class ActionLandmarkSearch(Action):
    """Search for properties near a landmark"""
    
    def name(self) -> Text:
        return "action_landmark_search"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            landmark = tracker.get_slot("landmark")
            
            if not landmark:
                dispatcher.utter_message(text="Please specify a landmark to search near.")
                return []
            
            logger.info(f"Searching properties near landmark: {landmark}")
            
            # Find landmark coordinates using Google Maps
            landmark_result = maps_service.find_landmark(landmark)
            
            if landmark_result['success']:
                coordinates = landmark_result['coordinates']
                
                # Search properties near landmark coordinates
                search_result = db_manager.search_properties_near_landmark(coordinates, radius_km=5)
                
                if search_result['success']:
                    properties = search_result['properties']
                    count = search_result['count']
                    
                    if count > 0:
                        message = f"🎯 Found **{count} properties** near **{landmark}**:\n\n"
                        
                        for i, prop in enumerate(properties[:5], 1):
                            rent = f"৳{prop['monthly_rent']:,}/month" if prop['monthly_rent'] else "Price on request"
                            distance = f"{prop['distance_km']} km away"
                            
                            message += f"**{i}. {prop['title']}**\n"
                            message += f"📍 {prop.get('thana', 'Location TBD')} • 📏 {distance}\n"
                            message += f"💰 {rent} | 🛏️ {int(prop['bedrooms']) if prop['bedrooms'] else 'N/A'} bed\n\n"
                        
                        message += "Would you like to see these properties on a map with the landmark location?"
                        
                        # Send structured data to frontend
                        dispatcher.utter_message(
                            text=message,
                            custom={
                                "properties": properties,
                                "count": count,
                                "search_type": "landmark",
                                "landmark": {
                                    "name": landmark,
                                    "coordinates": coordinates
                                }
                            }
                        )
                        return [SlotSet("search_results", properties)]
                        
                    else:
                        # No properties found near landmark - search in nearby areas
                        dispatcher.utter_message(text=f"No properties found directly near {landmark}. Let me search in nearby areas...")
                        return [FollowupAction("action_fallback_search")]
                
                else:
                    dispatcher.utter_message(text=f"Failed to search properties near {landmark}: {search_result['error']}")
                    return []
                    
            else:
                dispatcher.utter_message(text=f"Could not locate landmark '{landmark}'. Please check the spelling or try a different landmark.")
                return []
                
        except Exception as e:
            logger.error(f"Landmark search action failed: {e}")
            dispatcher.utter_message(text="Sorry, I encountered an error while searching near the landmark.")
            return []


class ActionShowAmenities(Action):
    """Show nearby amenities for a property or area"""
    
    def name(self) -> Text:
        return "action_show_amenities"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            amenity_type = tracker.get_slot("amenity_type")
            search_results = tracker.get_slot("search_results")
            
            if not amenity_type:
                dispatcher.utter_message(text="What type of amenities would you like to see? (hospitals, schools, restaurants, etc.)")
                return []
            
            # Get coordinates from the first property in search results or use a default location
            coordinates = None
            if search_results and len(search_results) > 0:
                prop = search_results[0]
                if prop.get('latitude') and prop.get('longitude'):
                    coordinates = {
                        'lat': float(prop['latitude']),
                        'lng': float(prop['longitude'])
                    }
            
            if not coordinates:
                # Use default Dhaka coordinates
                coordinates = {'lat': 23.8103, 'lng': 90.4125}
                dispatcher.utter_message(text=f"Showing {amenity_type} in central Dhaka area:\n")
            
            # Search for amenities using Google Places API
            amenities_result = maps_service.search_amenities_near_property(
                coordinates, amenity_type, radius=2000
            )
            
            if amenities_result['success']:
                places = amenities_result['places']
                count = amenities_result['count']
                
                if count > 0:
                    message = f"🏢 Found **{count} {amenity_type}** nearby:\n\n"
                    
                    for i, place in enumerate(places[:8], 1):  # Show first 8
                        name = place.get('name', 'Unnamed')
                        vicinity = place.get('vicinity', '')
                        rating = f" ⭐ {place['rating']}" if place.get('rating') else ""
                        
                        message += f"{i}. **{name}**{rating}\n"
                        if vicinity:
                            message += f"   📍 {vicinity}\n"
                        message += "\n"
                    
                    if count > 8:
                        message += f"...and {count - 8} more {amenity_type}.\n\n"
                    
                    message += "Would you like to see these locations on a map?"
                    
                    dispatcher.utter_message(text=message)
                    return []
                    
                else:
                    dispatcher.utter_message(text=f"No {amenity_type} found in the immediate area. You may want to expand your search radius.")
                    return []
            
            else:
                dispatcher.utter_message(text=f"Failed to find {amenity_type}: {amenities_result['error']}")
                return []
                
        except Exception as e:
            logger.error(f"Show amenities action failed: {e}")
            dispatcher.utter_message(text="Sorry, I encountered an error while searching for amenities.")
            return []


class ActionGetPropertyDetails(Action):
    """Get detailed information about a specific property"""
    
    def name(self) -> Text:
        return "action_get_property_details"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            property_id = tracker.get_slot("property_id")
            search_results = tracker.get_slot("search_results")
            
            # If no property_id specified, check if there are search results
            if not property_id and search_results and len(search_results) > 0:
                # Use the first property from search results
                property_data = search_results[0]
                property_id = str(property_data['id'])
            
            if not property_id:
                dispatcher.utter_message(text="Please specify which property you'd like details about.")
                return []
            
            # Get property details from database
            result = db_manager.get_property_details(property_id)
            
            if result['success']:
                prop = result['property']
                
                # Format detailed property information
                message = f"🏠 **{prop['title']}**\n\n"
                
                # Basic info
                message += f"📍 **Location:** {prop.get('full_address', 'Address not specified')}\n"
                message += f"🏘️ **Area:** {prop.get('thana', 'N/A')}, {prop.get('district', 'Dhaka')}\n\n"
                
                # Property details
                message += f"🏢 **Type:** {prop.get('property_type', 'N/A')}\n"
                message += f"🛏️ **Bedrooms:** {int(prop['bedrooms']) if prop['bedrooms'] else 'N/A'}\n"
                message += f"🚿 **Bathrooms:** {prop.get('bathrooms', 'N/A')}\n"
                message += f"📐 **Area:** {prop.get('square_feet', 'N/A')} sq ft\n\n"
                
                # Financial info
                rent = f"৳{prop['monthly_rent']:,}" if prop['monthly_rent'] else "On request"
                security = f"৳{prop['security_deposit']:,}" if prop['security_deposit'] else "N/A"
                message += f"💰 **Monthly Rent:** {rent}\n"
                message += f"🔒 **Security Deposit:** {security}\n\n"
                
                # Features
                features = []
                if prop.get('furnished'):
                    features.append("✨ Furnished")
                if prop.get('pets_allowed'):
                    features.append("🐾 Pet-friendly")
                
                if features:
                    message += f"✅ **Features:** {', '.join(features)}\n\n"
                
                # Amenities
                if prop.get('amenities'):
                    amenities_list = ", ".join(prop['amenities'])
                    message += f"🏢 **Amenities:** {amenities_list}\n\n"
                
                # Description
                if prop.get('description'):
                    message += f"📝 **Description:**\n{prop['description']}\n\n"
                
                # Owner info
                message += f"👤 **Owner:** {prop.get('owner_name', 'N/A')}\n"
                
                # Status
                status_emoji = {"vacant": "✅", "occupied": "❌", "maintenance": "🔧"}.get(prop.get('status'), "❓")
                message += f"{status_emoji} **Status:** {prop.get('status', 'Unknown').title()}\n\n"
                
                message += "Would you like to see nearby amenities or get the owner's contact information?"
                
                dispatcher.utter_message(text=message)
                return []
                
            else:
                dispatcher.utter_message(text=f"Could not find details for property {property_id}: {result['error']}")
                return []
                
        except Exception as e:
            logger.error(f"Get property details action failed: {e}")
            dispatcher.utter_message(text="Sorry, I encountered an error while getting property details.")
            return []


class ActionGetContactInfo(Action):
    """Get owner contact information for a property"""
    
    def name(self) -> Text:
        return "action_get_contact_info"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            property_id = tracker.get_slot("property_id")
            search_results = tracker.get_slot("search_results")
            
            # If no property_id, try to use first property from search results
            if not property_id and search_results and len(search_results) > 0:
                property_data = search_results[0]
                property_id = str(property_data['id'])
            
            if not property_id:
                dispatcher.utter_message(text="Please specify which property owner you'd like to contact.")
                return []
            
            # Get property details which include owner info
            result = db_manager.get_property_details(property_id)
            
            if result['success']:
                prop = result['property']
                
                message = f"📞 **Contact Information for {prop['title']}:**\n\n"
                message += f"👤 **Owner:** {prop.get('owner_name', 'N/A')}\n"
                message += f"📱 **Phone:** {prop.get('owner_phone', 'Not provided')}\n"
                message += f"📧 **Email:** {prop.get('owner_email', 'Not provided')}\n\n"
                message += "💡 **Tips for contacting:**\n"
                message += "• Be polite and introduce yourself\n"
                message += "• Mention the property address/title\n"
                message += "• Ask about availability and viewing times\n"
                message += "• Prepare questions about rent, deposit, and terms\n\n"
                message += "Good luck with your inquiry! 🏠"
                
                dispatcher.utter_message(text=message)
                return []
                
            else:
                dispatcher.utter_message(text=f"Could not find contact information: {result['error']}")
                return []
                
        except Exception as e:
            logger.error(f"Get contact info action failed: {e}")
            dispatcher.utter_message(text="Sorry, I encountered an error while getting contact information.")
            return []


class ActionCompareProperties(Action):
    """Compare two or more properties"""
    
    def name(self) -> Text:
        return "action_compare_properties"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            search_results = tracker.get_slot("search_results")
            
            if not search_results or len(search_results) < 2:
                dispatcher.utter_message(text="I need at least 2 properties to compare. Please search for properties first.")
                return []
            
            # Compare first two properties from search results
            prop1, prop2 = search_results[0], search_results[1]
            
            message = f"⚖️ **Property Comparison:**\n\n"
            
            # Property 1
            message += f"🏠 **Property 1: {prop1['title']}**\n"
            message += f"📍 Location: {prop1.get('thana', 'N/A')}\n"
            message += f"💰 Rent: ৳{prop1['monthly_rent']:,}/month\n"
            message += f"🛏️ Bedrooms: {int(prop1['bedrooms']) if prop1['bedrooms'] else 'N/A'}\n"
            message += f"🚿 Bathrooms: {prop1.get('bathrooms', 'N/A')}\n"
            
            features1 = []
            if prop1.get('furnished'):
                features1.append("Furnished")
            if prop1.get('pets_allowed'):
                features1.append("Pet-friendly")
            message += f"✨ Features: {', '.join(features1) if features1 else 'Basic'}\n\n"
            
            # Property 2
            message += f"🏠 **Property 2: {prop2['title']}**\n"
            message += f"📍 Location: {prop2.get('thana', 'N/A')}\n"
            message += f"💰 Rent: ৳{prop2['monthly_rent']:,}/month\n"
            message += f"🛏️ Bedrooms: {int(prop2['bedrooms']) if prop2['bedrooms'] else 'N/A'}\n"
            message += f"🚿 Bathrooms: {prop2.get('bathrooms', 'N/A')}\n"
            
            features2 = []
            if prop2.get('furnished'):
                features2.append("Furnished")
            if prop2.get('pets_allowed'):
                features2.append("Pet-friendly")
            message += f"✨ Features: {', '.join(features2) if features2 else 'Basic'}\n\n"
            
            # Comparison summary
            message += f"📊 **Quick Comparison:**\n"
            
            # Price comparison
            rent1 = prop1.get('monthly_rent', 0)
            rent2 = prop2.get('monthly_rent', 0)
            if rent1 and rent2:
                if rent1 < rent2:
                    message += f"💰 Property 1 is ৳{rent2 - rent1:,} cheaper per month\n"
                elif rent2 < rent1:
                    message += f"💰 Property 2 is ৳{rent1 - rent2:,} cheaper per month\n"
                else:
                    message += f"💰 Both properties have the same rent\n"
            
            # Space comparison
            beds1 = prop1.get('bedrooms', 0)
            beds2 = prop2.get('bedrooms', 0)
            if beds1 and beds2:
                if beds1 > beds2:
                    message += f"🛏️ Property 1 has {int(beds1 - beds2)} more bedroom(s)\n"
                elif beds2 > beds1:
                    message += f"🛏️ Property 2 has {int(beds2 - beds1)} more bedroom(s)\n"
            
            message += "\nWould you like detailed information about either property or their contact details?"
            
            dispatcher.utter_message(text=message)
            return []
            
        except Exception as e:
            logger.error(f"Compare properties action failed: {e}")
            dispatcher.utter_message(text="Sorry, I encountered an error while comparing properties.")
            return []


class ActionAreaInformation(Action):
    """Provide information about a specific area/location"""
    
    def name(self) -> Text:
        return "action_area_information"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            location = tracker.get_slot("location")
            
            if not location:
                dispatcher.utter_message(text="Which area would you like to know about?")
                return []
            
            # Get area statistics from database
            try:
                result = db_manager.search_properties({"location": location})
                
                if result['success']:
                    properties = result['properties']
                    count = len(properties)
                    
                    if count > 0:
                        # Calculate area statistics
                        rents = [p['monthly_rent'] for p in properties if p.get('monthly_rent')]
                        avg_rent = sum(rents) / len(rents) if rents else 0
                        min_rent = min(rents) if rents else 0
                        max_rent = max(rents) if rents else 0
                        
                        # Property types distribution
                        types = {}
                        for prop in properties:
                            prop_type = prop.get('property_type', 'Unknown')
                            types[prop_type] = types.get(prop_type, 0) + 1
                        
                        message = f"🏘️ **Area Information: {location}**\n\n"
                        message += f"🏠 **Available Properties:** {count}\n"
                        
                        if avg_rent > 0:
                            message += f"💰 **Rent Range:** ৳{min_rent:,} - ৳{max_rent:,}\n"
                            message += f"📊 **Average Rent:** ৳{int(avg_rent):,}/month\n\n"
                        
                        if types:
                            message += f"🏢 **Property Types Available:**\n"
                            for prop_type, qty in sorted(types.items(), key=lambda x: x[1], reverse=True):
                                message += f"• {prop_type.title()}: {qty} properties\n"
                            message += "\n"
                        
                        # Add some general area information based on location
                        area_info = self._get_area_description(location)
                        if area_info:
                            message += f"ℹ️ **About {location}:**\n{area_info}\n\n"
                        
                        message += f"Would you like to search for specific properties in {location}?"
                        
                        dispatcher.utter_message(text=message)
                        return []
                        
                    else:
                        message = f"📍 **{location}** is a location in Bangladesh, but we currently don't have any properties listed in our database for this area.\n\n"
                        message += "You might want to try:\n"
                        message += "• Searching in nearby areas\n"
                        message += "• Checking alternative spelling\n"
                        message += "• Expanding your search to the broader district\n\n"
                        message += "Would you like me to search in nearby areas instead?"
                        
                        dispatcher.utter_message(text=message)
                        return []
                
            except Exception as db_error:
                logger.error(f"Database error in area information: {db_error}")
                # Continue with general area information even if database fails
                pass
            
            # Provide general area information
            area_info = self._get_area_description(location)
            message = f"🏘️ **Area Information: {location}**\n\n"
            if area_info:
                message += f"{area_info}\n\n"
            else:
                message += f"{location} is an area in Bangladesh.\n\n"
            
            message += "I don't have specific property data for this area right now, but you can try searching for properties there!"
            
            dispatcher.utter_message(text=message)
            return []
            
        except Exception as e:
            logger.error(f"Area information action failed: {e}")
            dispatcher.utter_message(text="Sorry, I encountered an error while getting area information.")
            return []
    
    def _get_area_description(self, location: str) -> str:
        """Get description for common areas in Bangladesh"""
        descriptions = {
            "gulshan": "Gulshan is an upscale residential and commercial area in Dhaka, known for its modern amenities, restaurants, and diplomatic zone.",
            "banani": "Banani is a premium residential area adjacent to Gulshan, popular among expatriates and professionals.",
            "dhanmondi": "Dhanmondi is a well-planned residential area with good infrastructure, home to many universities and cultural centers.",
            "uttara": "Uttara is a modern planned residential area in northern Dhaka with wide roads and organized sectors.",
            "mirpur": "Mirpur is a densely populated area in Dhaka with affordable housing options and good transport connectivity.",
            "mohammadpur": "Mohammadpur is a mixed residential area offering budget-friendly accommodation options.",
            "old dhaka": "Old Dhaka is the historic part of the city with traditional architecture and cultural heritage sites.",
            "chittagong": "Chittagong is Bangladesh's port city and commercial capital, offering both urban and coastal living options."
        }
        
        return descriptions.get(location.lower(), "")


class ActionResetSearch(Action):
    """Reset search criteria and start fresh"""
    
    def name(self) -> Text:
        return "action_reset_search"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        dispatcher.utter_message(text="🔄 Search reset! Let's start fresh. What are you looking for?")
        
        # Clear all search-related slots
        return [
            SlotSet("location", None),
            SlotSet("budget", None),
            SlotSet("property_type", None),
            SlotSet("bedrooms", None),
            SlotSet("landmark", None),
            SlotSet("amenity_type", None),
            SlotSet("property_id", None),
            SlotSet("search_results", None)
        ]


class ActionBudgetAlternatives(Action):
    """Find alternative properties when exact budget match isn't available"""
    
    def name(self) -> Text:
        return "action_budget_alternatives"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            # Get search criteria from slots
            budget = tracker.get_slot("budget")
            location = tracker.get_slot("location")
            property_type = tracker.get_slot("property_type")
            bedrooms = tracker.get_slot("bedrooms")
            
            if not budget:
                dispatcher.utter_message(text="Please specify a budget to find alternative properties.")
                return []
            
            # Build search criteria
            search_criteria = {"budget": budget}
            if location: search_criteria["location"] = location
            if property_type: search_criteria["property_type"] = property_type
            if bedrooms: search_criteria["bedrooms"] = bedrooms
            
            # Search for properties with nearest budget (±25% range)
            result = db_manager.find_nearest_budget_properties(search_criteria)
            
            if result['success'] and result['count'] > 0:
                properties = result['properties']
                count = result['count']
                target_budget = result['target_budget']
                min_price = result['min_price']
                max_price = result['max_price']
                
                # Create a message with the alternatives
                message = f"🔍 I couldn't find properties exactly at **৳{target_budget:,}**, but I found **{count} alternatives** in similar price ranges:\n\n"
                
                # Add price range information
                message += f"💰 **Price range:** ৳{min_price:,} - ৳{max_price:,}\n\n"
                
                # Show properties organized by whether they're below or above target budget
                below_budget = [p for p in properties if p['monthly_rent'] < target_budget]
                above_budget = [p for p in properties if p['monthly_rent'] > target_budget]
                
                if below_budget:
                    message += f"**🔽 Below your budget:**\n"
                    for i, prop in enumerate(below_budget[:3], 1):
                        savings = target_budget - prop['monthly_rent']
                        message += f"**{i}. {prop['title']}**\n"
                        message += f"📍 {prop.get('thana', prop.get('neighborhood', 'Location TBD'))}\n"
                        message += f"💰 ৳{prop['monthly_rent']:,}/month (Save ৳{savings:,})\n"
                        message += f"🛏️ {int(prop['bedrooms']) if prop['bedrooms'] else 'N/A'} bedroom(s)\n\n"
                
                if above_budget:
                    message += f"**🔼 Above your budget:**\n"
                    for i, prop in enumerate(above_budget[:3], 1):
                        extra = prop['monthly_rent'] - target_budget
                        message += f"**{i}. {prop['title']}**\n"
                        message += f"📍 {prop.get('thana', prop.get('neighborhood', 'Location TBD'))}\n"
                        message += f"💰 ৳{prop['monthly_rent']:,}/month (Extra ৳{extra:,})\n"
                        message += f"🛏️ {int(prop['bedrooms']) if prop['bedrooms'] else 'N/A'} bedroom(s)\n\n"
                
                message += "Would you like to see more details about any of these properties or adjust your budget?"
                
                # Send structured data to frontend
                dispatcher.utter_message(
                    text=message,
                    custom={
                        "properties": properties,
                        "count": count,
                        "search_type": "budget_alternatives",
                        "target_budget": target_budget,
                        "price_range": {"min": min_price, "max": max_price}
                    }
                )
                return [SlotSet("search_results", properties)]
                
            else:
                # If still no results, suggest broadening search criteria
                dispatcher.utter_message(
                    text=f"I couldn't find properties near your budget of ৳{budget:,}. "
                         f"Try adjusting your budget range or other search criteria."
                )
                return []
                
        except Exception as e:
            logger.error(f"Budget alternatives action failed: {e}")
            dispatcher.utter_message(text="Sorry, I encountered an error while finding budget alternatives.")
            return []


class ActionFallbackSearch(Action):
    """Fallback search when no results found in specified area"""
    
    def name(self) -> Text:
        return "action_fallback_search"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            location = tracker.get_slot("location")
            landmark = tracker.get_slot("landmark")
            budget = tracker.get_slot("budget")
            
            # Check if this is a budget-related search with no results
            if budget is not None:
                # Try budget alternatives first
                return [FollowupAction("action_budget_alternatives")]
            
            search_location = location or landmark
            
            if not search_location:
                # Show available properties without specific fallback messaging
                result = db_manager.search_properties({})
                
                if result['success'] and result['count'] > 0:
                    properties = result['properties'][:3]
                    
                    message = "🏠 **Here are some available properties in popular areas:**\n\n"
                    for i, prop in enumerate(properties, 1):
                        message += f"**{i}. {prop['title']}**\n"
                        message += f"📍 {prop.get('thana', 'Location TBD')}\n"
                        message += f"💰 ৳{prop['monthly_rent']:,}/month\n\n"
                    
                    dispatcher.utter_message(text=message)
                    return [SlotSet("search_results", properties)]
                
                return []
            
            # Try to find nearby areas using Google Maps or suggest alternatives
            try:
                if landmark:
                    landmark_result = maps_service.find_landmark(landmark)
                    if landmark_result['success']:
                        coordinates = landmark_result['coordinates']
                        nearby_areas = maps_service.get_nearby_thanas(coordinates)
                        
                        if nearby_areas:
                            # Search in nearby areas
                            for area in nearby_areas:
                                area_result = db_manager.search_properties({"location": area})
                                if area_result['success'] and area_result['count'] > 0:
                                    properties = area_result['properties'][:3]
                                    
                                    message = f"🎯 No properties found directly near **{landmark}**, but I found **{area_result['count']} properties** in nearby **{area}**:\n\n"
                                    
                                    for i, prop in enumerate(properties, 1):
                                        message += f"**{i}. {prop['title']}**\n"
                                        message += f"📍 {prop.get('thana', area)}\n"
                                        message += f"💰 ৳{prop['monthly_rent']:,}/month\n\n"
                                    
                                    message += "Would you like to see more properties in this area?"
                                    
                                    dispatcher.utter_message(text=message)
                                    return [SlotSet("search_results", properties)]
                
            except Exception as maps_error:
                logger.error(f"Maps service error in fallback search: {maps_error}")
            
            # If we reach here, provide helpful suggestions without redundant messaging
            message = f"Let me help you find alternatives:\n\n"
            message += "• Try searching in nearby areas or with broader location names\n"
            message += "• Check the spelling of the location\n"
            message += "• Consider expanding your budget or requirements\n\n"
            message += "Would you like me to show you popular areas with available properties?"
            
            dispatcher.utter_message(text=message)
            return []
            
        except Exception as e:
            logger.error(f"Fallback search action failed: {e}")
            # Avoid sending generic fallback messages on error
            return []


# Form validation for property search
class ValidatePropertySearchForm(FormValidationAction):
    """Validate property search form"""
    
    def name(self) -> Text:
        return "validate_property_search_form"
    
    def validate_budget(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate budget input"""
        
        if slot_value is None:
            return {"budget": None}
        
        # Extract numeric value from budget
        budget_str = str(slot_value).lower()
        budget_value = None
        
        # Try to extract number from various formats
        import re
        numbers = re.findall(r'\d+', budget_str)
        
        if numbers:
            budget_value = int(numbers[0])
            
            # Handle thousands
            if 'k' in budget_str or 'thousand' in budget_str:
                budget_value *= 1000
            
            # Reasonable budget validation
            if budget_value < 1000:
                dispatcher.utter_message(text="That budget seems quite low. Are you sure you meant ৳{:,}?".format(budget_value))
                return {"budget": budget_value}
            elif budget_value > 200000:
                dispatcher.utter_message(text="That's a high budget! I'll search for premium properties.")
                return {"budget": budget_value}
            else:
                return {"budget": budget_value}
        
        # If we can't parse the budget, ask for clarification
        dispatcher.utter_message(text="Could you please specify your budget as a number in Taka? (e.g., 25000)")
        return {"budget": None}