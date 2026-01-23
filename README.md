# Disease Portal - Gene Enrichment Analysis 🧬

A Streamlit-based web application for disease-herb gene enrichment analysis with AI-powered pathway insights.

## Features

- 🔬 Disease-Herb gene overlap analysis
- 📊 EnrichR API integration for pathway enrichment
- 🤖 AI-powered comparative analysis (Gemini 2.0 Flash)
- 💊 Support for multiple prescription comparisons
- 🩺 Clinical interview question generation
- 📈 Interactive results visualization
- 🗄️ Database explorer with search functionality

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/umarashraf914/Systems_Biology.git
   cd Systems_Biology
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Download the database** (if not present)
   ```bash
   python download_db.py
   ```

4. **Set environment variables**
   ```bash
   # Windows PowerShell
   $env:GEMINI_API_KEY="your_api_key_here"
   
   # Linux/Mac
   export GEMINI_API_KEY=your_api_key_here
   ```

5. **Run the app**
   ```bash
   streamlit run streamlit_app.py
   ```

6. Open http://localhost:8501 in your browser

## Deployment

### Streamlit Cloud (Easiest) ⭐

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click "New app" and select your repository
4. Set the main file to `streamlit_app.py`
5. Add secrets in the Advanced settings:
   ```toml
   GEMINI_API_KEY = "your_api_key_here"
   ```
6. Deploy!

### Render.com

1. Push your code to GitHub
2. Go to [Render.com](https://render.com) and create a new Web Service
3. Connect your GitHub repository
4. Set build command: `pip install -r requirements.txt && python download_db.py`
5. Set start command: `streamlit run streamlit_app.py --server.port $PORT --server.headless true`
6. Add environment variable: `GEMINI_API_KEY`
7. Deploy!

### Railway.app

1. Push to GitHub
2. Go to [Railway.app](https://railway.app)
3. Connect repository and add `GEMINI_API_KEY` variable
4. Deploy automatically!

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key for AI analysis | Yes (for AI features) |

## Tech Stack

- **Frontend**: Streamlit
- **Database**: SQLite
- **AI**: Google Gemini 2.0 Flash
- **APIs**: EnrichR, DisGeNET
- **Data**: BATMAN-TCM (Herb-Gene associations)

## Project Structure

```
├── streamlit_app.py      # Main Streamlit application
├── services.py           # Core analysis services
├── llm_service.py        # AI/LLM integration
├── config.py             # Configuration settings
├── models.py             # Database models
├── download_db.py        # Database download script
├── diseaseportal.db      # SQLite database (not in git)
├── requirements.txt      # Python dependencies
└── .streamlit/
    └── config.toml       # Streamlit configuration
```

## License

MIT License

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
