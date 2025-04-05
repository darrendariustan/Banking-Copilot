import os
import pandas as pd
import logging
import uuid
from datetime import datetime
import re
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='transfer.log'
)
LOGGER = logging.getLogger('money_transfer')

class MoneyTransfer:
    """Class to handle money transfers between users in the AletaBanc Copilot system."""
    
    def __init__(self, data_dir=None):
        """Initialize with data directory path."""
        if data_dir is None:
            # Try multiple approaches to find the data directory
            # First, try the original approach
            possible_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
            
            # If that doesn't work, try a direct path relative to current directory
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
            
            # Log column names to verify data structure
            LOGGER.info(f"Accounts columns: {list(self.accounts.columns)}")
            LOGGER.info(f"Transactions columns: {list(self.transactions.columns)}")
            LOGGER.info(f"Users columns: {list(self.users.columns)}")
            
            # Convert date columns to datetime
            if 'date' in self.transactions.columns:
                try:
                    self.transactions['date'] = pd.to_datetime(self.transactions['date'], errors='coerce')
                    # Fill NaT values with a default date if any conversion failed
                    if self.transactions['date'].isna().any():
                        LOGGER.warning(f"Some transaction dates could not be converted to datetime")
                        # Don't replace NaT values, they'll be handled during filtering
                except Exception as e:
                    LOGGER.error(f"Error converting transaction dates to datetime: {e}")
                    # Continue without date conversion, we'll handle it during filtering
            
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
            return False
    
    def save_data(self):
        """Save updated data back to CSV files."""
        try:
            # Save accounts
            self.accounts.to_csv(self.accounts_file, index=False)
            
            # Save transactions
            self.transactions.to_csv(self.transactions_file, index=False)
            
            LOGGER.info("Successfully saved updated data to CSV files")
            return True
        except Exception as e:
            LOGGER.error(f"Error saving data: {e}")
            return False
    
    def validate_user(self, user_id):
        """Validate that a user exists."""
        if user_id is None:
            return False
        
        # Check if users attribute exists and is not empty
        if not hasattr(self, 'users') or self.users.empty:
            # Check against default user IDs when users data couldn't be loaded
            default_user_ids = ["USR001", "USR002", "USR003", "USR004", "USR005"]
            return user_id in default_user_ids
        
        user = self.users[self.users['user_id'] == user_id]
        return not user.empty
    
    def get_account_by_type(self, user_id, account_type="REGULAR_SAVINGS"):
        """Get a user's account by type."""
        if not self.validate_user(user_id):
            LOGGER.warning(f"User {user_id} not found")
            return None
        
        account = self.accounts[
            (self.accounts['owner_id'] == user_id) &
            (self.accounts['account_type'] == account_type)
        ]
        
        if account.empty:
            LOGGER.warning(f"Account type {account_type} not found for user {user_id}")
            return None
        
        return account.iloc[0]
    
    def validate_amount(self, amount):
        """Validate the transfer amount."""
        if not isinstance(amount, (int, float)):
            return False, "Amount must be a number (e.g., 100 or 100.50)"
        
        if amount <= 0:
            return False, "Amount must be greater than zero"
        
        if amount > 10000:
            return False, "Transfers over $10,000 require additional authorization. Please contact support."
        
        return True, "Amount valid"
    
    def check_sufficient_funds(self, user_id, account_type, amount):
        """Check if an account has sufficient funds for a transfer."""
        account = self.get_account_by_type(user_id, account_type)
        
        if account is None:
            return False, "Account not found"
        
        balance = float(account['balance'])
        
        if balance < amount:
            # More helpful message with suggestions
            other_accounts = self.accounts[(self.accounts['owner_id'] == user_id) & 
                                        (self.accounts['account_type'] != account_type)]
            
            suggestion = ""
            if not other_accounts.empty:
                accounts_with_funds = other_accounts[other_accounts['balance'].astype(float) >= amount]
                if not accounts_with_funds.empty:
                    suitable_account = accounts_with_funds.iloc[0]
                    suggestion = f" You have sufficient funds in your {suitable_account['account_name']} account."
            
            return False, f"Insufficient funds. Current balance: ${balance:.2f}. Amount needed: ${amount:.2f}.{suggestion}"
        
        return True, "Sufficient funds"
    
    def validate_currency(self, source_user_id, target_user_id, 
                         source_account_type="REGULAR_SAVINGS", 
                         target_account_type="REGULAR_SAVINGS"):
        """Validate that both accounts use USD."""
        source_account = self.get_account_by_type(source_user_id, source_account_type)
        target_account = self.get_account_by_type(target_user_id, target_account_type)
        
        if source_account is None or target_account is None:
            return False, "One or both accounts not found"
        
        if source_account['currency'] != 'USD' or target_account['currency'] != 'USD':
            return False, "Both accounts must use USD for transfers"
        
        return True, "Currency validation passed"
    
    def generate_transaction_id(self):
        """Generate a unique transaction ID."""
        # Get the max transaction ID and increment it
        if self.transactions.empty:
            next_id = 1
        else:
            # Extract numeric part from transaction IDs
            tx_ids = self.transactions['transaction_id'].str.extract(r'TX(\d+)', expand=False)
            tx_ids = pd.to_numeric(tx_ids, errors='coerce')
            next_id = tx_ids.max() + 1
        
        return f"TX{next_id:04d}"
    
    def transfer_money(self, source_user_id, target_user_id, amount, 
                        source_account_type="REGULAR_SAVINGS", 
                        target_account_type="REGULAR_SAVINGS",
                        description=None):
        """
        Transfer money between users' accounts
        
        Parameters:
        source_user_id: ID of user sending money
        target_user_id: ID of user receiving money
        amount: Amount to transfer (float)
        source_account_type: Type of source account (default: REGULAR_SAVINGS)
        target_account_type: Type of target account (default: REGULAR_SAVINGS)
        description: Optional description of the transfer
        
        Returns:
        dict: Result of transfer with status and message
        """
        LOGGER.info(f"Transfer request: {source_user_id} -> {target_user_id}, amount: ${amount}")
        
        # Create a backup of the accounts and transactions data before making any changes
        accounts_backup = self.accounts.copy()
        transactions_backup = self.transactions.copy()
        
        try:
            # Security validations
            if not self.validate_user(source_user_id):
                return {
                    "status": "error", 
                    "code": "USER_NOT_FOUND",
                    "message": f"Source user {source_user_id} not found"
                }
            
            if not self.validate_user(target_user_id):
                return {
                    "status": "error", 
                    "code": "USER_NOT_FOUND",
                    "message": f"Target user {target_user_id} not found"
                }
            
            # Validate amount
            amount_valid, amount_message = self.validate_amount(amount)
            if not amount_valid:
                return {
                    "status": "error", 
                    "code": "INVALID_AMOUNT",
                    "message": amount_message
                }
            
            # Check sufficient funds
            funds_sufficient, funds_message = self.check_sufficient_funds(
                source_user_id, source_account_type, amount
            )
            if not funds_sufficient:
                return {
                    "status": "error", 
                    "code": "INSUFFICIENT_FUNDS",
                    "message": funds_message
                }
            
            # Validate currency
            currency_valid, currency_message = self.validate_currency(
                source_user_id, target_user_id, source_account_type, target_account_type
            )
            if not currency_valid:
                return {
                    "status": "error",
                    "code": "CURRENCY_MISMATCH",
                    "message": currency_message
                }
            
            # Get source account
            source_account = self.get_account_by_type(source_user_id, source_account_type)
            source_account_id = source_account['account_id']
            source_balance = float(source_account['balance'])
            source_currency = source_account['currency']
            
            # Get target account
            target_account = self.get_account_by_type(target_user_id, target_account_type)
            target_account_id = target_account['account_id']
            target_balance = float(target_account['balance'])
            target_currency = target_account['currency']
            
            # Update balances in DataFrame
            source_idx = self.accounts.index[self.accounts['account_id'] == source_account_id].tolist()[0]
            target_idx = self.accounts.index[self.accounts['account_id'] == target_account_id].tolist()[0]
            
            new_source_balance = source_balance - amount
            new_target_balance = target_balance + amount
            
            self.accounts.at[source_idx, 'balance'] = new_source_balance
            self.accounts.at[target_idx, 'balance'] = new_target_balance
            
            # Get source and target user names for better descriptions
            source_user = self.users[self.users['user_id'] == source_user_id].iloc[0]
            target_user = self.users[self.users['user_id'] == target_user_id].iloc[0]
            
            source_name = f"{source_user['first_name']} {source_user['last_name']}"
            target_name = f"{target_user['first_name']} {target_user['last_name']}"
            
            # Create custom description if not provided
            if description is None:
                description = f"Transfer to {target_name}"
            
            # Record transactions with proper timestamp format
            current_timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            transaction_id = self.generate_transaction_id()
            next_transaction_id = f"TX{int(transaction_id[2:]) + 1:04d}"
            
            # Source transaction (negative amount)
            source_txn = {
                'transaction_id': transaction_id,
                'account_id': source_account_id,
                'date': current_timestamp,
                'description': description,
                'category': 'Transfers',
                'amount': -amount,
                'currency': source_currency,
                'balance_after': new_source_balance,
                'status': 'completed',
                'merchant_name': 'Internal Transfer',
                'location': 'N/A',
                'transaction_type': 'transfer'
            }
            
            # Target transaction (positive amount)
            target_txn = {
                'transaction_id': next_transaction_id,
                'account_id': target_account_id,
                'date': current_timestamp,
                'description': f"Transfer from {source_name}",
                'category': 'Transfers',
                'amount': amount,
                'currency': target_currency,
                'balance_after': new_target_balance,
                'status': 'completed',
                'merchant_name': 'Internal Transfer',
                'location': 'N/A',
                'transaction_type': 'transfer'
            }
            
            # Add transactions to dataframe
            self.transactions = pd.concat([self.transactions, pd.DataFrame([source_txn, target_txn])], ignore_index=True)
            
            # Save updated data to CSV files
            save_success = self.save_data()
            if not save_success:
                # Restore from backup if save fails
                self.accounts = accounts_backup
                self.transactions = transactions_backup
                return {
                    "status": "error", 
                    "code": "SAVE_FAILURE",
                    "message": "Failed to save transaction. Transfer aborted."
                }
            
            LOGGER.info(f"Transfer successful: ${amount} from {source_user_id} to {target_user_id}")
            
            return {
                "status": "success",
                "message": f"Successfully transferred ${amount:.2f} from {source_name} to {target_name}",
                "source_balance": new_source_balance,
                "target_balance": new_target_balance,
                "transaction_id": transaction_id,
                "timestamp": current_timestamp
            }
            
        except Exception as e:
            # Restore from backup if any error occurs
            self.accounts = accounts_backup
            self.transactions = transactions_backup
            LOGGER.error(f"Transaction error: {e}")
            return {
                "status": "error",
                "code": "SYSTEM_ERROR",
                "message": f"An unexpected error occurred: {str(e)}"
            }

    def get_transfer_history(self, user_id, days=30, account_type=None):
        """
        Get transfer history for a user
        
        Parameters:
        user_id: ID of user
        days: Number of days of history to retrieve
        account_type: Optional account type filter
        
        Returns:
        list: List of transfer transactions
        """
        if not self.validate_user(user_id):
            return {
                "status": "error", 
                "code": "USER_NOT_FOUND",
                "message": f"User {user_id} not found"
            }
        
        # Check if accounts DataFrame has the required columns
        if self.accounts.empty or 'owner_id' not in self.accounts.columns or 'account_id' not in self.accounts.columns:
            LOGGER.error(f"Required columns missing in accounts data for transfer history")
            return {
                "status": "error",
                "code": "DATA_ERROR",
                "message": "Unable to retrieve account information. Please try again later."
            }
        
        # Get user accounts
        if account_type:
            accounts = self.accounts[
                (self.accounts['owner_id'] == user_id) &
                (self.accounts['account_type'] == account_type)
            ]['account_id'].tolist()
        else:
            accounts = self.accounts[self.accounts['owner_id'] == user_id]['account_id'].tolist()
        
        if not accounts:
            return {
                "status": "error", 
                "code": "NO_ACCOUNTS",
                "message": "No accounts found"
            }
        
        # Check if transactions DataFrame has the required columns
        if self.transactions.empty or 'account_id' not in self.transactions.columns or 'date' not in self.transactions.columns:
            LOGGER.error(f"Required columns missing in transactions data for transfer history")
            return {
                "status": "success",
                "message": "No transfers found",
                "transfers": []
            }
        
        # Get cutoff date
        cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=days)
        
        # Initialize transfers as empty DataFrame in case all code paths fail
        transfers = pd.DataFrame()
        
        try:
            # Ensure date column is datetime type
            if not pd.api.types.is_datetime64_any_dtype(self.transactions['date']):
                LOGGER.info("Converting date column to datetime")
                # Make a copy to avoid modifying the original DataFrame
                transactions_copy = self.transactions.copy()
                try:
                    transactions_copy['date'] = pd.to_datetime(transactions_copy['date'])
                    # Filter with datetime comparison
                    transfers = transactions_copy[
                        (transactions_copy['account_id'].isin(accounts)) &
                        (transactions_copy['date'] >= cutoff_date) &
                        (transactions_copy['category'] == 'Transfers')
                    ].sort_values('date', ascending=False)
                except Exception as e:
                    LOGGER.error(f"Error converting dates: {e}")
                    # If conversion fails, use a filtered approach without date comparison
                    transfers = self.transactions[
                        (self.transactions['account_id'].isin(accounts)) &
                        (self.transactions['category'] == 'Transfers')
                    ].sort_values('date', ascending=False)
            else:
                # Filter transfers with datetime comparison
                transactions_copy = self.transactions.copy()
                transfers = transactions_copy[
                    (transactions_copy['account_id'].isin(accounts)) &
                    (transactions_copy['date'] >= cutoff_date) &
                    (transactions_copy['category'] == 'Transfers')
                ].sort_values('date', ascending=False)
        except Exception as e:
            LOGGER.error(f"Error filtering transfers: {e}")
            # Fallback: return all transfers without date filtering
            try:
                transfers = self.transactions[
                    (self.transactions['account_id'].isin(accounts)) &
                    (self.transactions['category'] == 'Transfers')
                ].sort_values('date', ascending=False)
            except Exception as inner_e:
                LOGGER.error(f"Failed to get transfers with fallback method: {inner_e}")
                # If everything fails, we already have transfers as empty DataFrame
        
        if transfers.empty:
            return {"status": "success", "message": "No transfers found", "transfers": []}
        
        # Format transfers
        formatted_transfers = []
        for _, txn in transfers.iterrows():
            try:
                formatted_transfer = {
                    'transaction_id': txn['transaction_id'],
                    'date': txn['date'].strftime('%Y-%m-%d') if hasattr(txn['date'], 'strftime') else str(txn['date']),
                    'description': txn['description'],
                    'amount': f"{txn['amount']} {txn['currency']}",
                    'account_id': txn['account_id']
                }
                
                # Only add balance_after if it exists
                if 'balance_after' in txn:
                    formatted_transfer['balance_after'] = float(txn['balance_after'])
                
                formatted_transfers.append(formatted_transfer)
            except Exception as e:
                LOGGER.error(f"Error formatting transfer: {e}")
                # Continue with next transfer
        
        return {
            "status": "success",
            "message": f"Found {len(formatted_transfers)} transfers",
            "transfers": formatted_transfers
        }
    
    def get_accounts_with_sufficient_funds(self, user_id, amount):
        """
        Find accounts for a user with sufficient funds for a transfer
        
        Parameters:
        user_id: ID of user
        amount: Required amount
        
        Returns:
        list: List of accounts with sufficient funds
        """
        if not self.validate_user(user_id):
            return []
        
        # Get all accounts for this user
        user_accounts = self.accounts[self.accounts['owner_id'] == user_id]
        
        if user_accounts.empty:
            return []
        
        # Filter accounts with sufficient balance
        accounts_with_funds = user_accounts[user_accounts['balance'].astype(float) >= amount]
        
        if accounts_with_funds.empty:
            return []
        
        # Format accounts for display
        result = []
        for _, account in accounts_with_funds.iterrows():
            result.append({
                'account_id': account['account_id'],
                'account_name': account['account_name'],
                'account_type': account['account_type'],
                'balance': float(account['balance']),
                'currency': account['currency']
            })
        
        return result

