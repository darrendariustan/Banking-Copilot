# AletaBank Copilot

🚀 **Visit the Live App:** [https://banking-copilot.onrender.com/](https://banking-copilot.onrender.com/) 

*Note: The live app might be unstable due to a free backend server on render, it would be strongly recommended to download all files under the Section 'Setup and Deployment' instead. Otherwise watch the demo video below.*

A secure banking chatbot application built to help customers manage their finances. It provides a voice and text interface to query account information, transactions, scheduled payments, and financial news.

## 🎥 Demo Video

Watch our application in action! Check out the demo video to see the banking copilot's features and capabilities:

📹 **[PDAI_DemoR1.webm](./PDAI_DemoR1.webm)** - Partial walkthrough of the banking copilot functionality

*Note: You can download the video file to view it locally, or view it directly on GitHub.*

## LLM Model For Intent Recognition
1. First Layer: Uses intent embeddings from csv files, combined with sentence transformer methods with the Mini L6 LM v2 Model
2. Second Layer: If first layer fails, intent recognition is done through pattern recognition via regex matching
3. Third Layer: As a fallback for general inquiries, the chatbot is also connected to OpenAI and Yahooquery APIs (while also relying on its native Mini L6 LM v2 Model)

## Features

- **User Authentication**: Secure login system to protect user data
- **Voice & Text Interface**: Interact with the chatbot through voice or text
- **Financial Data Access**: View account balances, transactions, and scheduled payments
- **Financial News**: Get relevant financial news and investment insights
- **Account Security**: Users can only access their own accounts
- **Family Finance Management**: Parents can view shared mortgage information

## Demo Users

For demonstration purposes, the following users are available:

- Darren Smith (USR001)
- Maria Smith (USR002)
- Enric Smith (USR003)
- Randy Smith (USR004)
- Victor Smith (USR005)

Demo password format: firstname + last 3 digits of the user ID
(e.g., password for USR001 is `darren001`)

## Setup and Deployment

### 1. Verify Python Version Compatibility
Before installing packages, **ensure you are using a compatible Python version**:
- For example, if your project requires `torch==2.1.2`, use Python **3.10** or **3.11**.
- If you're using Python **3.12** or newer, update your dependencies (e.g., use `torch>=2.4.0`) or downgrade your Python version accordingly.
- Check your Python version with:
  ```
  python --version
  ```
### 2. Clone the Repository
Clone the project repository from GitHub:
   ```
   git clone https://github.com/darrendariustan/Banking-Copilot.git
   cd Banking-Copilot
   ```

### 3. Create a Virtual Environment
Create and activate a virtual environment to isolate your project's dependencies:
- On Windows (PowerShell):
  ```
  python -m venv venv
  .\venv\Scripts\activate
  ```
- On macOS/Linux:
  ```
  python -m venv venv
  python3 -m venv venv
  source venv/bin/activate
  ```

### 4. Install Dependencies
Install the required packages using `requirements.txt`: 
   ```
   pip install -r requirements.txt
   ```
Note:
If you encounter errors such as:
- `ModuleNotFoundError: No module named 'cryptography'`
- or conflicting package versions like for `langchain` and its dependencies

Try the following:
- For missing modules, install them manually (e.g., `pip install cryptography`).
- If dependency conflicts arise, consider letting pip automatically resolve versions by removing strict version pins (or updating them to known compatible versions).
- For issues with PyTorch, ensure your Python version matches the required compatibility or upgrade to a supported torch version (e.g., use `torch>=2.4.0` if using Python 3.12). Again from Point 1, it will be best to use Python 3.11.9.

### 5. Running the Application
After all dependencies are installed, start your Streamlit app with:
   ```
   streamlit run app.py
   ```
Your app should now be up and running!

## Sample Queries

Here are some example queries you can try:

- "What is my current family mortgage balance?"
- "What are some areas I can reduce spending on based on my spending analytics?"
- "How much do I have in my regular savings account?"
- "Based on my savings balance, what would you recommend me to invest in?"

## Security Features

- Authentication required to access any banking information
- Users can only view their own accounts
- Family mortgage information is only accessible to the Father
- Session management with auto-logout functionality

## Project Structure

```
Banking_Copilot/
├── app.py                          # Main Streamlit application entry point
├── requirements.txt                # Python dependencies
├── README.md                       # This file
│
├── core/                           # Core application utilities
│   ├── __init__.py
│   ├── auth.py                    # Authentication logic
│   ├── ui_utils.py                # UI styling and image utilities
│   └── session_utils.py           # Session state management
│
├── handlers/                       # Message processing handlers
│   ├── __init__.py
│   ├── chat_handler.py            # Text message processing
│   └── voice_handler.py           # Voice/audio message processing
│
├── pages/                          # Page rendering modules
│   ├── __init__.py
│   ├── account_overview.py         # Account Overview page
│   ├── money_transfer.py           # Money Transfer page
│   └── financial_advice.py        # Financial Advice page
│
├── modules/                        # Business logic modules (recommended location)
│   ├── chatbot.py                 # ChatBot class and NLP functionality
│   ├── account_dashboard.py        # Account dashboard functionality
│   ├── audio_utils.py             # Audio transcription and TTS
│   ├── financial_advice.py        # Financial advice logic
│   └── money_transfer.py          # Money transfer logic
│
├── data/                           # Data files
│   ├── accounts.csv               # Account data
│   ├── users.csv                  # User data
│   ├── transaction_history.csv    # Transaction data
│   ├── scheduled_payments.csv    # Scheduled payments
│   ├── intent.csv                 # Intent classification data
│   └── intent_embeddings.csv      # Intent embeddings
│
├── static/                         # Static assets
│   ├── assets/                    # Images and media
│   │   ├── Aletabank.png
│   │   └── background.jpg
│   └── css/                       # Stylesheets
│       ├── login.css
│       └── theme.css
│
├── config/                         # Configuration files (recommended location)
│   ├── Dockerfile                 # Docker configuration
│   ├── docker-compose.yml         # Docker Compose config
│   └── render.yaml                # Render deployment config
│
├── notebooks/                      # Jupyter notebooks (recommended location)
│   ├── intent_classification.ipynb
│   └── main.ipynb
│
├── docs/                           # Documentation (recommended location)
│   ├── deployment-checklist.md
│   └── FIXES_APPLIED.md
│
└── cache/                          # Cache directory (auto-generated)
    └── [cache files]
```

### Performance Optimizations

The application uses several caching and lazy loading strategies for optimal performance:

- **Resource Caching**: Heavy resources (ChatBot instances, ML models, OpenAI clients) are cached using `@st.cache_resource`
- **Data Caching**: CSV data files are cached for 1 hour using `@st.cache_data(ttl=3600)`
- **Lazy Loading**: ML models (SentenceTransformer) are loaded only when needed, not at module import time
- **Modular Structure**: Code is split into modules that import only when needed, reducing startup time

## Troubleshooting

If you encounter issues with the audio features:
- Ensure your browser has microphone permissions enabled
- Make sure your audio output is working properly

For any other issues, check the logs in `chatbot.log`. 
