# AletaBanc Copilot

A secure banking chatbot application built to help customers manage their finances. It provides a voice and text interface to query account information, transactions, scheduled payments, and financial news.

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

1. Install required packages:
   ```
   pip install -r requirements.txt
   ```

2. Run the application:
   ```
   streamlit run app.py
   ```

3. Access the application in your web browser at `http://localhost:8501`

## Sample Queries

Here are some example queries you can try:

- "What's my account balance?"
- "Show me my transactions from last week."
- "When is my next mortgage payment?"
- "What are my scheduled payments for this month?"
- "Show me spending by category for the past 30 days."
- "What's the latest financial news?"
- "Give me investment advice based on current market trends."

## Security Features

- Authentication required to access any banking information
- Users can only view their own accounts
- Family mortgage information is only accessible to parents
- Session management with auto-logout functionality

## Troubleshooting

If you encounter issues with the audio features:
- Ensure your browser has microphone permissions enabled
- Make sure your audio output is working properly

For any other issues, check the logs in `chatbot.log`. 
