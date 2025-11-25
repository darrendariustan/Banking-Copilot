"""Chat message processing handler."""
import streamlit as st
import datetime
import time
import re
import logging
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from modules.audio_utils import text_to_speech

LOGGER = logging.getLogger('BankingApp')

def process_money_transfer_intent(chatbot, user_input, user_id):
    """
    Process a voice command for transferring money between accounts.
    
    Args:
        chatbot: Instance of ChatBot
        user_input: The transcribed voice command
        user_id: The current user ID
    
    Returns:
        tuple: (bool success, str message)
    """
    try:
        from modules.money_transfer import MoneyTransfer
        
        # Use the intent analyzer to extract parameters
        intent_analysis = chatbot.intent_analyzer.analyze(user_input)
        
        # Extract parameters for the transfer
        params = intent_analysis.get("parameters", {})
        source_account_type = params.get("source_account_type")
        target_account_type = params.get("target_account_type")
        amount = params.get("amount")
        description = params.get("description", "Voice Transfer")
        
        # Validate we have the necessary parameters
        if not source_account_type or not target_account_type:
            return False, "I need to know which accounts to transfer between. Please specify your source and target accounts."
        
        if not amount:
            return False, "I need to know how much money to transfer. Please specify an amount."
        
        # Initialize MoneyTransfer class
        money_transfer = MoneyTransfer()
        
        # Execute the transfer
        result = money_transfer.transfer_money(
            source_user_id=user_id,
            target_user_id=user_id,  # Same user for both accounts
            amount=amount,
            source_account_type=source_account_type,
            target_account_type=target_account_type,
            description=description
        )
        
        # Check result and format response
        if result["status"] == "success":
            return True, f"I've successfully transferred ${amount:.2f} from your {source_account_type.replace('_', ' ').lower()} " \
                  f"to your {target_account_type.replace('_', ' ').lower()}. " \
                  f"Your new balance in the source account is ${result['source_balance']:.2f}."
        else:
            return False, f"I couldn't complete the transfer: {result['message']}. Please try again."
        
    except Exception as e:
        LOGGER.error(f"Error in voice money transfer: {e}")
        return False, "I encountered an error while trying to process the transfer. Please try again or use the transfer form instead."

def _classify_intent_with_fallback(chatbot, message):
    """Classify intent with fallback to pattern matching."""
    try:
        # Use standard classification first (embedding-based similarity)
        intent = chatbot.classify_text(message)
        st.session_state.debug_intent = f"Classified intent: {intent}"
        
        # Format intent for display (replace underscores with spaces)
        if "_" in intent:
            intent = intent.replace("_", " ")
        
        # Only use pattern matching as fallback if embedding classification returned "default"
        if intent == "default":
            # Get all account types and names from user accounts if available
            account_types = []
            account_names = []
            
            if hasattr(st, 'session_state') and 'dashboard_context' in st.session_state:
                try:
                    # Extract accounts from dashboard context
                    if 'accounts' in st.session_state.dashboard_context:
                        accounts = st.session_state.dashboard_context.get('accounts', [])
                        # Extract all account types and names
                        for account in accounts:
                            if 'account_type' in account:
                                account_type = account['account_type'].lower().replace('_', ' ')
                                account_types.append(account_type)
                            if 'account_name' in account:
                                account_name = account['account_name'].lower()
                                account_names.append(account_name)
                except Exception as e:
                    # Log but don't break if error occurs
                    logging.error(f"Error extracting account types: {str(e)}")
            
            # If no account types found, fallback to standard types
            if not account_types:
                account_types = ['savings', 'checking', 'account']
            
            # Combine account names and types for pattern matching
            account_identifiers = account_types + account_names
            account_pattern = '|'.join(account_identifiers)
            
            # Check for account balance query patterns as fallback
            account_balance_patterns = [
                rf"how much (do|have) i (have )?in my ({account_pattern})",
                rf"what('s| is) my ({account_pattern}) (account )?balance",
                rf"balance in (my )?({account_pattern})",
                rf"how much money (do|have) i (have )?in (my )?({account_pattern})",
            ]
            
            # Check for spending patterns as fallback
            spending_patterns = [
                r"(which|what) category should i cut back",
                r"spending analytics",
                r"where (am i|are my) (over)?spending",
                r"category.*spend",
                r"spend.*category"
            ]
            
            # Direct pattern match only as fallback
            if any(re.search(pattern, message.lower()) for pattern in account_balance_patterns):
                intent = "Account Inquiries"
                st.session_state.debug_intent += " (Fallback: Account Inquiries pattern match)"
            elif any(re.search(pattern, message.lower()) for pattern in spending_patterns):
                intent = "Spending Analysis"
                st.session_state.debug_intent += " (Fallback: Spending Analysis pattern match)"
    except AttributeError:
        # Fallback if classify_text is not available
        try:
            intent = chatbot._classify_intent(message)
            st.session_state.debug_intent = f"Fallback intent: {intent}"
            
            # Format intent for display
            if "_" in intent:
                intent = intent.replace("_", " ")
        except Exception as e:
            st.session_state.debug_intent = f"Error in intent classification: {str(e)}"
            intent = "default"
    
    return intent

