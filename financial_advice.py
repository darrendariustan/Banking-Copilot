import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging
import yahooquery as yq
from yahooquery import Ticker
import time
import os
from openai import OpenAI
import sys
import re
from audio_utils import text_to_speech, transcribe_audio
from streamlit_mic_recorder import mic_recorder
from langchain.memory import ConversationBufferWindowMemory

# Set up logging
logging.basicConfig(
    filename='financial_advice.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOGGER = logging.getLogger('FinancialAdvice')

class FinancialAdvice:
    """Class to handle the integrated financial advice feature."""
    
    def __init__(self, account_dashboard=None, chatbot=None):
        """Initialize the financial advice module with references to other system components."""
        self.account_dashboard = account_dashboard
        self.chatbot = chatbot
        
        # Stock indices to track in the context panel
        self.market_indices = {
            "^GSPC": "S&P 500",
            "^DJI": "Dow Jones",
            "^IXIC": "NASDAQ",
            "^FTSE": "FTSE 100"
        }
        
        # Cache for market data
        self.market_data_cache = {}
        self.market_data_timestamp = None
        
        # Chat history
        if "financial_advice_messages" not in st.session_state:
            st.session_state.financial_advice_messages = []
            
        # Conversation memory for each user
        # Create user-specific memory key
        self.memory_key = None
        if "current_user_id" in st.session_state:
            self.memory_key = f"financial_advice_memory_{st.session_state.current_user_id}"
            # Initialize user's conversation memory if it doesn't exist
            if self.memory_key not in st.session_state:
                st.session_state[self.memory_key] = ConversationBufferWindowMemory(k=5)
            
        # Audio response flag - ensure this is initialized
        if "audio_file" not in st.session_state:
            st.session_state.audio_file = None
            
        # LLM client
        try:
            self.openai_client = OpenAI()
        except Exception as e:
            LOGGER.error(f"Error initializing OpenAI client: {e}")
            self.openai_client = None
    
    def get_market_data(self, refresh=False):
        """Get current market data for major indices using yahooquery."""
        # Check if we have recent data in cache (refresh every 5 minutes)
        current_time = time.time()
        
        if not refresh and self.market_data_timestamp and current_time - self.market_data_timestamp < 300:
            return self.market_data_cache
        
        try:
            # Get data for major indices
            tickers = list(self.market_indices.keys())
            data = Ticker(tickers)
            
            # Get quote data
            quotes = data.price
            
            # Process and format the data
            market_data = []
            for ticker, name in self.market_indices.items():
                if ticker in quotes and isinstance(quotes[ticker], dict):
                    quote_data = quotes[ticker]
                    
                    # Extract relevant information
                    current_price = quote_data.get('regularMarketPrice', 0)
                    previous_close = quote_data.get('regularMarketPreviousClose', 0)
                    change = current_price - previous_close
                    percent_change = (change / previous_close * 100) if previous_close else 0
                    
                    market_data.append({
                        'index': name,
                        'ticker': ticker,
                        'price': current_price,
                        'change': change,
                        'percent_change': percent_change
                    })
            
            # Update cache
            self.market_data_cache = market_data
            self.market_data_timestamp = current_time
            
            return market_data
        
        except Exception as e:
            LOGGER.error(f"Error fetching market data: {e}")
            return self.market_data_cache if self.market_data_cache else []
    
    def get_user_portfolio_summary(self, user_id):
        """Get a summary of the user's financial portfolio."""
        portfolio_summary = {
            'total_assets': 0,
            'total_liabilities': 0,
            'net_worth': 0,
            'cash': 0,
            'investments': 0,
            'accounts': []
        }
        
        try:
            # Get user accounts
            if self.account_dashboard:
                accounts = self.account_dashboard.get_user_accounts(user_id)
                
                if not accounts.empty:
                    # Categorize and sum up account balances
                    for _, account in accounts.iterrows():
                        account_type = account.get('account_type', '')
                        balance = account.get('balance', 0)
                        
                        # Convert to numeric if it's a string
                        if isinstance(balance, str):
                            balance = pd.to_numeric(balance, errors='coerce') or 0
                        
                        # Add account to the list
                        portfolio_summary['accounts'].append({
                            'account_id': account.get('account_id', ''),
                            'account_name': account.get('account_name', ''),
                            'account_type': account_type,
                            'balance': balance
                        })
                        
                        # Categorize based on account type
                        if account_type in ['CHECKING', 'REGULAR_SAVINGS', 'HIGH_YIELD_SAVINGS', 'TRAVEL_SAVINGS']:
                            portfolio_summary['cash'] += balance
                            portfolio_summary['total_assets'] += balance
                        elif account_type in ['INVESTMENT']:
                            portfolio_summary['investments'] += balance
                            portfolio_summary['total_assets'] += balance
                        elif account_type in ['MORTGAGE']:
                            portfolio_summary['total_liabilities'] += balance
                
                # Calculate net worth
                portfolio_summary['net_worth'] = portfolio_summary['total_assets'] - portfolio_summary['total_liabilities']
            
            return portfolio_summary
        
        except Exception as e:
            LOGGER.error(f"Error getting user portfolio summary: {e}")
            return portfolio_summary
    
    def get_transaction_insights(self, user_id, days=90):
        """Get insights from user transactions for financial advice context."""
        insights = {
            'monthly_income': 0,
            'monthly_expenses': 0,
            'savings_rate': 0,
            'top_expense_categories': [],
            'unusual_spending': []
        }
        
        try:
            if self.account_dashboard:
                # Get monthly income vs expenses
                monthly_summary = self.account_dashboard.get_monthly_income_vs_expenses(user_id, months=3)
                
                if not monthly_summary.empty:
                    # Calculate average monthly income and expenses
                    insights['monthly_income'] = monthly_summary['income'].mean()
                    insights['monthly_expenses'] = monthly_summary['expenses'].mean()
                    
                    # Calculate savings rate
                    if insights['monthly_income'] > 0:
                        insights['savings_rate'] = (insights['monthly_income'] - insights['monthly_expenses']) / insights['monthly_income'] * 100
                
                # Get spending by category
                spending_by_category = self.account_dashboard.get_user_spending_by_category(user_id, days=days)
                
                if not spending_by_category.empty:
                    # Get top expense categories
                    top_categories = spending_by_category.head(5)
                    insights['top_expense_categories'] = top_categories.to_dict('records')
            
            return insights
        
        except Exception as e:
            LOGGER.error(f"Error getting transaction insights: {e}")
            return insights
    
    def get_investment_recommendations(self, user_id, risk_profile="moderate"):
        """Generate investment recommendations based on user portfolio and risk profile."""
        # This would typically call the LLM with appropriate context
        # For now, return placeholder recommendations
        
        recommendations = {
            'allocation': {
                'stocks': 60,
                'bonds': 30,
                'cash': 10
            },
            'specific_recommendations': []
        }
        
        # Adjust allocation based on risk profile
        if risk_profile == "conservative":
            recommendations['allocation'] = {'stocks': 40, 'bonds': 50, 'cash': 10}
        elif risk_profile == "aggressive":
            recommendations['allocation'] = {'stocks': 80, 'bonds': 15, 'cash': 5}
        
        return recommendations
    
    def generate_financial_advice(self, user_id, user_query, audio_output=False):
        """Generate financial advice based on user query and financial data."""
        try:
            # Get user portfolio data for context
            portfolio = self.get_user_portfolio_summary(user_id)
            
            # Get transaction insights
            transaction_insights = self.get_transaction_insights(user_id)
            
            # Get market data for context
            market_data = self.get_market_data()
            
            # Construct the context for the LLM
            context = {
                "portfolio": portfolio,
                "transaction_insights": transaction_insights,
                "market_data": market_data,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Convert context to a text representation for the prompt
            context_text = f"""
Financial Context:
- Net Worth: ${portfolio['net_worth']:,.2f}
- Total Assets: ${portfolio['total_assets']:,.2f}
- Total Liabilities: ${portfolio['total_liabilities']:,.2f}
- Cash: ${portfolio['cash']:,.2f}
- Investments: ${portfolio['investments']:,.2f}
- Monthly Income (avg): ${transaction_insights['monthly_income']:,.2f}
- Monthly Expenses (avg): ${transaction_insights['monthly_expenses']:,.2f}
- Savings Rate: {transaction_insights['savings_rate']:.1f}%

Market Context:
"""
            
            # Add market data to context text
            for index_data in market_data:
                context_text += f"- {index_data['index']}: {index_data['price']:,.2f} ({'+' if index_data['percent_change'] >= 0 else ''}{index_data['percent_change']:.2f}%)\n"
            
            # Get conversation memory if available
            memory_key = f"financial_advice_memory_{user_id}"
            conversation_history = ""
            
            if memory_key in st.session_state:
                # Get the conversation history
                memory = st.session_state[memory_key]
                # Extract memory variables (which include the conversation history)
                memory_variables = memory.load_memory_variables({})
                conversation_history = memory_variables.get("history", "")
            
            # Construct the full prompt for the LLM
            prompt = f"""
You are a financial advisor assistant. The user has the following financial context:

{context_text}

{('Previous conversation:' + conversation_history) if conversation_history else 'This is a new conversation.'}

Based on this context and any previous conversation, please provide helpful, personalized financial advice in response to the user's query:
"{user_query}"

Important guidelines:
1. Be concise and practical.
2. Include specific recommendations relevant to their financial situation.
3. Mention relevant market context where appropriate.
4. Add appropriate disclaimers about financial advice.
5. Focus on helping with their specific request.
6. Maintain continuity with previous responses if relevant.
"""
            
            # Call LLM if available
            if self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system", "content": "You are a financial advisor assistant."},
                              {"role": "user", "content": prompt}],
                    max_tokens=500
                )
                
                advice_text = response.choices[0].message.content
            else:
                # Fallback if OpenAI client not available
                advice_text = "I'm unable to provide personalized financial advice at the moment. Please try again later."
            
            # Update conversation memory
            if memory_key in st.session_state:
                memory = st.session_state[memory_key]
                memory.save_context(
                    {"input": user_query},
                    {"output": advice_text}
                )
            
            # Generate audio if requested
            if audio_output:
                try:
                    # Log the audio generation attempt
                    LOGGER.info(f"Generating audio response for query: '{user_query[:30]}...'")
                    
                    # Use the existing text_to_speech function
                    text_to_speech(advice_text)
                    
                    # Check if file was created with detailed verification
                    if os.path.exists('response.wav'):
                        file_size = os.path.getsize('response.wav')
                        # Set flag to play audio in UI
                        st.session_state.audio_file = 'response.wav'
                        LOGGER.info(f"Audio response generated successfully: {len(advice_text)} chars, file size: {file_size} bytes")
                    else:
                        LOGGER.error("Failed to create audio file despite no exception")
                except Exception as e:
                    LOGGER.error(f"Error generating audio response: {e}")
                    # Ensure audio_file is set to None in case of an error
                    st.session_state.audio_file = None
            
            return advice_text
        
        except Exception as e:
            LOGGER.error(f"Error generating financial advice: {e}")
            return f"I encountered an error while generating financial advice. Please try again later."
    
    def render_market_context_panel(self):
        """Render the market context panel with current market data."""
        st.subheader("Market Snapshot")
        
        # Get market data
        market_data = self.get_market_data()
        
        if market_data:
            # Create a stylish table for market indices
            market_df = pd.DataFrame(market_data)
            
            # Style the market data display
            for idx, row in market_df.iterrows():
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.write(f"**{row['index']}**")
                with col2:
                    st.write(f"{row['price']:,.2f}")
                with col3:
                    change_text = f"{'+' if row['percent_change'] >= 0 else ''}{row['percent_change']:.2f}%"
                    change_color = "green" if row['percent_change'] >= 0 else "red"
                    st.markdown(f"<span style='color:{change_color}'>{change_text}</span>", unsafe_allow_html=True)
            
            # Add last updated time
            if self.market_data_timestamp:
                st.caption(f"Last updated: {datetime.fromtimestamp(self.market_data_timestamp).strftime('%H:%M:%S')}")
                
                # Remove refresh button but keep auto-refresh functionality
                # Market data will still refresh automatically based on cache timeout
        else:
            st.info("Market data is currently unavailable.")
    
    def render_portfolio_summary(self, user_id, user_fullname):
        """Render the user's portfolio summary."""
        st.subheader(f"{user_fullname}'s Financial Overview")
        
        # Get user portfolio data
        portfolio = self.get_user_portfolio_summary(user_id)
        
        # Create a summary card
        summary_cols = st.columns(3)
        with summary_cols[0]:
            st.metric("Net Worth", f"${portfolio['net_worth']:,.2f}")
        with summary_cols[1]:
            st.metric("Total Assets", f"${portfolio['total_assets']:,.2f}")
        with summary_cols[2]:
            st.metric("Total Liabilities", f"${portfolio['total_liabilities']:,.2f}")
        
        # Asset allocation chart
        if portfolio['total_assets'] > 0:
            st.subheader("Asset Allocation")
            
            # Prepare data for the pie chart
            labels = ["Cash", "Investments"]
            values = [portfolio['cash'], portfolio['investments']]
            
            # Create the pie chart
            fig = px.pie(
                values=values,
                names=labels,
                title="Asset Allocation",
                color_discrete_sequence=px.colors.sequential.Blues,
                hole=0.4
            )
            
            # Update layout
            fig.update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
                margin=dict(t=30, b=10, l=10, r=10)
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    def get_top_performing_stocks(self, limit=5, market="us_market"):
        """Get top performing stocks by percentage change."""
        try:
            # Define lists of popular stocks to query
            popular_stocks = {
                "us_market": [
                    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA", 
                    "JPM", "V", "WMT", "PG", "JNJ", "UNH", "HD", "BAC",
                    "MA", "XOM", "PFE", "DIS", "NFLX", "ADBE", "PYPL", "CRM",
                    "INTC", "VZ", "CSCO", "CMCSA", "PEP", "KO", "T"
                ]
            }
            
            # Get stock data for the selected market
            stocks_to_query = popular_stocks.get(market, popular_stocks["us_market"])
            
            # Fetch data using yahooquery
            ticker_data = Ticker(stocks_to_query)
            quotes = ticker_data.price
            
            # Process the data to get percentage changes
            stock_performance = []
            
            for symbol, data in quotes.items():
                if isinstance(data, dict):
                    # Extract relevant metrics
                    try:
                        current_price = data.get('regularMarketPrice', 0)
                        previous_close = data.get('regularMarketPreviousClose', 0)
                        
                        if previous_close and current_price:
                            percent_change = ((current_price - previous_close) / previous_close) * 100
                            
                            # Add other useful information
                            market_cap = data.get('marketCap', 0)
                            name = data.get('shortName', symbol)
                            
                            stock_performance.append({
                                'symbol': symbol,
                                'name': name,
                                'price': current_price,
                                'percent_change': percent_change,
                                'market_cap': market_cap
                            })
                    except Exception as e:
                        LOGGER.error(f"Error processing data for {symbol}: {e}")
            
            # Sort by percentage change (descending) and get the top stocks
            top_stocks = sorted(stock_performance, key=lambda x: abs(x['percent_change']), reverse=True)[:limit]
            
            return top_stocks
            
        except Exception as e:
            LOGGER.error(f"Error fetching top performing stocks: {e}")
            return []

    def get_stock_history(self, symbols, period="1mo"):
        """Get historical stock data for the specified symbols."""
        try:
            # Make sure we have a list of symbols
            if isinstance(symbols, str):
                symbols = [symbols]
            
            # Fetch historical data
            ticker_data = Ticker(symbols)
            history = ticker_data.history(period=period)
            
            # Process and return the data
            return history
        
        except Exception as e:
            LOGGER.error(f"Error fetching stock history: {e}")
            return pd.DataFrame()

    def render_top_stocks(self, limit=5):
        """Render visualization of top performing stocks by percentage change."""
        st.subheader("Top Performing Stocks")
        
        with st.spinner("Fetching latest stock data..."):
            # Get top performing stocks
            top_stocks = self.get_top_performing_stocks(limit=limit)
            
            if not top_stocks:
                st.info("Unable to fetch stock data at this time. Please try again later.")
                return
            
            # Display the top stocks in a table
            cols = st.columns([3, 2, 2])
            cols[0].write("**Stock**")
            cols[1].write("**Price**")
            cols[2].write("**Change**")
            
            for stock in top_stocks:
                col1, col2, col3 = st.columns([3, 2, 2])
                
                with col1:
                    st.write(f"{stock['name']} ({stock['symbol']})")
                
                with col2:
                    st.write(f"${stock['price']:,.2f}")
                
                with col3:
                    change = stock['percent_change']
                    change_text = f"{'+' if change >= 0 else ''}{change:.2f}%"
                    change_color = "green" if change >= 0 else "red"
                    st.markdown(f"<span style='color:{change_color}'>{change_text}</span>", unsafe_allow_html=True)
            
            # Get symbols for the top stocks
            symbols = [stock['symbol'] for stock in top_stocks]
            
            # Get historical data for these stocks
            history = self.get_stock_history(symbols)
            
            if not history.empty:
                # Prepare data for plotting
                st.subheader("30-Day Price History")
                
                # Create normalized line chart to show percentage change
                fig = go.Figure()
                
                for symbol in symbols:
                    # Filter data for this symbol
                    if isinstance(history.index, pd.MultiIndex):
                        stock_data = history.xs(symbol, level=0)
                    else:
                        # If not a MultiIndex, filter using the symbol column
                        stock_data = history[history['symbol'] == symbol]
                    
                    if not stock_data.empty and 'close' in stock_data.columns:
                        # Get the first day's close price to use as baseline
                        baseline_price = stock_data['close'].iloc[0]
                        
                        # Calculate percentage change from day 0
                        normalized_data = ((stock_data['close'] / baseline_price) - 1) * 100
                        
                        fig.add_trace(go.Scatter(
                            x=stock_data.index,
                            y=normalized_data,
                            mode='lines',
                            name=symbol
                        ))
                
                # Update layout
                fig.update_layout(
                    title="30-Day Relative Performance (% Change)",
                    xaxis_title="Date",
                    yaxis_title="% Change from Day 0",
                    hovermode="x unified",
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    ),
                    # Add a zero line for reference
                    yaxis=dict(
                        zeroline=True,
                        zerolinewidth=1,
                        zerolinecolor='gray'
                    )
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Also provide the original absolute price chart for reference
                with st.expander("View Absolute Price Chart"):
                    fig_abs = go.Figure()
                    
                    for symbol in symbols:
                        # Filter data for this symbol again
                        if isinstance(history.index, pd.MultiIndex):
                            stock_data = history.xs(symbol, level=0)
                        else:
                            stock_data = history[history['symbol'] == symbol]
                        
                        if not stock_data.empty and 'close' in stock_data.columns:
                            fig_abs.add_trace(go.Scatter(
                                x=stock_data.index,
                                y=stock_data['close'],
                                mode='lines',
                                name=symbol
                            ))
                    
                    fig_abs.update_layout(
                        title="30-Day Close Price Trends (Absolute $)",
                        xaxis_title="Date",
                        yaxis_title="Close Price ($)",
                        hovermode="x unified",
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                    )
                    
                    st.plotly_chart(fig_abs, use_container_width=True)
            else:
                st.info("Historical price data is currently unavailable.")
    
    def render_chat_interface(self, user_id, user_fullname):
        """Render the main chat interface for financial advice."""
        st.subheader("Ask for Financial Advice")
        
        # Initialize chat history if it doesn't exist
        if "financial_advice_messages" not in st.session_state:
            st.session_state.financial_advice_messages = []
            
        # Audio response handling with improved verification
        if st.session_state.audio_file:
            audio_file_path = st.session_state.audio_file
            
            if os.path.exists(audio_file_path):
                try:
                    # Log attempt to play audio
                    file_size = os.path.getsize(audio_file_path)
                    LOGGER.info(f"Attempting to play audio response, file size: {file_size} bytes")
                    
                    # Load and play the audio file with proper resource management
                    with open(audio_file_path, "rb") as audio_file:
                        audio_bytes = audio_file.read()
                    
                    # Display audio player with clear label
                    st.write("🔊 Voice Response:")
                    st.audio(audio_bytes, format="audio/wav")
                    
                    # Reset the flag after playing
                    st.session_state.audio_file = None
                    LOGGER.info("Audio response played successfully")
                except Exception as e:
                    LOGGER.error(f"Error playing audio response: {e}")
                    st.session_state.audio_file = None
            else:
                # Audio file doesn't exist despite flag being set
                LOGGER.error(f"Audio file {audio_file_path} not found despite audio_file={st.session_state.audio_file}")
                st.session_state.audio_file = None
        
        # Display chat messages
        for message in st.session_state.financial_advice_messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        
        # Chat input and voice recording
        chat_cols = st.columns([4, 1])
        
        with chat_cols[0]:
            # Text input for user query
            user_input = st.chat_input(
                "Ask about your finances, investments, or market trends...",
                key="financial_advice_input"
            )
        
        # Voice recording using streamlit-mic-recorder
        with chat_cols[1]:
            voice_recording = mic_recorder(
                start_prompt="🎤 Start",
                stop_prompt="🔴 Stop",
                key="financial_advice_voice"
            )
            
            # Process voice recording if available
            if voice_recording:
                # Transcribe the audio
                transcribed_text = transcribe_audio(voice_recording)
                
                if transcribed_text:
                    # Add user message to chat history
                    st.session_state.financial_advice_messages.append({"role": "user", "content": transcribed_text})
                    
                    # Display user message
                    with st.chat_message("user"):
                        st.write(transcribed_text)
                    
                    # Generate response
                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            response = self.generate_financial_advice(user_id, transcribed_text, audio_output=True)
                            st.write(response)
                    
                    # Add assistant response to chat history
                    st.session_state.financial_advice_messages.append({"role": "assistant", "content": response})
                    
                    # Force a rerun to show the audio player
                    st.rerun()
        
        # Process text input
        if user_input:
            # Add user message to chat history
            st.session_state.financial_advice_messages.append({"role": "user", "content": user_input})
            
            # Display user message
            with st.chat_message("user"):
                st.write(user_input)
            
            # Generate response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = self.generate_financial_advice(user_id, user_input, audio_output=True)
                    st.write(response)
            
            # Add assistant response to chat history
            st.session_state.financial_advice_messages.append({"role": "assistant", "content": response})
            
            # Force a rerun to show the audio player (same as voice input)
            st.rerun()
    
    def ensure_user_state_initialized(self, user_id):
        """
        Ensure user-specific state variables are properly initialized.
        This helps maintain consistent state across different users and sessions.
        """
        # Initialize user-specific memory key
        memory_key = f"financial_advice_memory_{user_id}"
        if memory_key not in st.session_state:
            LOGGER.info(f"Initializing conversation memory for user {user_id}")
            st.session_state[memory_key] = ConversationBufferWindowMemory(k=5)
            
        # Ensure audio response flag is initialized
        if "audio_file" not in st.session_state:
            st.session_state.audio_file = None
            
        # Initialize financial advice messages if needed
        if "financial_advice_messages" not in st.session_state:
            st.session_state.financial_advice_messages = []
            
        # Log current state for debugging
        LOGGER.debug(f"User state initialized: user_id={user_id}, audio_file={st.session_state.audio_file}")
        
    def render_financial_advice_page(self, user_id, user_fullname):
        """Render the full financial advice page with all components."""
        st.title("Financial Advice")
        
        # Ensure user state is properly initialized
        self.ensure_user_state_initialized(user_id)
        
        # Layout: Context panel at top, chat interface below
        with st.container():
            panel_cols = st.columns([2, 3])
            
            # Left column: Market context panel
            with panel_cols[0]:
                self.render_market_context_panel()
            
            # Right column: Portfolio summary
            with panel_cols[1]:
                self.render_portfolio_summary(user_id, user_fullname)
        
        # Top stocks visualization (replacing investment recommendations)
        self.render_top_stocks(limit=5)
        
        # Chat interface
        self.render_chat_interface(user_id, user_fullname)

def render_financial_advice_page(user_id="user123", user_fullname="Darren Smith"):
    """Renders the financial advice page with an instance of the FinancialAdvice class."""
    # This function would be called from app.py when the user selects "Financial Advice"
    
    # Import other components as needed
    from account_dashboard import AccountDashboard
    
    try:
        # Initialize components
        account_dashboard = AccountDashboard()
        
        # Load user data
        account_dashboard.load_data()
        
        # Create the financial advice instance
        financial_advice = FinancialAdvice(account_dashboard=account_dashboard)
        
        # Ensure user has conversation memory and proper state initialization
        financial_advice.ensure_user_state_initialized(user_id)
        
        # Render the financial advice page
        financial_advice.render_financial_advice_page(user_id, user_fullname)
        
    except Exception as e:
        LOGGER.error(f"Error rendering financial advice page: {e}")
        st.error("An error occurred while loading the financial advice page. Please try again later.")

if __name__ == "__main__":
    # This allows testing the module independently
    render_financial_advice_page() 