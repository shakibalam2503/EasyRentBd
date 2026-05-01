
const mysql = require('mysql2');
require('dotenv').config();

const dbConfig = {
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB_NAME || 'propertymanagement',
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
};

const pool = mysql.createPool(dbConfig);

// Test the connection
pool.getConnection((err, connection) => {
    if (err) {
        
        if (err.code === 'PROTOCOL_CONNECTION_LOST') {
            console.error('Database connection was closed.');
        } else if (err.code === 'ER_CON_COUNT_ERROR') {
            console.error('Database has too many connections.');
        } else if (err.code === 'ECONNREFUSED') {
            console.error('Database connection was refused. Check if your database server (e.g., XAMPP, WAMP) is running.');
        } else if (err.code === 'ER_ACCESS_DENIED_ERROR') {
            console.error('Database access denied. Check your username and password in the .env file.');
        } else {
            console.error('DB Error Code:', err.code);
            console.error('DB Error Message:', err.message);
        }
        console.error('************************************************************');
        // Exit process if cannot connect to DB, as the app is useless without it.
        process.exit(1);
    }
    if (connection) {
        console.log('Successfully connected to the database.');
        connection.release();
    }
});

module.exports = pool.promise();
