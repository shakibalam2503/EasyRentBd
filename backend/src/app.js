
const express = require('express');
const cors = require('cors');
const path = require('path'); // Import path module
require('dotenv').config();

const app = express();

app.use(cors({ origin: '*', methods: 'GET,HEAD,PUT,PATCH,POST,DELETE' }));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve static files from the frontend directory
app.use(express.static(path.join(__dirname, '../../frontend')));

// Serve static files from the public directory
app.use(express.static('public'));

const authRoutes = require('./routes/authRoutes');
const propertyRoutes = require('./routes/propertyRoutes');
const dashboardRoutes = require('./routes/dashboardRoutes');
const locationRoutes = require('./routes/locationRoutes');
const chatbotRoutes = require('./routes/chatbotRoutes');

app.use('/api/auth', authRoutes);
app.use('/api/properties', propertyRoutes);
app.use('/api/dashboard', dashboardRoutes);
app.use('/api/location', locationRoutes);
app.use('/api/chatbot', chatbotRoutes);

app.get('/', (req, res) => {
    res.send('Backend server is running!');
});



const PORT = process.env.PORT || 5000;

app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});
