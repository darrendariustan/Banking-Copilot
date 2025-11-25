import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import uuid
import logging
import altair as alt
import time

# Configure logging - only if not already configured
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='dashboard.log'
    )
LOGGER = logging.getLogger('account_dashboard')

class AccountDashboard:
    """Class to handle account overview, transaction history, and spending analytics."""
    
    def __init__(self, data_dir=None):
        """Initialize with data directory path."""
        # Set up data directory similar to MoneyTransfer class
        if data_dir is None:
            # Try going up one level from modules/ to root, then to data/
            possible_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
            
            if not os.path.exists(possible_path):
                possible_path = 'data'
                LOGGER.info(f"Using direct path to data directory: {os.path.abspath(possible_path)}")
            else:
                LOGGER.info(f"Using calculated path to data directory: {possible_path}")
            
            self.data_dir = possible_path
        else:
            self.data_dir = data_dir
            LOGGER.info(f"Using provided data directory: {data_dir}")
        
        self.accounts_file = os.path.join(self.data_dir, 'accounts.csv')
        self.transactions_file = os.path.join(self.data_dir, 'transaction_history.csv')
        self.users_file = os.path.join(self.data_dir, 'users.csv')
        self.scheduled_payments_file = os.path.join(self.data_dir, 'scheduled_payments.csv')
        
        # Load data
        self.load_data()
    
    def load_data(self):
        """Load accounts, transactions and user data from CSV files."""
        try:
            # Log the file paths we're trying to load
            LOGGER.info(f"Loading accounts from: {self.accounts_file}")
            LOGGER.info(f"Loading transactions from: {self.transactions_file}")
            LOGGER.info(f"Loading users from: {self.users_file}")
            
            # Check if files exist
            if not os.path.exists(self.accounts_file):
                LOGGER.error(f"Accounts file does not exist: {self.accounts_file}")
                raise FileNotFoundError(f"Accounts file not found: {self.accounts_file}")
            
            if not os.path.exists(self.transactions_file):
                LOGGER.error(f"Transactions file does not exist: {self.transactions_file}")
                raise FileNotFoundError(f"Transactions file not found: {self.transactions_file}")
            
            if not os.path.exists(self.users_file):
                LOGGER.error(f"Users file does not exist: {self.users_file}")
                raise FileNotFoundError(f"Users file not found: {self.users_file}")
            
            # Load the data
            self.accounts = pd.read_csv(self.accounts_file)
            self.transactions = pd.read_csv(self.transactions_file)
            self.users = pd.read_csv(self.users_file)
            
            # Try to load scheduled payments if they exist
            if os.path.exists(self.scheduled_payments_file):
                self.scheduled_payments = pd.read_csv(self.scheduled_payments_file)
                LOGGER.info(f"Loaded {len(self.scheduled_payments)} scheduled payments")
            else:
                LOGGER.warning(f"Scheduled payments file not found: {self.scheduled_payments_file}")
                self.scheduled_payments = pd.DataFrame()
            
            # Convert date columns to datetime
            if 'date' in self.transactions.columns:
                try:
                    self.transactions['date'] = pd.to_datetime(self.transactions['date'], errors='coerce')
                except Exception as e:
                    LOGGER.error(f"Error converting transaction dates to datetime: {e}")
            
            LOGGER.info(f"Loaded {len(self.accounts)} accounts, {len(self.transactions)} transactions")
            LOGGER.info(f"Loaded {len(self.users)} users")
            
            return True
        except Exception as e:
            LOGGER.error(f"Error loading data: {e}")
            # Initialize empty DataFrames when loading fails to prevent attribute errors
            if not hasattr(self, 'accounts'):
                self.accounts = pd.DataFrame()
            if not hasattr(self, 'transactions'):
                self.transactions = pd.DataFrame()
            if not hasattr(self, 'users'):
                self.users = pd.DataFrame()
            if not hasattr(self, 'scheduled_payments'):
                self.scheduled_payments = pd.DataFrame()
            return False
    
    def get_user_accounts(self, user_id):
        """Get all accounts for a specific user."""
        if not self.accounts.empty:
            user_accounts = self.accounts[self.accounts['owner_id'] == user_id]
            return user_accounts
        return pd.DataFrame()
    
    def get_user_transactions(self, user_id, days=30, account_type=None):
        """Get transaction history for a user, optionally filtered by account type and time period."""
        if self.transactions.empty:
            return pd.DataFrame()
        
        # Get all user accounts
        user_accounts = self.get_user_accounts(user_id)
        if user_accounts.empty:
            return pd.DataFrame()
        
        # Filter by account type if specified
        if account_type:
            user_accounts = user_accounts[user_accounts['account_type'] == account_type]
            if user_accounts.empty:
                return pd.DataFrame()
        
        # Get account IDs to filter transactions
        account_ids = user_accounts['account_id'].tolist()
        
        # Filter transactions by account IDs
        user_transactions = self.transactions[self.transactions['account_id'].isin(account_ids)].copy()
        
        # Add account type for each transaction
        if not user_accounts.empty:
            # Create a mapping of account_id to account_type
            account_type_map = user_accounts.set_index('account_id')['account_type'].to_dict()
            
            # Add account_type column to transactions
            user_transactions['account_type'] = user_transactions['account_id'].map(account_type_map)
        
        # Filter by date if needed
        if days > 0 and 'date' in user_transactions.columns:
            # Handle possible NaT values
            user_transactions = user_transactions.dropna(subset=['date'])
            
            # Get current date and filter by date range
            # Since we're working with example data, use the max date in the dataset as "today"
            latest_date = user_transactions['date'].max()
            if pd.notna(latest_date):
                start_date = latest_date - pd.Timedelta(days=days)
                user_transactions = user_transactions[user_transactions['date'] >= start_date]
        
        # Sort by date (descending)
        if 'date' in user_transactions.columns:
            user_transactions = user_transactions.sort_values('date', ascending=False)
        
        return user_transactions
    
    def get_user_spending_by_category(self, user_id, days=30, account_type=None):
        """Get spending analytics by category for a user."""
        # Get user transactions
        transactions = self.get_user_transactions(user_id, days, account_type)
        
        if transactions.empty:
            return pd.DataFrame()
        
        # Filter only debit/expense transactions (negative amounts)
        if 'amount' in transactions.columns:
            # Convert amount to numeric if it's a string
            if transactions['amount'].dtype == 'object':
                transactions['amount'] = pd.to_numeric(transactions['amount'], errors='coerce')
            
            # Filter only negative amounts (expenses)
            expenses = transactions[transactions['amount'] < 0].copy()
            
            # Take absolute value for better visualization
            expenses['amount'] = expenses['amount'].abs()
            
            # Group by category
            if 'category' in expenses.columns:
                category_spending = expenses.groupby('category')['amount'].sum().reset_index()
                
                # Sort by highest spending
                category_spending = category_spending.sort_values('amount', ascending=False)
                
                return category_spending
        
        return pd.DataFrame()
    
    def get_account_balance_trend(self, user_id, account_type=None, days=90, exclude_mortgage=False):
        """Calculate balance trend over time based on transactions."""
        # Get user transactions
        transactions = self.get_user_transactions(user_id, days, account_type)
        
        if transactions.empty or 'balance_after' not in transactions.columns:
            return pd.DataFrame()
        
        # Convert to numeric if needed
        if transactions['balance_after'].dtype == 'object':
            transactions['balance_after'] = pd.to_numeric(transactions['balance_after'], errors='coerce')
        
        # Group by date and get the last balance of each day
        if 'date' in transactions.columns:
            # Extract just the date part
            transactions['date_only'] = transactions['date'].dt.date
            
            # Get account types for each transaction
            # We need to merge the account type from accounts DataFrame
            if 'account_id' in transactions.columns and not self.accounts.empty:
                # Create a mapping of account_id to account_type
                account_type_map = self.accounts.set_index('account_id')['account_type'].to_dict()
                
                # Add account_type column to transactions
                transactions['account_type'] = transactions['account_id'].map(account_type_map)
                
                # Filter out mortgage accounts if needed
                if exclude_mortgage:
                    transactions = transactions[transactions['account_type'] != 'MORTGAGE']
            
            # Check if we should filter by account type
            if account_type and 'account_type' in transactions.columns:
                transactions = transactions[transactions['account_type'] == account_type]
            
            # Group by date and get the last balance of each day
            # Use the first balance of each day (since we've sorted descending)
            daily_balance = transactions.groupby('date_only')['balance_after'].first().reset_index()
            
            # Sort by date (ascending for trend line)
            daily_balance = daily_balance.sort_values('date_only')
            
            return daily_balance
        
        return pd.DataFrame()
    
    def get_monthly_income_vs_expenses(self, user_id, months=6, account_type=None):
        """Calculate monthly income vs expenses."""
        # Get user transactions
        transactions = self.get_user_transactions(user_id, days=months*30, account_type=account_type)
        
        if transactions.empty:
            return pd.DataFrame()
        
        # Convert amount to numeric if needed
        if transactions['amount'].dtype == 'object':
            transactions['amount'] = pd.to_numeric(transactions['amount'], errors='coerce')
        
        # Add month column
        if 'date' in transactions.columns:
            transactions['month'] = transactions['date'].dt.strftime('%Y-%m')
            
            # Calculate income (positive amounts) and expenses (negative amounts) by month
            monthly_summary = pd.DataFrame()
            
            # Group by month
            grouped = transactions.groupby('month')
            
            # Calculate income and expenses for each month
            monthly_data = []
            for month, group in grouped:
                income = group[group['amount'] > 0]['amount'].sum()
                expenses = group[group['amount'] < 0]['amount'].abs().sum()
                monthly_data.append({'month': month, 'income': income, 'expenses': expenses})
            
            monthly_summary = pd.DataFrame(monthly_data)
            
            # Sort by month
            monthly_summary = monthly_summary.sort_values('month')
            
            return monthly_summary
        
        return pd.DataFrame()
    
    def render_account_dashboard(self, user_id, user_fullname):
        """Render the integrated account dashboard with overview, transactions, and analytics."""
        st.title("Account Dashboard")
        st.write(f"Welcome, {user_fullname}! Here's your financial summary.")
        
        # Get user accounts
        user_accounts = self.get_user_accounts(user_id)
        
        if user_accounts.empty:
            st.error(f"No accounts found for user {user_id}")
            return
        
        # Create tabs for the dashboard sections
        overview_tab, transactions_tab, analytics_tab = st.tabs([
            "Account Overview", 
            "Transaction History", 
            "Spending Analytics"
        ])
        
        # Filter controls for all tabs
        with st.sidebar:
            st.subheader("Dashboard Controls")
            
            # Account selection
            account_options = [("All Accounts", None)] + [
                (f"{row['account_name']} ({row['account_type']})", row['account_type']) 
                for _, row in user_accounts.iterrows()
            ]
            selected_account_label, selected_account_type = account_options[
                st.selectbox(
                    "Select Account",
                    options=range(len(account_options)),
                    format_func=lambda i: account_options[i][0]
                )
            ]
            
            # Time period selection
            time_options = {
                "Last 30 days": 30,
                "Last 60 days": 60,
                "Last 90 days": 90,
                "Last 6 months": 180,
                "Last year": 365
            }
            selected_time_label = st.selectbox("Time Period", options=list(time_options.keys()))
            selected_time_days = time_options[selected_time_label]
        
        # Account Overview Tab
        with overview_tab:
            # Header stats
            # Separate assets from liabilities (mortgage)
            assets = user_accounts[user_accounts['account_type'] != 'MORTGAGE']
            liabilities = user_accounts[user_accounts['account_type'] == 'MORTGAGE']
            
            # Calculate total assets (excluding mortgage)
            total_assets = assets['balance'].astype(float).sum()
            
            # Calculate total liabilities (mortgage accounts)
            total_liabilities = liabilities['balance'].astype(float).sum()
            
            total_accounts = len(user_accounts)
            
            # Display account summary
            st.subheader("Account Summary")
            
            # Summary metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Assets", f"${total_assets:,.2f}")
            if total_liabilities > 0:
                col2.metric("Total Liabilities", f"${total_liabilities:,.2f}")
            col3.metric("Number of Accounts", total_accounts)
            
            # Account details in a nice table
            st.subheader("Your Accounts")
            
            # Format account data for display
            display_accounts = user_accounts.copy()
            
            # Format currency columns
            for col in ['balance', 'available_balance']:
                if col in display_accounts.columns:
                    display_accounts[col] = display_accounts[col].astype(float).map('${:,.2f}'.format)
            
            # Format interest rate
            if 'interest_rate' in display_accounts.columns:
                display_accounts['interest_rate'] = display_accounts['interest_rate'].astype(float).map('{:.2f}%'.format)
            
            # Select and order columns for display
            display_cols = ['account_name', 'account_type', 'balance', 'available_balance', 
                         'interest_rate', 'open_date', 'status']
            display_accounts = display_accounts[
                [col for col in display_cols if col in display_accounts.columns]
            ]
            
            # Display account table
            st.dataframe(
                display_accounts,
                column_config={
                    "account_name": "Account Name",
                    "account_type": "Type",
                    "balance": "Balance",
                    "available_balance": "Available",
                    "interest_rate": "Interest Rate",
                    "open_date": "Opened On",
                    "status": "Status"
                },
                use_container_width=True
            )
            
            # Balance trend graph
            st.subheader("Balance Trend")
            
            # Get balance trend data - exclude mortgage accounts
            balance_trend = self.get_account_balance_trend(
                user_id, 
                account_type=selected_account_type,
                days=selected_time_days,
                exclude_mortgage=True  # Add parameter to exclude mortgage
            )
            
            if not balance_trend.empty:
                # Create line chart
                fig = px.line(
                    balance_trend, 
                    x='date_only', 
                    y='balance_after',
                    labels={'date_only': 'Date', 'balance_after': 'Balance'},
                    title=f"Asset Balance History - {selected_account_label}"
                )
                fig.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Balance ($)",
                    hovermode="x unified"
                )
                # Add dollar signs to y-axis
                fig.update_layout(yaxis=dict(tickprefix="$"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Insufficient data to display balance trend.")
            
            # Display mortgage balance trend if it exists
            if not liabilities.empty and selected_account_type is None:  # Only show in "All Accounts" view
                st.subheader("Mortgage Balance Trend")
                
                # Get mortgage balance trend data
                mortgage_trend = self.get_account_balance_trend(
                    user_id,
                    account_type="MORTGAGE",
                    days=selected_time_days
                )
                
                if not mortgage_trend.empty:
                    # Create line chart for mortgage balance
                    fig = px.line(
                        mortgage_trend,
                        x='date_only',
                        y='balance_after',
                        labels={'date_only': 'Date', 'balance_after': 'Balance'},
                        title="Mortgage Balance History"
                    )
                    fig.update_layout(
                        xaxis_title="Date",
                        yaxis_title="Balance ($)",
                        hovermode="x unified"
                    )
                    # Add dollar signs to y-axis
                    fig.update_layout(yaxis=dict(tickprefix="$"))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Insufficient data to display mortgage trend.")
            
            # Upcoming scheduled payments
            if hasattr(self, 'scheduled_payments') and not self.scheduled_payments.empty:
                st.subheader("Upcoming Scheduled Payments")
                
                # Filter scheduled payments for this user
                # Get user's account IDs to filter scheduled payments
                user_account_ids = user_accounts['account_id'].tolist()
                
                # Use account_id instead of user_id to filter scheduled payments
                if 'account_id' in self.scheduled_payments.columns:
                    user_scheduled = self.scheduled_payments[
                        self.scheduled_payments['account_id'].isin(user_account_ids)
                    ]
                    
                    if not user_scheduled.empty:
                        # Format for display
                        for col in ['amount']:
                            if col in user_scheduled.columns:
                                user_scheduled[col] = user_scheduled[col].astype(float).map('${:,.2f}'.format)
                        
                        # Display upcoming payments
                        st.dataframe(
                            user_scheduled,
                            column_config={
                                "payee_name": "Recipient",
                                "amount": "Amount",
                                "frequency": "Frequency",
                                "next_date": "Next Date",
                                "category": "Category",
                                "description": "Description"
                            },
                            use_container_width=True
                        )
                    else:
                        st.info("No upcoming scheduled payments.")
                else:
                    st.info("Scheduled payments information not available.")
        
        # Transaction History Tab
        with transactions_tab:
            st.subheader("Transaction History")
            
            # Get filtered transactions
            transactions = self.get_user_transactions(
                user_id,
                days=selected_time_days,
                account_type=selected_account_type
            )
            
            if transactions.empty:
                st.info(f"No transactions found for the selected period.")
                return
            
            # Display transaction count
            st.write(f"Showing {len(transactions)} transactions for {selected_account_label}")
            
            # Format transactions for display
            display_transactions = transactions.copy()
            
            # Format date
            if 'date' in display_transactions.columns:
                display_transactions['date'] = display_transactions['date'].dt.strftime('%Y-%m-%d %H:%M')
            
            # Format amount
            if 'amount' in display_transactions.columns:
                # Convert to float first if needed
                display_transactions.loc[:, 'amount'] = pd.to_numeric(display_transactions['amount'], errors='coerce')
                
                # Apply color coding
                def format_amount(value):
                    if pd.isna(value):
                        return ""
                    elif value < 0:
                        return f"📤 ${abs(value):,.2f}"
                    else:
                        return f"📥 ${value:,.2f}"
                
                display_transactions.loc[:, 'formatted_amount'] = display_transactions['amount'].apply(format_amount)
            
            # Format balance
            if 'balance_after' in display_transactions.columns:
                display_transactions['balance_after'] = pd.to_numeric(
                    display_transactions['balance_after'], errors='coerce'
                ).map('${:,.2f}'.format)
            
            # Select columns for display
            display_cols = ['date', 'description', 'category', 'formatted_amount', 
                         'balance_after', 'merchant_name', 'transaction_type']
            
            # Ensure all columns exist
            display_cols = [col for col in display_cols if col in display_transactions.columns]
            
            # Create dataframe with selected columns
            display_df = display_transactions[display_cols]
            
            # Display transaction table
            st.dataframe(
                display_df,
                column_config={
                    "date": "Date & Time",
                    "description": "Description",
                    "category": "Category",
                    "formatted_amount": "Amount",
                    "balance_after": "Balance After",
                    "merchant_name": "Merchant",
                    "transaction_type": "Type"
                },
                use_container_width=True
            )
            
            # Transaction amounts over time - show credits as positive and debits as negative
            st.subheader("Transaction Amounts Over Time")
            
            if 'date' in transactions.columns and 'amount' in transactions.columns:
                # Ensure amount is numeric
                transactions['amount'] = pd.to_numeric(transactions['amount'], errors='coerce')
                
                # Create date column if working with datetime
                transactions['date_only'] = transactions['date'].dt.date
                
                # Group by date and transaction type
                # We'll keep debits as negative values
                transaction_amounts = []
                
                # Group the transactions by date and calculate the sum for each day
                daily_amounts = transactions.groupby(['date_only'])['amount'].sum().reset_index()
                
                # For each day, separate into credit and debit amounts
                for _, row in daily_amounts.iterrows():
                    date = row['date_only']
                    amount = row['amount']
                    
                    # Get credits (positive) for this date
                    day_credits = transactions[(transactions['date_only'] == date) & 
                                              (transactions['amount'] > 0)]['amount'].sum()
                    
                    # Get debits (negative) for this date
                    day_debits = transactions[(transactions['date_only'] == date) & 
                                             (transactions['amount'] < 0)]['amount'].sum()
                    
                    if day_credits > 0:
                        transaction_amounts.append({
                            'date_only': date,
                            'amount': day_credits,
                            'type': 'Credits'
                        })
                    
                    if day_debits < 0:
                        transaction_amounts.append({
                            'date_only': date,
                            'amount': day_debits,  # Keep as negative
                            'type': 'Debits'
                        })
                
                # Convert to DataFrame
                amounts_by_date = pd.DataFrame(transaction_amounts)
                
                if not amounts_by_date.empty:
                    # Create bar chart showing credits as positive and debits as negative
                    fig = px.bar(
                        amounts_by_date,
                        x='date_only',
                        y='amount',
                        color='type',
                        labels={'date_only': 'Date', 'amount': 'Amount ($)', 'type': 'Transaction Type'},
                        title="Daily Transaction Amounts",
                        color_discrete_map={'Credits': 'rgb(26, 118, 255)', 'Debits': 'rgb(246, 78, 139)'}
                    )
                    
                    # Add dollar signs to y-axis and make sure 0 is centered
                    fig.update_layout(
                        yaxis=dict(
                            tickprefix="$",
                            zeroline=True,
                            zerolinewidth=2,
                            zerolinecolor='#999999'
                        ),
                        hovermode="x unified"
                    )
                    
                    # Improve hover information with proper formatting for positive/negative values
                    fig.update_traces(
                        hovertemplate='%{y:$,.2f}'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No transaction amount data available for the selected period.")
        
        # Spending Analytics Tab
        with analytics_tab:
            st.subheader("Spending Analytics")
            
            # Get category spending data
            category_spending = self.get_user_spending_by_category(
                user_id,
                days=selected_time_days,
                account_type=selected_account_type
            )
            
            if category_spending.empty:
                st.info(f"No spending data found for the selected period.")
                return
            
            # Create pie chart for category spending
            st.subheader("Spending by Category")
            
            # Create pie chart
            fig = px.pie(
                category_spending,
                values='amount',
                names='category',
                title="Spending Distribution",
                hole=0.4
            )
            
            # Improve layout
            fig.update_traces(
                textposition='inside', 
                textinfo='percent+label',
                marker=dict(line=dict(color='#000000', width=1))
            )
            
            # Show the pie chart
            st.plotly_chart(fig, use_container_width=True)
            
            # Monthly Income vs Expenses
            st.subheader("Monthly Income vs Expenses")
            
            # Get monthly data
            monthly_data = self.get_monthly_income_vs_expenses(
                user_id,
                months=selected_time_days // 30 or 6,  # Convert days to months
                account_type=selected_account_type
            )
            
            if not monthly_data.empty:
                # Create bar chart
                fig = go.Figure()
                
                # Add income bars
                fig.add_trace(go.Bar(
                    x=monthly_data['month'],
                    y=monthly_data['income'],
                    name='Income',
                    marker_color='rgb(26, 118, 255)'
                ))
                
                # Add expense bars
                fig.add_trace(go.Bar(
                    x=monthly_data['month'],
                    y=monthly_data['expenses'],
                    name='Expenses',
                    marker_color='rgb(246, 78, 139)'
                ))
                
                # Update layout
                fig.update_layout(
                    title=f"Monthly Income vs Expenses - {selected_account_label}",
                    xaxis_title="Month",
                    yaxis_title="Amount ($)",
                    barmode='group',
                    hovermode="x unified",
                    yaxis=dict(tickprefix="$")
                )
                
                # Display the chart
                st.plotly_chart(fig, use_container_width=True)
                
                # Calculate savings rate
                total_income = monthly_data['income'].sum()
                total_expenses = monthly_data['expenses'].sum()
                
                if total_income > 0:
                    savings_rate = (total_income - total_expenses) / total_income * 100
                    
                    # Display metrics
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Income", f"${total_income:,.2f}")
                    col2.metric("Total Expenses", f"${total_expenses:,.2f}")
                    col3.metric("Savings Rate", f"{savings_rate:.1f}%")
                
                # Transaction breakdown by type
                st.subheader("Transaction Breakdown")
                
                # Get transaction type data
                transactions = self.get_user_transactions(
                    user_id, 
                    days=selected_time_days,
                    account_type=selected_account_type
                )
                
                if 'transaction_type' in transactions.columns:
                    # Count transactions by type
                    tx_by_type = transactions.groupby('transaction_type').size().reset_index(name='count')
                    
                    # Create horizontal bar chart
                    fig = px.bar(
                        tx_by_type.sort_values('count'),
                        y='transaction_type',
                        x='count',
                        orientation='h',
                        title="Transaction Types",
                        labels={'transaction_type': 'Type', 'count': 'Number of Transactions'}
                    )
                    
                    # Display the chart
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Insufficient data to display monthly income vs expenses.")

        # Store dashboard data in session state for LLM chart awareness
        # This makes the chart data available to the chatbot for context
        dashboard_context = {
            'user_id': user_id,
            'user_fullname': user_fullname,
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'total_accounts': total_accounts,
            'selected_account': selected_account_label,
            'selected_time_period': selected_time_label,
            'accounts': user_accounts.to_dict('records'),  # Include full accounts data
            'chart_data': {}
        }
        
        # Add balance trend data if available
        if 'balance_trend' in locals() and not balance_trend.empty:
            dashboard_context['chart_data']['balance_trend'] = balance_trend.to_dict('records')
        
        # Add mortgage trend data if available
        if 'mortgage_trend' in locals() and not mortgage_trend.empty:
            dashboard_context['chart_data']['mortgage_trend'] = mortgage_trend.to_dict('records')
            
        # Add spending data if it was retrieved
        if 'category_spending' in locals() and not category_spending.empty:
            dashboard_context['chart_data']['category_spending'] = category_spending.to_dict('records')
            
        # Add income vs expenses data if available
        if 'monthly_data' in locals() and not monthly_data.empty:
            dashboard_context['chart_data']['income_vs_expenses'] = monthly_data.to_dict('records')
        
        # Store in session state for the LLM to access
        st.session_state.dashboard_context = dashboard_context
        
        # Store chart data in session state for chatbot to access
        if "chart_data" in st.session_state:
            # Merge new chart data with existing data to preserve any values not updated in this render
            st.session_state.chart_data.update(dashboard_context['chart_data'])
        else:
            # First time setting chart data
            st.session_state.chart_data = dashboard_context['chart_data']
        
        return dashboard_context


def display_account_dashboard(user_id, user_fullname):
    """Display the integrated account dashboard."""
    dashboard = AccountDashboard()
    
    # Get cached chart data if available
    cached_chart_data = st.session_state.get("chart_data", {})
    
    # Always render the dashboard to ensure visuals appear
    dashboard_data = dashboard.render_account_dashboard(user_id, user_fullname)
    
    # Update timestamp
    st.session_state.dashboard_last_render = time.time()
    
    # If we have dashboard data, return it with possibly cached chart data
    if dashboard_data:
        # If we have existing cached chart data, ensure it's preserved
        if cached_chart_data and "chart_data" not in dashboard_data:
            dashboard_data["chart_data"] = cached_chart_data
        elif cached_chart_data and "chart_data" in dashboard_data:
            # Merge new chart data with cached data to ensure all values are preserved
            dashboard_data["chart_data"].update(cached_chart_data)
    
    return dashboard_data