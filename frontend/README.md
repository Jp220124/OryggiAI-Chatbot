# Advance Chatbot - Frontend

A modern, user-friendly web interface for the Advance Chatbot SQL Query Assistant.

## Features

- **Beautiful UI**: Modern gradient design with smooth animations
- **Real-time Chat**: Interactive chat interface with user and bot messages
- **SQL Display**: Shows generated SQL queries with syntax highlighting
- **Copy to Clipboard**: Easily copy SQL queries
- **Connection Status**: Real-time server connection indicator
- **Example Queries**: Click-to-use example questions
- **Metadata Display**: Shows result count, tables used, and execution time
- **Error Handling**: Clear error messages and graceful degradation
- **Responsive Design**: Works on desktop, tablet, and mobile devices

## Setup Instructions

### 1. Make Sure Backend is Running

The frontend connects to the backend API at `http://localhost:9001`

**Start the backend:**
```bash
cd D:\OryggiAI_Service\Advance_Chatbot
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 9001
```

### 2. Open the Frontend

Simply double-click on `index.html` or open it in your browser:
```bash
# Method 1: Double-click index.html in Windows Explorer

# Method 2: From command line
cd frontend
start index.html
```

The frontend will automatically:
- Check connection to the backend
- Display connection status (Connected/Disconnected)
- Enable/disable input based on connection status

## Usage

### Asking Questions

1. Type your question in natural language in the input box
2. Click the send button or press Enter
3. Wait for the chatbot to:
   - Generate SQL query using Gemini 2.5 Pro
   - Execute the query on the database
   - Return results in natural language

### Example Questions

Click on any of these example questions to try them:
- "How many total employees are in the database?"
- "Show me the top 5 departments with the most employees"
- "How many employees joined in the last 30 days?"
- "List all active employees"

### Understanding Results

Each bot response shows:
- **Answer**: Natural language answer to your question
- **SQL Query**: Generated SQL code (with copy button)
- **Metadata**:
  - Number of results returned
  - Database tables used
  - Query execution time

## File Structure

```
frontend/
├── index.html     # Main HTML file
├── style.css      # All styling and animations
├── app.js         # JavaScript for API communication
└── README.md      # This file
```

## Configuration

### Changing Backend URL

If your backend is running on a different port or server, edit `app.js`:

```javascript
// Line 2 in app.js
const API_BASE_URL = 'http://localhost:9001/api/chat';
```

### Customizing Colors

Edit CSS variables in `style.css`:

```css
:root {
    --primary-color: #4F46E5;    /* Change main color */
    --primary-hover: #4338CA;    /* Change hover color */
    /* ... more variables */
}
```

## Troubleshooting

### Frontend shows "Disconnected"
- Ensure backend is running on port 9001
- Check backend logs for errors
- Verify CORS is properly configured

### Queries timeout
- Check database connection
- Verify FAISS index is loaded
- Look at backend terminal for errors

### Can't click example questions
- Refresh the page
- Check browser console (F12) for JavaScript errors

## Browser Compatibility

Tested on:
- Google Chrome (recommended)
- Microsoft Edge
- Mozilla Firefox
- Safari

## Security Notes

- Frontend runs locally (file://)
- No sensitive data is stored in browser
- All queries go through backend validation
- XSS protection implemented

## Future Enhancements

Planned features:
- Query history
- Export results to CSV/Excel
- Dark mode toggle
- Custom SQL editor
- Saved queries
- Multi-language support

## Support

For issues or questions:
1. Check backend logs: `D:\OryggiAI_Service\Advance_Chatbot\logs\`
2. Verify database connection
3. Review browser console (F12) for errors

## License

Part of Advance Chatbot project