def _get_chart_context(selected_menu):
    """Get chart context for chatbot responses."""
    chart_context = None
    if selected_menu == "Account Overview" and "chart_data" in st.session_state:
        try:
            # Convert chart data to a readable format for the chatbot
            chart_data = st.session_state.chart_data
            
            # Ensure all required keys exist
            required_keys = ['checking_balance', 'savings_balance', 'credit_balance', 
                            'avg_income', 'avg_expenses', 'savings_rate',
                            'highest_expense_month', 'highest_expense_amount',
                            'lowest_expense_month', 'lowest_expense_amount',
                            'current_balance', 'balance_90day_high', 'balance_90day_high_date',
                            'balance_90day_low', 'balance_90day_low_date', 
                            'balance_monthly_trend_pct', 'spending_distribution', 'mortgage']
            
            # Check if all required keys exist
            missing_keys = [key for key in required_keys if key not in chart_data]
            
            if not missing_keys:
                chart_context = f"""
                Current account balances:
                - Checking: ${chart_data['checking_balance']:,.2f}
                - Savings: ${chart_data['savings_balance']:,.2f}
                - Credit Card: ${chart_data['credit_balance']:,.2f}
                
                Income vs Expenses:
                - Average monthly income: ${chart_data['avg_income']:,}
                - Average monthly expenses: ${chart_data['avg_expenses']:,}
                - Current savings rate: {chart_data['savings_rate']}%
                - Highest expense month: {chart_data['highest_expense_month']} (${chart_data['highest_expense_amount']:,})
                - Lowest expense month: {chart_data['lowest_expense_month']} (${chart_data['lowest_expense_amount']:,})
                
                Account Balance Trend:
                - Current balance: ${chart_data['current_balance']:,}
                - 90-day high: ${chart_data['balance_90day_high']:,} on {chart_data['balance_90day_high_date']}
                - 90-day low: ${chart_data['balance_90day_low']:,} on {chart_data['balance_90day_low_date']}
                - Monthly trend: {chart_data['balance_monthly_trend_pct']}% growth
                
                Spending Distribution:
                {'; '.join([f"{category}: {details['percentage']}% (${details['amount']:,})" 
                            for category, details in chart_data['spending_distribution'].items()])}
                
                Mortgage:
                - Original amount: ${chart_data['mortgage']['original_amount']:,}
                - Current balance: ${chart_data['mortgage']['current_balance']:,}
                - Paid off: ${chart_data['mortgage']['paid_off']:,} ({chart_data['mortgage']['paid_off_percentage']}%)
                - Monthly payment: ${chart_data['mortgage']['monthly_payment']:,}
                - Interest rate: {chart_data['mortgage']['interest_rate']}%
                """
            else:
                # Fall back to a simpler context if keys are missing
                chart_context = f"User is viewing their account dashboard with financial information."
        except Exception as e:
            # Log the error but continue without chart context
            logging.error(f"Error generating chart context: {str(e)}")
            chart_context = None
    
    return chart_context

def process_text_message(chatbot, chat_history, backup_key, selected_menu):
    """Process a text message from the user."""
    try:
        # Prevent multiple runs of the same message
        current_time = time.time()
        if current_time - st.session_state.last_run_timestamp < 0.5:
            return
            
        st.session_state.last_run_timestamp = current_time
        
        current_message = st.session_state.user_question
        
        # Create a hash of the message to track if it's been processed
        message_hash = f"{current_message}:{st.session_state.current_user_id}"
        
        # Skip if this exact message has already been processed recently
        if message_hash in st.session_state.processed_messages:
            st.session_state.user_question = ""  # Still clear the input
            st.session_state.send_input = False  # Reset send_input to prevent reruns
            return
            
        # Add to processed messages to prevent looping
        st.session_state.processed_messages.add(message_hash)
        
        # Limit size of processed messages set
        if len(st.session_state.processed_messages) > 20:
            # Keep only the 10 most recent messages
            st.session_state.processed_messages = set(list(st.session_state.processed_messages)[-10:])
        
        st.session_state.processing_message = True
        
        # Generate timestamp for this interaction
        timestamp = datetime.datetime.now().isoformat()
        
        # Add user message to chat history
        chat_history.add_user_message(current_message)
        
        # Update chat history backup
        st.session_state[backup_key].append({"type": "human", "content": current_message})
        
        # Get chart context if available
        chart_context = _get_chart_context(selected_menu)
        
        # Get chatbot response
        try:
            if chart_context:
                response = chatbot.get_response(current_message, chart_context=chart_context)
            else:
                response = chatbot.get_response(current_message)
        except Exception as e:
            # Provide a helpful response if there's an error
            logging.error(f"Error getting chatbot response: {str(e)}")
            response = "I'm sorry, I couldn't process that request. Could you please rephrase your question?"
        
        # Add AI response to chat history
        chat_history.add_ai_message(response)
        
        # Update chat history backup
        st.session_state[backup_key].append({"type": "ai", "content": response})
        
        # Classify intent
        intent = _classify_intent_with_fallback(chatbot, current_message)
        
        # Convert to speech
        text_to_speech(response)
        
        # Store audio file in session state
        st.session_state.audio_file = "response.wav"
        st.session_state.last_intent = intent
        
        # Force refresh to update chat history
        current_time = datetime.datetime.now().timestamp()
        st.session_state.last_rerun = current_time
        
        # Store the current menu selection before rerun
        st.session_state.selected_menu = selected_menu
        
        # Reset send_input and user_question to prevent continuous reruns
        st.session_state.send_input = False
        st.session_state.user_question = ""
        
        st.rerun()
    except Exception as e:
        st.error(f"Error processing message: {e}")
    finally:
        # Always ensure processing_message is reset
        st.session_state.processing_message = False
        # Reset send_input even on error
        st.session_state.send_input = False
        st.session_state.user_question = ""

