"""Voice message processing handler."""
import streamlit as st
import datetime
import time
import logging
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from modules.audio_utils import transcribe_audio, text_to_speech
from .chat_handler import process_money_transfer_intent, _classify_intent_with_fallback

LOGGER = logging.getLogger('BankingApp')

def process_voice_message(voice_recording, chatbot, chat_history, backup_key, selected_menu, user_id):
    """Process a voice recording from the user."""
    try:
        # Prevent multiple runs of the same message
        current_time = time.time()
        if current_time - st.session_state.last_run_timestamp < 0.5:
            return
            
        st.session_state.last_run_timestamp = current_time
        
        # Log the voice recording received
        st.session_state.debug_audio = "Voice recording received"
        
        # Directly use voice_recording with our improved transcribe_audio function
        transcribed_text = transcribe_audio(voice_recording)
        
        # Add debug info
        if transcribed_text:
            st.session_state.debug_transcription = f"Transcribed text: {transcribed_text}"
        else:
            st.session_state.debug_transcription = "Transcription failed or returned empty"
            st.session_state.send_input = False  # Reset to prevent continuous reruns
            st.rerun()
            return
            
        # Create a hash of the message to track if it's been processed
        message_hash = f"{transcribed_text}:{user_id}"
        
        # Skip if this exact message has already been processed recently
        if message_hash in st.session_state.processed_messages:
            st.session_state.debug_transcription += " (Skipped - duplicate message)"
            st.session_state.send_input = False  # Reset to prevent continuous reruns
            st.rerun()
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
        chat_history.add_user_message(transcribed_text)
        
        # Update chat history backup
        st.session_state[backup_key].append({"type": "human", "content": transcribed_text})
        
        # Classify intent
        intent = _classify_intent_with_fallback(chatbot, transcribed_text)
        
        # Check for money transfer intent
        if intent == "Money_Transfer" or intent == "Money Transfer":
            # Process as money transfer
            try:
                success, response = process_money_transfer_intent(chatbot, transcribed_text, user_id)
            except Exception as e:
                # If there's an error processing the money transfer, provide a helpful message
                response = f"I encountered an issue processing your money transfer request. Could you please rephrase it with the amount and accounts you want to transfer between?"
                logging.error(f"Error in money transfer processing: {str(e)}")
        else:
            # Get standard response with error handling
            try:
                response = chatbot.get_response(transcribed_text)
            except Exception as e:
                # Provide a helpful response if there's an error
                logging.error(f"Error getting chatbot response: {str(e)}")
                response = "I'm sorry, I couldn't process that request. Could you please rephrase your question?"
        
        # Add AI response to chat history
        chat_history.add_ai_message(response)
        
        # Update chat history backup
        st.session_state[backup_key].append({"type": "ai", "content": response})
        
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
        
        # Reset send_input to prevent continuous reruns
        st.session_state.send_input = False
        
        st.rerun()
    except Exception as e:
        st.error(f"Error processing audio: {e}")
    finally:
        # Always ensure processing_message is reset
        st.session_state.processing_message = False
        # Reset send_input even on error
        st.session_state.send_input = False

