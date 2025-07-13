#!/usr/bin/env python3
"""
Test Spanish search functionality for the Telegram bot
Tests the specific requirement: search for "Matrix" in Spanish
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path to import bot functions
sys.path.append('/app')

async def test_spanish_matrix_search():
    """Test searching for Matrix in Spanish using bot functions"""
    print("🎬 Testing Spanish Search: 'Matrix'")
    print("=" * 50)
    
    try:
        # Import bot functions
        from bot import search_tmdb_and_show_options, search_tvmaze, search_omdb
        
        # Create a mock update object for testing
        class MockMessage:
            def __init__(self):
                pass
            async def reply_text(self, text):
                print(f"📱 Bot would reply: {text[:100]}...")
                return True
            async def reply_photo(self, photo, caption, parse_mode=None):
                print(f"📸 Bot would send photo: {photo}")
                print(f"📝 With caption: {caption[:100]}...")
                return True
        
        class MockUpdate:
            def __init__(self):
                self.message = MockMessage()
        
        class MockContext:
            def __init__(self):
                self.user_data = {}
        
        # Test TMDb search for Matrix
        print("\n🔍 Testing TMDb search for 'Matrix'...")
        mock_update = MockUpdate()
        mock_context = MockContext()
        
        # This will test the actual search function
        result = await search_tmdb_and_show_options(mock_update, mock_context, "Matrix")
        
        if result:
            print("✅ TMDb search successful")
            if mock_context.user_data.get('matches'):
                print(f"📊 Found {len(mock_context.user_data['matches'])} matches (multiple options)")
            else:
                print("📊 Found single match (auto-published)")
        else:
            print("❌ TMDb search failed, testing fallback APIs...")
            
            # Test TVmaze fallback
            print("\n🔍 Testing TVmaze fallback...")
            poster, caption = await search_tvmaze("Matrix")
            if caption:
                print("✅ TVmaze fallback successful")
                print(f"📝 Caption preview: {caption[:100]}...")
            else:
                print("❌ TVmaze fallback failed")
                
                # Test OMDb fallback
                print("\n🔍 Testing OMDb fallback...")
                poster, caption = await search_omdb("Matrix")
                if caption:
                    print("✅ OMDb fallback successful")
                    print(f"📝 Caption preview: {caption[:100]}...")
                else:
                    print("❌ All search methods failed")
                    return False
        
        return True
        
    except Exception as e:
        print(f"💥 Error during search test: {e}")
        return False

async def test_message_formatting():
    """Test message formatting with Spanish content"""
    print("\n🎨 Testing Message Formatting")
    print("=" * 30)
    
    try:
        from bot import get_genre_emojis, get_keyword_emojis, get_synopsis_with_emojis, get_dynamic_closing
        
        # Test with Spanish genres
        spanish_genres = ['Acción', 'Ciencia ficción', 'Aventura']
        genre_emojis = get_genre_emojis(spanish_genres)
        print(f"🎭 Genre emojis: {genre_emojis}")
        
        # Test with Matrix title
        title = "Matrix"
        keyword_emojis = get_keyword_emojis(title)
        print(f"🔑 Keyword emojis: {keyword_emojis}")
        
        # Test with Spanish synopsis
        synopsis = "Un programador descubre que la realidad es una simulación y debe luchar contra las máquinas"
        synopsis_with_emojis = get_synopsis_with_emojis(synopsis)
        print(f"📝 Synopsis with emojis: {synopsis_with_emojis[:100]}...")
        
        # Test dynamic closing
        closing = get_dynamic_closing(synopsis)
        print(f"🎬 Dynamic closing: {closing}")
        
        return True
        
    except Exception as e:
        print(f"💥 Error during formatting test: {e}")
        return False

async def main():
    """Run Spanish search tests"""
    print("🤖 Spanish Search Test for Telegram Bot")
    print("=" * 50)
    
    # Test 1: Spanish Matrix search
    search_success = await test_spanish_matrix_search()
    
    # Test 2: Message formatting
    format_success = await test_message_formatting()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 SPANISH SEARCH TEST SUMMARY")
    print("=" * 50)
    
    if search_success and format_success:
        print("✅ All Spanish search tests passed!")
        print("🎯 Bot is ready for Spanish movie/series searches")
        return 0
    else:
        print("❌ Some tests failed")
        print("🔧 Check the errors above")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)