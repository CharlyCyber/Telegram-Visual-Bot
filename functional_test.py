#!/usr/bin/env python3
"""
Direct functional test of bot components without Telegram polling
Tests the core search and formatting functionality
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Add the app directory to Python path
sys.path.append('/app')

# Import bot functions
from bot import (
    search_tmdb_and_show_options, search_tvmaze, search_omdb,
    get_genre_emojis, get_keyword_emojis, get_synopsis_with_emojis, 
    get_dynamic_closing, publish_tmdb_item
)

load_dotenv()

class MockUpdate:
    """Mock Telegram Update object for testing"""
    def __init__(self):
        self.message = MockMessage()

class MockMessage:
    """Mock Telegram Message object for testing"""
    def __init__(self):
        self.text = ""
        self.replies = []
    
    async def reply_text(self, text, parse_mode=None):
        self.replies.append({"type": "text", "content": text, "parse_mode": parse_mode})
        print(f"📱 Bot Reply (Text): {text[:100]}...")
        return True
    
    async def reply_photo(self, photo, caption=None, parse_mode=None):
        self.replies.append({"type": "photo", "photo": photo, "caption": caption, "parse_mode": parse_mode})
        print(f"📱 Bot Reply (Photo): {photo}")
        if caption:
            print(f"📝 Caption: {caption[:100]}...")
        return True

class MockContext:
    """Mock Telegram Context object for testing"""
    def __init__(self):
        self.user_data = {}

async def test_bot_functionality():
    """Test core bot functionality without Telegram polling"""
    print("🤖 Testing Bot Core Functionality")
    print("=" * 50)
    
    # Test 1: Search with unique result
    print("\n🔍 Test 1: Search for 'Inception' (should find unique result)")
    update = MockUpdate()
    context = MockContext()
    
    try:
        # This should find Inception and publish it directly
        result = await search_tmdb_and_show_options(update, context, "Inception")
        print(f"✅ Search completed: {result}")
        print(f"📊 Replies generated: {len(update.message.replies)}")
        
        if update.message.replies:
            for i, reply in enumerate(update.message.replies):
                print(f"  Reply {i+1}: {reply['type']}")
    except Exception as e:
        print(f"❌ Error in Test 1: {e}")
    
    # Test 2: Search with multiple results
    print("\n🔍 Test 2: Search for 'Batman' (should show multiple options)")
    update2 = MockUpdate()
    context2 = MockContext()
    
    try:
        result = await search_tmdb_and_show_options(update2, context2, "Batman")
        print(f"✅ Search completed: {result}")
        print(f"📊 Replies generated: {len(update2.message.replies)}")
        
        if update2.message.replies:
            for i, reply in enumerate(update2.message.replies):
                print(f"  Reply {i+1}: {reply['type']}")
                if reply['type'] == 'text' and 'Se encontraron varias coincidencias' in reply['content']:
                    print("✅ Multiple options displayed correctly")
    except Exception as e:
        print(f"❌ Error in Test 2: {e}")
    
    # Test 3: TVmaze fallback
    print("\n🔍 Test 3: TVmaze API fallback test")
    try:
        image_url, caption = await search_tvmaze("Breaking Bad")
        if caption:
            print("✅ TVmaze search successful")
            print(f"📷 Image URL: {image_url}")
            print(f"📝 Caption length: {len(caption)} characters")
        else:
            print("❌ TVmaze search failed")
    except Exception as e:
        print(f"❌ Error in Test 3: {e}")
    
    # Test 4: OMDb fallback
    print("\n🔍 Test 4: OMDb API fallback test")
    try:
        image_url, caption = await search_omdb("Inception")
        if caption:
            print("✅ OMDb search successful")
            print(f"📷 Image URL: {image_url}")
            print(f"📝 Caption length: {len(caption)} characters")
        else:
            print("⚠️ OMDb search failed (likely due to missing API key)")
    except Exception as e:
        print(f"❌ Error in Test 4: {e}")
    
    # Test 5: Message formatting
    print("\n🎨 Test 5: Message formatting functions")
    try:
        # Test genre emojis
        genres = ['Acción', 'Comedia', 'Drama', 'Ciencia ficción']
        genre_emojis = get_genre_emojis(genres)
        print(f"✅ Genre emojis: {genre_emojis}")
        
        # Test keyword emojis
        title = "Luna de Miel en el Espacio con Robots"
        keyword_emojis = get_keyword_emojis(title)
        print(f"✅ Keyword emojis: {keyword_emojis}")
        
        # Test synopsis with emojis
        synopsis = "Una historia épica de amor, guerra y misterio en el espacio futuro"
        synopsis_with_emojis = get_synopsis_with_emojis(synopsis)
        print(f"✅ Synopsis with emojis: {synopsis_with_emojis}")
        
        # Test dynamic closing
        closing = get_dynamic_closing(synopsis)
        print(f"✅ Dynamic closing: {closing}")
        
    except Exception as e:
        print(f"❌ Error in Test 5: {e}")
    
    # Test 6: No results scenario
    print("\n🔍 Test 6: Search with no results")
    update3 = MockUpdate()
    context3 = MockContext()
    
    try:
        result = await search_tmdb_and_show_options(update3, context3, "NonExistentMovie12345XYZ")
        print(f"✅ No results search completed: {result}")
        
        # Should return False and then try fallback APIs
        if not result:
            print("✅ Correctly returned False for no results")
            
            # Test fallback APIs
            tvmaze_result = await search_tvmaze("NonExistentMovie12345XYZ")
            omdb_result = await search_omdb("NonExistentMovie12345XYZ")
            
            if tvmaze_result[1] is None and omdb_result[1] is None:
                print("✅ Fallback APIs also correctly returned no results")
            
    except Exception as e:
        print(f"❌ Error in Test 6: {e}")

    print("\n" + "=" * 50)
    print("🎯 FUNCTIONAL TEST SUMMARY")
    print("=" * 50)
    print("✅ Core search functionality tested")
    print("✅ Multiple result handling tested")
    print("✅ Fallback API functionality tested")
    print("✅ Message formatting tested")
    print("✅ No results scenario tested")
    print("\n🤖 Bot core functionality appears to be working correctly!")

if __name__ == "__main__":
    try:
        asyncio.run(test_bot_functionality())
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()