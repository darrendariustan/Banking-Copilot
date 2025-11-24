# Import langchain components with error handling for compatibility
try:
    from langchain.chains import LLMChain
    from langchain.prompts import PromptTemplate
    from langchain.memory import ConversationBufferWindowMemory
except ImportError as e:
    # Try alternative import paths for newer versions
    try:
        from langchain.chains.llm import LLMChain
        from langchain.prompts.prompt import PromptTemplate
        from langchain.memory.buffer_window import ConversationBufferWindowMemory
    except ImportError:
        raise ImportError(f"Could not import required langchain components: {e}. Please check your langchain installation.")

try:
    from langchain_openai import ChatOpenAI
except ImportError as e:
    raise ImportError(f"Could not import ChatOpenAI: {e}. Please install langchain-openai package.")
from sentence_transformers import SentenceTransformer
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import os
import re
import requests
from datetime import datetime, timedelta
import pickle
import logging
import yahooquery as yq
from yahooquery import Ticker
import time
import streamlit as st
from openai import OpenAI

# Set up logging at the module level instead of per instance
# Only configure if not already configured (prevents conflicts with other modules)
if not logging.getLogger().handlers:
    logging.basicConfig(
        filename='chatbot.log',
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
LOGGER = logging.getLogger('BankingChatbot')

@st.cache_resource
def get_sentence_transformer():
    """Cached loading of sentence transformer model"""
    model_name = 'all-MiniLM-L6-v2'
    model = SentenceTransformer(model_name)
    return model

@st.cache_resource
def get_llm():
    """Cached loading of LLM"""
    return ChatOpenAI(temperature=0.3)

# Create cache directory at module level
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

def create_chat_memory(chat_history):
    """Return a ConversationBufferWindowMemory object with a chat history of 6 messages."""
    return ConversationBufferWindowMemory(memory_key="history", chat_memory=chat_history, k=6, input_key="query")

def get_llm_chain(llm, memory):
    """Returns a LLMChain object with a template for a virtual assistant for family banking customer support."""
    template = """
    Act as a virtual assistant for family banking customer support. Your name is Finance Bro.
    You have access to the customers' banking information and should use it when relevant.
    
    The customers consist of Darren and Maria Smith (parents), and their children Enric, Randy, and Victor.
    Each family member has different types of accounts:
    1. REGULAR_SAVINGS - The standard savings account
    2. TRAVEL_SAVINGS - Savings account specifically for travel expenses
    3. HIGH_YIELD_SAVINGS - A higher interest rate savings account
    4. INVESTMENT - Retirement and investment accounts
    The family also has a shared mortgage account (MORTGAGE) that Darren and Maria are paying over 6 years.
    
    IMPORTANT ACCOUNT STRUCTURE:
    1. When a user asks about their "savings account" without being specific, show them ALL their 
       savings accounts (Regular, Travel, and High-Yield) to avoid confusion.
    2. Always provide the specific account name and balance when responding to account inquiries.
    3. CRITICAL INSTRUCTION: You MUST copy-paste the EXACT balance values shown in the context.
       DO NOT round, approximate, or use placeholder values under any circumstances.
       For example, if the account shows $15245.32, you MUST display exactly $15245.32, not $15,000 or $15k.
    4. Include the account ID (e.g., ACC001) when displaying account information.
    5. NEVER modify the account balance values for any reason - show them exactly as provided in the context.
    
    IMPORTANT SECURITY RULES:
    1. Only provide account information to the authenticated user.
    2. Do not share information about other family members' accounts unless asking about the shared mortgage.
    3. If asked about another family member's account, politely decline and explain it's for security reasons.
    4. You can share general family financial metrics with any family member.
    5. The user's identity is: {user_fullname} with ID: {user_id}
    
    If any family member asks about their account information, transactions, scheduled payments, 
    or other banking details, refer to the specific data you have access to rather than giving generic responses.
    
    When providing financial advice, consider the context of a family unit, including shared expenses,
    individual financial goals, children's education planning, and family vacations.
    
    If financial news or investment information is provided, analyze it and incorporate specific insights 
    from the news into your financial advice. Connect market trends to practical recommendations for the family.
    
    {context}
    
    Current conversation:
    {history}
    Human: {query}
    AI:
    """
    prompt = PromptTemplate(template=template, input_variables=['query', 'history', 'context', 'user_fullname', 'user_id'])
    chain = LLMChain(prompt=prompt, llm=llm, memory=memory)
    return chain

# New Intent Analyzer for better query understanding
class IntentAnalyzer:
    """Advanced banking query intent analyzer with parameter extraction."""
    
    def __init__(self):
        self.intents = {
            "Account_Balance": {
                "patterns": [
                    r"balance", r"how much (do|have) I", r"what('s| is) my balance", 
                    r"available funds", r"account total", r"check.*balance"
                ],
                "parameters": ["account_type", "account_id", "specific_account"]
            },
            "Transaction_History": {
                "patterns": [
                    r"transaction", r"spend", r"spent", r"history", r"recent",
                    r"purchases", r"payment history", r"activity"
                ],
                "parameters": ["account_id", "time_period", "transaction_type", "amount", "merchant"]
            },
            "Interest_Rates": {
                "patterns": [
                    r"interest( rate)?s?", r"apy", r"apr", r"earning", r"yield",
                    r"percent(age)?", r"return"
                ],
                "parameters": ["account_type", "account_id", "comparison"]
            },
            "Account_Details": {
                "patterns": [
                    r"details", r"information", r"about my account", r"account info",
                    r"statement", r"summary"
                ],
                "parameters": ["account_id", "account_type"]
            },
            "Scheduled_Payments": {
                "patterns": [
                    r"payment", r"bill", r"scheduled", r"upcoming", r"automatic",
                    r"autopay", r"recurring"
                ],
                "parameters": ["payment_type", "due_date", "amount", "payee"]
            },
            "Mortgage_Info": {
                "patterns": [
                    r"mortgage", r"house", r"loan", r"property", r"real estate", 
                    r"home loan", r"principal", r"refinance"
                ],
                "parameters": ["payment_amount", "interest_rate", "principal", "term"]
            },
            "Investment_Advice": {
                "patterns": [
                    r"invest", r"investing", r"investment", r"portfolio", r"diversify",
                    r"asset allocation", r"retirement", r"stock", r"bond", r"should I invest",
                    r"how much.*invest", r"where.*invest", r"what.*invest"
                ],
                "parameters": ["account_type", "risk_level", "time_horizon", "amount"]
            },
            "Money_Transfer": {
                "patterns": [
                    r"transfer", r"move money", r"send money", r"transfer funds", r"move funds",
                    r"transfer \$", r"move \$", r"send \$", r"from my .* to my", r"between my accounts"
                ],
                "parameters": ["source_account_type", "target_account_type", "amount", "description"]
            },
            "Spending_Analysis": {
                "patterns": [
                    r"spending analytics", r"spending analysis", r"budget analysis", r"cut back", 
                    r"reduce spending", r"expense analysis", r"spending category", r"spending breakdown",
                    r"budget reduction", r"where.*money.*going", r"where.*spending", r"overspending", 
                    r"spending trends", r"expenses? breakdown", r"category.*spend(ing)?", 
                    r"which category", r"spending distribution", r"spending chart"
                ],
                "parameters": ["time_period", "category_name", "amount", "comparison"]
            }
        }
    
    def analyze(self, query):
        """
        Analyze a user query to identify intent and extract parameters.
        
        Args:
            query: The user's question or request
            
        Returns:
            dict: Intent classification and extracted parameters
        """
        query = query.lower()
        matched_intents = {}
        
        # Check each intent
        for intent_name, intent_data in self.intents.items():
            match_count = 0
            for pattern in intent_data["patterns"]:
                if re.search(pattern, query, re.IGNORECASE):
                    match_count += 1
            
            if match_count > 0:
                matched_intents[intent_name] = match_count
        
        # Find best matching intent
        if not matched_intents:
            primary_intent = "General_Query"
            confidence = 0
        else:
            primary_intent = max(matched_intents, key=matched_intents.get)
            confidence = matched_intents[primary_intent] / len(self.intents[primary_intent]["patterns"])
        
        # Extract parameters for the identified intent
        extracted_params = self._extract_parameters(query, primary_intent)
        
        # Secondary intent (if any)
        secondary_intents = []
        for intent, count in matched_intents.items():
            if intent != primary_intent and count > 0:
                secondary_intents.append(intent)
        
        return {
            "primary_intent": primary_intent,
            "confidence": confidence,
            "parameters": extracted_params,
            "secondary_intents": secondary_intents,
            "query": query
        }
    
    def _extract_parameters(self, query, intent_name):
        """Extract parameters from the query based on identified intent."""
        params = {}
        
        if intent_name == "General_Query" or intent_name not in self.intents:
            return params
        
        # Specific patterns for parameter extraction
        account_types = {
            "savings": "REGULAR_SAVINGS",
            "checking": "CHECKING",
            "regular savings": "REGULAR_SAVINGS",
            "high-yield": "HIGH_YIELD_SAVINGS",
            "high yield": "HIGH_YIELD_SAVINGS",
            "travel": "TRAVEL_SAVINGS",
            "retirement": "INVESTMENT",
            "investment": "INVESTMENT",
            "mortgage": "MORTGAGE"
        }
        
        # Look for account types
        if "account_type" in self.intents[intent_name]["parameters"]:
            for key, value in account_types.items():
                if key in query:
                    params["account_type"] = value
                    break
        
        # Money transfer specific extraction
        if intent_name == "Money_Transfer":
            # Extract source and target account types
            source_match = re.search(r'from\s+my\s+([a-zA-Z\-]+(?:\s+[a-zA-Z\-]+)?)\s+(?:account)?', query, re.IGNORECASE)
            target_match = re.search(r'to\s+my\s+([a-zA-Z\-]+(?:\s+[a-zA-Z\-]+)?)\s+(?:account)?', query, re.IGNORECASE)
            
            if source_match:
                source_type = source_match.group(1).lower()
                for key, value in account_types.items():
                    if key in source_type:
                        params["source_account_type"] = value
                        break
            
            if target_match:
                target_type = target_match.group(1).lower()
                for key, value in account_types.items():
                    if key in target_type:
                        params["target_account_type"] = value
                        break
            
            # Extract amount
            amount_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*(?:dollars?)?', query, re.IGNORECASE)
            if amount_match:
                params["amount"] = float(amount_match.group(1))
            
            # Extract description
            description_match = re.search(r'for\s+([a-zA-Z\s]+?)(?:\.|\?|$|expenses)', query, re.IGNORECASE)
            if description_match:
                description = description_match.group(1).strip()
                if description:
                    params["description"] = f"{description} expenses"
            
            # Default values if not found
            if "source_account_type" not in params:
                params["source_account_type"] = "REGULAR_SAVINGS"
            if "target_account_type" not in params:
                params["target_account_type"] = "TRAVEL_SAVINGS"
            if "amount" not in params:
                params["amount"] = None  # Will need to prompt user
        
        # Time period pattern extraction
        if any(param in self.intents[intent_name]["parameters"] for param in ["time_period", "days"]):
            time_period_match = re.search(r'(last|past)\s+(\d+)\s+(day|days|week|weeks|month|months)', query, re.IGNORECASE)
            if time_period_match:
                value = int(time_period_match.group(2))
                unit = time_period_match.group(3).lower()
                
                if 'week' in unit:
                    days = value * 7
                elif 'month' in unit:
                    days = value * 30
                else:
                    days = value
                
                params["time_period"] = {"unit": unit, "value": days}
            else:
                # Default to 30 days if no specific period mentioned
                params["time_period"] = {"unit": "days", "value": 30}
        
        # Specific amount pattern extraction
        if "amount" in self.intents[intent_name]["parameters"] and "amount" not in params:
            amount_match = re.search(r'\$?\s*(\d+(?:\.\d+)?)', query, re.IGNORECASE)
            if amount_match:
                params["amount"] = float(amount_match.group(1))
        
        return params

# Add caching for data loading
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_banking_data():
    """Cached loading of banking datasets from CSV files."""
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    try:
        # Load CSVs with explicit paths for clarity
        transactions = pd.read_csv(os.path.join(data_dir, 'transaction_history.csv'))
        accounts = pd.read_csv(os.path.join(data_dir, 'accounts.csv'))
        users = pd.read_csv(os.path.join(data_dir, 'users.csv'))
        scheduled_payments = pd.read_csv(os.path.join(data_dir, 'scheduled_payments.csv'))
        
        # Convert date columns to datetime
        transactions['date'] = pd.to_datetime(transactions['date'])
        scheduled_payments['next_date'] = pd.to_datetime(scheduled_payments['next_date'])
        
        LOGGER.info(f"Cached {len(accounts)} accounts, {len(transactions)} transactions")
        LOGGER.info(f"Cached {len(users)} users, {len(scheduled_payments)} scheduled payments")
        
        return {
            'transactions': transactions,
            'accounts': accounts,
            'users': users,
            'scheduled_payments': scheduled_payments
        }
    except Exception as e:
        LOGGER.error(f"Error loading banking data: {e}")
        # Return empty dataframes if files don't exist
        return {
            'transactions': pd.DataFrame(),
            'accounts': pd.DataFrame(),
            'users': pd.DataFrame(),
            'scheduled_payments': pd.DataFrame()
        }

# Add consolidated caching for NLP data loading
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_nlp_data():
    """Cached loading of all NLP-related data (intents and embeddings)"""
    intent_data = pd.read_csv('intent.csv')
    embeddings = pd.read_csv('intent_embeddings.csv')
    LOGGER.info(f"Cached NLP data: {len(intent_data)} intents, {embeddings.shape} embeddings")
    return {
        'intent_data': intent_data,
        'embeddings': embeddings
    }

class ChatBot:
    def __init__(self):
        # Initialize all the required components
        self._init_openai_client()
        self._init_intent_classifier()
        self._load_config()
        
    def _init_openai_client(self):
        """Initialize OpenAI client with API key."""
        try:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            if not os.getenv("OPENAI_API_KEY"):
                logging.error("No OpenAI API key found in environment variables")
        except Exception as e:
            logging.error(f"Error initializing OpenAI client: {str(e)}")

    def _init_intent_classifier(self):
        """Initialize the intent classifier based on embeddings."""
        # Load embeddings for intent classification
        try:
            from sentence_transformers import SentenceTransformer
            
            # Load the pre-trained model
            model_name = 'all-MiniLM-L6-v2'
            self.model = SentenceTransformer(model_name)
            
            # Load intent data and embeddings with robust error handling
            try:
                # Try loading with default parameters first
                self.intent_data = pd.read_csv("intent.csv")
            except pd.errors.ParserError as e:
                # If parsing error occurs, try with error handling mode
                logging.warning(f"CSV parsing error, attempting recovery: {str(e)}")
                # Use on_bad_lines parameter for newer pandas versions
                try:
                    self.intent_data = pd.read_csv("intent.csv", on_bad_lines='skip')
                except TypeError:
                    # Fall back to older parameter names for backwards compatibility
                    self.intent_data = pd.read_csv("intent.csv", error_bad_lines=False, warn_bad_lines=True)
                
                # If still empty, try different approach
                if self.intent_data.empty:
                    logging.warning("Trying alternative loading approach for intent data")
                    # Try to load with Python's built-in CSV reader for more control
                    import csv
                    rows = []
                    try:
                        with open("intent.csv", 'r', encoding='utf-8') as f:
                            reader = csv.reader(f)
                            header = next(reader)  # Get header
                            for i, row in enumerate(reader, 2):  # Start from line 2
                                if len(row) >= 2:  # Ensure we have at least 2 columns
                                    rows.append([row[0], row[1]])  # Only take first two columns
                        
                        self.intent_data = pd.DataFrame(rows, columns=['texts', 'intents'])
                    except Exception as csv_err:
                        logging.error(f"Failed to recover using CSV reader: {str(csv_err)}")
            
            # Check if we have valid intent data
            if self.intent_data is None or self.intent_data.empty:
                logging.error("Could not load intent data, using default patterns only")
                # Create minimal fallback intent data
                self.intent_data = pd.DataFrame({
                    'texts': [
                        'What is my account balance?', 
                        'How much do I have in my savings?',
                        'Transfer money between accounts',
                        'Security question',
                        'Customer service'
                    ],
                    'intents': [
                        'Account Inquiries', 
                        'Account Inquiries',
                        'Money Transfer',
                        'Security',
                        'Customer Service'
                    ]
                })
            
            # Extract lists from dataframe
            self.intent_texts = self.intent_data["texts"].tolist()
            self.intent_labels = self.intent_data["intents"].tolist()
            
            # Load pre-computed embeddings if available
            embeddings_loaded = False
            if os.path.exists("intent_embeddings.csv"):
                try:
                    embedded_data = pd.read_csv("intent_embeddings.csv")
                    # Verify dimensions match our intent data
                    if len(embedded_data) == len(self.intent_texts):
                        self.intent_embeddings = embedded_data.values
                        embeddings_loaded = True
                        logging.info(f"Loaded {len(embedded_data)} pre-computed embeddings")
                    else:
                        logging.warning("Embeddings count mismatch with intent data, recomputing")
                except Exception as emb_err:
                    logging.warning(f"Error loading embeddings, will recompute: {str(emb_err)}")
            
            # Compute embeddings if not already loaded
            if not embeddings_loaded:
                logging.info("Computing embeddings for intent classification")
                self.intent_embeddings = self.model.encode(self.intent_texts)
                
                # Save embeddings for future use
                pd.DataFrame(self.intent_embeddings).to_csv("intent_embeddings.csv", index=False)
                
            logging.info("Intent classifier initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing intent classifier: {str(e)}")
            self.model = None
            self.intent_embeddings = None
            
    def _load_config(self):
        """Load configurations for different intents."""
        # Configurations for different intent handlers
        self.config = {
            "Account Inquiries": {
                "system_prompt": """You are a helpful banking assistant specializing in account information.

                When responding to account inquiries:
                1. Check ALL available account types in the user's profile
                2. Match the account name or type mentioned in their query EXACTLY
                3. For balance inquiries, provide the EXACT balance from the account data
                4. If a specific account is mentioned (e.g., "travel savings", "high-yield savings"), 
                   ALWAYS provide information about that exact account
                5. Always use the specific account name and type as shown in their account list
                
                If the user asks about:
                - Account balances: Provide the current balance of the requested account(s)
                - Interest rates: Provide the current rates for their accounts
                - Account details: Share relevant account information
                - Transaction history: Summarize recent transactions
                
                Use the exact account names and types as they appear in the user's account list.
                When asked about a specific account like "travel savings" or "high-yield savings",
                make sure to provide information about that specific account.
                
                Keep your responses professional, helpful, and concise.
                """
            },
            "Transactions": {
                "system_prompt": """You are a helpful banking assistant.
                Help the customer with their transactions, payments, 
                and transfers.
                
                For bill payments, you can:
                - Schedule future payments
                - Set up recurring payments
                - Pay immediately from checking or savings
                
                For money transfers, you can:
                - Transfer between accounts
                - Send money to contacts
                - Wire transfers (with fees)
                
                Keep your responses professional, helpful, and concise.
                """
            },
            "Financial Management": {
                "system_prompt": """You are a helpful banking assistant with
                financial advisory capabilities. Provide guidance on financial 
                management, investments, and savings.
                
                Our current offerings:
                - Savings account: 1.5% APY
                - Money Market: 2.1% APY
                - Certificates of Deposit: 3.0% APY (5-year)
                - Investment accounts (managed by certified advisors)
                
                Financial tips you can share:
                - Budgeting strategies
                - Saving for goals
                - Debt management
                - Investment basics
                
                Keep your responses professional, helpful, and concise.
                """
            },
            "Security": {
                "system_prompt": """You are a helpful banking assistant focused
                on security. Handle the customer's security concerns with 
                utmost priority.
                
                For suspicious activities, always advise:
                - Changing passwords immediately
                - Reviewing recent transactions
                - Contacting fraud department (555-123-4567)
                
                For lost/stolen cards:
                - Report immediately
                - Card will be deactivated
                - Replacement sent within 3-5 business days
                
                Security features available:
                - Two-factor authentication
                - Biometric login
                - Transaction alerts
                
                Keep your responses professional, helpful, and concise.
                """
            },
            "Customer Service": {
                "system_prompt": """You are a helpful banking assistant for
                customer service. Help the customer with their general service
                needs and direct them to the right resources.
                
                Customer service hours:
                - Phone: 24/7
                - Branch: 9AM-5PM weekdays, 9AM-12PM Saturdays
                
                Contact options:
                - Phone: 555-123-4567
                - Email: support@bankname.com
                - Live chat: Available on website 24/7
                
                Common service requests:
                - Password reset
                - Update contact information
                - Dispute transactions
                - Technical support for online/mobile banking
                
                Keep your responses professional, helpful, and concise.
                """
            },
            "Money Transfer": {
                "system_prompt": """You are a helpful banking assistant.
                You specialize in helping customers transfer money between their accounts.
                
                The customer has the following accounts:
                - Checking Account: $5,432.10
                - Savings Account: $12,345.67
                - High-Yield Savings: $7,890.12
                - Travel Fund: $2,500.00
                - Retirement Account: $45,678.90
                
                You can help them transfer any amount between these accounts.
                Be precise about confirming the amount, source account, and destination account.
                
                Keep your responses professional, helpful, and concise.
                """
            },
            "Chart Analysis": {
                "system_prompt": """You are a helpful banking assistant with financial data analysis capabilities.
                You are viewing the customer's account dashboard and can interpret the charts displayed there.
                
                The customer may ask you about:
                
                1. Income vs Expenses chart:
                   - Monthly income: $5,200 on average
                   - Monthly expenses: $4,100 on average
                   - Savings rate: 21% of income
                   - Highest expense month: March ($4,850)
                   - Lowest expense month: January ($3,750)
                
                2. Account Balance Trend:
                   - Current balance: $17,778
                   - 90-day high: $18,400 (February 15)
                   - 90-day low: $15,600 (January 3)
                   - Overall trend: Increasing at ~3% monthly
                
                3. Spending Distribution:
                   - Housing: 35% ($1,435)
                   - Food: 15% ($615)
                   - Transportation: 12% ($492)
                   - Entertainment: 10% ($410)
                   - Utilities: 8% ($328)
                   - Shopping: 12% ($492)
                   - Other: 8% ($328)
                
                4. Mortgage Trend:
                   - Original amount: $250,000
                   - Current balance: $228,400
                   - Paid off: $21,600 (8.6%)
                   - Monthly payment: $1,250
                   - Interest rate: 4.5%
                
                When answering, refer specifically to the data shown in these charts.
                Provide insights about what the data means for their financial health.
                Recommend actions based on the trends you observe.
                
                Keep your responses professional, helpful, and concise.
                """
            },
            "Spending Analysis": {
                "system_prompt": """You are a helpful banking assistant specializing in spending analytics.
                You are viewing the customer's spending distribution chart and can provide actionable insights.
                
                When analyzing spending patterns, consider:
                
                1. Spending Distribution by Category:
                   - Identify categories with the highest spending
                   - Compare spending to typical household benchmarks
                   - Suggest categories where the customer might cut back
                   - Identify unusual or unexpected spending patterns
                
                2. Budget Recommendations:
                   - Recommend specific, actionable steps to reduce spending
                   - Suggest realistic budget goals for each category
                   - Identify potential savings opportunities
                   - Recommend specific categories to focus on first
                
                3. Saving Strategies:
                   - Calculate potential monthly/yearly savings from reductions
                   - Suggest alternative options for high-spending categories
                   - Recommend automated savings approaches
                
                Always reference the specific data shown in their charts.
                Be specific about which categories they should focus on and why.
                Provide concrete advice they can implement immediately.
                
                Keep your responses professional, helpful, and concise.
                """
            },
            "default": {
                "system_prompt": """You are a helpful banking assistant.
                Answer the customer's questions about banking services, accounts,
                and financial matters.
                
                You can help with:
                - Account information
                - Transactions and transfers
                - Financial advice
                - Security concerns
                - Customer service needs
                
                IMPORTANT: When the user asks about account balances or information:
                1. Check ALL available account types in the user's profile (savings, checking, credit card, travel savings, high-yield savings, etc.)
                2. Match the account name or type mentioned in their query exactly
                3. If a specific account is mentioned (e.g., "travel savings", "high-yield savings"), ALWAYS provide information about that exact account
                4. Provide the exact balance for the specific account they asked about
                5. Never say you don't have information about an account if it's listed in their accounts data
                
                Keep your responses professional, helpful, and concise.
                """
            }
        }
        
        # Load specialized handlers
        self._load_money_transfer_handler()

    def _load_money_transfer_handler(self):
        """Load the specialized money transfer handler for that intent."""
        try:
            from money_transfer import MoneyTransfer
            
            # Create a custom handler class since MoneyTransferHandler doesn't exist
            class MoneyTransferHandler:
                def __init__(self):
                    self.money_transfer = MoneyTransfer()
                    
                def handle(self, user_input):
                    """Process money transfer related queries"""
                    return "I can help you transfer money between accounts. Please provide the source account, destination account, and amount."
                    
            self.money_transfer_handler = MoneyTransferHandler()
        except ImportError as e:
            logging.error(f"Error loading money transfer handler: {str(e)}")
            # Create a dummy handler that returns a helpful message
            class MoneyTransferHandler:
                def handle(self, user_input):
                    return "I'm sorry, the money transfer service is currently unavailable. Please try again later."
            self.money_transfer_handler = MoneyTransferHandler()

    def _classify_intent(self, user_input):
        """Classify the user's intent based on their input."""
        if self.model is None or self.intent_embeddings is None:
            return "default"
            
        try:
            # First try embedding-based classification (primary method)
            # Encode the user input
            user_embedding = self.model.encode([user_input])
            
            # Calculate cosine similarity with all intent embeddings
            from sklearn.metrics.pairwise import cosine_similarity
            similarities = cosine_similarity(user_embedding, self.intent_embeddings)[0]
            
            # Find the most similar intent
            most_similar_idx = np.argmax(similarities)
            predicted_intent = self.intent_data["intents"].iloc[most_similar_idx]
            similarity_score = similarities[most_similar_idx]
            
            # Log the classification
            logging.info(f"Intent classification: {predicted_intent} with similarity {similarity_score}")
            
            # Check if we have dashboard context that might indicate chart/spending related query
            chart_context_available = False
            try:
                if hasattr(st, 'session_state') and 'dashboard_context' in st.session_state:
                    dc = st.session_state.dashboard_context
                    if 'chart_data' in dc and 'category_spending' in dc['chart_data'] and dc['chart_data']['category_spending']:
                        chart_context_available = True
            except Exception as context_error:
                # Don't let session state errors break intent classification
                logging.error(f"Error checking session state: {str(context_error)}")
            
            # Determine threshold based on context
            threshold = 0.4 if chart_context_available else 0.5
            
            # Lower threshold for account-related queries
            if any(term in user_input.lower() for term in [
                "account", "balance", "savings", "checking", "travel", "high-yield", 
                "how much", "money in", "funds", "available"
            ]):
                logging.info("Lowering threshold for account-related query")
                threshold = 0.35
            
            # If similarity is above threshold, return the embedding-based result
            if similarity_score > threshold:
                # Special case: if intent is Chart Analysis but query is about spending, upgrade it
                if "chart" in predicted_intent.lower() and any(word in user_input.lower() for word in ["spend", "spending", "category", "budget"]):
                    logging.info(f"Upgraded Chart Analysis to Spending Analysis due to spending keywords")
                    return "Spending Analysis"
                    
                # Special case: if query mentions any savings account type, ensure Account Inquiries intent
                if any(term in user_input.lower() for term in ["savings", "travel savings", "high-yield", "regular savings"]):
                    if "balance" in user_input.lower() or "how much" in user_input.lower():
                        logging.info(f"Enforcing Account Inquiries intent for savings query")
                        return "Account Inquiries"
                        
                return predicted_intent
            
            # If embedding classification isn't confident enough, try pattern matching as fallback
            # Only do pattern matching if embedding classification confidence is low
            spending_patterns = [
                r"(which|what) category should i cut back",
                r"spending analytics",
                r"where (am i|are my) (over)?spending",
                r"reduce spending",
                r"cut back on",
                r"budget",
                r"spending category",
                r"expense(s)? breakdown"
            ]
            
            # Check for spending-related patterns
            for pattern in spending_patterns:
                if re.search(pattern, user_input.lower(), re.IGNORECASE):
                    logging.info(f"Fallback pattern match for Spending Analysis: {pattern}")
                    return "Spending Analysis"
                    
            # Check for basic spending keywords after checking for specific patterns
            if any(word in user_input.lower() for word in ["spend", "spending", "budget", "category", "cut back"]):
                logging.info(f"Keyword fallback to Spending Analysis")
                return "Spending Analysis"
                
            # Enhanced account inquiry patterns with savings account focus
            account_patterns = [
                r"how much (do|have) i (have )?in my (savings|checking|travel|high.yield|account)",
                r"what('s| is) my (savings|checking|travel|high.yield) (account )?balance",
                r"balance in (my )?(savings|checking|travel|high.yield)",
                r"how much money (do|have) i (have )?in (my )?(savings|checking|travel|high.yield)",
                r"what('s| is) (in|the balance of) my (savings|checking|travel|high.yield)",
                r"how much (money )?(do i have|is) (in|available in) my (account|savings|checking|travel)",
                r"travel savings",
                r"high.yield savings"
            ]
            
            # Check for account inquiry patterns
            for pattern in account_patterns:
                if re.search(pattern, user_input.lower(), re.IGNORECASE):
                    logging.info(f"Fallback pattern match: Account Inquiries based on pattern {pattern}")
                    return "Account Inquiries"
            
            # Simple keyword-based fallback for savings accounts
            savings_keywords = [
                "savings", "save", "saving", "travel savings", "high-yield", 
                "high yield", "regular savings", "money", "funds", "account balance"
            ]
            
            if any(keyword in user_input.lower() for keyword in savings_keywords) and (
                "how much" in user_input.lower() or 
                "balance" in user_input.lower() or
                "do i have" in user_input.lower()
            ):
                logging.info(f"Keyword fallback to Account Inquiries for savings query")
                return "Account Inquiries"
                
            # Default fallback    
            return "default"
        except Exception as e:
            logging.error(f"Error in intent classification: {str(e)}")
            return "default"

    def classify_text(self, user_input):
        """Public method to classify text, wrapping the internal _classify_intent method."""
        return self._classify_intent(user_input)

    def get_response(self, user_input, chart_context=None):
        """
        Generate a response to the user's input.
        
        Args:
            user_input: The user's input text
            chart_context: Optional context from financial charts being viewed
            
        Returns:
            str: The chatbot's response
        """
        try:
            # First ensure the input is actually a string to prevent variable name references
            if not isinstance(user_input, str):
                logging.warning(f"Non-string input received: {type(user_input)}")
                user_input = str(user_input)
                
            # Clean user input
            user_input = user_input.strip()
            if not user_input:
                return "I didn't receive any input. How can I help you today?"
            
            # Add account information to context if available
            accounts_context = ""
            if hasattr(st, 'session_state') and 'dashboard_context' in st.session_state:
                try:
                    dc = st.session_state.dashboard_context
                    if 'accounts' in dc and dc['accounts']:
                        accounts_context = "\n\n=== USER ACCOUNTS INFORMATION ===\n"
                        accounts_context += "| ACCOUNT NAME | ACCOUNT TYPE | BALANCE |\n"
                        accounts_context += "|-------------|--------------|--------|\n"
                        
                        for account in dc['accounts']:
                            account_name = account.get('account_name', 'Unknown')
                            account_type = account.get('account_type', 'Unknown')
                            balance = account.get('balance', 0)
                            try:
                                balance_float = float(balance)
                                balance_str = f"${balance_float:,.2f}"
                            except (ValueError, TypeError):
                                balance_str = str(balance)
                            
                            accounts_context += f"| {account_name} | {account_type} | {balance_str} |\n"
                            
                        # Add a note to ensure the LLM uses this information
                        accounts_context += "\nIMPORTANT: When asked about ANY account, use ONLY the account information provided above."
                except Exception as e:
                    logging.error(f"Error formatting accounts context: {e}")
            
            # Append accounts context to chart context if available
            if chart_context and accounts_context:
                chart_context += accounts_context
            elif accounts_context:
                chart_context = accounts_context
                
            # Sanitize user input to prevent direct variable reference errors
            # Convert common financial terms that might match variable names to safe queries
            safe_input = user_input
            financial_terms_mapping = {
                'checking_balance': 'checking account balance',
                'savings_balance': 'savings account balance',
                'credit_balance': 'credit card balance',
                'mortgage': 'mortgage details',
                'spending_distribution': 'spending distribution',
                'avg_income': 'average income',
                'avg_expenses': 'average expenses',
                'balance_trend': 'balance trend'
            }
            
            # Replace any exact matches with safer terms
            for term, replacement in financial_terms_mapping.items():
                if safe_input.lower() == term.lower():
                    logging.info(f"Replacing potential variable reference '{term}' with '{replacement}'")
                    safe_input = replacement
            
            # First use embedding-based classification (primary method)
            intent = self.classify_text(safe_input)
            
            # Check if this is a generic savings query (for grouping regular, travel, high-yield savings)
            is_savings_query = self._is_generic_savings_query(safe_input)
            
            # Normalize the intent (replace underscores with spaces)
            if "_" in intent:
                intent = intent.replace("_", " ")
            
            # Force Account Inquiries intent for generic savings queries
            if is_savings_query and intent == "default":
                intent = "Account Inquiries"
                logging.info("Forcing Account Inquiries intent for generic savings query")
            
            # Only use pattern matching as fallback if embedding classification returned "default"
            if intent == "default":
                # Direct pattern matching for spending-related queries as fallback
                spending_patterns = [
                    r"(which|what) category should i cut back",
                    r"spending analytics",
                    r"where (am i|are my) (over)?spending",
                    r"reduce spending",
                    r"cut back on",
                    r"budget",
                    r"spending category",
                    r"expense(s)? breakdown"
                ]
                
                # Check for spending-related patterns
                for pattern in spending_patterns:
                    if re.search(pattern, safe_input.lower(), re.IGNORECASE):
                        logging.info(f"Fallback pattern match: Spending Analysis based on pattern {pattern}")
                        intent = "Spending Analysis"
                        break
                        
                # Account balance patterns as fallback
                if intent == "default":
                    account_patterns = [
                        r"how much (do|have) i (have )?in my (savings|checking|account|travel|high.yield)",
                        r"what('s| is) my (savings|checking|travel|high.yield) (account )?balance",
                        r"balance in (my )?(savings|checking|travel|high.yield)",
                        r"how much money (do|have) i (have )?in (my )?(savings|checking|travel|high.yield)"
                    ]
                    
                    for pattern in account_patterns:
                        if re.search(pattern, safe_input.lower(), re.IGNORECASE):
                            logging.info(f"Fallback pattern match: Account Inquiries based on pattern {pattern}")
                            intent = "Account Inquiries"
                            break
            
            logging.info(f"Final intent (after fallback checks): {intent}")
            
            # Handle money transfer intent with specialized handler
            if intent == "Money Transfer":
                logging.info("Using money transfer handler")
                return self.money_transfer_handler.handle(safe_input)
                
            # Get system prompt based on intent
            system_prompt = self.config.get(intent, self.config["default"])["system_prompt"]
            
            # For account balance inquiries, ensure we prioritize real account data
            if "Account" in intent or "balance" in safe_input.lower() or is_savings_query:
                # Get banking context first to ensure we have account data
                banking_context = self.prepare_banking_context(safe_input, intent)
                
                # Add explicit instruction to use actual account data
                system_prompt += """
                
                IMPORTANT INSTRUCTION: When responding about account balances or financial information,
                ONLY use the ACTUAL USER BANKING DATA provided below. Do NOT use sample data or make up numbers.
                If specific account data is not provided, tell the user you don't have that information.
                """
                
                # Add special instruction for generic savings queries
                if is_savings_query:
                    system_prompt += """
                    
                    SPECIAL INSTRUCTION FOR SAVINGS ACCOUNTS:
                    The user is asking about savings accounts in general. You should provide information about
                    ALL savings account types (Regular Savings, Travel Savings, High-Yield Savings) in your response.
                    List each savings account with its specific name, type, and balance.
                    """
                
                # Add banking context to prompt to ensure LLM has actual account data
                if banking_context:
                    system_prompt += f"\n\n===== ACTUAL USER BANKING DATA (Use ONLY this data) =====\n{banking_context}"
                else:
                    logging.error("No banking context available for account inquiry")
            
            # Add chart context to prompt if available and relevant 
            chart_aware_intents = ["Chart Analysis", "Spending Analysis", "Account Inquiries", "Financial Management"]
            if chart_context and any(intent_name in intent for intent_name in chart_aware_intents):
                system_prompt += f"\n\nCurrent financial data from dashboard:\n{chart_context}"
            
            # For other intents, add general banking context
            if intent != "Account Inquiries" and "Account" not in intent:
                banking_context_intents = ["Transactions", "Money Transfer", 
                                         "Financial Management", "Investment Advice", "Interest Rates"]
                if any(intent_name in intent for intent_name in banking_context_intents):
                    banking_context = self.prepare_banking_context(safe_input, intent)
                    if banking_context:
                        system_prompt += f"\n\nUSER BANKING DATA:\n{banking_context}"
                        logging.info("Added banking context to prompt")
            
            # Generate response using OpenAI
            logging.info(f"Generating response for intent: {intent}")
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": safe_input}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            # Extract and return the assistant's message
            assistant_message = response.choices[0].message.content
            return assistant_message
        except Exception as e:
            logging.error(f"Error generating response: {str(e)}")
            return "I'm sorry, I encountered an error while processing your request. Please try again."

    def _is_generic_savings_query(self, user_input):
        """Check if user is asking about savings accounts in general, without specifying type."""
        # Convert to lowercase for case-insensitive matching
        input_lower = user_input.lower()
        
        # Check for generic savings terms
        generic_savings_terms = [
            "savings account", "savings balance", "in my savings", 
            "savings", "save", "saved"
        ]
        
        # Check for specific account type mentions
        specific_account_terms = [
            "travel savings", "high-yield", "high yield", "regular savings"
        ]
        
        # Check if input contains generic savings terms
        contains_generic = any(term in input_lower for term in generic_savings_terms)
        
        # Check if input contains specific account type mentions 
        contains_specific = any(term in input_lower for term in specific_account_terms)
        
        # Check for a balance or account inquiry pattern
        inquiry_pattern = any(term in input_lower for term in [
            "how much", "balance", "do i have", "available", "what is in", "what's in"
        ])
        
        # Return True if it's a generic savings query without specific account mention
        is_generic = contains_generic and not contains_specific and inquiry_pattern
        
        if is_generic:
            logging.info(f"Identified generic savings query: '{user_input}'")
            
        return is_generic

    def prepare_banking_context(self, user_input, basic_intent, intent_analysis=None):
        """
        Generate contextual information to enhance the chatbot's response for banking queries.
        
        Args:
            user_input: The user's original query
            basic_intent: The detected basic intent category
            intent_analysis: (Optional) Deep intent analysis for parameter extraction
            
        Returns:
            str: Relevant context for the chatbot to use
        """
        LOGGER.info(f"Preparing context for intent '{basic_intent}'")
        
        context_parts = []
        
        # Check if this is a generic savings query
        is_savings_query = self._is_generic_savings_query(user_input)
        
        # Check if dashboard context is available for chart awareness
        chart_context = ""
        if hasattr(st, 'session_state') and 'dashboard_context' in st.session_state:
            dc = st.session_state.dashboard_context
            chart_context = f"\n== ACCOUNT DASHBOARD CONTEXT ==\n"
            chart_context += f"Overview: {dc['user_fullname']} has {dc['total_accounts']} accounts with total assets of ${dc['total_assets']:.2f}"
            
            if dc['total_liabilities'] > 0:
                chart_context += f" and total liabilities of ${dc['total_liabilities']:.2f}"
            
            chart_context += f"\nCurrently viewing: {dc['selected_account']} for {dc['selected_time_period']}\n"
            
            # Add specific chart data information if available
            if 'chart_data' in dc:
                if 'balance_trend' in dc['chart_data'] and dc['chart_data']['balance_trend']:
                    # Extract start, end, min, max values from balance trend
                    bt = dc['chart_data']['balance_trend']
                    chart_context += f"\nBalance Trend: Showing data from {bt[0]['date_only']} to {bt[-1]['date_only']}\n"
                    balances = [float(item['balance_after']) for item in bt]
                    chart_context += f"- Starting balance: ${balances[0]:.2f}\n"
                    chart_context += f"- Current balance: ${balances[-1]:.2f}\n"
                    chart_context += f"- Highest balance: ${max(balances):.2f}\n"
                    chart_context += f"- Lowest balance: ${min(balances):.2f}\n"
                
                if 'mortgage_trend' in dc['chart_data'] and dc['chart_data']['mortgage_trend']:
                    # Extract mortgage information
                    mt = dc['chart_data']['mortgage_trend']
                    chart_context += f"\nMortgage Trend: Showing data from {mt[0]['date_only']} to {mt[-1]['date_only']}\n"
                    balances = [float(item['balance_after']) for item in mt]
                    chart_context += f"- Starting balance: ${balances[0]:.2f}\n"
                    chart_context += f"- Current balance: ${balances[-1]:.2f}\n"
                    chart_context += f"- Total paid: ${balances[0] - balances[-1]:.2f}\n"
                
                if 'category_spending' in dc['chart_data'] and dc['chart_data']['category_spending']:
                    # Extract spending distribution
                    cs = dc['chart_data']['category_spending']
                    chart_context += f"\nSpending Distribution:\n"
                    for item in cs[:5]:  # Top 5 categories
                        chart_context += f"- {item['category']}: ${float(item['amount']):.2f}\n"
                
                if 'income_vs_expenses' in dc['chart_data'] and dc['chart_data']['income_vs_expenses']:
                    # Extract income vs expenses data
                    ie = dc['chart_data']['income_vs_expenses']
                    chart_context += f"\nIncome vs Expenses (last {len(ie)} months):\n"
                    total_income = sum(float(item['income']) for item in ie)
                    total_expenses = sum(float(item['expenses']) for item in ie)
                    chart_context += f"- Total income: ${total_income:.2f}\n"
                    chart_context += f"- Total expenses: ${total_expenses:.2f}\n"
                    if total_income > 0:
                        savings_rate = (total_income - total_expenses) / total_income * 100
                        chart_context += f"- Savings rate: {savings_rate:.1f}%\n"
            
            context_parts.append(chart_context)
        
        # Add user account information
        user_data = self.get_user_data()
        if user_data:
            context_parts.append(f"USER INFORMATION:\nUser ID: {user_data['user_id']}\nName: {user_data['first_name']} {user_data['last_name']}\nEmail: {user_data['email']}")
        
        # Get account information
        account_info = self.get_account_info()
        if account_info:
            accounts_text = "===== CURRENT REAL ACCOUNT BALANCES =====\n"
            
            # Special handling for savings accounts if this is a generic savings query
            if is_savings_query:
                savings_accounts = []
                other_accounts = []
                
                # Categorize accounts
                for account in account_info:
                    account_type = account.get('account_type', '').lower()
                    if 'savings' in account_type:
                        savings_accounts.append(account)
                    else:
                        other_accounts.append(account)
                
                # Add special section for ALL savings accounts if this is a generic savings query
                if savings_accounts:
                    accounts_text += "\n>> ALL SAVINGS ACCOUNTS <<\n"
                    for account in savings_accounts:
                        # Format account name consistently
                        account_name = account.get('account_name', 'Unknown Account')
                        account_type = account.get('account_type', '').lower()
                        
                        # Format the account data with clear labeling
                        accounts_text += f"* {account_name} ({account_type.upper()}) *\n"
                        
                        # Make the balance stand out
                        if 'balance' in account:
                            try:
                                balance = float(account['balance'])
                                accounts_text += f"BALANCE: ${balance:.2f}\n"
                            except (ValueError, TypeError):
                                accounts_text += f"Balance: {account['balance']}\n"
                        
                        # Add other account details
                        accounts_text += f"Account ID: {account.get('account_id', 'N/A')}\n"
                        
                        if 'interest_rate' in account:
                            accounts_text += f"Interest Rate: {account['interest_rate']}%\n"
                        
                        accounts_text += f"Status: {account.get('status', 'Active')}\n\n"
                    
                    # Add other accounts after savings accounts
                    if other_accounts:
                        accounts_text += "\n>> OTHER ACCOUNTS <<\n"
                        for account in other_accounts:
                            account_name = account.get('account_name', 'Unknown Account')
                            account_type = account.get('account_type', '').lower()
                            
                            accounts_text += f"* {account_name} ({account_type.upper()}) *\n"
                            
                            if 'balance' in account:
                                try:
                                    balance = float(account['balance'])
                                    accounts_text += f"Balance: ${balance:.2f}\n"
                                except (ValueError, TypeError):
                                    accounts_text += f"Balance: {account['balance']}\n"
                            
                            accounts_text += f"Account ID: {account.get('account_id', 'N/A')}\n\n"
                else:
                    accounts_text += "No savings accounts found for this user.\n"
            else:
                # Standard account listing for non-savings-specific queries
                for account in account_info:
                    # Format account name consistently
                    account_name = account.get('account_name', 'Unknown Account')
                    if isinstance(account_name, str) and ('savings' in account_name.lower() or 'checking' in account_name.lower()):
                        formatted_name = account_name
                    else:
                        account_type = account.get('account_type', '').lower()
                        if 'savings' in account_type:
                            formatted_name = f"{account_name} (Savings Account)"
                        elif 'checking' in account_type:
                            formatted_name = f"{account_name} (Checking Account)"
                        else:
                            formatted_name = f"{account_name} ({account_type})"
                    
                    # Format the account data with clear labeling
                    accounts_text += f">> Account: {formatted_name} <<\n"
                    
                    # Make the balance stand out
                    if 'balance' in account:
                        try:
                            balance = float(account['balance'])
                            accounts_text += f"BALANCE: ${balance:.2f}\n"
                        except (ValueError, TypeError):
                            accounts_text += f"Balance: {account['balance']}\n"
                    
                    # Add other account details
                    accounts_text += f"Account ID: {account.get('account_id', 'N/A')}\n"
                    accounts_text += f"Account Type: {account.get('account_type', 'N/A')}\n"
                    
                    if 'available_balance' in account:
                        try:
                            available = float(account['available_balance'])
                            accounts_text += f"Available Balance: ${available:.2f}\n"
                        except (ValueError, TypeError):
                            accounts_text += f"Available Balance: {account['available_balance']}\n"
                    
                    if 'interest_rate' in account:
                        accounts_text += f"Interest Rate: {account['interest_rate']}%\n"
                    
                    accounts_text += f"Status: {account.get('status', 'Active')}\n\n"
            
            context_parts.append(accounts_text)
            LOGGER.info(f"Added detailed account information for {len(account_info)} accounts")
        else:
            LOGGER.warning("No account information available for banking context")
        
        # Format the context as a newline-separated string
        result = "\n".join(context_parts)
        LOGGER.info(f"Banking context prepared: {len(result)} characters")
        return result

    def get_user_data(self):
        """
        Get user data for the current user from session state or data files.
        
        Returns:
            dict: User data including name, email, etc. or None if not found
        """
        try:
            # First check if user data is in session state
            if hasattr(st, 'session_state'):
                if 'dashboard_context' in st.session_state and 'user_id' in st.session_state.dashboard_context:
                    user_id = st.session_state.dashboard_context['user_id']
                elif 'current_user_id' in st.session_state:
                    user_id = st.session_state.current_user_id
                else:
                    LOGGER.warning("No user ID found in session state")
                    return None
                
                # Load user data from CSV
                users_df = load_banking_data()['users']
                
                if users_df is not None and not users_df.empty:
                    user_data = users_df[users_df['user_id'] == user_id]
                    if not user_data.empty:
                        user_row = user_data.iloc[0]
                        return {
                            'user_id': user_id,
                            'first_name': user_row['first_name'],
                            'last_name': user_row['last_name'],
                            'email': user_row['email'] if 'email' in user_row else f"{user_row['first_name'].lower()}@example.com"
                        }
            
            return None
        except Exception as e:
            LOGGER.error(f"Error retrieving user data: {str(e)}")
            return None

    def get_account_info(self):
        """
        Get account information for the current user from session state or data files.
        
        Returns:
            list: List of account dictionaries with details or None if not found
        """
        try:
            # Check if we have user_id in session state
            user_id = None
            
            if hasattr(st, 'session_state'):
                if 'dashboard_context' in st.session_state and 'user_id' in st.session_state.dashboard_context:
                    user_id = st.session_state.dashboard_context['user_id']
                elif 'current_user_id' in st.session_state:
                    user_id = st.session_state.current_user_id
            
            if not user_id:
                LOGGER.warning("No user ID found for account info")
                return None
            
            LOGGER.info(f"Getting account info for user ID: {user_id}")
            
            # PRIORITY 1: First try to get from dashboard context - most up-to-date live data
            if hasattr(st, 'session_state') and 'dashboard_context' in st.session_state:
                dc = st.session_state.dashboard_context
                if 'accounts' in dc and dc['accounts']:
                    LOGGER.info(f"Found {len(dc['accounts'])} accounts in dashboard context for user {user_id}")
                    for account in dc['accounts']:
                        # Log account details for debugging
                        if 'account_name' in account and 'balance' in account:
                            LOGGER.info(f"Account: {account['account_name']}, Balance: ${float(account['balance']):.2f}")
                    return dc['accounts']
            
            # PRIORITY 2: Try to get from dashboard 'Your Accounts' table data
            if hasattr(st, 'session_state') and 'dashboard_context' in st.session_state:
                dc = st.session_state.dashboard_context
                
                account_fields = ['Account Name', 'Type', 'Balance', 'Available', 'Interest Rate', 'Opened On', 'Status']
                account_keys = ['account_name', 'account_type', 'balance', 'available_balance', 'interest_rate', 'opened_on', 'status']
                
                if 'account_data' in dc and isinstance(dc['account_data'], list) and len(dc['account_data']) > 0:
                    LOGGER.info(f"Using account_data from dashboard context for user {user_id}")
                    accounts = []
                    for i, account_data in enumerate(dc['account_data']):
                        # Convert to standard format
                        account_dict = {
                            'account_id': f"ACC{i+1}",
                            'owner_id': user_id
                        }
                        for k, field in enumerate(account_fields):
                            if field in account_data and k < len(account_keys):
                                account_dict[account_keys[k]] = account_data[field]
                        accounts.append(account_dict)
                    LOGGER.info(f"Converted {len(accounts)} accounts from dashboard account_data")
                    return accounts
            
            # PRIORITY 3: Fallback to loading from data files directly
            data = load_banking_data()
            accounts_df = data['accounts']
            
            if accounts_df is not None and not accounts_df.empty:
                user_accounts = accounts_df[accounts_df['owner_id'] == user_id]
                if not user_accounts.empty:
                    account_records = user_accounts.to_dict('records')
                    LOGGER.info(f"Loaded {len(account_records)} accounts from data file for user {user_id}")
                    for account in account_records:
                        # Log account details for debugging
                        if 'account_name' in account and 'balance' in account:
                            LOGGER.info(f"Account from CSV: {account['account_name']}, Balance: ${float(account['balance']):.2f}")
                    return account_records
            
            LOGGER.warning(f"No account information found for user {user_id}")
            return None
        except Exception as e:
            LOGGER.error(f"Error retrieving account information: {str(e)}")
            return None