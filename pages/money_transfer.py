"""Money Transfer page."""
import streamlit as st
import datetime
import pandas as pd
import logging
from modules.money_transfer import MoneyTransfer, get_user_select_options, get_account_select_options, validate_transfer_input

LOGGER = logging.getLogger('BankingApp')

def render_money_transfer(user_id):
    """Render the Money Transfer page."""
    st.header("Money Transfer")
    
    # Initialize money transfer module
    money_transfer = MoneyTransfer()
    
    # Check for redirects from previous actions
    if 'redirect_to_overview' in st.session_state and st.session_state.redirect_to_overview:
        # Clear the redirect flag
        st.session_state.redirect_to_overview = False
        # Set the selected menu to Account Overview
        st.session_state.previous_menu = "Money Transfer"
        st.session_state.selected_menu = "Account Overview"
        st.rerun()
    
    st.subheader("Transfer Money Between Accounts")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### From")
        # Source user selection (default to current user)
        users = get_user_select_options(money_transfer)
        source_user_id = st.selectbox(
            "Source User", 
            options=[user['value'] for user in users],
            format_func=lambda x: next((user['label'] for user in users if user['value'] == x), x),
            index=[i for i, user in enumerate(users) if user['value'] == user_id][0] if 'current_user_id' in st.session_state else 0,
            key="source_user"
        )
        
        # Source account selection
        source_accounts = get_account_select_options(money_transfer, source_user_id)
        if not source_accounts:
            st.warning(f"No accounts found for selected user.")
            source_account_type = None
        else:
            source_account_type = st.selectbox(
                "Source Account",
                options=[account['value'] for account in source_accounts],
                format_func=lambda x: next((account['label'] for account in source_accounts if account['value'] == x), x),
                key="source_account"
            )
    
    with col2:
        st.markdown("### To")
        # Target user selection
        target_user_id = st.selectbox(
            "Target User", 
            options=[user['value'] for user in users],
            format_func=lambda x: next((user['label'] for user in users if user['value'] == x), x),
            key="target_user"
        )
        
        # Target account selection
        target_accounts = get_account_select_options(money_transfer, target_user_id)
        if not target_accounts:
            st.warning(f"No accounts found for selected user.")
            target_account_type = None
        else:
            target_account_type = st.selectbox(
                "Target Account",
                options=[account['value'] for account in target_accounts],
                format_func=lambda x: next((account['label'] for account in target_accounts if account['value'] == x), x),
                key="target_account"
            )
    
    # Amount and description
    amount_str = st.text_input("Amount ($)", placeholder="Enter amount e.g. 100.00")
    description = st.text_input("Description (Optional)", placeholder="Enter description")
    
    # Show validation information to guide users
    if amount_str:
        amount_valid, amount_result = validate_transfer_input(amount_str)
        if not amount_valid:
            st.warning(amount_result)
        elif float(amount_result) > 1000:
            st.info("Note: Large transfers may require additional verification.")
    
    # Check if both source and target accounts are selected before showing the transfer button
    transfer_disabled = (source_account_type is None or target_account_type is None or 
                       source_user_id == target_user_id and source_account_type == target_account_type)
    
    # Transfer button with helpful tooltip
    transfer_btn = st.button(
        "Transfer Money", 
        disabled=transfer_disabled,
        help="Transfer funds between accounts. Both source and target accounts must be selected."
    )
    
    if transfer_disabled and source_user_id == target_user_id and source_account_type == target_account_type:
        st.warning("Cannot transfer money to the same account")
        
    # Process transfer
    if transfer_btn:
        # Validate amount
        amount_valid, amount_result = validate_transfer_input(amount_str)
        
        if not amount_valid:
            st.error(amount_result)
        else:
            # Show progress indicator during processing
            with st.spinner("Processing transfer..."):
                # Process transfer
                result = money_transfer.transfer_money(
                    source_user_id,
                    target_user_id,
                    amount_result,
                    source_account_type,
                    target_account_type,
                    description
                )
            
            if result["status"] == "success":
                # Success feedback with better formatting
                st.success(result["message"])
                
                # Create a container for the transfer details
                with st.container():
                    st.markdown("### Transfer Details")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"💰 Source Balance: ${result['source_balance']:.2f}")
                    with col2:
                        st.info(f"💰 Target Balance: ${result['target_balance']:.2f}")
                        
                    st.markdown(f"Transaction ID: `{result['transaction_id']}`")
                    st.markdown(f"Date: `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
                    
                    # Add options to view updated accounts or make another transfer
                    st.markdown("### What's next?")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("View Account Overview"):
                            # Set session state to redirect to account overview
                            st.session_state.redirect_to_overview = True
                            st.rerun()
                    with col2:
                        if st.button("Make Another Transfer"):
                            # Clear form fields for a new transfer
                            st.session_state.pop('source_account', None)
                            st.session_state.pop('target_user', None)
                            st.session_state.pop('target_account', None)
                            st.rerun()
            else:
                # More detailed error feedback
                st.error(result["message"])
                if "code" in result and result["code"] == "INSUFFICIENT_FUNDS":
                    # Show accounts with sufficient funds if available
                    sufficient_accounts = money_transfer.get_accounts_with_sufficient_funds(
                        source_user_id, amount_result)
                    if sufficient_accounts:
                        st.markdown("#### Accounts with sufficient funds:")
                        for acct in sufficient_accounts:
                            st.info(
                                f"• {acct['account_name']} ({acct['account_type']}): " + 
                                f"${acct['balance']:.2f} {acct['currency']}"
                            )
                elif "code" in result and result["code"] == "SYSTEM_ERROR":
                    st.warning("A system error occurred. Please try again later or contact support.")
    
    # Transfer History with better formatting
    st.markdown("---")
    st.subheader("Recent Transfers")
    history_tab1, history_tab2 = st.tabs(["Sent", "Received"])
    
    # Helper function to format the transfer history
    def display_transfer_history(transfers_df, direction):
        if not transfers_df.empty:
            # Create a more user-friendly display
            for index, row in transfers_df.iterrows():
                with st.container():
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.markdown(f"**{row['date']}**")
                        amount_str = row['amount']
                        if direction == "sent":
                            st.markdown(f"📤 `{amount_str}`")
                        else:
                            st.markdown(f"📥 `{amount_str}`")
                    with col2:
                        st.markdown(f"**{row['description']}**")
                        if 'balance_after' in row:
                            st.markdown(f"Balance after: ${row['balance_after']:.2f}")
                        st.markdown(f"ID: {row['transaction_id']}")
                    st.markdown("---")
        else:
            if direction == "sent":
                st.info("No outgoing transfers found")
            else:
                st.info("No incoming transfers found")
    
    # Get user's transfer history
    transfer_history = money_transfer.get_transfer_history(user_id)
    
    # Display sent transfers
    with history_tab1:
        if transfer_history["status"] == "success" and "transfers" in transfer_history and len(transfer_history["transfers"]) > 0:
            try:
                transfers_df = pd.DataFrame(transfer_history["transfers"])
                # Filter only outgoing transfers (negative amounts)
                outgoing = transfers_df[transfers_df["amount"].str.contains("-")]
                # Sort by date, most recent first
                if not outgoing.empty and 'date' in outgoing.columns:
                    try:
                        # Sort if possible
                        outgoing = outgoing.sort_values('date', ascending=False)
                    except Exception as e:
                        LOGGER.warning(f"Could not sort by date: {e}")
                display_transfer_history(outgoing, "sent")
            except Exception as e:
                LOGGER.warning(f"Unable to display transfer history: {str(e)}")
                st.info("No outgoing transfers found")
        else:
            status_message = transfer_history.get("message", "No transfer history available")
            st.info(status_message)
    
    # Display received transfers
    with history_tab2:
        if transfer_history["status"] == "success" and "transfers" in transfer_history and len(transfer_history["transfers"]) > 0:
            try:
                transfers_df = pd.DataFrame(transfer_history["transfers"])
                # Filter only incoming transfers (positive amounts)
                incoming = transfers_df[~transfers_df["amount"].str.contains("-")]
                # Sort by date, most recent first
                if not incoming.empty and 'date' in incoming.columns:
                    try:
                        # Sort if possible
                        incoming = incoming.sort_values('date', ascending=False)
                    except Exception as e:
                        LOGGER.warning(f"Could not sort by date: {e}")
                display_transfer_history(incoming, "received")
            except Exception as e:
                LOGGER.warning(f"Unable to display transfer history: {str(e)}")
                st.info("No incoming transfers found")
        else:
            status_message = transfer_history.get("message", "No transfer history available")
            st.info(status_message)