# UI Integration Functions

def get_user_select_options(money_transfer):
    """Get list of users for dropdown selection."""
    options = []
    
    # Check if users attribute exists and is not empty
    if not hasattr(money_transfer, 'users') or money_transfer.users.empty:
        # Provide default user options when data loading failed
        default_users = [
            {"user_id": "USR001", "first_name": "Darren", "last_name": "Smith"},
            {"user_id": "USR002", "first_name": "Maria", "last_name": "Smith"},
            {"user_id": "USR003", "first_name": "Enric", "last_name": "Smith"},
            {"user_id": "USR004", "first_name": "Randy", "last_name": "Smith"},
            {"user_id": "USR005", "first_name": "Victor", "last_name": "Smith"}
        ]
        for user in default_users:
            options.append({
                'value': user['user_id'],
                'label': f"{user['first_name']} {user['last_name']} ({user['user_id']})"
            })
        LOGGER.warning("Using default user options because users data couldn't be loaded")
        return options
    
    for _, user in money_transfer.users.iterrows():
        options.append({
            'value': user['user_id'],
            'label': f"{user['first_name']} {user['last_name']} ({user['user_id']})"
        })
    return options

def get_account_select_options(money_transfer, user_id):
    """Get list of accounts for a user for dropdown selection."""
    # Check if accounts attribute exists and is not empty
    if not hasattr(money_transfer, 'accounts') or money_transfer.accounts.empty:
        LOGGER.warning(f"No accounts data available for user {user_id}")
        return []
    
    # Check if accounts DataFrame has required columns
    required_columns = ['owner_id', 'account_type', 'account_name', 'balance', 'currency']
    for col in required_columns:
        if col not in money_transfer.accounts.columns:
            LOGGER.warning(f"Required column '{col}' missing in accounts data")
            return []
    
    if not money_transfer.validate_user(user_id):
        return []
    
    options = []
    accounts = money_transfer.accounts[money_transfer.accounts['owner_id'] == user_id]
    
    for _, account in accounts.iterrows():
        options.append({
            'value': account['account_type'],
            'label': f"{account['account_name']} ({account['account_type']}) - ${float(account['balance']):.2f} {account['currency']}"
        })
    
    return options

def validate_transfer_input(amount_str):
    """Validate user input for transfer amount."""
    if not amount_str:
        return False, "Amount cannot be empty"
    
    # Remove any currency symbols and commas
    clean_amount = re.sub(r'[,$]', '', amount_str.strip())
    
    try:
        amount = float(clean_amount)
    except ValueError:
        return False, "Amount must be a valid number"
    
    if amount <= 0:
        return False, "Amount must be greater than zero"
    
    return True, amount 