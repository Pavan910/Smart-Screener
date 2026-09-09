# Smart Screener

> AI-powered resume parsing and ranking system using Artificial Intelligence

An intelligent talent screening tool that automatically analyzes resumes and ranks candidates against job descriptions using advanced language models.

## Features

- Upload multiple resumes (PDF, DOCX, TXT formats)
- AI-powered resume analysis using Groq (Llama 3.1 70B model)
- Intelligent skill matching and scoring
- Beautiful dashboard UI with candidate rankings
- Fallback to keyword-based matching if API key not configured

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Free Groq API Key

1. Visit [https://console.groq.com/keys](https://console.groq.com/keys)
2. Sign up for a free account
3. Create a new API key

### 3. Configure Environment

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Then edit `.env` and add your Groq API key:

```
GROQ_API_KEY=your_actual_api_key_here
```

### 4. Run the Server

```bash
python server.py
```

Then browse to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Usage

1. Enter a job description in the text area
2. Upload resume files (drag & drop or click to browse)
3. Click "Scan Resumes" to analyze
4. View AI-powered rankings and best candidate recommendations

## Tech Stack

- **Backend**: Python HTTP Server
- **AI**: Groq API (Llama 3.1 70B)
- **Frontend**: Vanilla JavaScript + Modern CSS
- **Resume Parsing**: pypdf, python-docx

## Note

The application works without an API key using keyword-based matching, but for best results, configure the Groq API key for intelligent AI-powered analysis.

## Demo

Upload resumes in various formats (PDF, DOCX, TXT) and watch the AI analyze and rank candidates in real-time.

## How It Works

1. **Resume Upload**: Drag and drop or select multiple resume files
2. **AI Analysis**: Groq's Llama 3.1 70B model analyzes each resume against your job description
3. **Smart Ranking**: Candidates are scored 0-100 based on skill match, experience, and overall fit
4. **Instant Results**: View detailed rankings, skill coverage, and hiring recommendations

## API Information

This project uses the **Groq API** which offers:
- **Free tier** with generous limits
- **Fast inference** with LPU (Language Processing Unit) technology
- **Multiple models**: Llama 3.1, Mixtral, Gemma, and more
- **No credit card required** for signup

Get your free API key at: https://console.groq.com/keys

## Project Structure

```
smart-screener/
├── server.py          # Python backend with Groq integration
├── index.html         # Frontend dashboard
├── app.js            # Client-side logic
├── styles.css        # UI styling
├── requirements.txt  # Python dependencies
├── .env.example      # Environment template
└── data/            # Upload directory (auto-created)
```

## Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests

## License

MIT License - feel free to use this project for personal or commercial purposes.

## Acknowledgments

- [Groq](https://groq.com/) for providing free, fast LLM API access
- Built with Llama 3.1 70B model for intelligent resume analysis

---
