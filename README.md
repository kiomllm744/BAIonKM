# Disease Portal - EnrichR Analysis

A Flask-based web application for disease-herb gene enrichment analysis with AI-powered pathway insights.

## Features

- 🔬 Disease-Herb gene overlap analysis
- 📊 EnrichR API integration for pathway enrichment
- 🤖 AI-powered comparative analysis (Gemini 2.0)
- 💊 Support for multiple prescription comparisons
- 🩺 Clinical interview question generation
- 📈 Interactive results visualization

## Local Development

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables:
   ```bash
   export GEMINI_API_KEY=your_api_key_here
   ```
4. Run the app:
   ```bash
   python app.py
   ```

## Deployment

### Render.com (Recommended)

1. Push your code to GitHub
2. Go to [Render.com](https://render.com) and sign up
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Set environment variables:
   - `GEMINI_API_KEY`: Your Google Gemini API key
6. Deploy!

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key for AI analysis | Yes |
| `FLASK_ENV` | Set to `production` for deployment | No |

## Tech Stack

- **Backend**: Flask, SQLAlchemy
- **Database**: SQLite
- **AI**: Google Gemini 2.0 Flash
- **APIs**: EnrichR, DisGeNET

## License

MIT License
