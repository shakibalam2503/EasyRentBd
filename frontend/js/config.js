// Application Configuration
const AppConfig = {
    // Backend API URL - change this for production deployment
    API_BASE_URL: 'http://localhost:5000',
    
    // API Endpoints
    ENDPOINTS: {
        CHATBOT: {
            SESSION: '/api/chatbot/session',
            MESSAGE: '/api/chatbot/message',
            HEALTH: '/api/chatbot/health',
            HISTORY: '/api/chatbot/history'
        },
        PROPERTIES: {
            SEARCH: '/api/properties',
            DETAILS: '/api/properties'
        },
        LOCATION: {
            MAPS_KEY: '/api/location/config/maps-key'
        }
    },
    
    // Chat Configuration
    CHAT: {
        MAX_MESSAGE_LENGTH: 1000,
        TYPING_INDICATOR_DELAY: 500,
        HEALTH_CHECK_INTERVAL: 30000, // 30 seconds
        SUGGESTION_DELAY: 500
    },
    
    // Map Configuration
    MAP: {
        DEFAULT_CENTER: { lat: 23.8103, lng: 90.4125 }, // Dhaka center
        DEFAULT_ZOOM: 12,
        SINGLE_PROPERTY_ZOOM: 15
    },
    
    // UI Configuration
    UI: {
        ANIMATION_DURATION: 300,
        DEBOUNCE_DELAY: 300
    },
    
    // Helper methods
    getApiUrl: function(endpoint) {
        return this.API_BASE_URL + endpoint;
    }
};

// Helper function to get full API URL
AppConfig.getApiUrl = function(endpoint) {
    return this.API_BASE_URL + endpoint;
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AppConfig;
}